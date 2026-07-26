"""Fixture loading and deterministic normal-window augmentation for model training."""

from __future__ import annotations

import copy
import json
import random
from collections.abc import Iterable
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

from processing.features import FeatureVector, extract_features


def load_events(path: Path) -> list[dict[str, Any]]:
    text = path.read_text()
    if path.suffix == ".jsonl":
        events = [json.loads(line) for line in text.splitlines() if line.strip()]
    else:
        value = json.loads(text)
        events = value if isinstance(value, list) else [value]
    if not all(isinstance(item, dict) for item in events):
        raise ValueError("event input must contain JSON objects")
    return events


def augmented_normal_windows(
    seed_events: Iterable[dict[str, Any]],
    *,
    count: int = 256,
    seed: int = 42,
) -> list[FeatureVector]:
    """Create deterministic benign variation; never use unresolved alerts as normal."""
    source = list(seed_events)
    if not source:
        raise ValueError("normal seed events are required")
    randomizer = random.Random(seed)
    destinations = {
        str(item["destination"]) for item in source if isinstance(item.get("destination"), str)
    }
    windows: list[FeatureVector] = []
    for run in range(count):
        events = copy.deepcopy(source)
        shift = timedelta(minutes=randomizer.randint(-180, 180))
        for index, event in enumerate(events):
            stamp = datetime.fromisoformat(str(event["timestamp"]).replace("Z", "+00:00"))
            event["timestamp"] = (stamp + shift).isoformat().replace("+00:00", "Z")
            event["event_id"] = f"train-{run:04d}-{index:03d}"
            if isinstance(event.get("request_bytes"), int):
                factor = randomizer.uniform(0.65, 1.35)
                event["request_bytes"] = max(0, int(event["request_bytes"] * factor))
            attributes = event.get("attributes")
            if isinstance(attributes, dict) and "response_bytes" in attributes:
                factor = randomizer.uniform(0.65, 1.35)
                attributes["response_bytes"] = max(0, int(attributes["response_bytes"] * factor))
        windows.append(extract_features(events, known_destinations=destinations))
    return windows
