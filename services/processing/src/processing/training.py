"""Reproducible synthetic training, evaluation, and promotion workflow."""

from __future__ import annotations

import hashlib
import json
import math
from pathlib import Path
from typing import Any

import numpy as np

from processing.anomaly import IsolationForestModel
from processing.autoencoder import AutoencoderConfig, AutoencoderModel
from processing.features import FeatureVector, extract_features
from processing.lifecycle import evaluate, promote
from processing.pipeline import detect_window
from processing.synthetic import load_windows


def _destinations(windows: list[dict[str, Any]]) -> set[str]:
    return {
        str(event["destination"])
        for window in windows
        for event in window["events"]
        if isinstance(event.get("destination"), str) and ":3128" not in event["destination"]
    }


def _vectors(windows: list[dict[str, Any]], known_destinations: set[str]) -> list[FeatureVector]:
    return [
        extract_features(window["events"], known_destinations=known_destinations)
        for window in windows
    ]


def train_bundle(
    dataset_dir: Path,
    artifact_dir: Path,
    *,
    seed: int = 42,
    autoencoder_epochs: int = 150,
) -> dict[str, Any]:
    training = load_windows(dataset_dir / "train-normal.jsonl")
    evaluation_windows = load_windows(dataset_dir / "evaluation.jsonl")
    truth = json.loads((dataset_dir / "expected.json").read_text())["labels"]
    known = _destinations(training)
    training_vectors = _vectors(training, known)
    normal_eval = [item for item in evaluation_windows if truth[item["window_id"]] == "normal"]
    suspicious_eval = [
        item for item in evaluation_windows if truth[item["window_id"]] == "suspicious"
    ]
    normal_vectors = _vectors(normal_eval, known)
    suspicious_vectors = _vectors(suspicious_eval, known)

    isolation_model = IsolationForestModel.train(training_vectors, random_state=seed)
    normal_scores = sorted(isolation_model.anomaly_score(item) for item in normal_vectors)
    cutoff_index = min(len(normal_scores) - 1, math.floor(len(normal_scores) * 0.95))
    anomaly_threshold = float(np.nextafter(normal_scores[cutoff_index], math.inf))
    isolation_evaluation = evaluate(
        isolation_model,
        normal_vectors,
        suspicious_vectors,
        threshold=anomaly_threshold,
    )

    normal_alerts = sum(
        detect_window(item["events"], known_destinations=known).finding is not None
        for item in normal_eval
    )
    suspicious_alerts = sum(
        detect_window(item["events"], known_destinations=known).finding is not None
        for item in suspicious_eval
    )
    rule_false_positive_rate = normal_alerts / len(normal_eval)
    rule_true_positive_rate = suspicious_alerts / len(suspicious_eval)
    if rule_false_positive_rate > 0.05 or rule_true_positive_rate < 0.9:
        raise RuntimeError("deterministic detector failed evaluation gates")

    artifact_dir.mkdir(parents=True, exist_ok=True)
    candidate = artifact_dir / "isolation-forest-candidate.pkl"
    isolation_model.save(candidate)
    promoted = promote(
        candidate,
        artifact_dir / "registry",
        isolation_evaluation,
        version=isolation_model.version,
    )

    autoencoder = AutoencoderModel.train(
        training_vectors,
        AutoencoderConfig(epochs=autoencoder_epochs, seed=seed),
    )
    normal_errors = [autoencoder.reconstruction_error(item) for item in normal_vectors]
    suspicious_errors = [autoencoder.reconstruction_error(item) for item in suspicious_vectors]
    autoencoder_threshold = float(np.quantile(normal_errors, 0.99, method="higher"))
    autoencoder_fpr = sum(item > autoencoder_threshold for item in normal_errors) / len(
        normal_errors
    )
    autoencoder_tpr = sum(item > autoencoder_threshold for item in suspicious_errors) / len(
        suspicious_errors
    )
    snapshot_id = hashlib.sha256((dataset_dir / "manifest.json").read_bytes()).hexdigest()[:16]
    autoencoder_path = artifact_dir / f"{autoencoder.version}.pt"
    autoencoder.save(autoencoder_path, snapshot_id=f"synthetic-{snapshot_id}")

    report = {
        "schema_version": "1.0",
        "seed": seed,
        "dataset": {
            "training_normal": len(training),
            "evaluation_normal": len(normal_eval),
            "evaluation_suspicious": len(suspicious_eval),
        },
        "rules": {
            "false_positive_rate": rule_false_positive_rate,
            "true_positive_rate": rule_true_positive_rate,
        },
        "isolation_forest": {
            "version": isolation_model.version,
            "threshold": anomaly_threshold,
            "false_positive_rate": isolation_evaluation.normal_false_positive_rate,
            "true_positive_rate": isolation_evaluation.suspicious_true_positive_rate,
            "artifact": str(promoted),
            "promoted": isolation_evaluation.passes,
        },
        "autoencoder": {
            "version": autoencoder.version,
            "threshold": autoencoder_threshold,
            "false_positive_rate": autoencoder_fpr,
            "true_positive_rate": autoencoder_tpr,
            "artifact": str(autoencoder_path),
            "snapshot_id": f"synthetic-{snapshot_id}",
        },
    }
    (artifact_dir / "training-report.json").write_text(
        json.dumps(report, indent=2, sort_keys=True) + "\n"
    )
    return report
