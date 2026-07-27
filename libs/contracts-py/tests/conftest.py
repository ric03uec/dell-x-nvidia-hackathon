"""Shared paths for locating the frozen contracts/ directory from this package.

contracts-py is a workspace member, but the schemas and examples it must stay
faithful to live at the repo root in contracts/, not inside this package. Tests
here read that directory directly so drift between the two is caught, not
copied around.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

PACKAGE_ROOT = Path(__file__).resolve().parent.parent
REPO_ROOT = PACKAGE_ROOT.parent.parent
CONTRACTS_DIR = REPO_ROOT / "contracts"
EXAMPLES_DIR = CONTRACTS_DIR / "examples"


@pytest.fixture(scope="session")
def contracts_dir() -> Path:
    assert CONTRACTS_DIR.is_dir(), f"expected {CONTRACTS_DIR} to exist"
    return CONTRACTS_DIR


@pytest.fixture(scope="session")
def examples_dir() -> Path:
    assert EXAMPLES_DIR.is_dir(), f"expected {EXAMPLES_DIR} to exist"
    return EXAMPLES_DIR


def load_json(path: Path) -> dict:
    return json.loads(path.read_text())
