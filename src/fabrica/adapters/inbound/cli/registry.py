"""Product CLI contribution registry."""

from __future__ import annotations

from fabrica.adapters.inbound.cli.composition import (
    run_agent_runtime_contribution_command,
    run_developer_workflow_contribution_command,
)
from fabrica.adapters.inbound.cli.contributions import CliContribution
from fabrica.features.agent_runtime.adapters.inbound.cli.contribution import (
    AGENT_RUNTIME_CLI_COMMAND_TYPES,
    register_agent_runtime_cli_commands,
)
from fabrica.features.developer_workflow.adapters.inbound.cli.contribution import (
    DEVELOPER_WORKFLOW_CLI_COMMAND_TYPES,
    register_developer_workflow_cli_commands,
)


def default_cli_contributions() -> tuple[CliContribution, ...]:
    """Return product CLI contributions in parser/dispatch order."""
    return (
        CliContribution(
            name="agent_runtime",
            command_types=AGENT_RUNTIME_CLI_COMMAND_TYPES,
            register_commands=register_agent_runtime_cli_commands,
            run_command=run_agent_runtime_contribution_command,
        ),
        CliContribution(
            name="developer_workflow",
            command_types=DEVELOPER_WORKFLOW_CLI_COMMAND_TYPES,
            register_commands=register_developer_workflow_cli_commands,
            run_command=run_developer_workflow_contribution_command,
        ),
    )
