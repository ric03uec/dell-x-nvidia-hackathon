from __future__ import annotations

import pytest

from processing.inference import InferenceError, LocalLiteLLMInvestigator


def test_external_inference_url_is_rejected(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("LOCAL_INFERENCE_API_KEY", "synthetic-test-key")
    monkeypatch.setenv("LOCAL_INFERENCE_URL", "https://localhost.example.com/v1")
    with pytest.raises(InferenceError, match="loopback"):
        LocalLiteLLMInvestigator.from_env()


def test_loopback_inference_url_is_accepted(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("LOCAL_INFERENCE_API_KEY", "synthetic-test-key")
    monkeypatch.setenv("LOCAL_INFERENCE_URL", "http://127.0.0.1:14000/v1")
    adapter = LocalLiteLLMInvestigator.from_env()
    assert adapter.base_url == "http://127.0.0.1:14000/v1"
