"""Composition helpers for developer workflow and git-related tools."""

from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

import httpx

from fabrica.bootstrap.composition.codex_runtime import (
    DEFAULT_COMMIT_MESSAGE_CODEX_MODEL,
    DEFAULT_COMMIT_MESSAGE_CODEX_REASONING_EFFORT,
    create_codex_runtime,
)
from fabrica.bootstrap.composition.skill_context import SkillContextBounds, create_skill_context_loader
from fabrica.features.agent_runtime.adapters.outbound.registered_tool import RegisteredTool
from fabrica.features.agent_runtime.application.dtos import LocalAgentRunCommand, LocalAgentRunResult
from fabrica.features.codex_transport.adapters.outbound.codex_backend_http import CodexBackendRequestSettings
from fabrica.features.developer_workflow.adapters.outbound.commit_message_agent_runtime import (
    AgentRuntimeCommitMessageSynthesizer,
    AgentRuntimeStagedFileCommitMessageAnalyzer,
    SkillContextCommitMessageSynthesizer,
)
from fabrica.features.developer_workflow.adapters.outbound.git_registered_tool import (
    create_git_context_registered_tools as create_git_context_registered_tool_adapters,
)
from fabrica.features.developer_workflow.adapters.outbound.git_registered_tool import (
    create_git_staged_changes_registered_tools,
)
from fabrica.features.developer_workflow.adapters.outbound.git_subprocess import (
    GitCommitSubprocessCreator,
    GitContextSubprocessLoader,
    GitStagedChangesSubprocessLoader,
    PreCommitSubprocessRunner,
)
from fabrica.features.developer_workflow.adapters.outbound.pre_commit_registered_tool import (
    create_pre_commit_registered_tools,
)
from fabrica.features.developer_workflow.application.dtos import (
    GitContextDiffBounds,
    GitStagedDiffBounds,
)
from fabrica.features.developer_workflow.application.use_cases import (
    CommitMessageWorkflow,
    ConfirmedCommitWorkflow,
    CreateGitCommit,
    GenerateCommitMessage,
    GenerateCommitMessageOptions,
)
from fabrica.features.query_execution.application.use_cases import BoundedAsyncQueryFanoutExecutor
from fabrica.shared_kernel.model_usage import ModelCostEvidence, ModelUsageEvidence


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
class PreCommitToolOptions:
    """Composition options for optional mutating pre-commit registered tools.

    The configured working directory is a composition-owned trust boundary; the
    model cannot choose it. Construction only wires a subprocess-backed runner.
    Pre-commit hooks are executed lazily when the returned tool handler is
    invoked and may modify files or pre-commit caches.
    """

    working_directory: Path | None = None
    timeout_seconds: float = 120.0
    verbose_diagnostics: bool = False


class CommitMessageRuntime(Protocol):
    """Runtime protocol consumed by the composed commit-message workflow."""

    def run(self, command: LocalAgentRunCommand) -> LocalAgentRunResult:
        """Run one prepared local agent command."""

    async def run_async(self, command: LocalAgentRunCommand) -> LocalAgentRunResult:
        """Run one prepared local agent command asynchronously."""


class EvidenceRecordingCommitMessageRuntime:
    """Runtime decorator that records model evidence from commit-message model calls."""

    def __init__(self, runtime: CommitMessageRuntime) -> None:
        self._runtime = runtime
        self._usage_evidence: list[ModelUsageEvidence] = []
        self._cost_evidence: list[ModelCostEvidence] = []

    @property
    def usage_evidence(self) -> tuple[ModelUsageEvidence, ...]:
        """Return collected usage evidence in model-call order."""
        return tuple(self._usage_evidence)

    @property
    def cost_evidence(self) -> tuple[ModelCostEvidence, ...]:
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
        pre_commit_runner=PreCommitSubprocessRunner(
            working_directory=workflow_options.git_working_directory,
            timeout_seconds=workflow_options.git_timeout_seconds,
            verbose_diagnostics=workflow_options.verbose_diagnostics,
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
        query_executor=BoundedAsyncQueryFanoutExecutor(),
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


def create_pre_commit_registered_tool_adapters(
    options: PreCommitToolOptions | None = None,
) -> tuple[RegisteredTool, ...]:
    """Create explicitly opt-in mutating pre-commit registered tools.

    Construction only wires the subprocess-backed pre-commit runner. Hooks are
    executed lazily when the returned tool handler is invoked and may modify files
    or pre-commit caches.
    """
    tool_options = options or PreCommitToolOptions()
    return create_pre_commit_registered_tools(
        PreCommitSubprocessRunner(
            working_directory=tool_options.working_directory,
            timeout_seconds=tool_options.timeout_seconds,
            verbose_diagnostics=tool_options.verbose_diagnostics,
        ),
    )
