"""Explicit in-process registered-tool adapter for offline tool-loop proofs."""

from fabrica.features.agent_runtime.adapters.outbound.registered_tool.adapter import (
    RegisteredSkillToolPreparer,
    RegisteredToolExecutor,
    SkillAssociatedRegisteredTool,
)
from fabrica.features.agent_runtime.application.ports import RegisteredTool, RegisteredToolHandler

__all__ = [
    "RegisteredSkillToolPreparer",
    "RegisteredTool",
    "RegisteredToolExecutor",
    "RegisteredToolHandler",
    "SkillAssociatedRegisteredTool",
]
