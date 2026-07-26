"""Assert every model's field set and enum-valued fields agree with its schema.

This is the anti-drift gate the bead requires: whichever side (schema or
model) is authored, this test fails the moment the two disagree instead of
letting the divergence surface later at integration.
"""

from __future__ import annotations

from pathlib import Path
from typing import get_args

import pytest
from _registry import CASES
from conftest import load_json


@pytest.mark.parametrize("case", CASES, ids=[case.schema_name for case in CASES])
def test_model_field_set_matches_schema_properties(case, contracts_dir: Path) -> None:
    schema = load_json(contracts_dir / case.schema_name)

    schema_properties = set(schema["properties"].keys())
    model_fields = set(case.model.model_fields.keys())

    assert model_fields == schema_properties, (
        f"{case.model.__name__} fields {model_fields} != "
        f"{case.schema_name} properties {schema_properties}"
    )


@pytest.mark.parametrize("case", CASES, ids=[case.schema_name for case in CASES])
def test_model_required_fields_match_schema_required(case, contracts_dir: Path) -> None:
    schema = load_json(contracts_dir / case.schema_name)

    schema_required = set(schema["required"])
    model_required = {
        name for name, field in case.model.model_fields.items() if field.is_required()
    }

    assert model_required == schema_required, (
        f"{case.model.__name__} required fields {model_required} != "
        f"{case.schema_name} required {schema_required}"
    )


@pytest.mark.parametrize("case", CASES, ids=[case.schema_name for case in CASES])
def test_model_enum_literals_match_schema_enums(case, contracts_dir: Path) -> None:
    schema = load_json(contracts_dir / case.schema_name)

    for field_name in case.enum_fields:
        schema_enum = set(schema["properties"][field_name]["enum"])
        model_literal = set(get_args(case.model.model_fields[field_name].annotation))

        assert model_literal == schema_enum, (
            f"{case.model.__name__}.{field_name} Literal {model_literal} != "
            f"{case.schema_name} enum {schema_enum}"
        )


def test_every_schema_file_is_covered(contracts_dir: Path) -> None:
    """Fail loudly if a new/renamed schema lands without a case exercising it."""
    covered = {case.schema_name for case in CASES}
    top_level = {p.name for p in contracts_dir.glob("*.schema.json") if p.is_file()}
    uncovered = sorted(top_level - covered)
    assert not uncovered, f"schemas not covered by any drift case: {uncovered}"
