"""Model-free CLI adapter for the reporting-only mature-agent corpus."""

import argparse
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

from fabrica.adapters.inbound.cli.command import Command, CommandContext, CommandRegistry

AGENT_EVALUATE_COMMAND_NAME = "agent-evaluate"
DEFAULT_EVALUATION_REPORT_PATH = Path(".reports/mature-agent-evaluation/report.json")


@dataclass(frozen=True, slots=True)
class CliEvaluationCommand:
    """Output location selected for one deterministic evaluation report."""

    destination: Path


type AgentEvaluationCliHandler = Callable[[CliEvaluationCommand, CommandContext], int]


def register_agent_evaluation_cli_commands(
    commands: CommandRegistry, *, evaluate_command: AgentEvaluationCliHandler
) -> None:
    """Register the reporting-only offline corpus command."""
    commands.register(
        Command(
            name=AGENT_EVALUATE_COMMAND_NAME,
            summary="run the deterministic reporting-only mature-agent corpus",
            configure=_configure_parser,
            decode=_decode,
            run=evaluate_command,
            description=(
                "Runs fixed normalized session-evidence fixtures offline without credentials, provider access, "
                "or workspace-agent execution. This report is not a release gate."
            ),
        )
    )


def _configure_parser(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--report-path",
        default=DEFAULT_EVALUATION_REPORT_PATH,
        type=Path,
        help="Deterministic JSON report path (default: .reports/mature-agent-evaluation/report.json).",
    )


def _decode(namespace: argparse.Namespace) -> CliEvaluationCommand:
    return CliEvaluationCommand(destination=namespace.report_path)


__all__ = [
    "AGENT_EVALUATE_COMMAND_NAME",
    "DEFAULT_EVALUATION_REPORT_PATH",
    "AgentEvaluationCliHandler",
    "CliEvaluationCommand",
    "register_agent_evaluation_cli_commands",
]
