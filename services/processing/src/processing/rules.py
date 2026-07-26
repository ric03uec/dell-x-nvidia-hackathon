"""Explainable rules and deterministic risk contributions."""

from __future__ import annotations

from dataclasses import dataclass

from processing.features import FeatureVector


@dataclass(frozen=True)
class RiskContribution:
    detector: str
    points: float
    evidence: str


@dataclass(frozen=True)
class RuleScore:
    score: float
    contributions: tuple[RiskContribution, ...]

    @property
    def detectors(self) -> tuple[str, ...]:
        return tuple(item.detector for item in self.contributions)


def score_rules(features: FeatureVector) -> RuleScore:
    values = features.as_dict()
    contributions: list[RiskContribution] = []

    def add(condition: bool, detector: str, points: float, evidence: str) -> None:
        if condition:
            contributions.append(RiskContribution(detector, points, evidence))

    add(
        values["sensitive_access"] > 0,
        "sensitive_access",
        15,
        "A sensitive resource was accessed.",
    )
    add(
        values["archive_activity"] > 0,
        "staging_activity",
        15,
        "Data was archived or staged in the same event window.",
    )
    add(
        values["egress_activity"] > 0,
        "egress_attempt",
        10,
        "The correlated process attempted network egress.",
    )
    add(
        values["new_destination"] > 0 and values["upload_activity"] > 0,
        "new_destination",
        15,
        "An upload targeted a destination absent from the known baseline.",
    )
    request_bytes = values["log_request_bytes"]
    add(
        request_bytes >= 16.0 and values["upload_activity"] > 0,
        "large_transfer",
        25,
        "The event window contains a large outbound transfer.",
    )
    add(
        values["outside_work_hours"] > 0,
        "outside_work_hours",
        10,
        "Activity occurred outside the configured work-hours baseline.",
    )
    add(
        values["sensitive_json_fields"] > 0,
        "sensitive_field_indicator",
        10,
        "A payload advertised a sensitive field name; its value was not retained.",
    )
    add(
        values["blocked_activity"] > 0,
        "policy_enforcement",
        5,
        "A correlated action was blocked by policy.",
    )
    return RuleScore(min(100.0, sum(item.points for item in contributions)), tuple(contributions))
