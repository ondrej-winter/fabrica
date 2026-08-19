"""Bootstrap-owned product CLI command registrar assembly."""

from __future__ import annotations

from typing import TYPE_CHECKING

from fabrica.bootstrap.cli.contracts import CliDependencyOverrides
from fabrica.bootstrap.cli.features.agent_runtime import (
    run_agent_runtime_command,
    run_script_execute_command,
    run_script_policy_command,
)
from fabrica.bootstrap.cli.features.developer_workflow import run_commit_message_command, run_confirmed_commit_command
from fabrica.features.agent_runtime.adapters.inbound.cli.registration import register_agent_runtime_cli_commands
from fabrica.features.developer_workflow.adapters.inbound.cli.registration import (
    register_developer_workflow_cli_commands,
)

if TYPE_CHECKING:
    from fabrica.adapters.inbound.cli import CommandRegistrar


def create_cli_command_registrars(
    *,
    overrides: CliDependencyOverrides | None = None,
) -> tuple[CommandRegistrar, ...]:
    """Create feature-owned command registrars with bootstrap-owned handlers."""
    dependency_overrides = overrides or CliDependencyOverrides()
    return (
        lambda subparsers: register_agent_runtime_cli_commands(
            subparsers,
            run_command=run_agent_runtime_command(
                dependency_overrides.runtime,
                selected_context_runtime=dependency_overrides.selected_context_runtime,
            ),
            script_policy_command=run_script_policy_command(dependency_overrides.script_policy_evaluator),
            script_execute_command=run_script_execute_command(dependency_overrides.script_executor),
        ),
        lambda subparsers: register_developer_workflow_cli_commands(
            subparsers,
            commit_message_command=run_commit_message_command(dependency_overrides.commit_message_workflow),
            commit_command=run_confirmed_commit_command(dependency_overrides.confirmed_commit_workflow),
        ),
    )
