"""One row per contract: which example, which schema, which model.

Shared by the round-trip and schema-drift tests so both exercise the same
example<->schema<->model triples contracts/validate.py already validates.
"""

from __future__ import annotations

from dataclasses import dataclass

from contracts_py.models import (
    Approval,
    EnforcementResult,
    Event,
    Finding,
    PolicyRecommendation,
)


@dataclass(frozen=True)
class ContractCase:
    example_name: str
    schema_name: str
    model: type
    # Field names whose schema "enum" must match a Literal on the model.
    enum_fields: frozenset[str] = frozenset()


CASES: tuple[ContractCase, ...] = (
    ContractCase("event.json", "event.schema.json", Event),
    ContractCase("finding.json", "finding.schema.json", Finding, frozenset({"severity"})),
    ContractCase(
        "policy-recommendation.json",
        "policy-recommendation.schema.json",
        PolicyRecommendation,
        frozenset({"action_type"}),
    ),
    ContractCase("approval.json", "approval.schema.json", Approval, frozenset({"decision"})),
    ContractCase(
        "enforcement-result.json",
        "enforcement-result.schema.json",
        EnforcementResult,
        frozenset({"status"}),
    ),
)
