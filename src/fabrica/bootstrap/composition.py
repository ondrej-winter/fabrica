"""Composition root for Fabrica workflow and runtime wiring.

This module is the consumer-facing bootstrap boundary for Fabrica workflows and
runtime experiments. Factory functions here construct application use cases and wire
concrete adapters, but construction must stay side-effect light: factories do
not read Codex credentials, inspect skill roots, call model backends, execute
tools or scripts, or prompt for approval unless a factory docstring explicitly
says otherwise.

Potentially risky capabilities are opt-in composition decisions. Registered
tools are available only when supplied to a tool-loop factory, staged-git tools
are exposed only through the staged-git helper, and selected skill scripts are
denied by default unless an approval lookup returns an exact approved metadata
binding. Runtime I/O and caller-visible failures are reported through the
application result DTOs returned by the composed use case.
"""

import asyncio
from dataclasses import dataclass, field
from pathlib import Path
from typing import Protocol

import httpx

from fabrica.features.agent_runtime.adapters.outbound.codex_transport_model import CodexTransportAgentModel
from fabrica.features.agent_runtime.adapters.outbound.pydantic_ai_model import (
    CodexTransportPydanticAICompletion,
    PydanticAIAgentModel,
    PydanticAICompletion,
    PydanticAIToolAwareAgentModel,
    PydanticAIToolAwareTurn,
)
from fabrica.features.agent_runtime.adapters.outbound.registered_tool import (
    RegisteredSkillToolPreparer,
    RegisteredTool,
    RegisteredToolExecutor,
    SkillAssociatedRegisteredTool,
)
from fabrica.features.agent_runtime.adapters.outbound.skill_markdown_file import (
    SkillMarkdownFileContextLoader,
    SkillResourceFileContextLoader,
)
from fabrica.features.agent_runtime.adapters.outbound.skill_script_file import SkillScriptFileMetadataLoader
from fabrica.features.agent_runtime.adapters.outbound.skill_script_subprocess import SkillScriptSubprocessExecutor
from fabrica.features.agent_runtime.application.dtos import (
    LocalAgentRunCommand,
    LocalAgentRunResult,
    LocalAgentRunStatus,
    ModelCostEvidence,
    ModelUsageEvidence,
    RuntimeObservation,
    SelectedSkill,
    SelectedSkillResource,
    SkillContextBounds,
    SkillResourceContextBounds,
    SkillScriptApprovalBinding,
    SkillScriptApprovalDecision,
    SkillScriptApprovalStatus,
    SkillScriptSandboxPolicy,
    SkillToolExposureStatus,
    SkillToolPreparationCommand,
    SkillToolPreparationResult,
    ToolDefinition,
    ToolLoopLimits,
    ToolLoopRunResult,
)
from fabrica.features.agent_runtime.application.ports import (
    SkillContextLoadError,
    SkillScriptApprovalLookup,
    ToolAwareAgentModel,
)
from fabrica.features.agent_runtime.application.use_cases import (
    EvaluateSkillScriptPolicy,
    ExecuteSkillScript,
    LoadSkillContext,
    LoadSkillResourceContext,
    PrepareSkillTools,
    RunLocalAgent,
    RunToolLoop,
)
from fabrica.features.codex_transport.adapters.outbound.codex_auth_file import CodexAuthFileCredentialStore
from fabrica.features.codex_transport.adapters.outbound.codex_backend_http import (
    CodexBackendHttpAdapter,
    CodexBackendRequestSettings,
    CodexUsageRequestSettings,
)
from fabrica.features.codex_transport.application.use_cases import CompleteWithCodexTransport
from fabrica.features.developer_workflow.adapters.outbound.commit_message_agent_runtime import (
    AgentRuntimeCommitMessageSynthesizer,
    AgentRuntimeStagedFileCommitMessageAnalyzer,
)
from fabrica.features.developer_workflow.adapters.outbound.git_context_registered_tool import (
    create_git_context_registered_tools as create_git_context_registered_tool_adapters,
)
from fabrica.features.developer_workflow.adapters.outbound.git_staged_changes_registered_tool import (
    create_git_staged_changes_registered_tools,
)
from fabrica.features.developer_workflow.adapters.outbound.git_subprocess import (
    GitCommitSubprocessCreator,
    GitContextSubprocessLoader,
    GitStagedChangesSubprocessLoader,
)
from fabrica.features.developer_workflow.application.dtos import (
    CommitMessageRecommendation,
    CreateGitCommitCommand,
    GenerateCommitMessageResult,
    GitCommitResult,
    GitContextDiffBounds,
    GitStagedDiffBounds,
    SynthesizeCommitMessageCommand,
)
from fabrica.features.developer_workflow.application.ports import (
    AsyncCommitMessageSynthesizer,
    CommitMessageAnalysisError,
    CommitMessageSynthesisError,
    GitCommitError,
    GitStagedChangesLoadError,
)
from fabrica.features.developer_workflow.application.use_cases import (
    DEFAULT_COMMIT_MESSAGE_SKILL_ID,
    CreateGitCommit,
    GenerateCommitMessage,
    GenerateCommitMessageError,
    GenerateCommitMessageOptions,
)

DEFAULT_CODEX_AUTH_FILE = Path.home() / ".codex" / "auth.json"
DEFAULT_COMMIT_MESSAGE_CODEX_MODEL = "gpt-5.3-codex-spark"
DEFAULT_COMMIT_MESSAGE_CODEX_REASONING_EFFORT = "low"


@dataclass(frozen=True, slots=True)
class SkillContextAugmentationOptions:
    """Composition options for selected skill markdown and resource context.

    Selected files are loaded lazily when a command is augmented or when a
    composed model-driven runtime is run. ``verbose_diagnostics`` may include
    additional non-secret troubleshooting metadata in result observations.
    """

    skill_selections: tuple[SelectedSkill, ...] = field(default_factory=tuple)
    resource_selections: tuple[SelectedSkillResource, ...] = field(default_factory=tuple)
    skill_roots: tuple[Path, ...] | None = None
    skill_bounds: SkillContextBounds | None = None
    resource_bounds: SkillResourceContextBounds | None = None
    verbose_diagnostics: bool = False


@dataclass(frozen=True, slots=True)
class SkillScriptPolicyEvaluationOptions:
    """Composition options for selected skill script policy evaluation.

    Construction is metadata-loader wiring only; script files are inspected when
    the returned evaluator is called. Without an explicit ``approval_lookup``,
    selected scripts are denied by default in non-interactive runs.
    """

    skill_roots: tuple[Path, ...] | None = None
    sandbox_policy: SkillScriptSandboxPolicy = field(default_factory=SkillScriptSandboxPolicy)
    max_script_bytes: int | None = None
    verbose_diagnostics: bool = False
    approval_lookup: SkillScriptApprovalLookup | None = None


@dataclass(frozen=True, slots=True)
class SkillScriptExecutionOptions:
    """Composition options for selected skill script execution.

    Script execution remains policy-gated. Construction does not inspect skill
    roots or execute scripts; the selected script can run only after evaluation
    returns an approved binding. ``working_directory`` controls subprocess cwd
    and interpreter fields select the command used for approved scripts.
    """

    skill_roots: tuple[Path, ...] | None = None
    sandbox_policy: SkillScriptSandboxPolicy = field(default_factory=SkillScriptSandboxPolicy)
    max_script_bytes: int | None = None
    verbose_diagnostics: bool = False
    approval_lookup: SkillScriptApprovalLookup | None = None
    python_interpreter: str | Path | None = None
    shell_interpreter: str | Path = "/bin/sh"
    working_directory: Path | None = None


@dataclass(frozen=True, slots=True)
class CommitMessageWorkflowOptions:
    """Composition options for selected-skill commit-message generation.

    Options define the staged-git, selected-skill, and Codex transport wiring
    used by commit-message factories. Timeouts are expressed in seconds when a
    numeric value is accepted. Construction does not read git state,
    credentials, skill files, or call model backends; those effects occur during
    workflow execution.
    """

    codex_model: str | None = None
    codex_reasoning_effort: str | None = None
    codex_auth_file_path: Path | None = None
    codex_http_client: httpx.Client | None = None
    codex_timeout: float | httpx.Timeout | None = None
    skill_roots: tuple[Path, ...] | None = None
    staged_diff_bounds: GitStagedDiffBounds | None = None
    skill_bounds: SkillContextBounds | None = None
    git_timeout_seconds: float = 10.0
    git_working_directory: Path | None = None
    max_parallel_analysis: int = 4
    verbose_diagnostics: bool = False


@dataclass(frozen=True, slots=True)
class StagedGitToolOptions:
    """Composition options for optional read-only staged git registered tools.

    The configured working directory is a composition-owned trust boundary; the
    model cannot choose it. ``timeout_seconds`` is the subprocess timeout for
    read-only staged-git inspection, and bounds limit returned staged diff data.
    """

    working_directory: Path | None = None
    bounds: GitStagedDiffBounds | None = None
    timeout_seconds: float = 10.0
    verbose_diagnostics: bool = False


@dataclass(frozen=True, slots=True)
class ReadOnlyGitContextToolOptions:
    """Composition options for optional read-only git context registered tools.

    The configured working directory is a composition-owned trust boundary; the
    model cannot choose it. Construction only wires subprocess-backed loaders and
    does not inspect git state. ``bounds`` limits returned diff data and
    ``timeout_seconds`` limits read-only git inspection commands.
    """

    working_directory: Path | None = None
    bounds: GitContextDiffBounds | None = None
    timeout_seconds: float = 10.0
    verbose_diagnostics: bool = False


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


class CommitMessageRuntime(Protocol):
    """Runtime protocol consumed by the composed commit-message workflow."""

    def run(self, command: LocalAgentRunCommand) -> LocalAgentRunResult:
        """Run one prepared local agent command."""

    async def run_async(self, command: LocalAgentRunCommand) -> LocalAgentRunResult:
        """Run one prepared local agent command asynchronously."""


class CommitMessageGenerator(Protocol):
    """Generator protocol consumed by composed commit workflows."""

    async def generate_async(self, *, skill_id: str) -> GenerateCommitMessageResult:
        """Generate one commit-message recommendation result."""


class GitCommitter(Protocol):
    """Committer protocol consumed by the confirmed commit workflow."""

    def create(self, command: CreateGitCommitCommand) -> GitCommitResult:
        """Create a git commit from an approved command."""


@dataclass(frozen=True, slots=True)
class CommitMessageWorkflow:
    """Composed workflow that runs evidence-first commit-message generation."""

    generator: CommitMessageGenerator
    evidence_recorder: "CommitMessageEvidenceRecorder | None" = None

    def run(
        self, command: object | None = None, *, skill_id: str = DEFAULT_COMMIT_MESSAGE_SKILL_ID
    ) -> LocalAgentRunResult:
        """Generate a recommendation and map it to the local runtime result contract."""
        return asyncio.run(self.run_async(command, skill_id=skill_id))

    async def run_async(
        self, command: object | None = None, *, skill_id: str = DEFAULT_COMMIT_MESSAGE_SKILL_ID
    ) -> LocalAgentRunResult:
        """Generate a recommendation asynchronously and map it to the runtime result contract."""
        selected_skill_id = getattr(command, "skill_id", skill_id)
        if self.evidence_recorder is not None:
            self.evidence_recorder.reset()
        try:
            result = await self.generator.generate_async(skill_id=selected_skill_id)
        except GitStagedChangesLoadError as err:
            return LocalAgentRunResult(
                status=LocalAgentRunStatus.CONFIGURATION_ERROR,
                observations=(
                    RuntimeObservation(
                        message=str(err),
                        metadata={"category": err.category, **err.metadata},
                    ),
                ),
            )
        except SkillContextLoadError as err:
            return LocalAgentRunResult(
                status=LocalAgentRunStatus.CONFIGURATION_ERROR,
                observations=(
                    RuntimeObservation(
                        message=str(err),
                        metadata={"category": err.category, **err.metadata},
                    ),
                ),
            )
        except (GenerateCommitMessageError, ValueError) as err:
            return LocalAgentRunResult(
                status=LocalAgentRunStatus.CONFIGURATION_ERROR,
                observations=(
                    RuntimeObservation(
                        message=str(err),
                        metadata={
                            "category": "invalid_commit_message_input",
                            **getattr(err, "metadata", {}),
                        },
                    ),
                ),
            )
        except (CommitMessageAnalysisError, CommitMessageSynthesisError) as err:
            return LocalAgentRunResult(
                status=LocalAgentRunStatus.MODEL_ERROR,
                observations=(
                    RuntimeObservation(
                        message=str(err),
                        metadata={
                            "category": "commit_message_model_failure",
                            **err.metadata,
                        },
                    ),
                ),
            )
        return LocalAgentRunResult(
            status=LocalAgentRunStatus.SUCCESS,
            output_text=_format_commit_message_recommendation(result.recommendation),
            usage_evidence=self.evidence_recorder.usage_evidence if self.evidence_recorder is not None else (),
            cost_evidence=self.evidence_recorder.cost_evidence if self.evidence_recorder is not None else (),
        )


@dataclass(frozen=True, slots=True)
class ConfirmedCommitWorkflowResult:
    """Result of generating a recommendation and attempting an approved commit."""

    status: LocalAgentRunStatus
    recommendation: CommitMessageRecommendation | None = None
    commit_result: GitCommitResult | None = None
    output_text: str | None = None
    observations: tuple[RuntimeObservation, ...] = field(default_factory=tuple)
    usage_evidence: tuple[ModelUsageEvidence, ...] = field(default_factory=tuple)
    cost_evidence: tuple[ModelCostEvidence, ...] = field(default_factory=tuple)
    commit_attempted: bool = False

    def __post_init__(self) -> None:
        object.__setattr__(self, "observations", tuple(self.observations))
        object.__setattr__(self, "usage_evidence", tuple(self.usage_evidence))
        object.__setattr__(self, "cost_evidence", tuple(self.cost_evidence))

    @property
    def succeeded(self) -> bool:
        """Return whether recommendation generation and commit creation succeeded."""
        return self.status is LocalAgentRunStatus.SUCCESS


@dataclass(frozen=True, slots=True)
class ConfirmedCommitWorkflow:
    """Composed workflow for an externally approved generated git commit."""

    generator: CommitMessageGenerator
    committer: GitCommitter
    evidence_recorder: "CommitMessageEvidenceRecorder | None" = None

    def run(
        self, command: object | None = None, *, skill_id: str = DEFAULT_COMMIT_MESSAGE_SKILL_ID
    ) -> ConfirmedCommitWorkflowResult:
        """Generate a recommendation and create the approved git commit."""
        return asyncio.run(self.run_async(command, skill_id=skill_id))

    def generate(
        self, command: object | None = None, *, skill_id: str = DEFAULT_COMMIT_MESSAGE_SKILL_ID
    ) -> ConfirmedCommitWorkflowResult:
        """Generate a recommendation without creating a git commit."""
        return asyncio.run(self.generate_async(command, skill_id=skill_id))

    async def run_async(
        self, command: object | None = None, *, skill_id: str = DEFAULT_COMMIT_MESSAGE_SKILL_ID
    ) -> ConfirmedCommitWorkflowResult:
        """Generate a recommendation asynchronously and create the approved git commit."""
        generation_result = await self.generate_async(command, skill_id=skill_id)
        if not generation_result.succeeded or generation_result.recommendation is None:
            return generation_result
        return self.commit(
            generation_result.recommendation,
            output_text=generation_result.output_text,
            usage_evidence=generation_result.usage_evidence,
            cost_evidence=generation_result.cost_evidence,
        )

    async def generate_async(
        self, command: object | None = None, *, skill_id: str = DEFAULT_COMMIT_MESSAGE_SKILL_ID
    ) -> ConfirmedCommitWorkflowResult:
        """Generate a recommendation asynchronously without creating a git commit."""
        selected_skill_id = getattr(command, "skill_id", skill_id)
        if self.evidence_recorder is not None:
            self.evidence_recorder.reset()
        try:
            result = await self.generator.generate_async(skill_id=selected_skill_id)
        except GitStagedChangesLoadError as err:
            return self._failure_result(
                LocalAgentRunStatus.CONFIGURATION_ERROR,
                RuntimeObservation(
                    message=str(err),
                    metadata={"category": err.category, **err.metadata},
                ),
            )
        except SkillContextLoadError as err:
            return self._failure_result(
                LocalAgentRunStatus.CONFIGURATION_ERROR,
                RuntimeObservation(
                    message=str(err),
                    metadata={"category": err.category, **err.metadata},
                ),
            )
        except (GenerateCommitMessageError, ValueError) as err:
            return self._failure_result(
                LocalAgentRunStatus.CONFIGURATION_ERROR,
                RuntimeObservation(
                    message=str(err),
                    metadata={
                        "category": "invalid_commit_message_input",
                        **getattr(err, "metadata", {}),
                    },
                ),
            )
        except (CommitMessageAnalysisError, CommitMessageSynthesisError) as err:
            return self._failure_result(
                LocalAgentRunStatus.MODEL_ERROR,
                RuntimeObservation(
                    message=str(err),
                    metadata={
                        "category": "commit_message_model_failure",
                        **err.metadata,
                    },
                ),
            )

        recommendation = result.recommendation
        output_text = _format_commit_message_recommendation(recommendation)

        return ConfirmedCommitWorkflowResult(
            status=LocalAgentRunStatus.SUCCESS,
            recommendation=recommendation,
            output_text=output_text,
            usage_evidence=self._usage_evidence,
            cost_evidence=self._cost_evidence,
        )

    def commit(
        self,
        recommendation: CommitMessageRecommendation,
        *,
        output_text: str | None = None,
        usage_evidence: tuple[ModelUsageEvidence, ...] | None = None,
        cost_evidence: tuple[ModelCostEvidence, ...] | None = None,
    ) -> ConfirmedCommitWorkflowResult:
        """Create a git commit from an externally approved recommendation."""
        try:
            commit_result = self.committer.create(
                CreateGitCommitCommand(message=recommendation.commit_message),
            )
        except GitCommitError as err:
            return ConfirmedCommitWorkflowResult(
                status=LocalAgentRunStatus.CONFIGURATION_ERROR,
                recommendation=recommendation,
                output_text=output_text,
                observations=(
                    RuntimeObservation(
                        message=str(err),
                        metadata={
                            "category": "git_commit_failed",
                            "commit_attempted": True,
                            **err.metadata,
                        },
                    ),
                ),
                usage_evidence=usage_evidence or self._usage_evidence,
                cost_evidence=cost_evidence or self._cost_evidence,
                commit_attempted=True,
            )

        return ConfirmedCommitWorkflowResult(
            status=LocalAgentRunStatus.SUCCESS,
            recommendation=recommendation,
            commit_result=commit_result,
            output_text=output_text,
            usage_evidence=usage_evidence or self._usage_evidence,
            cost_evidence=cost_evidence or self._cost_evidence,
            commit_attempted=True,
        )

    @property
    def _usage_evidence(self):
        return self.evidence_recorder.usage_evidence if self.evidence_recorder is not None else ()

    @property
    def _cost_evidence(self):
        return self.evidence_recorder.cost_evidence if self.evidence_recorder is not None else ()

    def _failure_result(
        self,
        status: LocalAgentRunStatus,
        observation: RuntimeObservation,
    ) -> ConfirmedCommitWorkflowResult:
        return ConfirmedCommitWorkflowResult(
            status=status,
            observations=(observation,),
            usage_evidence=self._usage_evidence,
            cost_evidence=self._cost_evidence,
        )


class CommitMessageEvidenceRecorder(Protocol):
    """Recorder for model evidence collected during a commit-message workflow run."""

    @property
    def usage_evidence(self):
        """Return usage evidence observed during the active workflow run."""

    @property
    def cost_evidence(self):
        """Return cost evidence observed during the active workflow run."""

    def reset(self) -> None:
        """Clear evidence from previous workflow runs."""


class EvidenceRecordingCommitMessageRuntime:
    """Runtime decorator that records model evidence from commit-message model calls."""

    def __init__(self, runtime: CommitMessageRuntime) -> None:
        self._runtime = runtime
        self._usage_evidence = []
        self._cost_evidence = []

    @property
    def usage_evidence(self):
        """Return collected usage evidence in model-call order."""
        return tuple(self._usage_evidence)

    @property
    def cost_evidence(self):
        """Return collected cost evidence in model-call order."""
        return tuple(self._cost_evidence)

    def reset(self) -> None:
        """Clear evidence from previous workflow runs."""
        self._usage_evidence.clear()
        self._cost_evidence.clear()

    def run(self, command: LocalAgentRunCommand) -> LocalAgentRunResult:
        """Run the wrapped runtime and record any returned model evidence."""
        result = self._runtime.run(command)
        self._record(result)
        return result

    async def run_async(self, command: LocalAgentRunCommand) -> LocalAgentRunResult:
        """Run the wrapped runtime asynchronously and record any returned model evidence."""
        result = await self._runtime.run_async(command)
        self._record(result)
        return result

    def _record(self, result: LocalAgentRunResult) -> None:
        self._usage_evidence.extend(result.usage_evidence)
        self._cost_evidence.extend(result.cost_evidence)


@dataclass(frozen=True, slots=True)
class SkillContextCommitMessageSynthesizer:
    """Synthesizer decorator that loads selected skill markdown before synthesis."""

    synthesizer: AsyncCommitMessageSynthesizer
    skill_context_loader: LoadSkillContext

    async def synthesize_async(self, command: SynthesizeCommitMessageCommand) -> CommitMessageRecommendation:
        """Load selected skill context and delegate final synthesis."""
        skill_context = await asyncio.to_thread(
            self.skill_context_loader.load,
            (SelectedSkill(skill_id=command.skill_id),),
        )
        skill_markdown = skill_context[0].text if skill_context else None
        return await self.synthesizer.synthesize_async(
            SynthesizeCommitMessageCommand(
                evidence_bundle=command.evidence_bundle,
                skill_id=command.skill_id,
                skill_markdown=skill_markdown,
            ),
        )


def _format_commit_message_recommendation(recommendation: CommitMessageRecommendation) -> str:
    """Format a recommendation with the stable terminal output labels."""
    return (
        f"Summary:\n{recommendation.summary}\n\n"
        f"Rationale:\n{recommendation.rationale}\n\n"
        f"Commit message:\n{recommendation.commit_message}"
    )


class DenyByDefaultSkillScriptApprovalLookup:
    """Non-interactive approval lookup that denies every selected script."""

    def get_approval(self, binding: SkillScriptApprovalBinding) -> SkillScriptApprovalDecision:
        """Return a deterministic absence-of-approval decision."""
        return SkillScriptApprovalDecision(
            status=SkillScriptApprovalStatus.NOT_REQUESTED,
            binding=binding,
        )


def create_skill_context_loader(
    *,
    skill_roots: tuple[Path, ...] | None = None,
    bounds: SkillContextBounds | None = None,
    verbose_diagnostics: bool = False,
) -> LoadSkillContext:
    """Create a use case for loading selected local Agent Skills as runtime context.

    The helper wires filesystem access at the composition root. It only constructs
    dependencies; selected ``SKILL.md`` files are read when the returned use case
    is called.
    """
    return LoadSkillContext(
        loader=SkillMarkdownFileContextLoader(
            skill_roots=skill_roots,
            verbose_diagnostics=verbose_diagnostics,
        ),
        bounds=bounds,
    )


def create_skill_augmented_local_agent_command(
    command: LocalAgentRunCommand,
    selections: tuple[SelectedSkill, ...],
    *,
    skill_roots: tuple[Path, ...] | None = None,
    bounds: SkillContextBounds | None = None,
    verbose_diagnostics: bool = False,
) -> LocalAgentRunCommand:
    """Return a local runtime command augmented with selected Agent Skill context.

    This helper loads explicitly selected local ``SKILL.md`` markdown only. It
    does not create a Codex runtime, read Codex credentials, call a backend, or
    execute skill scripts/resources.
    """
    skill_context_loader = create_skill_context_loader(
        skill_roots=skill_roots,
        bounds=bounds,
        verbose_diagnostics=verbose_diagnostics,
    )
    return skill_context_loader.augment_command(command, selections)


def create_skill_resource_context_loader(
    *,
    skill_roots: tuple[Path, ...] | None = None,
    bounds: SkillResourceContextBounds | None = None,
    verbose_diagnostics: bool = False,
) -> LoadSkillResourceContext:
    """Create a use case for loading selected Agent Skill resources as context."""
    return LoadSkillResourceContext(
        loader=SkillResourceFileContextLoader(
            skill_roots=skill_roots,
            verbose_diagnostics=verbose_diagnostics,
        ),
        bounds=bounds,
    )


def create_skill_resource_augmented_local_agent_command(
    command: LocalAgentRunCommand,
    selections: tuple[SelectedSkillResource, ...],
    *,
    skill_roots: tuple[Path, ...] | None = None,
    bounds: SkillResourceContextBounds | None = None,
    verbose_diagnostics: bool = False,
) -> LocalAgentRunCommand:
    """Return a local runtime command augmented with selected skill resources."""
    resource_context_loader = create_skill_resource_context_loader(
        skill_roots=skill_roots,
        bounds=bounds,
        verbose_diagnostics=verbose_diagnostics,
    )
    return resource_context_loader.augment_command(command, selections)


def create_skill_context_augmented_local_agent_command(
    command: LocalAgentRunCommand,
    options: SkillContextAugmentationOptions,
) -> LocalAgentRunCommand:
    """Return a command augmented with selected skill markdown and resources."""
    augmented = command
    if options.skill_selections:
        augmented = create_skill_augmented_local_agent_command(
            augmented,
            options.skill_selections,
            skill_roots=options.skill_roots,
            bounds=options.skill_bounds,
            verbose_diagnostics=options.verbose_diagnostics,
        )
    if options.resource_selections:
        augmented = create_skill_resource_augmented_local_agent_command(
            augmented,
            options.resource_selections,
            skill_roots=options.skill_roots,
            bounds=options.resource_bounds,
            verbose_diagnostics=options.verbose_diagnostics,
        )
    return augmented


def create_commit_message_workflow(
    *,
    runtime: CommitMessageRuntime,
    options: CommitMessageWorkflowOptions | None = None,
) -> CommitMessageWorkflow:
    """Create the selected-skill commit-message workflow with injected runtime."""
    workflow_options = options or CommitMessageWorkflowOptions()
    evidence_recording_runtime = EvidenceRecordingCommitMessageRuntime(runtime)
    generator = _create_commit_message_generator(
        runtime=evidence_recording_runtime,
        options=workflow_options,
    )
    return CommitMessageWorkflow(
        generator=generator,
        evidence_recorder=evidence_recording_runtime,
    )


def create_confirmed_commit_workflow(
    *,
    runtime: CommitMessageRuntime,
    options: CommitMessageWorkflowOptions | None = None,
) -> ConfirmedCommitWorkflow:
    """Create the selected-skill confirmed commit workflow with injected runtime."""
    workflow_options = options or CommitMessageWorkflowOptions()
    evidence_recording_runtime = EvidenceRecordingCommitMessageRuntime(runtime)
    generator = _create_commit_message_generator(
        runtime=evidence_recording_runtime,
        options=workflow_options,
    )
    return ConfirmedCommitWorkflow(
        generator=generator,
        committer=CreateGitCommit(
            commit_creator=GitCommitSubprocessCreator(
                working_directory=workflow_options.git_working_directory,
                timeout_seconds=workflow_options.git_timeout_seconds,
                verbose_diagnostics=workflow_options.verbose_diagnostics,
            ),
        ),
        evidence_recorder=evidence_recording_runtime,
    )


def _create_commit_message_generator(
    *,
    runtime: CommitMessageRuntime,
    options: CommitMessageWorkflowOptions,
) -> GenerateCommitMessage:
    """Create the evidence-first commit-message generator shared by commit workflows."""
    staged_changes_loader = GitStagedChangesSubprocessLoader(
        working_directory=options.git_working_directory,
        bounds=options.staged_diff_bounds,
        timeout_seconds=options.git_timeout_seconds,
        verbose_diagnostics=options.verbose_diagnostics,
    )
    skill_context_loader = create_skill_context_loader(
        skill_roots=options.skill_roots,
        bounds=options.skill_bounds,
        verbose_diagnostics=options.verbose_diagnostics,
    )
    return GenerateCommitMessage(
        staged_changes_loader=staged_changes_loader,
        analyzer=AgentRuntimeStagedFileCommitMessageAnalyzer(runtime),
        synthesizer=SkillContextCommitMessageSynthesizer(
            synthesizer=AgentRuntimeCommitMessageSynthesizer(runtime),
            skill_context_loader=skill_context_loader,
        ),
        options=GenerateCommitMessageOptions(max_parallel_analysis=options.max_parallel_analysis),
    )


def create_codex_commit_message_workflow(
    options: CommitMessageWorkflowOptions | None = None,
) -> CommitMessageWorkflow:
    """Create the Codex-backed selected-skill commit-message workflow."""
    workflow_options = options or CommitMessageWorkflowOptions()
    return create_commit_message_workflow(
        runtime=create_codex_runtime(
            auth_file_path=workflow_options.codex_auth_file_path,
            http_client=workflow_options.codex_http_client,
            timeout=workflow_options.codex_timeout,
            request_settings=CodexBackendRequestSettings(
                model=workflow_options.codex_model or DEFAULT_COMMIT_MESSAGE_CODEX_MODEL,
                reasoning_effort=(
                    workflow_options.codex_reasoning_effort or DEFAULT_COMMIT_MESSAGE_CODEX_REASONING_EFFORT
                ),
            ),
        ),
        options=workflow_options,
    )


def create_codex_confirmed_commit_workflow(
    options: CommitMessageWorkflowOptions | None = None,
) -> ConfirmedCommitWorkflow:
    """Create the Codex-backed selected-skill confirmed commit workflow."""
    workflow_options = options or CommitMessageWorkflowOptions()
    return create_confirmed_commit_workflow(
        runtime=create_codex_runtime(
            auth_file_path=workflow_options.codex_auth_file_path,
            http_client=workflow_options.codex_http_client,
            timeout=workflow_options.codex_timeout,
            request_settings=CodexBackendRequestSettings(
                model=workflow_options.codex_model or DEFAULT_COMMIT_MESSAGE_CODEX_MODEL,
                reasoning_effort=(
                    workflow_options.codex_reasoning_effort or DEFAULT_COMMIT_MESSAGE_CODEX_REASONING_EFFORT
                ),
            ),
        ),
        options=workflow_options,
    )


def create_skill_script_policy_evaluator(
    options: SkillScriptPolicyEvaluationOptions | None = None,
) -> EvaluateSkillScriptPolicy:
    """Create a use case for selected Agent Skill script policy evaluation.

    The helper wires read-only metadata inspection and a non-interactive approval
    dependency at the composition root. Construction does not read skill roots,
    read Codex credentials, call backends, prompt for approval, or execute
    scripts.
    """
    policy_options = options or SkillScriptPolicyEvaluationOptions()
    sandbox_policy = policy_options.sandbox_policy
    return EvaluateSkillScriptPolicy(
        metadata_loader=SkillScriptFileMetadataLoader(
            skill_roots=policy_options.skill_roots,
            max_script_bytes=policy_options.max_script_bytes or sandbox_policy.max_script_bytes,
            verbose_diagnostics=policy_options.verbose_diagnostics,
        ),
        approval_lookup=policy_options.approval_lookup or DenyByDefaultSkillScriptApprovalLookup(),
    )


def create_skill_script_executor(
    options: SkillScriptExecutionOptions | None = None,
) -> ExecuteSkillScript:
    """Create a policy-gated use case for selected Agent Skill script execution.

    The helper wires metadata inspection, non-interactive approval lookup, policy
    evaluation, and constrained subprocess execution. Construction does not read
    skill roots, execute scripts, prompt for approval, read Codex credentials, or
    call backends.
    """
    execution_options = options or SkillScriptExecutionOptions()
    policy_evaluator = create_skill_script_policy_evaluator(
        SkillScriptPolicyEvaluationOptions(
            skill_roots=execution_options.skill_roots,
            sandbox_policy=execution_options.sandbox_policy,
            max_script_bytes=execution_options.max_script_bytes,
            verbose_diagnostics=execution_options.verbose_diagnostics,
            approval_lookup=execution_options.approval_lookup,
        ),
    )
    executor = SkillScriptSubprocessExecutor(
        skill_roots=execution_options.skill_roots,
        python_interpreter=execution_options.python_interpreter,
        shell_interpreter=execution_options.shell_interpreter,
        working_directory=execution_options.working_directory,
        verbose_diagnostics=execution_options.verbose_diagnostics,
    )
    return ExecuteSkillScript(policy_evaluator=policy_evaluator, executor=executor)


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


def create_staged_git_registered_tools(options: StagedGitToolOptions | None = None) -> tuple[RegisteredTool, ...]:
    """Create explicitly opt-in read-only staged git registered tools.

    Construction only wires the subprocess-backed staged changes loader. Git state
    is inspected lazily when one of the returned tool handlers is invoked.
    """
    tool_options = options or StagedGitToolOptions()
    loader = GitStagedChangesSubprocessLoader(
        working_directory=tool_options.working_directory,
        bounds=tool_options.bounds,
        timeout_seconds=tool_options.timeout_seconds,
        verbose_diagnostics=tool_options.verbose_diagnostics,
    )
    return create_git_staged_changes_registered_tools(loader)


def create_read_only_git_context_registered_tools(
    options: ReadOnlyGitContextToolOptions | None = None,
) -> tuple[RegisteredTool, ...]:
    """Create explicitly opt-in read-only git context registered tools.

    This v1 helper is intentionally internal to the composition module rather
    than exported from ``fabrica.bootstrap``. Construction only wires the
    subprocess-backed git context loader. Git state is inspected lazily when one
    of the returned tool handlers is invoked.
    """
    tool_options = options or ReadOnlyGitContextToolOptions()
    loader = GitContextSubprocessLoader(
        working_directory=tool_options.working_directory,
        bounds=tool_options.bounds,
        timeout_seconds=tool_options.timeout_seconds,
        verbose_diagnostics=tool_options.verbose_diagnostics,
    )
    return create_git_context_registered_tool_adapters(
        worktree_loader=loader,
        commit_loader=loader,
        ref_loader=loader,
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
    preparer = PrepareSkillTools(preparer=RegisteredSkillToolPreparer(runtime_options.skill_tools))
    preparation = preparer.prepare(
        SkillToolPreparationCommand(
            selected_skills=context_options.skill_selections,
            max_selected_tools=runtime_options.max_selected_tools or len(runtime_options.skill_tools) or 1,
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


def create_codex_runtime(
    *,
    auth_file_path: Path | None = None,
    http_client: httpx.Client | None = None,
    timeout: float | httpx.Timeout | None = None,
    request_settings: CodexBackendRequestSettings | None = None,
    usage_request_settings: CodexUsageRequestSettings | None = None,
) -> RunLocalAgent:
    """Create a local runtime use case backed by the Codex transport path.

    The factory wires concrete adapters at the composition root but does not read
    credentials or call the live backend during construction. Credential loading
    and HTTP I/O happen only when the returned runtime use case is executed.
    """
    backend = (
        CodexBackendHttpAdapter(
            request_settings=request_settings,
            usage_request_settings=usage_request_settings,
            timeout=timeout,
            client=http_client,
        )
        if timeout is not None
        else CodexBackendHttpAdapter(
            request_settings=request_settings,
            usage_request_settings=usage_request_settings,
            client=http_client,
        )
    )

    transport = CompleteWithCodexTransport(
        credential_store=CodexAuthFileCredentialStore(auth_file_path or DEFAULT_CODEX_AUTH_FILE),
        backend=backend,
    )
    return RunLocalAgent(model=CodexTransportAgentModel(transport=transport))


def create_pydantic_ai_runtime(
    *,
    completion: PydanticAICompletion,
    model_name: str = "synthetic-codex",
) -> RunLocalAgent:
    """Create a local runtime use case backed by the PydanticAI adapter proof.

    The factory wires an explicitly supplied completion dependency for offline
    compatibility tests and future composition experiments. Construction does
    not read credentials, call a backend, load skill roots, or execute scripts.
    """
    return RunLocalAgent(model=PydanticAIAgentModel(completion=completion, model_name=model_name))


def create_codex_pydantic_ai_runtime(
    *,
    auth_file_path: Path | None = None,
    http_client: httpx.Client | None = None,
    timeout: float | httpx.Timeout | None = None,
    request_settings: CodexBackendRequestSettings | None = None,
    model_name: str = "codex-transport",
) -> RunLocalAgent:
    """Create a PydanticAI runtime backed by the Codex completion boundary.

    Construction only wires dependencies. Credential loading and HTTP I/O happen
    when the returned runtime is executed.
    """
    backend = (
        CodexBackendHttpAdapter(
            request_settings=request_settings,
            timeout=timeout,
            client=http_client,
        )
        if timeout is not None
        else CodexBackendHttpAdapter(
            request_settings=request_settings,
            client=http_client,
        )
    )
    transport = CompleteWithCodexTransport(
        credential_store=CodexAuthFileCredentialStore(auth_file_path or DEFAULT_CODEX_AUTH_FILE),
        backend=backend,
    )
    completion = CodexTransportPydanticAICompletion(transport=transport)
    return RunLocalAgent(model=PydanticAIAgentModel(completion=completion, model_name=model_name))
