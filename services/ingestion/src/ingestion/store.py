"""SQLite persistence for ingestion.

Every read and write in the service goes through these functions. The MCP tools
call the same ones the REST handlers do — that is what keeps the two surfaces
from drifting, and it is why no tool needs raw SQL (dxnvh-2jb.7).

ponytail: one CREATE TABLE IF NOT EXISTS, no migration framework. Ceiling —
the moment a column has to change on data worth keeping, this needs alembic or
an equivalent. That is dxnvh-2jb.2, not this.
"""

from __future__ import annotations

import json
import sqlite3
import time
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any

SCHEMA = """
CREATE TABLE IF NOT EXISTS events (
    event_id     TEXT PRIMARY KEY,
    ts           REAL NOT NULL,
    src          TEXT,
    destination  TEXT,
    dst_ip       TEXT,
    method       TEXT,
    req_bytes    INTEGER,
    resp_bytes   INTEGER,
    result       TEXT,
    source_type  TEXT NOT NULL DEFAULT 'squid',
    raw          TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_events_ts ON events(ts);
CREATE INDEX IF NOT EXISTS idx_events_dest ON events(destination);

CREATE TABLE IF NOT EXISTS findings (
    finding_id  TEXT PRIMARY KEY,
    ts          REAL NOT NULL,
    summary     TEXT NOT NULL,
    risk_score  INTEGER NOT NULL,
    event_ids   TEXT NOT NULL,
    payload     TEXT
);

CREATE TABLE IF NOT EXISTS recommendations (
    recommendation_id TEXT PRIMARY KEY,
    ts                REAL NOT NULL,
    finding_id        TEXT,
    action_type       TEXT NOT NULL,
    destination       TEXT NOT NULL,
    rationale         TEXT NOT NULL,
    status            TEXT NOT NULL DEFAULT 'pending',
    payload            TEXT
);

CREATE TABLE IF NOT EXISTS decisions (
    recommendation_id TEXT PRIMARY KEY,
    decision          TEXT NOT NULL,
    actor             TEXT NOT NULL,
    ts                REAL NOT NULL,
    payload           TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS enforcement_results (
    enforcement_result_id TEXT PRIMARY KEY,
    recommendation_id     TEXT NOT NULL,
    ts                    REAL NOT NULL,
    payload               TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS finding_labels (
    label_id    INTEGER PRIMARY KEY AUTOINCREMENT,
    finding_id  TEXT NOT NULL,
    ts          REAL NOT NULL,
    payload     TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS snapshots (
    snapshot_id TEXT PRIMARY KEY,
    ts          REAL NOT NULL,
    path        TEXT NOT NULL
);

-- The squid denylist. A row here exists ONLY because a human approved a
-- recommendation; nothing in the model path writes to it directly.
CREATE TABLE IF NOT EXISTS rules (
    destination       TEXT PRIMARY KEY,
    ts                REAL NOT NULL,
    recommendation_id TEXT,
    approved_by       TEXT NOT NULL
);
"""


def connect(db_path: str | Path) -> sqlite3.Connection:
    path = Path(db_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    # WAL so the collector writing does not block the dashboard reading.
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA synchronous=NORMAL")
    conn.executescript(SCHEMA)
    _ensure_column(conn, "findings", "payload", "TEXT")
    _ensure_column(conn, "recommendations", "payload", "TEXT")
    conn.commit()
    return conn


def _ensure_column(conn: sqlite3.Connection, table: str, column: str, declaration: str) -> None:
    columns = {row["name"] for row in conn.execute(f"PRAGMA table_info({table})")}
    if column not in columns:
        conn.execute(f"ALTER TABLE {table} ADD COLUMN {column} {declaration}")


def healthy(conn: sqlite3.Connection) -> bool:
    try:
        conn.execute("SELECT 1 FROM events LIMIT 1").fetchone()
        return True
    except sqlite3.Error:
        return False


# --- events -------------------------------------------------------------


def add_event(conn: sqlite3.Connection, record: dict[str, Any]) -> str:
    """Persist one squid-shaped record. Returns its event_id.

    The exfilguard logformat is key=value, so the field names arrive already
    matching (dxnvh-dwj.2). `raw` keeps the whole record so a later contract
    freeze can re-derive fields we did not promote to columns.
    """
    event_id = record.get("event_id") or f"evt-{uuid.uuid4().hex[:12]}"
    attributes = record.get("attributes")
    attributes = attributes if isinstance(attributes, dict) else {}
    uri = record.get("uri") or attributes.get("uri") or ""
    destination = record.get("destination") or uri.split("//")[-1].split("/")[0] or None
    timestamp = record.get("ts") or _epoch(record.get("timestamp")) or time.time()
    conn.execute(
        """INSERT OR IGNORE INTO events
           (event_id, ts, src, destination, dst_ip, method, req_bytes,
            resp_bytes, result, source_type, raw)
           VALUES (?,?,?,?,?,?,?,?,?,?,?)""",
        (
            event_id,
            float(timestamp),
            record.get("src") or record.get("actor"),
            destination,
            record.get("dst_ip") or attributes.get("dst_ip"),
            record.get("method") or attributes.get("method"),
            record.get("req_bytes") or record.get("request_bytes"),
            record.get("resp_bytes") or attributes.get("response_bytes"),
            record.get("result") or attributes.get("result"),
            record.get("source_type") or "squid",
            json.dumps(record, sort_keys=True),
        ),
    )
    conn.commit()
    return event_id


def _epoch(value: Any) -> float | None:
    if not isinstance(value, str):
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00")).timestamp()
    except ValueError:
        return None


def _event_payload(row: sqlite3.Row) -> dict[str, Any]:
    stored = dict(row)
    raw = json.loads(stored["raw"])
    if isinstance(raw, dict) and raw.get("schema_version") and raw.get("event_id"):
        return raw
    stored["raw"] = raw
    return stored


def list_events(
    conn: sqlite3.Connection,
    limit: int = 100,
    destination: str | None = None,
    src: str | None = None,
) -> list[dict[str, Any]]:
    sql = "SELECT * FROM events"
    where: list[str] = []
    params: list[Any] = []
    if destination:
        where.append("destination = ?")
        params.append(destination)
    if src:
        where.append("src = ?")
        params.append(src)
    if where:
        sql += " WHERE " + " AND ".join(where)
    sql += " ORDER BY ts DESC LIMIT ?"
    params.append(min(limit, 1000))
    return [_event_payload(r) for r in conn.execute(sql, params).fetchall()]


def events_by_ids(conn: sqlite3.Connection, ids: list[str]) -> list[dict[str, Any]]:
    if not ids:
        return []
    marks = ",".join("?" * len(ids))
    rows = conn.execute(
        f"SELECT * FROM events WHERE event_id IN ({marks}) ORDER BY ts", ids
    ).fetchall()
    return [_event_payload(r) for r in rows]


# --- findings and recommendations ---------------------------------------


def add_finding(
    conn: sqlite3.Connection, summary: str, risk_score: int, event_ids: list[str]
) -> str:
    finding_id = f"fnd-{uuid.uuid4().hex[:12]}"
    payload = {
        "schema_version": "1.0",
        "finding_id": finding_id,
        "summary": summary,
        "risk_score": int(risk_score),
        "severity": _severity(int(risk_score)),
        "event_ids": event_ids,
    }
    conn.execute(
        """
        INSERT INTO findings (finding_id, ts, summary, risk_score, event_ids, payload)
        VALUES (?,?,?,?,?,?)
        """,
        (
            finding_id,
            time.time(),
            summary,
            int(risk_score),
            json.dumps(event_ids),
            json.dumps(payload, sort_keys=True),
        ),
    )
    conn.commit()
    return finding_id


def _severity(score: int) -> str:
    if score >= 90:
        return "critical"
    if score >= 70:
        return "high"
    if score >= 40:
        return "medium"
    return "low"


def put_finding(conn: sqlite3.Connection, payload: dict[str, Any]) -> str:
    finding_id = str(payload["finding_id"])
    event_ids = payload.get("event_ids")
    if not isinstance(event_ids, list) or not event_ids:
        raise ValueError("event_ids must be a non-empty list")
    conn.execute(
        """
        INSERT INTO findings (finding_id, ts, summary, risk_score, event_ids, payload)
        VALUES (?,?,?,?,?,?)
        ON CONFLICT(finding_id) DO UPDATE SET
          summary=excluded.summary, risk_score=excluded.risk_score,
          event_ids=excluded.event_ids, payload=excluded.payload
        """,
        (
            finding_id,
            time.time(),
            str(payload.get("summary", "")),
            int(payload["risk_score"]),
            json.dumps(event_ids),
            json.dumps(payload, sort_keys=True),
        ),
    )
    conn.commit()
    return finding_id


def _finding_payload(row: sqlite3.Row) -> dict[str, Any]:
    if row["payload"]:
        value = json.loads(row["payload"])
        if isinstance(value, dict):
            return value
    finding = dict(row)
    finding["event_ids"] = json.loads(finding["event_ids"])
    finding.pop("payload", None)
    finding.setdefault("schema_version", "1.0")
    finding.setdefault("severity", _severity(int(finding["risk_score"])))
    return finding


def get_finding(conn: sqlite3.Connection, finding_id: str) -> dict[str, Any] | None:
    row = conn.execute("SELECT * FROM findings WHERE finding_id = ?", (finding_id,)).fetchone()
    return _finding_payload(row) if row else None


def list_findings(conn: sqlite3.Connection) -> list[dict[str, Any]]:
    rows = conn.execute("SELECT * FROM findings ORDER BY ts DESC").fetchall()
    return [_finding_payload(row) for row in rows]


def add_recommendation(
    conn: sqlite3.Connection,
    action_type: str,
    destination: str,
    rationale: str,
    finding_id: str | None = None,
) -> str:
    recommendation_id = f"rec-{uuid.uuid4().hex[:12]}"
    normalized_action = "deny_destination" if action_type == "block_destination" else action_type
    payload = {
        "schema_version": "1.0",
        "recommendation_id": recommendation_id,
        "finding_id": finding_id,
        "action_type": normalized_action,
        "target": destination,
        "scope": "business-agent",
        "reason": rationale,
    }
    conn.execute(
        """INSERT INTO recommendations
           (recommendation_id, ts, finding_id, action_type, destination,
            rationale, status, payload)
           VALUES (?,?,?,?,?,?,'pending',?)""",
        (
            recommendation_id,
            time.time(),
            finding_id,
            normalized_action,
            destination,
            rationale,
            json.dumps(payload, sort_keys=True),
        ),
    )
    conn.commit()
    return recommendation_id


def put_recommendation(conn: sqlite3.Connection, payload: dict[str, Any]) -> str:
    if payload.get("action_type") != "deny_destination":
        raise ValueError("action_type must be deny_destination")
    recommendation_id = str(payload["recommendation_id"])
    conn.execute(
        """
        INSERT INTO recommendations
          (recommendation_id, ts, finding_id, action_type, destination,
           rationale, status, payload)
        VALUES (?,?,?,?,?,?,'pending',?)
        ON CONFLICT(recommendation_id) DO UPDATE SET
          finding_id=excluded.finding_id, action_type=excluded.action_type,
          destination=excluded.destination, rationale=excluded.rationale,
          payload=excluded.payload
        """,
        (
            recommendation_id,
            time.time(),
            payload.get("finding_id"),
            payload["action_type"],
            payload["target"],
            payload.get("reason", ""),
            json.dumps(payload, sort_keys=True),
        ),
    )
    conn.commit()
    return recommendation_id


def _recommendation_payload(row: sqlite3.Row) -> dict[str, Any]:
    if row["payload"]:
        value = json.loads(row["payload"])
        if isinstance(value, dict):
            value["status"] = row["status"]
            return value
    value = dict(row)
    value.pop("payload", None)
    value.update(
        {
            "schema_version": "1.0",
            "target": value.pop("destination"),
            "scope": "business-agent",
            "reason": value.pop("rationale"),
        }
    )
    return value


def list_recommendations(
    conn: sqlite3.Connection, status: str | None = None
) -> list[dict[str, Any]]:
    if status:
        rows = conn.execute(
            "SELECT * FROM recommendations WHERE status = ? ORDER BY ts DESC", (status,)
        ).fetchall()
    else:
        rows = conn.execute("SELECT * FROM recommendations ORDER BY ts DESC").fetchall()
    return [_recommendation_payload(r) for r in rows]


def decide(
    conn: sqlite3.Connection, recommendation_id: str, approve: bool, actor: str
) -> dict[str, Any] | None:
    """Approve or reject. Approval of a block is the ONLY path into `rules`."""
    row = conn.execute(
        "SELECT * FROM recommendations WHERE recommendation_id = ?", (recommendation_id,)
    ).fetchone()
    if row is None:
        return None

    rec = dict(row)
    status = "approved" if approve else "rejected"
    conn.execute(
        "UPDATE recommendations SET status = ? WHERE recommendation_id = ?",
        (status, recommendation_id),
    )
    decision_payload = {
        "schema_version": "1.0",
        "recommendation_id": recommendation_id,
        "decision": status,
        "analyst": actor,
        "timestamp": datetime.now().astimezone().isoformat(),
    }
    conn.execute(
        """
        INSERT INTO decisions(recommendation_id, decision, actor, ts, payload)
        VALUES (?,?,?,?,?)
        ON CONFLICT(recommendation_id) DO UPDATE SET
          decision=excluded.decision, actor=excluded.actor, ts=excluded.ts,
          payload=excluded.payload
        """,
        (
            recommendation_id,
            status,
            actor,
            time.time(),
            json.dumps(decision_payload, sort_keys=True),
        ),
    )
    if approve and rec["action_type"] in {"block_destination", "deny_destination"}:
        conn.execute(
            """INSERT OR REPLACE INTO rules
               (destination, ts, recommendation_id, approved_by) VALUES (?,?,?,?)""",
            (rec["destination"], time.time(), recommendation_id, actor),
        )
    conn.commit()
    updated = conn.execute(
        "SELECT * FROM recommendations WHERE recommendation_id = ?", (recommendation_id,)
    ).fetchone()
    return _recommendation_payload(updated)


def add_label(conn: sqlite3.Connection, finding_id: str, payload: dict[str, Any]) -> None:
    conn.execute(
        "INSERT INTO finding_labels(finding_id, ts, payload) VALUES (?,?,?)",
        (finding_id, time.time(), json.dumps(payload, sort_keys=True)),
    )
    conn.commit()


def put_enforcement_result(conn: sqlite3.Connection, payload: dict[str, Any]) -> str:
    result_id = str(payload["enforcement_result_id"])
    conn.execute(
        """
        INSERT INTO enforcement_results(
          enforcement_result_id, recommendation_id, ts, payload
        ) VALUES (?,?,?,?)
        ON CONFLICT(enforcement_result_id) DO UPDATE SET payload=excluded.payload
        """,
        (
            result_id,
            payload["recommendation_id"],
            time.time(),
            json.dumps(payload, sort_keys=True),
        ),
    )
    conn.commit()
    return result_id


def list_enforcement_results(conn: sqlite3.Connection) -> list[dict[str, Any]]:
    rows = conn.execute("SELECT payload FROM enforcement_results ORDER BY ts").fetchall()
    return [json.loads(row["payload"]) for row in rows]


def approved_policies(
    conn: sqlite3.Connection, after_id: str | None = None
) -> list[dict[str, Any]]:
    sql = "SELECT * FROM recommendations WHERE status = 'approved'"
    parameters: tuple[Any, ...] = ()
    if after_id:
        sql += " AND recommendation_id > ?"
        parameters = (after_id,)
    sql += " ORDER BY recommendation_id"
    return [_recommendation_payload(row) for row in conn.execute(sql, parameters).fetchall()]


def create_snapshot(conn: sqlite3.Connection, db_path: str | Path) -> tuple[str, Path]:
    snapshot_id = f"snapshot-{uuid.uuid4().hex[:12]}"
    destination = Path(db_path).parent / "snapshots" / f"{snapshot_id}.sqlite"
    destination.parent.mkdir(parents=True, exist_ok=True)
    target = sqlite3.connect(destination)
    try:
        conn.backup(target)
    finally:
        target.close()
    conn.execute(
        "INSERT INTO snapshots(snapshot_id, ts, path) VALUES (?,?,?)",
        (snapshot_id, time.time(), str(destination)),
    )
    conn.commit()
    return snapshot_id, destination


def counts(conn: sqlite3.Connection) -> dict[str, int]:
    tables = ("events", "findings", "recommendations", "enforcement_results")
    return {
        table: int(conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]) for table in tables
    }


# --- rules (what squid asks for) ----------------------------------------


def list_rules(conn: sqlite3.Connection) -> list[dict[str, Any]]:
    return [dict(r) for r in conn.execute("SELECT * FROM rules ORDER BY ts DESC").fetchall()]


def is_denied(conn: sqlite3.Connection, destination: str) -> bool:
    """Exact host match, plus parent-domain match so a rule on `evil.test`
    also covers `up.evil.test`. Squid's dstdomain does the same thing."""
    host = (destination or "").split(":")[0].lower()
    if not host:
        return False
    candidates = [host]
    parts = host.split(".")
    candidates += [".".join(parts[i:]) for i in range(1, len(parts) - 1)]
    marks = ",".join("?" * len(candidates))
    row = conn.execute(
        f"SELECT 1 FROM rules WHERE destination IN ({marks}) LIMIT 1", candidates
    ).fetchone()
    return row is not None
