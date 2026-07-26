from pathlib import Path

from fastapi.testclient import TestClient

from agentkit import validate_file
from business_agent.app import app

PROJECT = Path(__file__).resolve().parents[1]


def test_this_agents_manifest_and_policy_are_valid() -> None:
    # Arrange
    manifest = PROJECT / "agents.yaml"
    policy = PROJECT / "policy.yaml"

    # Act
    errors = validate_file(manifest) + validate_file(policy)

    # Assert
    assert errors == ()


def test_greet_returns_a_greeting_for_the_named_subject() -> None:
    # Arrange
    client = TestClient(app)

    # Act
    body = client.get("/greet/spark").json()

    # Assert
    assert body == {"greeting": "hello, spark"}


def test_health_endpoint_is_inherited_from_agentkit() -> None:
    # Arrange
    client = TestClient(app)

    # Act
    body = client.get("/healthz").json()

    # Assert
    assert body["agent"] == "business-agent"
    assert body["status"] == "ok"
