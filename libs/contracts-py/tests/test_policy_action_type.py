"""action_type is a closed enum (integration rule 5): out-of-enum must not construct."""

from __future__ import annotations

from pathlib import Path

import pytest
from conftest import load_json
from pydantic import ValidationError

from contracts_py.models import PolicyRecommendation


def test_unlisted_action_type_fails_to_construct(examples_dir: Path) -> None:
    payload = load_json(examples_dir / "invalid" / "policy-recommendation-bad-action-type.json")
    assert (
        payload["action_type"]
        not in PolicyRecommendation.model_fields["action_type"].annotation.__args__
    )

    with pytest.raises(ValidationError, match="action_type"):
        PolicyRecommendation.model_validate(payload)


def test_valid_action_type_constructs(examples_dir: Path) -> None:
    payload = load_json(examples_dir / "policy-recommendation.json")

    recommendation = PolicyRecommendation.model_validate(payload)

    assert recommendation.action_type == "deny_destination"
