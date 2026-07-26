from __future__ import annotations

import subprocess
import tempfile
import unittest
from pathlib import Path

from gpu_telemetry import GpuTelemetryCollector, parse_meminfo, parse_nvidia_smi


class GpuTelemetryTests(unittest.TestCase):
    def test_parses_nvidia_smi_csv(self) -> None:
        telemetry = parse_nvidia_smi("62, 24100, 119700\n")
        self.assertEqual(telemetry["utilization_percent"], 62)
        self.assertEqual(telemetry["memory_used_bytes"], 24_100 * 1024 * 1024)
        self.assertEqual(telemetry["memory_total_bytes"], 119_700 * 1024 * 1024)

    def test_parses_unified_memory_from_meminfo(self) -> None:
        telemetry = parse_meminfo("MemTotal: 120000000 kB\nMemAvailable: 90000000 kB\n")
        self.assertEqual(telemetry["memory_used_bytes"], 30_000_000 * 1024)
        self.assertEqual(telemetry["memory_total_bytes"], 120_000_000 * 1024)

    def test_gb10_prefers_unified_memory_and_caches_collection(self) -> None:
        calls = 0

        def run(*args, **kwargs):
            nonlocal calls
            calls += 1
            return subprocess.CompletedProcess(args[0], 0, "71, 20000, 100000\n", "")

        with tempfile.TemporaryDirectory() as directory:
            meminfo = Path(directory) / "meminfo"
            meminfo.write_text("MemTotal: 120000000 kB\nMemAvailable: 80000000 kB\n")
            collector = GpuTelemetryCollector(
                runner=run,
                meminfo_path=meminfo,
                prefer_unified_memory=True,
                monotonic=lambda: 10.0,
            )
            first = collector.collect()
            second = collector.collect()

        self.assertEqual(first, second)
        self.assertEqual(calls, 1)
        self.assertEqual(first["utilization_percent"], 71)
        self.assertTrue(first["gpu_present"])
        self.assertEqual(first["memory_scope"], "unified")
        self.assertEqual(first["source"], "nvidia-smi+/proc/meminfo")
        self.assertEqual(first["memory_used_bytes"], 40_000_000 * 1024)

    def test_reports_unavailable_without_inventing_values(self) -> None:
        def unavailable(*args, **kwargs):
            raise FileNotFoundError

        collector = GpuTelemetryCollector(
            runner=unavailable,
            meminfo_path=Path("/missing/meminfo"),
            prefer_unified_memory=True,
        )
        telemetry = collector.collect()

        self.assertEqual(telemetry["status"], "unavailable")
        self.assertIsNone(telemetry["utilization_percent"])
        self.assertIsNone(telemetry["memory_total_bytes"])


if __name__ == "__main__":
    unittest.main()
