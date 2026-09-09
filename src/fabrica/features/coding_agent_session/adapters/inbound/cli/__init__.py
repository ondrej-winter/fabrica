"""Coding-agent-session CLI command adapters."""

from fabrica.features.coding_agent_session.adapters.inbound.cli.command_models import (
    CliCodingAgentSessionCommand,
    CliSelectedResource,
    CodingAgentSessionCliCompositionOptions,
)
from fabrica.features.coding_agent_session.adapters.inbound.cli.contracts import CodingAgentSessionCliStreams
from fabrica.features.coding_agent_session.adapters.inbound.cli.registration import (
    CODING_AGENT_SESSION_CLI_COMMAND_NAMES,
    CodingAgentSessionCliHandler,
    register_coding_agent_session_cli_commands,
)
from fabrica.features.coding_agent_session.adapters.inbound.cli.runner import run_coding_agent_session_cli_command

__all__ = [
    "CODING_AGENT_SESSION_CLI_COMMAND_NAMES",
    "CliCodingAgentSessionCommand",
    "CliSelectedResource",
    "CodingAgentSessionCliCompositionOptions",
    "CodingAgentSessionCliHandler",
    "CodingAgentSessionCliStreams",
    "register_coding_agent_session_cli_commands",
    "run_coding_agent_session_cli_command",
]
