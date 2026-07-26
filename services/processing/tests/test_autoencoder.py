from __future__ import annotations

import json
from pathlib import Path

import pytest

from processing.autoencoder import AutoencoderConfig, AutoencoderModel
from processing.dataset import augmented_normal_windows
from processing.features import extract_features

ROOT = Path(__file__).parents[3]
NORMAL = json.loads((ROOT / "fixtures/expected/normal.json").read_text())
SUSPICIOUS = json.loads((ROOT / "fixtures/expected/suspicious.json").read_text())
KNOWN = {event["destination"] for event in NORMAL if "destination" in event}


def test_autoencoder_assigns_more_error_to_suspicious_window() -> None:
    pytest.importorskip("torch")
    training = augmented_normal_windows(NORMAL, count=64)
    model = AutoencoderModel.train(
        training,
        AutoencoderConfig(hidden_size=6, epochs=80, seed=42),
    )
    normal = extract_features(NORMAL, known_destinations=KNOWN)
    suspicious = extract_features(SUSPICIOUS, known_destinations=KNOWN)
    assert model.reconstruction_error(suspicious) > model.reconstruction_error(normal)
