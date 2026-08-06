"""Developer-workflow command registration for the product CLI."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING, Protocol, TextIO

from fabrica.adapters.inbound.cli.output import write_run_result
from fabrica.features.agent_runtime.application.dtos import (
    LocalAgentRunResult,
    LocalAgentRunStatus,
    RuntimeObservation,
)
from fabrica.features.developer_workflow.application.use_cases import DEFAULT_COMMIT_MESSAGE_SKILL_ID

if TYPE_CHECKING:
    import argparse

    from fabrica.adapters.inbound.cli.options import CliGlobalOptions
    from fabrica.bootstrap import ConfirmedCommitWorkflowResult
    from fabrica.features.developer_workflow.application.dtos import CommitMessageRecommendation


class CommitMessageWorkflowRunner(Protocol):
    """Protocol for commit-message workflow execution consumed by the CLI adapter."""

    def run(self, command: CliCommitMessageCommand) -> LocalAgentRunResult:
        """Run selected-skill commit-message generation."""


class ConfirmedCommitWorkflowRunner(Protocol):
    """Protocol for interactive confirmed commit workflow execution."""

    def generate(self, command: CliCommitCommand) -> ConfirmedCommitWorkflowResult:
        """Generate a commit-message recommendation without creating a commit."""

    def commit(self, recommendation: CommitMessageRecommendation) -> ConfirmedCommitWorkflowResult:
        """Create a git commit from an approved recommendation."""


@dataclass(frozen=True, slots=True)
class DeveloperWorkflowCliDependencies:
    """Injected dependencies for developer-workflow CLI commands."""

    commit_message_workflow: CommitMessageWorkflowRunner | None = None
    confirmed_commit_workflow: ConfirmedCommitWorkflowRunner | None = None


@dataclass(frozen=True, slots=True)
class DeveloperWorkflowCliStreams:
    """Normalized CLI input/output streams for developer-workflow commands."""

    stdin: TextIO
    stdout: TextIO
    stderr: TextIO


@dataclass(frozen=True, slots=True)
class CliCommitMessageCommand:
    """Parsed CLI arguments for selected-skill commit-message generation."""

    skill_id: str = DEFAULT_COMMIT_MESSAGE_SKILL_ID
    model: str | None = None
    reasoning_effort: str | None = None
    skill_roots: tuple[Path, ...] = field(default_factory=tuple)

    def __post_init__(self) -> None:
        object.__setattr__(self, "skill_roots", tuple(self.skill_roots))


@dataclass(frozen=True, slots=True)
class CliCommitCommand:
    """Parsed CLI arguments for interactive confirmed git commit creation."""

    skill_id: str = DEFAULT_COMMIT_MESSAGE_SKILL_ID
    model: str | None = None
    reasoning_effort: str | None = None
    skill_roots: tuple[Path, ...] = field(default_factory=tuple)

    def __post_init__(self) -> None:
        object.__setattr__(self, "skill_roots", tuple(self.skill_roots))


def register_developer_workflow_cli_commands(subparsers: argparse._SubParsersAction[argparse.ArgumentParser]) -> None:
    """Register developer-workflow owned commands on the product CLI parser."""
    commit_message_parser = subparsers.add_parser(
        "commit-message",
        help="preview a read-only commit message for staged git changes",
        description="Read staged git diff context and propose a commit message without creating a commit.",
    )
    _add_commit_message_generation_flags(commit_message_parser)
    _add_common_skill_root_flags(commit_message_parser)
    commit_message_parser.set_defaults(command_factory=_commit_message_command_from_namespace)

    commit_parser = subparsers.add_parser(
        "commit",
        help="create a git commit from a generated message after confirmation",
        description=(
            "Generate a staged-changes commit message, prompt for confirmation, "
            "then create a git commit only after approval."
        ),
    )
    _add_commit_message_generation_flags(commit_parser)
    _add_common_skill_root_flags(commit_parser)
    commit_parser.set_defaults(command_factory=_commit_command_from_namespace)


def run_developer_workflow_cli_command(
    command: CliCommitMessageCommand | CliCommitCommand,
    *,
    global_options: CliGlobalOptions,
    dependencies: DeveloperWorkflowCliDependencies,
    streams: DeveloperWorkflowCliStreams,
    evidence_writer: EvidenceWriter,
) -> int:
    """Run one developer-workflow owned CLI command."""
    if isinstance(command, CliCommitMessageCommand):
        workflow = dependencies.commit_message_workflow or _create_default_commit_message_workflow(
            command, global_options=global_options
        )
        result = workflow.run(command)
        return _write_runtime_result(
            result,
            global_options=global_options,
            stdout=streams.stdout,
            stderr=streams.stderr,
            evidence_writer=evidence_writer,
        )
    workflow = dependencies.confirmed_commit_workflow or _create_default_confirmed_commit_workflow(
        command, global_options=global_options
    )
    generation_result = workflow.generate(command)
    if not generation_result.succeeded or generation_result.recommendation is None:
        return _write_confirmed_commit_result(
            generation_result,
            global_options=global_options,
            streams=streams,
            evidence_writer=evidence_writer,
        )

    if generation_result.output_text:
        streams.stdout.write(generation_result.output_text)
        if not generation_result.output_text.endswith("\n"):
            streams.stdout.write("\n")
    streams.stdout.write("Commit with this message? [y/N] ")
    streams.stdout.flush()

    try:
        answer = streams.stdin.readline()
    except KeyboardInterrupt:
        interrupted_result = LocalAgentRunResult(
            status=LocalAgentRunStatus.SAFETY_DENIED,
            observations=(
                RuntimeObservation(
                    message="commit confirmation interrupted",
                    metadata={"category": "commit_confirmation_interrupted"},
                ),
            ),
            usage_evidence=generation_result.usage_evidence,
            cost_evidence=generation_result.cost_evidence,
        )
        return _write_runtime_result(
            interrupted_result,
            global_options=global_options,
            stdout=streams.stdout,
            stderr=streams.stderr,
            evidence_writer=evidence_writer,
        )

    if answer.strip().casefold() not in {"y", "yes"}:
        streams.stdout.write("Commit cancelled; no commit created.\n")
        evidence_writer(generation_result, global_options=global_options, stdout=streams.stdout)
        return 0

    commit_result = workflow.commit(generation_result.recommendation)
    if commit_result.succeeded and commit_result.commit_result is not None:
        if commit_result.commit_result.short_hash is not None:
            streams.stdout.write(f"Committed as {commit_result.commit_result.short_hash}.\n")
        else:
            streams.stdout.write("Committed.\n")
    return _write_confirmed_commit_result(
        commit_result,
        global_options=global_options,
        streams=streams,
        output_already_written=True,
        evidence_writer=evidence_writer,
    )


class EvidenceWriter(Protocol):
    """Protocol for writing requested model evidence after command output."""

    def __call__(
        self,
        result: LocalAgentRunResult | ConfirmedCommitWorkflowResult,
        *,
        global_options: CliGlobalOptions,
        stdout: TextIO,
    ) -> None:
        """Write model evidence selected by global CLI options."""


def _write_runtime_result(
    result: LocalAgentRunResult,
    *,
    global_options: CliGlobalOptions,
    stdout: TextIO,
    stderr: TextIO,
    evidence_writer: EvidenceWriter,
) -> int:
    exit_code = write_run_result(result, stdout=stdout, stderr=stderr)
    if global_options.print_usage or global_options.print_prices:
        evidence_writer(result, global_options=global_options, stdout=stdout)
    return exit_code


def _write_confirmed_commit_result(
    result: ConfirmedCommitWorkflowResult,
    *,
    global_options: CliGlobalOptions,
    streams: DeveloperWorkflowCliStreams,
    evidence_writer: EvidenceWriter,
    output_already_written: bool = False,
) -> int:
    runtime_result = LocalAgentRunResult(
        status=result.status,
        output_text=None if output_already_written else result.output_text,
        observations=result.observations,
        usage_evidence=result.usage_evidence,
        cost_evidence=result.cost_evidence,
    )
    return _write_runtime_result(
        runtime_result,
        global_options=global_options,
        stdout=streams.stdout,
        stderr=streams.stderr,
        evidence_writer=evidence_writer,
    )


def _create_default_commit_message_workflow(
    command: CliCommitMessageCommand,
    *,
    global_options: CliGlobalOptions,
) -> CommitMessageWorkflowRunner:
    from fabrica.bootstrap import (  # noqa: PLC0415
        CommitMessageWorkflowOptions,
        create_codex_commit_message_workflow,
    )

    return create_codex_commit_message_workflow(
        CommitMessageWorkflowOptions(
            codex_model=command.model,
            codex_reasoning_effort=command.reasoning_effort,
            skill_roots=command.skill_roots,
            verbose_diagnostics=global_options.verbose_diagnostics,
        ),
    )


def _create_default_confirmed_commit_workflow(
    command: CliCommitCommand,
    *,
    global_options: CliGlobalOptions,
) -> ConfirmedCommitWorkflowRunner:
    from fabrica.bootstrap import (  # noqa: PLC0415
        CommitMessageWorkflowOptions,
        create_codex_confirmed_commit_workflow,
    )

    return create_codex_confirmed_commit_workflow(
        CommitMessageWorkflowOptions(
            codex_model=command.model,
            codex_reasoning_effort=command.reasoning_effort,
            skill_roots=command.skill_roots,
            verbose_diagnostics=global_options.verbose_diagnostics,
        ),
    )


def _add_common_skill_root_flags(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--skill-root",
        dest="skill_roots",
        action="append",
        type=Path,
        default=[],
        help="Skill root override for explicit skill/resource/script selection. May be repeated.",
    )


def _add_commit_message_generation_flags(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--skill",
        dest="skill_id",
        default=DEFAULT_COMMIT_MESSAGE_SKILL_ID,
        help="Selected commit-message Agent Skill ID. Defaults to conventional-commits.",
    )
    parser.add_argument(
        "--model",
        dest="model",
        help="Optional Codex model override for commit-message generation.",
    )
    parser.add_argument(
        "--reasoning-effort",
        choices=("low", "medium", "high", "xhigh", "max", "ultra"),
        help="Optional Codex reasoning effort override for commit-message generation.",
    )


def _commit_message_command_from_namespace(namespace: argparse.Namespace) -> CliCommitMessageCommand:
    return CliCommitMessageCommand(
        skill_id=namespace.skill_id,
        model=namespace.model,
        reasoning_effort=namespace.reasoning_effort,
        skill_roots=tuple(namespace.skill_roots),
    )


def _commit_command_from_namespace(namespace: argparse.Namespace) -> CliCommitCommand:
    return CliCommitCommand(
        skill_id=namespace.skill_id,
        model=namespace.model,
        reasoning_effort=namespace.reasoning_effort,
        skill_roots=tuple(namespace.skill_roots),
    )
