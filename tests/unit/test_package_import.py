"""Package import smoke tests."""

import fabrica


def test_fabrica_package_imports() -> None:
    assert fabrica.__all__ == []
