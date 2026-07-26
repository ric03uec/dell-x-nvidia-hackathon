"""Validate a NemoClaw `agents.yaml` and an OpenShell `policy.yaml` locally.

The point is to fail on a laptop instead of after an rsync to the Spark. This
checks shape, not semantics — NemoClaw and OpenShell remain the authority on
what a valid manifest or policy means.
"""

from __future__ import annotations

import sys
from collections.abc import Sequence
from pathlib import Path
from typing import Any

import yaml

TOOL_VERBS = frozenset({"read", "write", "exec"})


def _tool_errors(label: str, node: Any) -> tuple[str, ...]:
    """Check a `tools:` block's allow/deny verbs against what NemoClaw accepts."""
    if not isinstance(node, dict):
        return ()
    tools = node.get("tools")
    if tools is None:
        return ()
    if not isinstance(tools, dict):
        return (f"agents.yaml: {label}.tools must be a mapping",)

    errors: list[str] = []
    for key in ("allow", "deny"):
        verbs = tools.get(key)
        if verbs is None:
            continue
        if not isinstance(verbs, list):
            errors.append(f"agents.yaml: {label}.tools.{key} must be a list")
            continue
        unknown = sorted({v for v in verbs if v not in TOOL_VERBS})
        if unknown:
            errors.append(
                f"agents.yaml: {label}.tools.{key} has unknown verbs {unknown}; "
                f"expected any of {sorted(TOOL_VERBS)}"
            )
    return tuple(errors)


def validate_agents(doc: Any) -> tuple[str, ...]:
    """Check a parsed NemoClaw multi-agent manifest. Returns readable errors."""
    if not isinstance(doc, dict):
        return ("agents.yaml: top level must be a mapping",)

    errors: list[str] = []
    main = doc.get("main")
    if main is not None and not isinstance(main, dict):
        errors.append("agents.yaml: 'main' must be a mapping")
    errors.extend(_tool_errors("main", main))

    agents = doc.get("agents")
    if agents is None:
        return tuple(errors)
    if not isinstance(agents, list):
        return (*errors, "agents.yaml: 'agents' must be a list")

    seen: set[str] = set()
    for index, agent in enumerate(agents):
        label = f"agents[{index}]"
        if not isinstance(agent, dict):
            errors.append(f"agents.yaml: {label} must be a mapping")
            continue
        agent_id = agent.get("id")
        if not isinstance(agent_id, str) or not agent_id.strip():
            errors.append(f"agents.yaml: {label} needs a non-empty 'id'")
        elif agent_id in seen:
            errors.append(f"agents.yaml: duplicate agent id {agent_id!r}")
        else:
            seen.add(agent_id)
        errors.extend(_tool_errors(label, agent))
    return tuple(errors)


def _endpoint_errors(rule_name: str, rule: Any) -> tuple[str, ...]:
    """Check one `network_policies` rule has usable endpoints."""
    if not isinstance(rule, dict):
        return (f"policy.yaml: network_policies.{rule_name} must be a mapping",)
    endpoints = rule.get("endpoints")
    if not isinstance(endpoints, list) or not endpoints:
        return (f"policy.yaml: network_policies.{rule_name} needs a non-empty 'endpoints' list",)
    return tuple(
        f"policy.yaml: network_policies.{rule_name}.endpoints[{i}] needs 'host' and 'port'"
        for i, endpoint in enumerate(endpoints)
        if not isinstance(endpoint, dict) or "host" not in endpoint or "port" not in endpoint
    )


def validate_policy(doc: Any) -> tuple[str, ...]:
    """Check a parsed OpenShell sandbox policy. Returns readable errors."""
    if not isinstance(doc, dict):
        return ("policy.yaml: top level must be a mapping",)

    errors: list[str] = []
    if "version" not in doc:
        errors.append("policy.yaml: missing 'version'")

    filesystem = doc.get("filesystem_policy")
    if filesystem is not None and not isinstance(filesystem, dict):
        errors.append("policy.yaml: 'filesystem_policy' must be a mapping")
    elif isinstance(filesystem, dict):
        errors.extend(
            f"policy.yaml: filesystem_policy.{key} must be a list of paths"
            for key in ("read_only", "read_write")
            if key in filesystem and not isinstance(filesystem[key], list)
        )
        # ponytail: only the shape we can confirm from this repo's own
        # template (a bool, e.g. `include_workdir: false`). What `true`
        # actually does is OpenShell's semantics, not this repo's — see
        # libs/skills/openshell-data-boundary for the landlock/process blind
        # spot this does NOT attempt to cover.
        include_workdir = filesystem.get("include_workdir")
        if include_workdir is not None and not isinstance(include_workdir, bool):
            errors.append("policy.yaml: filesystem_policy.include_workdir must be a bool")

    networks = doc.get("network_policies")
    if networks is not None and not isinstance(networks, dict):
        errors.append("policy.yaml: 'network_policies' must map a rule name to a rule")
    elif isinstance(networks, dict):
        for rule_name, rule in networks.items():
            errors.extend(_endpoint_errors(str(rule_name), rule))

    return tuple(errors)


def validate_file(path: Path) -> tuple[str, ...]:
    """Load a YAML file and validate it as a policy or a manifest, by filename."""
    if not path.is_file():
        return (f"{path}: not found",)
    try:
        doc = yaml.safe_load(path.read_text())
    except yaml.YAMLError as exc:
        return (f"{path}: invalid YAML — {exc}",)
    # ponytail: filename dispatch. Both formats are mappings with no shared
    # discriminator field, and every project names these two files the same way.
    validate = validate_policy if "polic" in path.name else validate_agents
    return validate(doc)


DEFAULT_FILES = ("agents.yaml", "policy.yaml")


def main(argv: Sequence[str] | None = None) -> int:
    args = list(sys.argv[1:] if argv is None else argv)
    if not args:
        # No paths given: default to this project's own agents.yaml/policy.yaml,
        # so `agentkit-validate` works unqualified from any agent's own directory.
        args = [f for f in DEFAULT_FILES if Path(f).is_file()]
        if not args:
            print(
                "usage: agentkit-validate [<agents.yaml> [policy.yaml ...]]\n"
                f"(no arguments given, and neither {' nor '.join(DEFAULT_FILES)} "
                "was found in the current directory)",
                file=sys.stderr,
            )
            return 2

    errors = tuple(error for arg in args for error in validate_file(Path(arg)))
    for error in errors:
        print(error, file=sys.stderr)
    if errors:
        print(f"\n{len(errors)} problem(s) found.", file=sys.stderr)
        return 1
    print(f"ok: {', '.join(args)}")
    return 0


def cli() -> None:
    raise SystemExit(main())
