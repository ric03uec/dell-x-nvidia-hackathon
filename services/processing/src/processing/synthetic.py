"""Deterministic synthetic windows for hackathon training and evaluation."""

from __future__ import annotations

import copy
import json
import random
from collections.abc import Iterable
from datetime import datetime
from pathlib import Path
from typing import Any

from processing.dataset import load_events

Window = dict[str, Any]


def _shift_events(
    events: list[dict[str, Any]],
    *,
    window_id: str,
    start: datetime,
) -> list[dict[str, Any]]:
    shifted = copy.deepcopy(events)
    original = datetime.fromisoformat(str(shifted[0]["timestamp"]).replace("Z", "+00:00"))
    for index, event in enumerate(shifted):
        stamp = datetime.fromisoformat(str(event["timestamp"]).replace("Z", "+00:00"))
        event["timestamp"] = (start + (stamp - original)).isoformat().replace("+00:00", "Z")
        event["event_id"] = f"evt-{window_id}-{index + 1:03d}"
        attributes = event.setdefault("attributes", {})
        attributes["openshell_run_id"] = window_id
        attributes["openclaw_agent_id"] = "business-agent"
    return shifted


def _normal_window(
    seed_events: list[dict[str, Any]],
    *,
    index: int,
    randomizer: random.Random,
) -> Window:
    window_id = f"normal-{index:05d}"
    day = 1 + index % 20
    hour = randomizer.randint(8, 17)
    start = datetime.fromisoformat(f"2026-07-{day:02d}T{hour:02d}:00:00+00:00")
    events = _shift_events(seed_events, window_id=window_id, start=start)
    approved = ("docs.internal.example", "pypi.org", "packages.internal.example")
    for event in events:
        attributes = event["attributes"]
        attributes["outside_work_hours"] = False
        if event.get("source_type") == "squid":
            destination = randomizer.choice(approved)
            event["destination"] = destination
            event["request_bytes"] = randomizer.randint(300, 4_000)
            attributes["uri"] = f"https://{destination}/synthetic/{{resource_id}}"
            attributes["response_bytes"] = randomizer.randint(1_000, 100_000)
    return {"window_id": window_id, "events": events}


def _suspicious_window(
    seed_events: list[dict[str, Any]],
    *,
    index: int,
    randomizer: random.Random,
) -> Window:
    window_id = f"suspicious-{index:05d}"
    day = 1 + index % 20
    hour = randomizer.choice((0, 1, 2, 3, 21, 22, 23))
    start = datetime.fromisoformat(f"2026-07-{day:02d}T{hour:02d}:00:00+00:00")
    events = _shift_events(seed_events, window_id=window_id, start=start)
    destination = f"receiver-{index % 31:02d}.demo.local"
    transfer_size = randomizer.randint(5_000_000, 75_000_000)
    for event in events:
        attributes = event["attributes"]
        attributes["outside_work_hours"] = True
        if event.get("action") == "http_upload":
            event["source_type"] = randomizer.choice(("squid", "mitmproxy"))
            event["destination"] = destination
            event["request_bytes"] = transfer_size
            attributes["uri"] = f"https://{destination}/upload/{{run_id}}"
            attributes["new_destination"] = True
            if randomizer.random() < 0.7:
                attributes["json_field_names"] = ["index", "random", "run", "token"]
                attributes["sensitive_field_names"] = ["token"]
                attributes["body_stored"] = False
    return {"window_id": window_id, "events": events}


def generate_dataset(
    normal_fixture: Path,
    suspicious_fixture: Path,
    output_dir: Path,
    *,
    train_normal: int = 800,
    eval_normal: int = 200,
    eval_suspicious: int = 200,
    seed: int = 42,
) -> dict[str, Any]:
    if min(train_normal, eval_normal, eval_suspicious) < 8:
        raise ValueError("each dataset partition requires at least eight windows")
    normal_seed = load_events(normal_fixture)
    suspicious_seed = load_events(suspicious_fixture)
    randomizer = random.Random(seed)
    training = [
        _normal_window(normal_seed, index=index, randomizer=randomizer)
        for index in range(train_normal)
    ]
    normal_eval = [
        _normal_window(normal_seed, index=train_normal + index, randomizer=randomizer)
        for index in range(eval_normal)
    ]
    suspicious_eval = [
        _suspicious_window(suspicious_seed, index=index, randomizer=randomizer)
        for index in range(eval_suspicious)
    ]
    evaluation = normal_eval + suspicious_eval
    randomizer.shuffle(evaluation)
    truth = {
        "schema_version": "1.0",
        "seed": seed,
        "labels": {
            **{item["window_id"]: "normal" for item in normal_eval},
            **{item["window_id"]: "suspicious" for item in suspicious_eval},
        },
    }
    output_dir.mkdir(parents=True, exist_ok=True)
    _write_windows(output_dir / "train-normal.jsonl", training)
    _write_windows(output_dir / "evaluation.jsonl", evaluation)
    (output_dir / "expected.json").write_text(json.dumps(truth, indent=2, sort_keys=True) + "\n")
    manifest = {
        "schema_version": "1.0",
        "seed": seed,
        "train_normal": train_normal,
        "eval_normal": eval_normal,
        "eval_suspicious": eval_suspicious,
        "sensitive_values_stored": False,
    }
    (output_dir / "manifest.json").write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n")
    return manifest


def load_windows(path: Path) -> list[Window]:
    windows = [json.loads(line) for line in path.read_text().splitlines() if line.strip()]
    if not all(isinstance(item, dict) and isinstance(item.get("events"), list) for item in windows):
        raise ValueError("window file contains invalid records")
    return windows


def _write_windows(path: Path, windows: Iterable[Window]) -> None:
    path.write_text("".join(json.dumps(item, sort_keys=True) + "\n" for item in windows))
