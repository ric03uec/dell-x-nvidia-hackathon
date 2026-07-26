from __future__ import annotations

import json
from pathlib import Path

from processing.anomaly import IsolationForestModel
from processing.dataset import augmented_normal_windows
from processing.features import extract_features
from processing.lifecycle import current_artifact, evaluate, promote, rollback

ROOT = Path(__file__).parents[3]
NORMAL = json.loads((ROOT / "fixtures/expected/normal.json").read_text())
SUSPICIOUS = json.loads((ROOT / "fixtures/expected/suspicious.json").read_text())
KNOWN = {event["destination"] for event in NORMAL if "destination" in event}


def test_evaluate_promote_and_rollback(tmp_path: Path) -> None:
    normal = augmented_normal_windows(NORMAL, count=64)
    model = IsolationForestModel.train(normal)
    suspicious = [extract_features(SUSPICIOUS, known_destinations=KNOWN)] * 10
    result = evaluate(model, normal, suspicious, threshold=80.0)
    assert result.passes

    candidate = tmp_path / "candidate.pkl"
    model.save(candidate)
    registry = tmp_path / "registry"
    first = promote(candidate, registry, result, version="v1")
    assert current_artifact(registry) == first

    second = promote(candidate, registry, result, version="v2")
    assert current_artifact(registry) == second
    assert rollback(registry, version="v1") == first
    assert current_artifact(registry) == first
