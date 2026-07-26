"""Host-side GPU telemetry for SquidWard's GB10 status panel."""

from __future__ import annotations

import platform
import re
import subprocess
import time
from collections.abc import Callable
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

MIB = 1024 * 1024
KIB = 1024


def _number(value: str) -> float | None:
    if not value or value.strip().upper() in {"N/A", "[N/A]", "NOT SUPPORTED"}:
        return None
    match = re.search(r"-?\d+(?:\.\d+)?", value)
    return float(match.group()) if match else None


def parse_nvidia_smi(output: str) -> dict[str, int | None]:
    """Parse one CSV row from the nvidia-smi query used by the collector."""
    line = next((line.strip() for line in output.splitlines() if line.strip()), "")
    fields = [field.strip() for field in line.split(",")]
    utilization = _number(fields[0]) if fields else None
    memory_used = _number(fields[1]) if len(fields) > 1 else None
    memory_total = _number(fields[2]) if len(fields) > 2 else None
    return {
        "utilization_percent": round(utilization) if utilization is not None else None,
        "memory_used_bytes": round(memory_used * MIB) if memory_used is not None else None,
        "memory_total_bytes": round(memory_total * MIB) if memory_total is not None else None,
    }


def parse_meminfo(content: str) -> dict[str, int | None]:
    """Return host unified-memory usage from Linux /proc/meminfo."""
    values: dict[str, int] = {}
    for line in content.splitlines():
        key, separator, remainder = line.partition(":")
        if not separator:
            continue
        value = _number(remainder)
        if value is not None:
            values[key] = round(value * KIB)
    total = values.get("MemTotal")
    available = values.get("MemAvailable")
    used = total - available if total is not None and available is not None else None
    return {"memory_used_bytes": used, "memory_total_bytes": total}


def _observed_at() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


class GpuTelemetryCollector:
    """Collect and briefly cache GPU utilization plus GB10 unified memory."""

    def __init__(
        self,
        *,
        runner: Callable[..., Any] = subprocess.run,
        meminfo_path: Path = Path("/proc/meminfo"),
        cache_seconds: float = 5.0,
        monotonic: Callable[[], float] = time.monotonic,
        prefer_unified_memory: bool | None = None,
    ) -> None:
        self._runner = runner
        self._meminfo_path = meminfo_path
        self._cache_seconds = cache_seconds
        self._monotonic = monotonic
        self._prefer_unified_memory = (
            platform.machine().lower() in {"aarch64", "arm64"}
            if prefer_unified_memory is None
            else prefer_unified_memory
        )
        self._cached_at = 0.0
        self._cached: dict[str, Any] | None = None

    def collect(self) -> dict[str, Any]:
        now = self._monotonic()
        if self._cached is not None and now - self._cached_at < self._cache_seconds:
            return dict(self._cached)

        telemetry: dict[str, Any] = {
            "status": "unavailable",
            "utilization_percent": None,
            "memory_used_bytes": None,
            "memory_total_bytes": None,
            "memory_scope": None,
            "gpu_present": False,
            "source": None,
            "observed_at": _observed_at(),
        }
        try:
            result = self._runner(
                [
                    "nvidia-smi",
                    "--query-gpu=utilization.gpu,memory.used,memory.total",
                    "--format=csv,noheader,nounits",
                ],
                capture_output=True,
                text=True,
                check=True,
                timeout=3,
            )
            telemetry["gpu_present"] = True
            telemetry.update(parse_nvidia_smi(result.stdout))
            telemetry["source"] = "nvidia-smi"
            if telemetry["memory_total_bytes"] is not None:
                telemetry["memory_scope"] = "device"
        except (FileNotFoundError, OSError, subprocess.SubprocessError):
            pass

        if self._prefer_unified_memory or telemetry["memory_total_bytes"] is None:
            try:
                memory = parse_meminfo(self._meminfo_path.read_text())
            except OSError:
                memory = {"memory_used_bytes": None, "memory_total_bytes": None}
            if memory["memory_total_bytes"] is not None:
                telemetry.update(memory)
                telemetry["memory_scope"] = "unified"
                telemetry["source"] = (
                    "nvidia-smi+/proc/meminfo" if telemetry["gpu_present"] else "/proc/meminfo"
                )

        if (
            telemetry["gpu_present"]
            and telemetry["utilization_percent"] is not None
            and telemetry["memory_total_bytes"] is not None
        ):
            telemetry["status"] = "healthy"
        elif telemetry["gpu_present"] or telemetry["memory_total_bytes"] is not None:
            telemetry["status"] = "degraded"

        self._cached = telemetry
        self._cached_at = now
        return dict(telemetry)
