"""Composition helpers for tool-loop and model-driven skill runtimes."""

from dataclasses import dataclass, field

from fabrica.bootstrap.composition.skill_context import (
    SkillContextAugmentationOptions,
    create_skill_context_augmented_local_agent_command,
)
from fabrica.features.agent_runtime.adapters.outbound.pydantic_ai_model import (
    PydanticAIToolAwareAgentModel,
    PydanticAIToolAwareTurn,
)
from fabrica.features.agent_runtime.adapters.outbound.registered_tool import (
    RegisteredSkillToolPreparer,
    RegisteredTool,
    RegisteredToolExecutor,
    SkillAssociatedRegisteredTool,
)
from fabrica.features.agent_runtime.application.dtos import (
    LocalAgentRunCommand,
    SkillToolExposureStatus,
    SkillToolPreparationCommand,
    SkillToolPreparationResult,
    ToolDefinition,
    ToolLoopLimits,
    ToolLoopRunResult,
)
from fabrica.features.agent_runtime.application.ports import ToolAwareAgentModel
from fabrica.features.agent_runtime.application.use_cases import PrepareSkillTools, RunToolLoop


@dataclass(frozen=True, slots=True)
class ModelDrivenSkillRuntimeOptions:
    """Composition options for model-driven selected skill context and tools.

    Only explicitly supplied ``skill_tools`` can be exposed to the model, and
    only for selected skills. Skill markdown/resources are loaded when the
    runtime is run; tool declarations are prepared during construction without
    invoking tool handlers.
    """

    skill_context_options: SkillContextAugmentationOptions = field(default_factory=SkillContextAugmentationOptions)
    skill_tools: tuple[SkillAssociatedRegisteredTool, ...] = field(default_factory=tuple)
    limits: ToolLoopLimits | None = None
    max_selected_tools: int | None = None


@dataclass(frozen=True, slots=True)
class ToolLoopRuntime:
    """Offline tool-loop runtime composed from explicit in-process tools."""

    runner: RunToolLoop
    available_tools: tuple[ToolDefinition, ...]
    limits: ToolLoopLimits | None = None

    def run(self, command: LocalAgentRunCommand) -> ToolLoopRunResult:
        """Run the composed tool loop with registered tool definitions."""
        return self.runner.run(command, available_tools=self.available_tools, limits=self.limits)


@dataclass(frozen=True, slots=True)
class ModelDrivenSkillRuntime:
    """Runtime that combines selected skill context with explicit safe tools."""

    runner: RunToolLoop
    context_options: SkillContextAugmentationOptions
    tool_preparation: SkillToolPreparationResult
    registered_tools: tuple[RegisteredTool, ...]
    limits: ToolLoopLimits | None = None

    @property
    def available_tools(self) -> tuple[ToolDefinition, ...]:
        """Return model-callable tools exposed for selected skills."""
        return self.tool_preparation.tool_definitions

    def run(self, command: LocalAgentRunCommand) -> ToolLoopRunResult:
        """Load selected context and run the bounded model-tool loop."""
        augmented = create_skill_context_augmented_local_agent_command(command, self.context_options)
        result = self.runner.run(augmented, available_tools=self.available_tools, limits=self.limits)
        if not self.tool_preparation.observations:
            return result
        return ToolLoopRunResult(
            status=result.status,
            output_text=result.output_text,
            tool_results=result.tool_results,
            observations=(*self.tool_preparation.observations, *result.observations),
        )


def create_tool_loop_runtime(
    *,
    model: ToolAwareAgentModel,
    tools: tuple[RegisteredTool, ...] = (),
    limits: ToolLoopLimits | None = None,
) -> ToolLoopRuntime:
    """Create an offline tool-loop runtime from explicit in-process tools.

    The helper wires only injected dependencies. Construction does not read Codex
    credentials, call backends, read skill roots, execute scripts, prompt for
    approval, dynamically import callables, or perform network I/O.
    """
    executor = RegisteredToolExecutor(tools)
    return ToolLoopRuntime(
        runner=RunToolLoop(model=model, tool_executor=executor),
        available_tools=executor.tool_definitions,
        limits=limits,
    )


def create_pydantic_ai_tool_loop_runtime(
    *,
    turn_runner: PydanticAIToolAwareTurn,
    tools: tuple[RegisteredTool, ...] = (),
    limits: ToolLoopLimits | None = None,
) -> ToolLoopRuntime:
    """Create an offline PydanticAI-shaped runtime with explicit registered tools.

    The helper only composes injected dependencies. Construction does not read
    Codex credentials, call backends, read skill roots, execute scripts, prompt
    for approval, dynamically import callables, or perform network I/O.
    """
    return create_tool_loop_runtime(
        model=PydanticAIToolAwareAgentModel(turn_runner=turn_runner),
        tools=tools,
        limits=limits,
    )


def create_model_driven_skill_runtime(
    *,
    model: ToolAwareAgentModel,
    options: ModelDrivenSkillRuntimeOptions | None = None,
) -> ModelDrivenSkillRuntime:
    """Create a runtime for selected skill context plus explicit skill tools.

    The helper prepares only composition-supplied tool associations during
    construction. It does not read skill roots, call models or backends, execute
    tools or scripts, prompt for approval, dynamically import callables, or read
    Codex credentials. Selected skill files and resources are loaded only when
    the returned runtime is run.
    """
    runtime_options = options or ModelDrivenSkillRuntimeOptions()
    context_options = runtime_options.skill_context_options
    max_selected_tools = (
        len(runtime_options.skill_tools) or 1
        if runtime_options.max_selected_tools is None
        else runtime_options.max_selected_tools
    )
    preparer = PrepareSkillTools(preparer=RegisteredSkillToolPreparer(runtime_options.skill_tools))
    preparation = preparer.prepare(
        SkillToolPreparationCommand(
            selected_skills=context_options.skill_selections,
            max_selected_tools=max_selected_tools,
        ),
    )
    registered_tools = tuple(
        skill_tool.registered_tool
        for skill_tool in runtime_options.skill_tools
        if _is_exposed_skill_tool(skill_tool, preparation)
    )
    executor = RegisteredToolExecutor(registered_tools)
    return ModelDrivenSkillRuntime(
        runner=RunToolLoop(model=model, tool_executor=executor),
        context_options=context_options,
        tool_preparation=preparation,
        registered_tools=registered_tools,
        limits=runtime_options.limits,
    )


def _is_exposed_skill_tool(
    skill_tool: SkillAssociatedRegisteredTool,
    preparation: SkillToolPreparationResult,
) -> bool:
    return any(
        declaration.status is SkillToolExposureStatus.REGISTERED
        and declaration.skill_id == skill_tool.skill_id
        and declaration.tool == skill_tool.registered_tool.definition
        for declaration in preparation.declarations
    )


def create_pydantic_ai_model_driven_skill_runtime(
    *,
    turn_runner: PydanticAIToolAwareTurn,
    options: ModelDrivenSkillRuntimeOptions | None = None,
) -> ModelDrivenSkillRuntime:
    """Create a PydanticAI-shaped runtime for selected skill context and tools."""
    return create_model_driven_skill_runtime(
        model=PydanticAIToolAwareAgentModel(turn_runner=turn_runner),
        options=options,
    )
