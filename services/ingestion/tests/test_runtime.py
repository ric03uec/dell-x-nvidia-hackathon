from __future__ import annotations

import subprocess
from pathlib import Path

from ingestion.runtime import GpuTelemetryCollector, parse_meminfo, parse_nvidia_smi


def test_parses_nvidia_smi_csv() -> None:
    telemetry = parse_nvidia_smi("62, 24100, 119700\n")
    assert telemetry["utilization_percent"] == 62
    assert telemetry["memory_used_bytes"] == 24_100 * 1024 * 1024
    assert telemetry["memory_total_bytes"] == 119_700 * 1024 * 1024


def test_parses_unified_memory_from_meminfo() -> None:
    telemetry = parse_meminfo("MemTotal: 120000000 kB\nMemAvailable: 90000000 kB\n")
    assert telemetry["memory_used_bytes"] == 30_000_000 * 1024
    assert telemetry["memory_total_bytes"] == 120_000_000 * 1024


def test_gb10_prefers_unified_memory_and_caches_collection(tmp_path: Path) -> None:
    calls = 0

    def run(*args, **kwargs):
        nonlocal calls
        calls += 1
        return subprocess.CompletedProcess(args[0], 0, "71, 20000, 100000\n", "")

    meminfo = tmp_path / "meminfo"
    meminfo.write_text("MemTotal: 120000000 kB\nMemAvailable: 80000000 kB\n")
    collector = GpuTelemetryCollector(
        runner=run,
        meminfo_path=meminfo,
        prefer_unified_memory=True,
        monotonic=lambda: 10.0,
    )
    first = collector.collect()
    second = collector.collect()

    assert first == second
    assert calls == 1
    assert first["utilization_percent"] == 71
    assert first["gpu_present"] is True
    assert first["memory_scope"] == "unified"
    assert first["source"] == "nvidia-smi+/proc/meminfo"
    assert first["memory_used_bytes"] == 40_000_000 * 1024


def test_reports_unavailable_without_inventing_values() -> None:
    def unavailable(*args, **kwargs):
        raise FileNotFoundError

    collector = GpuTelemetryCollector(
        runner=unavailable,
        meminfo_path=Path("/missing/meminfo"),
        prefer_unified_memory=True,
    )
    telemetry = collector.collect()
    assert telemetry["status"] == "unavailable"
    assert telemetry["utilization_percent"] is None
    assert telemetry["memory_total_bytes"] is None
