"""Terminal host adapters for coding-agent session questions and approvals."""

from fabrica.features.coding_agent_session.adapters.inbound.terminal.command_approval import (
    TerminalCommandApprovalResolver,
)
from fabrica.features.coding_agent_session.adapters.inbound.terminal.patch_approval import TerminalPatchApproval
from fabrica.features.coding_agent_session.adapters.inbound.terminal.question_transport import TerminalQuestionTransport

__all__ = ["TerminalCommandApprovalResolver", "TerminalPatchApproval", "TerminalQuestionTransport"]
