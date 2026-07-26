"""Every file in contracts/examples/ must round-trip through its model losslessly.

parse(example) -> model -> dump() must reproduce the original data exactly:
no dropped fields, no silently coerced values.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from _registry import CASES
from conftest import load_json


@pytest.mark.parametrize("case", CASES, ids=[case.example_name for case in CASES])
def test_example_round_trips_without_loss(case, examples_dir: Path) -> None:
    original = load_json(examples_dir / case.example_name)

    instance = case.model.model_validate(original)
    round_tripped = instance.model_dump(mode="json", exclude_none=True)

    assert round_tripped == original


def test_every_top_level_example_is_covered(examples_dir: Path) -> None:
    """Fail loudly if a new example lands without a case exercising it."""
    covered = {case.example_name for case in CASES}
    top_level = {p.name for p in examples_dir.glob("*.json") if p.is_file()}
    uncovered = sorted(top_level - covered)
    assert not uncovered, f"examples not covered by any round-trip case: {uncovered}"
