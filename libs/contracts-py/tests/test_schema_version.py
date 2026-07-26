"""schema_version is the contract's version gate: missing or unknown must fail clearly."""

from __future__ import annotations

from pathlib import Path

import pytest
from _registry import CASES
from conftest import load_json
from pydantic import ValidationError


@pytest.mark.parametrize("case", CASES, ids=[case.example_name for case in CASES])
def test_missing_schema_version_is_rejected(case, examples_dir: Path) -> None:
    payload = load_json(examples_dir / case.example_name)
    del payload["schema_version"]

    with pytest.raises(ValidationError, match="schema_version"):
        case.model.model_validate(payload)


@pytest.mark.parametrize("case", CASES, ids=[case.example_name for case in CASES])
def test_unknown_schema_version_is_rejected(case, examples_dir: Path) -> None:
    payload = {**load_json(examples_dir / case.example_name), "schema_version": "99.9"}

    with pytest.raises(ValidationError, match="unsupported schema_version"):
        case.model.model_validate(payload)
