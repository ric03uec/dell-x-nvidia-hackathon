"""Pydantic models mirroring the JSON Schemas frozen in `contracts/`.

Each model's field set and enum-valued fields are checked against the
corresponding schema by `tests/test_schema_drift.py` so the two representations
cannot silently drift apart — see that test before changing a field here or in
`contracts/*.schema.json`.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_serializer, field_validator

# Every contract example currently in contracts/examples/ is stamped "1.0".
# Extending this set is a reviewed contract change, not something a model
# consumer can silently opt into.
SUPPORTED_SCHEMA_VERSIONS: frozenset[str] = frozenset({"1.0"})


def _serialize_utc_z(value: datetime) -> str:
    """Render an aware datetime the same way the frozen examples do: trailing Z."""
    iso = value.isoformat()
    return iso[:-6] + "Z" if iso.endswith("+00:00") else iso


class ContractModel(BaseModel):
    """Shared base: every contract payload carries and validates schema_version."""

    schema_version: str

    @field_validator("schema_version")
    @classmethod
    def _check_schema_version(cls, value: str) -> str:
        if value not in SUPPORTED_SCHEMA_VERSIONS:
            raise ValueError(
                f"unsupported schema_version {value!r}; expected one of "
                f"{sorted(SUPPORTED_SCHEMA_VERSIONS)}"
            )
        return value


class Event(ContractModel):
    """Canonical Event — contracts/event.schema.json."""

    model_config = ConfigDict(extra="allow")

    event_id: str
    timestamp: datetime
    source_type: str
    actor: str
    user: str | None = None
    device: str | None = None
    action: str
    destination: str | None = None
    request_bytes: int | None = Field(default=None, ge=0)
    attributes: dict[str, Any] | None = None

    @field_serializer("timestamp")
    def _serialize_timestamp(self, value: datetime) -> str:
        return _serialize_utc_z(value)


class Finding(ContractModel):
    """Finding — contracts/finding.schema.json."""

    model_config = ConfigDict(extra="allow")

    finding_id: str
    event_ids: list[str] = Field(min_length=1)
    risk_score: float = Field(ge=0, le=100)
    severity: Literal["low", "medium", "high", "critical"]
    detectors: list[str] | None = None
    summary: str | None = None
    model_version: str | None = None


class PolicyRecommendation(ContractModel):
    """Policy Recommendation — contracts/policy-recommendation.schema.json.

    action_type is a CLOSED enumeration (integration rule 5): a generative
    model must never be able to emit an action_type outside this set, so an
    out-of-enum value fails Pydantic construction rather than merely being
    flagged. additionalProperties is false on the schema, mirrored here with
    extra="forbid".
    """

    model_config = ConfigDict(extra="forbid")

    recommendation_id: str
    finding_id: str
    action_type: Literal["deny_destination"]
    target: str
    scope: str
    reason: str | None = None
    expires_at: datetime | None = None

    @field_serializer("expires_at")
    def _serialize_expires_at(self, value: datetime | None) -> str | None:
        return _serialize_utc_z(value) if value is not None else None


class Approval(ContractModel):
    """Approval Decision — contracts/approval.schema.json."""

    model_config = ConfigDict(extra="allow")

    recommendation_id: str
    decision: Literal["approved", "rejected"]
    analyst: str
    timestamp: datetime

    @field_serializer("timestamp")
    def _serialize_timestamp(self, value: datetime) -> str:
        return _serialize_utc_z(value)


class EnforcementResult(ContractModel):
    """Enforcement Result — contracts/enforcement-result.schema.json."""

    model_config = ConfigDict(extra="allow")

    recommendation_id: str
    status: Literal["applied", "failed"]
    enforcement_point: str
    policy_version: str | None = None
