"""Bootstrap-owned composition for the Fabrica product CLI."""

from __future__ import annotations

import sys
from typing import TYPE_CHECKING, Protocol, TextIO

from fabrica.adapters.inbound.cli.contributions import CliError
from fabrica.adapters.inbound.cli.output import write_line, write_model_evidence_report
from fabrica.adapters.inbound.cli.parser import parse_args
from fabrica.adapters.inbound.cli.runner import CliCommandExecutionOptions, run_cli_command
from fabrica.bootstrap.cli_contributions import (
    create_agent_runtime_cli_contribution,
    create_developer_workflow_cli_contribution,
)

if TYPE_CHECKING:
    from collections.abc import Sequence

    from fabrica.adapters.inbound.cli.contributions import CliContribution
    from fabrica.features.agent_runtime.adapters.inbound.cli.contracts import AgentRuntimeCliDependencies
    from fabrica.features.developer_workflow.adapters.inbound.cli.contracts import DeveloperWorkflowCliDependencies
    from fabrica.shared_kernel.model_usage import ModelCostEvidence, ModelUsageEvidence

CLI_CONFIGURATION_ERROR_EXIT_CODE = 2


class ModelEvidenceResult(Protocol):
    """Result shape that can expose model evidence to the product CLI."""

    @property
    def usage_evidence(self) -> tuple[ModelUsageEvidence, ...]:
        """Return usage evidence emitted by the command."""

    @property
    def cost_evidence(self) -> tuple[ModelCostEvidence, ...]:
        """Return cost evidence emitted by the command."""


def main(argv: Sequence[str] | None = None) -> int:
    """Run the Fabrica CLI through bootstrap-owned default composition."""
    try:
        contributions = create_cli_contributions()
        invocation = parse_args(tuple(argv) if argv is not None else None, contributions=contributions)
        return run_cli_command(invocation, options=CliCommandExecutionOptions(contributions=contributions))
    except CliError as err:
        write_line(sys.stderr, f"error: {err}")
        return CLI_CONFIGURATION_ERROR_EXIT_CODE


def create_cli_contributions(
    *,
    agent_runtime_dependencies: AgentRuntimeCliDependencies | None = None,
    developer_workflow_dependencies: DeveloperWorkflowCliDependencies | None = None,
) -> tuple[CliContribution, ...]:
    """Create product CLI contributions with bootstrap-owned dependency providers."""
    return (
        create_agent_runtime_cli_contribution(
            dependencies=agent_runtime_dependencies,
            evidence_writer=_write_requested_agent_runtime_model_evidence,
        ),
        create_developer_workflow_cli_contribution(
            dependencies=developer_workflow_dependencies,
            evidence_writer=_write_requested_developer_workflow_model_evidence,
        ),
    )


def _write_requested_agent_runtime_model_evidence(
    result: ModelEvidenceResult,
    *,
    include_usage: bool,
    include_prices: bool,
    stdout: TextIO,
) -> None:
    _write_requested_model_evidence(
        result,
        print_usage=include_usage,
        print_prices=include_prices,
        stdout=stdout,
    )


def _write_requested_developer_workflow_model_evidence(
    result: ModelEvidenceResult,
    *,
    include_usage: bool,
    include_prices: bool,
    stdout: TextIO,
) -> None:
    _write_requested_model_evidence(
        result,
        print_usage=include_usage,
        print_prices=include_prices,
        stdout=stdout,
    )


def _write_requested_model_evidence(
    result: ModelEvidenceResult,
    *,
    print_usage: bool,
    print_prices: bool,
    stdout: TextIO,
) -> None:
    write_model_evidence_report(
        usage_evidence=result.usage_evidence,
        cost_evidence=result.cost_evidence,
        stdout=stdout,
        include_usage=print_usage,
        include_prices=print_prices,
    )
