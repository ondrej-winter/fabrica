"""Public bootstrap facade for the Fabrica product CLI."""

from fabrica.bootstrap.cli.contracts import CliDependencyOverrides
from fabrica.bootstrap.cli.entrypoint import CLI_CONFIGURATION_ERROR_EXIT_CODE, main, run_cli
from fabrica.bootstrap.cli.registration import create_cli_command_registrars

__all__ = [
    "CLI_CONFIGURATION_ERROR_EXIT_CODE",
    "CliDependencyOverrides",
    "create_cli_command_registrars",
    "main",
    "run_cli",
]
