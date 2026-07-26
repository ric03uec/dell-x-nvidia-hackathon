"""End-to-end window scoring and constrained recommendation generation."""

from __future__ import annotations

import hashlib
from collections.abc import Iterable
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any

from processing.anomaly import IsolationForestModel
from processing.features import Event, FeatureVector, extract_features
from processing.inference import InferenceError, Investigator
from processing.rules import RuleScore, score_rules


@dataclass(frozen=True)
class DetectionResult:
    features: FeatureVector
    rules: RuleScore
    anomaly_score: float | None
    risk_score: float
    finding: dict[str, Any] | None


def _stable_id(prefix: str, event_ids: Iterable[str]) -> str:
    digest = hashlib.sha256("\0".join(event_ids).encode()).hexdigest()[:16]
    return f"{prefix}-{digest}"


def _severity(score: float) -> str:
    if score >= 90:
        return "critical"
    if score >= 70:
        return "high"
    if score >= 40:
        return "medium"
    return "low"


def detect_window(
    events: Iterable[Event],
    *,
    known_destinations: Iterable[str] = (),
    anomaly_model: IsolationForestModel | None = None,
    threshold: float = 70.0,
) -> DetectionResult:
    window = list(events)
    features = extract_features(window, known_destinations=known_destinations)
    rules = score_rules(features)
    anomaly_score = anomaly_model.anomaly_score(features) if anomaly_model else None
    # Rules stay authoritative and available. The unsupervised model can add at
    # most 20 points, so it cannot turn weak evidence into a critical finding.
    model_points = min(20.0, (anomaly_score or 0.0) * 0.2)
    risk_score = min(100.0, rules.score + model_points)
    finding = None
    if risk_score >= threshold:
        detectors = list(rules.detectors)
        if anomaly_score is not None:
            detectors.append("isolation_forest")
        finding = {
            "schema_version": "1.0",
            "finding_id": _stable_id("finding", features.event_ids),
            "event_ids": list(features.event_ids),
            "risk_score": round(risk_score, 2),
            "severity": _severity(risk_score),
            "detectors": detectors,
            "summary": "Suspicious correlated activity: "
            + "; ".join(item.evidence for item in rules.contributions),
            "model_version": anomaly_model.version if anomaly_model else "rules-001",
            "evidence": [
                {
                    "detector": item.detector,
                    "points": item.points,
                    "description": item.evidence,
                }
                for item in rules.contributions
            ],
        }
    return DetectionResult(features, rules, anomaly_score, risk_score, finding)


def recommend_policy(
    detection: DetectionResult,
    investigator: Investigator,
    *,
    scope: str = "business-agent",
    now: datetime | None = None,
) -> tuple[dict[str, Any], dict[str, Any]]:
    """Enhance a finding with local prose while fixing policy fields in code."""
    if detection.finding is None or detection.features.destination is None:
        raise ValueError("a finding with a destination is required")
    evidence = {
        "finding_id": detection.finding["finding_id"],
        "risk_score": detection.risk_score,
        "detectors": list(detection.rules.detectors),
        "destination": detection.features.destination,
        "event_count": len(detection.features.event_ids),
    }
    try:
        investigation = investigator.investigate(evidence)
    except InferenceError:
        investigation = {
            "summary": detection.finding["summary"],
            "reason": "Deterministic evidence exceeded the review threshold.",
        }
    finding = {**detection.finding, "summary": investigation["summary"]}
    timestamp = now or datetime.now().astimezone()
    recommendation = {
        "schema_version": "1.0",
        "recommendation_id": _stable_id("rec", detection.features.event_ids),
        "finding_id": finding["finding_id"],
        # These security-sensitive fields never come from generative output.
        "action_type": "deny_destination",
        "target": detection.features.destination,
        "scope": scope,
        "reason": investigation["reason"],
        "expires_at": (timestamp + timedelta(days=1)).isoformat(),
    }
    return finding, recommendation
