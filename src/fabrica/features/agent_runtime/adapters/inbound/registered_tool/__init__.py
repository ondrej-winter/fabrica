"""Model-facing registered tools owned by the agent-runtime slice."""

from fabrica.features.agent_runtime.adapters.inbound.registered_tool.skills import (
    SKILLS_TOOL_NAME,
    SkillActivationToolContext,
    SkillsRegisteredToolAdapter,
    create_skills_registered_tool,
)
from fabrica.features.agent_runtime.adapters.inbound.registered_tool.submit_and_exit import (
    SubmitAndExitRegisteredToolAdapter,
    create_submit_and_exit_registered_tool,
)

__all__ = [
    "SKILLS_TOOL_NAME",
    "SkillActivationToolContext",
    "SkillsRegisteredToolAdapter",
    "SubmitAndExitRegisteredToolAdapter",
    "create_skills_registered_tool",
    "create_submit_and_exit_registered_tool",
]
