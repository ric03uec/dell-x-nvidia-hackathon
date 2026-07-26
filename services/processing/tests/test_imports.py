"""Scaffold-only checks: every subpackage in the section-6 layout exists and
imports cleanly (dxnvh-332.7)."""

import importlib


def test_live_offline_and_security_agent_subpackages_import_cleanly() -> None:
    # Arrange
    module_names = [
        "processing",
        "processing.live",
        "processing.offline",
        "processing.security_agent",
    ]

    # Act
    modules = [importlib.import_module(name) for name in module_names]

    # Assert
    assert all(module.__doc__ for module in modules)
