"""Deterministic feature extraction from canonical event windows."""

from __future__ import annotations

import math
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
from datetime import datetime
from typing import Any

Event = Mapping[str, Any]
FEATURE_NAMES = (
    "event_count",
    "log_request_bytes",
    "unique_destinations",
    "new_destination",
    "outside_work_hours",
    "sensitive_access",
    "archive_activity",
    "egress_activity",
    "upload_activity",
    "sensitive_json_fields",
    "blocked_activity",
    "sequence_span_seconds",
)
SENSITIVE_FIELDS = frozenset(
    {"token", "password", "secret", "api_key", "authorization", "cookie", "set-cookie"}
)


@dataclass(frozen=True)
class FeatureVector:
    values: tuple[float, ...]
    event_ids: tuple[str, ...]
    destination: str | None

    def as_dict(self) -> dict[str, float]:
        return dict(zip(FEATURE_NAMES, self.values, strict=True))


def _attributes(event: Event) -> Mapping[str, Any]:
    value = event.get("attributes", {})
    return value if isinstance(value, Mapping) else {}


def _is_true(value: Any) -> bool:
    return value is True


def _timestamp(value: Any) -> datetime | None:
    if not isinstance(value, str):
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None


def _field_names(attributes: Mapping[str, Any]) -> set[str]:
    names: set[str] = set()
    for key in ("json_field_names", "sensitive_field_names"):
        value = attributes.get(key, [])
        if isinstance(value, Sequence) and not isinstance(value, (str, bytes)):
            names.update(str(item).lower() for item in value)
    return names


def extract_features(
    events: Iterable[Event], *, known_destinations: Iterable[str] = ()
) -> FeatureVector:
    """Extract a fixed-width vector without retaining body or credential values."""
    window = list(events)
    known = set(known_destinations)
    destinations = [
        str(event["destination"]) for event in window if isinstance(event.get("destination"), str)
    ]
    external_destinations = [
        destination for destination in destinations if ":3128" not in destination
    ]
    candidate = external_destinations[-1] if external_destinations else None
    attributes = [_attributes(event) for event in window]
    actions = [str(event.get("action", "")).lower() for event in window]
    total_bytes = sum(
        max(0, int(event.get("request_bytes", 0)))
        for event in window
        if isinstance(event.get("request_bytes", 0), int)
    )
    timestamps = [stamp for event in window if (stamp := _timestamp(event.get("timestamp")))]
    span = (max(timestamps) - min(timestamps)).total_seconds() if len(timestamps) > 1 else 0.0

    values = (
        float(len(window)),
        math.log1p(total_bytes),
        float(len(set(external_destinations))),
        float(any(destination not in known for destination in external_destinations)),
        float(any(_is_true(item.get("outside_work_hours")) for item in attributes)),
        float(
            any(_is_true(item.get("sensitive")) for item in attributes)
            or any("sensitive" in action for action in actions)
        ),
        float(any("archive" in action or "stage" in action for action in actions)),
        float(any("egress" in action or "network" in action for action in actions)),
        float(any("upload" in action or action == "http_post" for action in actions)),
        float(any(_field_names(item) & SENSITIVE_FIELDS for item in attributes)),
        float(
            any(_is_true(item.get("blocked")) for item in attributes)
            or any("denied" in action for action in actions)
        ),
        max(0.0, span),
    )
    return FeatureVector(
        values=values,
        event_ids=tuple(str(event.get("event_id", "")) for event in window),
        destination=candidate,
    )
