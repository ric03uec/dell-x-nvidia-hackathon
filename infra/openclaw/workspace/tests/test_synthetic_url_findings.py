import importlib.util
import unittest
from pathlib import Path

MODULE_PATH = (
    Path(__file__).resolve().parents[1] / "tools" / "generate_synthetic_url_findings.py"
)
SPEC = importlib.util.spec_from_file_location("generate_synthetic_url_findings", MODULE_PATH)
assert SPEC and SPEC.loader
generator = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(generator)


class SyntheticUrlFindingsTest(unittest.TestCase):
    def test_builds_reproducible_safe_dataset(self) -> None:
        first = generator.build_dataset(1000, 20260726, "2026-07-26T18:00:00Z")
        second = generator.build_dataset(1000, 20260726, "2026-07-26T18:00:00Z")

        self.assertEqual(first, second)
        self.assertTrue(first["synthetic"])
        self.assertEqual(first["count"], 1000)
        self.assertEqual(len(first["findings"]), 1000)
        self.assertEqual(len({item["URL"] for item in first["findings"]}), 1000)
        self.assertTrue(all(".example.test/" in item["URL"] for item in first["findings"]))
        self.assertTrue(
            all(item["Evidence"].startswith("SYNTHETIC:") for item in first["findings"])
        )

    def test_cvss_matches_rating(self) -> None:
        dataset = generator.build_dataset(1000, 7, "2026-07-26T18:00:00Z")

        for finding in dataset["findings"]:
            minimum, maximum = generator.RATING_RANGES[finding["Rating"]]
            self.assertGreaterEqual(finding["CVSS"], minimum)
            self.assertLessEqual(finding["CVSS"], maximum)


if __name__ == "__main__":
    unittest.main()
