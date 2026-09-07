"""Tests for the root Fabrica module entrypoint."""

import runpy

import pytest

from fabrica.bootstrap import cli as bootstrap_cli

EXPECTED_EXIT_CODE = 7


def test_root_module_exits_with_bootstrap_cli_result(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(bootstrap_cli, "main", lambda: EXPECTED_EXIT_CODE)

    with pytest.raises(SystemExit) as error_info:
        runpy.run_module("fabrica.__main__", run_name="__main__")

    assert error_info.value.code == EXPECTED_EXIT_CODE
