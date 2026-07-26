"""Evaluation and atomic promotion/rollback for trusted local model artifacts."""

from __future__ import annotations

import json
import os
import shutil
from collections.abc import Iterable
from dataclasses import asdict, dataclass
from pathlib import Path

from processing.anomaly import IsolationForestModel
from processing.features import FeatureVector


@dataclass(frozen=True)
class Evaluation:
    normal_false_positive_rate: float
    suspicious_true_positive_rate: float
    threshold: float

    @property
    def passes(self) -> bool:
        return self.normal_false_positive_rate <= 0.05 and self.suspicious_true_positive_rate >= 0.9


def evaluate(
    model: IsolationForestModel,
    normal: Iterable[FeatureVector],
    suspicious: Iterable[FeatureVector],
    *,
    threshold: float = 60.0,
) -> Evaluation:
    normal_scores = [model.anomaly_score(item) for item in normal]
    suspicious_scores = [model.anomaly_score(item) for item in suspicious]
    if not normal_scores or not suspicious_scores:
        raise ValueError("normal and suspicious evaluation windows are required")
    false_positive_rate = sum(score >= threshold for score in normal_scores) / len(normal_scores)
    true_positive_rate = sum(score >= threshold for score in suspicious_scores) / len(
        suspicious_scores
    )
    return Evaluation(false_positive_rate, true_positive_rate, threshold)


def promote(
    candidate: Path,
    registry_dir: Path,
    evaluation: Evaluation,
    *,
    version: str,
) -> Path:
    if not evaluation.passes:
        raise ValueError("candidate failed promotion gates")
    registry_dir.mkdir(parents=True, exist_ok=True)
    destination = registry_dir / f"{version}.pkl"
    shutil.copyfile(candidate, destination)
    temporary = registry_dir / ".current.tmp"
    temporary.write_text(destination.name + "\n")
    os.replace(temporary, registry_dir / "current")
    (registry_dir / f"{version}.json").write_text(
        json.dumps({"version": version, "evaluation": asdict(evaluation)}, indent=2) + "\n"
    )
    return destination


def rollback(registry_dir: Path, *, version: str) -> Path:
    artifact = registry_dir / f"{version}.pkl"
    if not artifact.is_file():
        raise ValueError(f"unknown model version: {version}")
    temporary = registry_dir / ".current.tmp"
    temporary.write_text(artifact.name + "\n")
    os.replace(temporary, registry_dir / "current")
    return artifact


def current_artifact(registry_dir: Path) -> Path | None:
    pointer = registry_dir / "current"
    if not pointer.is_file():
        return None
    artifact = registry_dir / pointer.read_text().strip()
    return artifact if artifact.is_file() else None
