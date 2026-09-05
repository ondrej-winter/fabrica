"""Application use cases for local agent runtime orchestration."""

from fabrica.features.agent_runtime.application.use_cases.activate_skill import ActivateSkill
from fabrica.features.agent_runtime.application.use_cases.create_skill_registry_snapshot import (
    CreateSkillRegistrySnapshot,
)
from fabrica.features.agent_runtime.application.use_cases.evaluate_skill_script_policy import (
    EvaluateSkillScriptPolicy,
)
from fabrica.features.agent_runtime.application.use_cases.evaluate_skill_trust import EvaluateSkillTrust
from fabrica.features.agent_runtime.application.use_cases.execute_skill_script import ExecuteSkillScript
from fabrica.features.agent_runtime.application.use_cases.load_skill_context import LoadSkillContext
from fabrica.features.agent_runtime.application.use_cases.load_skill_resource_context import (
    LoadSkillResourceContext,
)
from fabrica.features.agent_runtime.application.use_cases.prepare_skill_tools import PrepareSkillTools
from fabrica.features.agent_runtime.application.use_cases.rehydrate_active_skill_context import (
    ActiveSkillContextRehydrationResult,
    ActiveSkillContextRehydrationStatus,
    RehydrateActiveSkillContext,
)
from fabrica.features.agent_runtime.application.use_cases.run_local_agent import RunLocalAgent
from fabrica.features.agent_runtime.application.use_cases.run_local_agent_with_selected_context import (
    RunLocalAgentWithSelectedContext,
)
from fabrica.features.agent_runtime.application.use_cases.run_tool_loop import RunToolLoop
from fabrica.features.agent_runtime.application.use_cases.submit_run_completion import (
    InMemoryRunStateMachine,
    SubmitRunCompletion,
    SubmitRunCompletionError,
)

__all__ = [
    "ActivateSkill",
    "ActiveSkillContextRehydrationResult",
    "ActiveSkillContextRehydrationStatus",
    "CreateSkillRegistrySnapshot",
    "EvaluateSkillScriptPolicy",
    "EvaluateSkillTrust",
    "ExecuteSkillScript",
    "InMemoryRunStateMachine",
    "LoadSkillContext",
    "LoadSkillResourceContext",
    "PrepareSkillTools",
    "RehydrateActiveSkillContext",
    "RunLocalAgent",
    "RunLocalAgentWithSelectedContext",
    "RunToolLoop",
    "SubmitRunCompletion",
    "SubmitRunCompletionError",
]
