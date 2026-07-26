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
    event_ids   TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS recommendations (
    recommendation_id TEXT PRIMARY KEY,
    ts                REAL NOT NULL,
    finding_id        TEXT,
    action_type       TEXT NOT NULL,
    destination       TEXT NOT NULL,
    rationale         TEXT NOT NULL,
    status            TEXT NOT NULL DEFAULT 'pending'
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
    conn.commit()
    return conn


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
    uri = record.get("uri") or ""
    conn.execute(
        """INSERT OR IGNORE INTO events
           (event_id, ts, src, destination, dst_ip, method, req_bytes,
            resp_bytes, result, source_type, raw)
           VALUES (?,?,?,?,?,?,?,?,?,?,?)""",
        (
            event_id,
            float(record.get("ts") or time.time()),
            record.get("src"),
            # CONNECT gives `host:port`; a plain URL gives a full URI. Both
            # reduce to the destination the rules key on.
            uri.split("//")[-1].split("/")[0] or None,
            record.get("dst_ip"),
            record.get("method"),
            record.get("req_bytes"),
            record.get("resp_bytes"),
            record.get("result"),
            record.get("source_type", "squid"),
            json.dumps(record, sort_keys=True),
        ),
    )
    conn.commit()
    return event_id


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
    return [dict(r) for r in conn.execute(sql, params).fetchall()]


def events_by_ids(conn: sqlite3.Connection, ids: list[str]) -> list[dict[str, Any]]:
    if not ids:
        return []
    marks = ",".join("?" * len(ids))
    rows = conn.execute(
        f"SELECT * FROM events WHERE event_id IN ({marks}) ORDER BY ts", ids
    ).fetchall()
    return [dict(r) for r in rows]


# --- findings and recommendations ---------------------------------------


def add_finding(
    conn: sqlite3.Connection, summary: str, risk_score: int, event_ids: list[str]
) -> str:
    finding_id = f"fnd-{uuid.uuid4().hex[:12]}"
    conn.execute(
        "INSERT INTO findings (finding_id, ts, summary, risk_score, event_ids) VALUES (?,?,?,?,?)",
        (finding_id, time.time(), summary, int(risk_score), json.dumps(event_ids)),
    )
    conn.commit()
    return finding_id


def get_finding(conn: sqlite3.Connection, finding_id: str) -> dict[str, Any] | None:
    row = conn.execute("SELECT * FROM findings WHERE finding_id = ?", (finding_id,)).fetchone()
    if row is None:
        return None
    finding = dict(row)
    finding["event_ids"] = json.loads(finding["event_ids"])
    return finding


def add_recommendation(
    conn: sqlite3.Connection,
    action_type: str,
    destination: str,
    rationale: str,
    finding_id: str | None = None,
) -> str:
    recommendation_id = f"rec-{uuid.uuid4().hex[:12]}"
    conn.execute(
        """INSERT INTO recommendations
           (recommendation_id, ts, finding_id, action_type, destination, rationale, status)
           VALUES (?,?,?,?,?,?,'pending')""",
        (recommendation_id, time.time(), finding_id, action_type, destination, rationale),
    )
    conn.commit()
    return recommendation_id


def list_recommendations(
    conn: sqlite3.Connection, status: str | None = None
) -> list[dict[str, Any]]:
    if status:
        rows = conn.execute(
            "SELECT * FROM recommendations WHERE status = ? ORDER BY ts DESC", (status,)
        ).fetchall()
    else:
        rows = conn.execute("SELECT * FROM recommendations ORDER BY ts DESC").fetchall()
    return [dict(r) for r in rows]


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
    if approve and rec["action_type"] == "block_destination":
        conn.execute(
            """INSERT OR REPLACE INTO rules
               (destination, ts, recommendation_id, approved_by) VALUES (?,?,?,?)""",
            (rec["destination"], time.time(), recommendation_id, actor),
        )
    conn.commit()
    rec["status"] = status
    return rec


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
