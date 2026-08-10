"""Compatibility exports for product CLI contribution composition."""

from fabrica.adapters.inbound.cli.agent_runtime_composition import run_agent_runtime_contribution_command
from fabrica.adapters.inbound.cli.developer_workflow_composition import run_developer_workflow_contribution_command

__all__ = [
    "run_agent_runtime_contribution_command",
    "run_developer_workflow_contribution_command",
]
