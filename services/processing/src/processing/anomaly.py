"""CPU Isolation Forest model with an explicit rules-only degradation path."""

from __future__ import annotations

import pickle
from collections.abc import Iterable
from dataclasses import dataclass
from pathlib import Path

import numpy as np
from sklearn.ensemble import IsolationForest  # type: ignore[import-untyped]
from sklearn.preprocessing import StandardScaler  # type: ignore[import-untyped]

from processing.features import FeatureVector


@dataclass
class IsolationForestModel:
    scaler: StandardScaler
    estimator: IsolationForest
    version: str = "isolation-forest-001"

    @classmethod
    def train(
        cls,
        normal_windows: Iterable[FeatureVector],
        *,
        random_state: int = 42,
    ) -> IsolationForestModel:
        matrix = np.asarray([item.values for item in normal_windows], dtype=np.float64)
        if matrix.ndim != 2 or len(matrix) < 8:
            raise ValueError("at least eight normal windows are required")
        scaler = StandardScaler().fit(matrix)
        estimator = IsolationForest(
            n_estimators=200,
            contamination="auto",
            random_state=random_state,
            n_jobs=1,
        ).fit(scaler.transform(matrix))
        return cls(scaler=scaler, estimator=estimator)

    def anomaly_score(self, features: FeatureVector) -> float:
        """Return a bounded 0..100 score; higher means more anomalous."""
        matrix = self.scaler.transform(np.asarray([features.values], dtype=np.float64))
        raw = float(-self.estimator.decision_function(matrix)[0])
        return max(0.0, min(100.0, 50.0 + raw * 200.0))

    def save(self, path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(pickle.dumps(self, protocol=pickle.HIGHEST_PROTOCOL))

    @classmethod
    def load(cls, path: Path) -> IsolationForestModel:
        value = pickle.loads(path.read_bytes())  # noqa: S301 - trusted local artifact only
        if not isinstance(value, cls):
            raise ValueError("artifact is not an IsolationForestModel")
        return value


def safe_load(path: Path | None) -> IsolationForestModel | None:
    """Return no model when an artifact is absent or invalid; live rules continue."""
    if path is None or not path.exists():
        return None
    try:
        return IsolationForestModel.load(path)
    except (OSError, ValueError, pickle.UnpicklingError, EOFError):
        return None
