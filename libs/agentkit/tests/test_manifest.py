from pathlib import Path

import pytest

from agentkit.manifest import main, validate_agents, validate_file, validate_policy
from agentkit.service import create_app


def test_reports_duplicate_agent_ids() -> None:
    # Arrange
    doc = {"agents": [{"id": "writer"}, {"id": "writer"}]}

    # Act
    errors = validate_agents(doc)

    # Assert
    assert any("duplicate agent id 'writer'" in e for e in errors)


def test_reports_agent_missing_an_id() -> None:
    # Arrange
    doc = {"agents": [{"model": "nvidia/nemotron-3-nano-30b"}]}

    # Act
    errors = validate_agents(doc)

    # Assert
    assert any("needs a non-empty 'id'" in e for e in errors)


def test_reports_unknown_tool_verbs() -> None:
    # Arrange
    doc = {"agents": [{"id": "writer", "tools": {"allow": ["read", "delete"]}}]}

    # Act
    errors = validate_agents(doc)

    # Assert
    assert any("unknown verbs ['delete']" in e for e in errors)


def test_reports_policy_missing_version() -> None:
    # Arrange
    doc = {"filesystem_policy": {"read_only": ["/usr"]}}

    # Act
    errors = validate_policy(doc)

    # Assert
    assert any("missing 'version'" in e for e in errors)


def test_reports_non_bool_include_workdir() -> None:
    # Arrange
    doc = {"version": 1, "filesystem_policy": {"include_workdir": "yes"}}

    # Act
    errors = validate_policy(doc)

    # Assert
    assert any("filesystem_policy.include_workdir must be a bool" in e for e in errors)


def test_accepts_bool_include_workdir() -> None:
    # Arrange
    doc = {"version": 1, "filesystem_policy": {"include_workdir": False}}

    # Act
    errors = validate_policy(doc)

    # Assert
    assert not errors


def test_reports_endpoint_without_host_or_port() -> None:
    # Arrange
    doc = {"version": 1, "network_policies": {"api": {"endpoints": [{"host": "example.com"}]}}}

    # Act
    errors = validate_policy(doc)

    # Assert
    assert any("endpoints[0] needs 'host' and 'port'" in e for e in errors)


def test_reports_missing_file(tmp_path: Path) -> None:
    # Arrange
    missing = tmp_path / "agents.yaml"

    # Act
    errors = validate_file(missing)

    # Assert
    assert any("not found" in e for e in errors)


def test_reports_invalid_yaml(tmp_path: Path) -> None:
    # Arrange
    broken = tmp_path / "agents.yaml"
    broken.write_text("agents: [\n  - id: unclosed\n")

    # Act
    errors = validate_file(broken)

    # Assert
    assert any("invalid YAML" in e for e in errors)


def test_main_defaults_to_cwd_agents_and_policy_yaml(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # Arrange
    monkeypatch.chdir(tmp_path)
    (tmp_path / "agents.yaml").write_text("agents: []\n")
    (tmp_path / "policy.yaml").write_text("version: 1\n")

    # Act
    exit_code = main([])

    # Assert
    assert exit_code == 0


def test_main_with_no_args_and_no_default_files_prints_usage(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    # Arrange
    monkeypatch.chdir(tmp_path)

    # Act
    exit_code = main([])

    # Assert
    assert exit_code == 2
    assert "usage: agentkit-validate" in capsys.readouterr().err


def test_health_endpoint_reports_the_agent_and_its_inference_route() -> None:
    # Arrange
    from fastapi.testclient import TestClient

    client = TestClient(create_app("hello-agent"))

    # Act
    body = client.get("/healthz").json()

    # Assert
    assert body["status"] == "ok"
    assert body["agent"] == "hello-agent"
    assert body["inference"].startswith("http")
