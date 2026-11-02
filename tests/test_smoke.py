"""Smoke test: the package can be imported."""

import econ_corpus


def test_package_imports() -> None:
    assert econ_corpus is not None
