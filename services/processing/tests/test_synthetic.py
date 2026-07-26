from __future__ import annotations

import json
from pathlib import Path

from processing.synthetic import generate_dataset, load_windows

ROOT = Path(__file__).parents[3]


def test_synthetic_events_are_deterministic_and_match_separate_truth(tmp_path: Path) -> None:
    first = tmp_path / "first"
    second = tmp_path / "second"
    arguments = {
        "normal_fixture": ROOT / "fixtures/expected/normal.json",
        "suspicious_fixture": ROOT / "fixtures/expected/suspicious.json",
        "train_normal": 8,
        "eval_normal": 8,
        "eval_suspicious": 8,
        "seed": 7,
    }
    generate_dataset(output_dir=first, **arguments)
    generate_dataset(output_dir=second, **arguments)
    assert (first / "train-normal.jsonl").read_bytes() == (
        second / "train-normal.jsonl"
    ).read_bytes()
    assert (first / "evaluation.jsonl").read_bytes() == (second / "evaluation.jsonl").read_bytes()

    windows = load_windows(first / "evaluation.jsonl")
    truth = json.loads((first / "expected.json").read_text())["labels"]
    assert {window["window_id"] for window in windows} == set(truth)
    assert set(truth.values()) == {"normal", "suspicious"}

    serialized = (first / "evaluation.jsonl").read_text().lower()
    assert "password-value" not in serialized
    assert "authorization: bearer" not in serialized
    assert '"token":' not in serialized
