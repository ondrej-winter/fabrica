"""Unit tests for bootstrap CLI entrypoint error handling."""

from typing import NoReturn

import fabrica.bootstrap.cli.entrypoint as cli_entrypoint
from fabrica.adapters.inbound.cli import RegistrationError
from fabrica.bootstrap import cli as bootstrap_cli

EXPECTED_CLI_CONFIGURATION_ERROR_EXIT_CODE = 2


def test_translates_bootstrap_wiring_errors_to_stable_stderr(monkeypatch, capsys) -> None:
    """Keep expected composition failures from leaking tracebacks by default."""

    def fail_command_registration_creation(*, overrides: object | None = None) -> NoReturn:
        _ = overrides
        msg = "synthetic CLI wiring failure"
        raise RegistrationError(msg)

    monkeypatch.setattr(cli_entrypoint, "create_cli_command_registrars", fail_command_registration_creation)

    exit_code = bootstrap_cli.main(())

    assert exit_code == EXPECTED_CLI_CONFIGURATION_ERROR_EXIT_CODE
    captured = capsys.readouterr()
    assert captured.out == ""
    assert captured.err == "error: synthetic CLI wiring failure\n"
