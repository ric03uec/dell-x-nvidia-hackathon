"""Investigation boundary used by policy recommendation unit tests."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any, Protocol


class InferenceError(RuntimeError):
    pass


class Investigator(Protocol):
    def investigate(self, evidence: Mapping[str, Any]) -> Mapping[str, str]: ...
