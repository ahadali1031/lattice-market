"""Smoke test: confirms the package is importable and wired up correctly."""

import lattice


def test_package_imports_with_version() -> None:
    assert lattice.__version__ == "0.1.0"
