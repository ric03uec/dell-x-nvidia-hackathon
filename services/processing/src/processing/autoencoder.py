"""Offline PyTorch autoencoder for anomaly scoring over safe snapshot features."""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from pathlib import Path

import numpy as np
from numpy.typing import NDArray

from processing.features import FEATURE_NAMES, FeatureVector


@dataclass(frozen=True)
class AutoencoderConfig:
    hidden_size: int = 8
    epochs: int = 150
    learning_rate: float = 0.01
    seed: int = 42


class AutoencoderModel:
    """Torch is imported lazily so the live CPU path never depends on it."""

    version = "autoencoder-001"

    def __init__(
        self,
        network: object,
        mean: NDArray[np.float32],
        scale: NDArray[np.float32],
    ) -> None:
        self.network = network
        self.mean = mean
        self.scale = scale

    @classmethod
    def train(
        cls,
        normal_windows: Iterable[FeatureVector],
        config: AutoencoderConfig | None = None,
    ) -> AutoencoderModel:
        import torch
        from torch import nn

        config = config or AutoencoderConfig()
        matrix = np.asarray([item.values for item in normal_windows], dtype=np.float32)
        if matrix.ndim != 2 or len(matrix) < 8:
            raise ValueError("at least eight normal windows are required")
        mean = matrix.mean(axis=0)
        scale = matrix.std(axis=0)
        scale[scale < 1e-6] = 1.0
        normalized = torch.tensor((matrix - mean) / scale)
        torch.manual_seed(config.seed)
        network = nn.Sequential(
            nn.Linear(len(FEATURE_NAMES), config.hidden_size),
            nn.ReLU(),
            nn.Linear(config.hidden_size, len(FEATURE_NAMES)),
        )
        optimizer = torch.optim.Adam(network.parameters(), lr=config.learning_rate)
        for _ in range(config.epochs):
            optimizer.zero_grad()
            reconstruction = network(normalized)
            loss = nn.functional.mse_loss(reconstruction, normalized)
            loss.backward()  # type: ignore[no-untyped-call]
            optimizer.step()
        network.eval()
        return cls(network, mean, scale)

    def reconstruction_error(self, features: FeatureVector) -> float:
        import torch
        from torch import nn

        matrix = np.asarray([features.values], dtype=np.float32)
        normalized = torch.tensor((matrix - self.mean) / self.scale)
        with torch.no_grad():
            reconstructed = self.network(normalized)  # type: ignore[operator]
            return float(nn.functional.mse_loss(reconstructed, normalized).item())

    def save(self, path: Path, *, snapshot_id: str) -> None:
        import torch

        path.parent.mkdir(parents=True, exist_ok=True)
        torch.save(
            {
                "version": self.version,
                "snapshot_id": snapshot_id,
                "mean": self.mean,
                "scale": self.scale,
                "state_dict": self.network.state_dict(),  # type: ignore[attr-defined]
            },
            path,
        )
