"""Bootstrap-owned handler for the interactive coding-agent session command."""

from __future__ import annotations

import asyncio
import hashlib
from pathlib import Path
from typing import TYPE_CHECKING, TextIO

from fabrica.bootstrap.composition.coding_agent_session import (
    create_terminal_workspace_coding_agent_session_runtime,
    prepare_terminal_workspace_coding_agent_session_resume_runtime,
)
from fabrica.features.agent_session.adapters.outbound.posix_filesystem import PosixSessionRecordStore
from fabrica.features.agent_session.application import ReplanSafetyState, ResumeDisposition
from fabrica.features.coding_agent_session.adapters.inbound.cli.command_models import (
    CliCodingAgentSessionCommand,
    CliSessionRecordCommand,
)
from fabrica.features.coding_agent_session.adapters.inbound.cli.contracts import CodingAgentSessionCliStreams
from fabrica.features.coding_agent_session.adapters.inbound.cli.runner import run_coding_agent_session_cli_command
from fabrica.features.coding_agent_session.adapters.inbound.cli.session_records import run_session_record_cli_command
from fabrica.features.coding_agent_session.adapters.inbound.terminal import TerminalStaleContextReplanAcknowledgement
from fabrica.features.coding_agent_session.application.dtos import CodingAgentSessionCommand

if TYPE_CHECKING:
    from fabrica.adapters.inbound.cli import CommandContext
    from fabrica.bootstrap.composition.coding_agent_session import WorkspaceCodingAgentSessionRuntime
    from fabrica.features.coding_agent_session.adapters.inbound.cli.command_models import (
        CodingAgentSessionCliCompositionOptions,
    )
    from fabrica.features.coding_agent_session.adapters.inbound.cli.registration import CodingAgentSessionCliHandler
    from fabrica.features.coding_agent_session.application.ports import CodingAgentSessionRuntime


def run_coding_agent_session_command(
    runtime_override: CodingAgentSessionRuntime | None,
) -> CodingAgentSessionCliHandler:
    """Create the public CLI handler for a workspace-scoped coding-agent session."""

    def run(
        command: CliCodingAgentSessionCommand | CliSessionRecordCommand,
        composition_options: CodingAgentSessionCliCompositionOptions,
        context: CommandContext,
    ) -> int:
        streams = CodingAgentSessionCliStreams(stdout=context.stdout, stderr=context.stderr)
        _warn_when_session_records_are_not_git_ignored(command.workspace_root, context.stderr)
        if isinstance(command, CliCodingAgentSessionCommand):
            return run_coding_agent_session_cli_command(
                command,
                streams=streams,
                runtime=runtime_override
                or _create_default_runtime(
                    workspace_root=command.workspace_root,
                    stdin=context.stdin,
                    stdout=context.stdout,
                    skill_roots=composition_options.skill_roots,
                ),
            )
        if command.operation != "resume":
            return run_session_record_cli_command(
                command,
                store=PosixSessionRecordStore(command.workspace_root),
                stdout=context.stdout,
                stderr=context.stderr,
            )
        return _run_resume(command, streams=streams, context=context, skill_roots=composition_options.skill_roots)

    return run


def _create_default_runtime(
    *,
    workspace_root: Path,
    stdin: TextIO,
    stdout: TextIO,
    skill_roots: tuple[Path, ...],
) -> CodingAgentSessionRuntime:
    """Create the default terminal session runtime after CLI validation."""
    return asyncio.run(
        create_terminal_workspace_coding_agent_session_runtime(
            workspace_root=workspace_root,
            stdin=stdin,
            stdout=stdout,
            skill_roots=skill_roots,
        )
    )


def _run_resume(
    command: CliSessionRecordCommand,
    *,
    streams: CodingAgentSessionCliStreams,
    context: CommandContext,
    skill_roots: tuple[Path, ...],
) -> int:
    session_id = command.session_id
    prompt = command.prompt
    if session_id is None or prompt is None:
        msg = "resume command was not fully validated"
        raise ValueError(msg)
    prepared = asyncio.run(
        prepare_terminal_workspace_coding_agent_session_resume_runtime(
            workspace_root=command.workspace_root,
            session_id=session_id,
            stdin=context.stdin,
            stdout=context.stdout,
            skill_roots=skill_roots,
        )
    )
    if prepared.preparation.disposition is ResumeDisposition.UNAVAILABLE:
        streams.stderr.write(f"session resume unavailable: {prepared.preparation.stale_context_reason}\n")
        return 3
    if prepared.preparation.disposition is ResumeDisposition.STALE_CONTEXT:
        if prepared.runtime is None:
            msg = "stale-context resume preparation did not produce a runtime"
            raise RuntimeError(msg)
        return _run_stale_context_replan(command, streams=streams, context=context, runtime=prepared.runtime)
    if prepared.runtime is None:
        msg = "normal resume preparation did not produce a runtime"
        raise RuntimeError(msg)
    return run_coding_agent_session_cli_command(
        CliCodingAgentSessionCommand(workspace_root=command.workspace_root, prompt=prompt),
        streams=streams,
        runtime=prepared.runtime,
    )


def _run_stale_context_replan(
    command: CliSessionRecordCommand,
    *,
    streams: CodingAgentSessionCliStreams,
    context: CommandContext,
    runtime: WorkspaceCodingAgentSessionRuntime,
) -> int:
    """Run an inspection-only replan turn before a separately acknowledged execution turn."""
    session_id = command.session_id
    prompt = command.prompt
    if session_id is None or prompt is None:
        msg = "stale-context replan command was not fully validated"
        raise ValueError(msg)
    gate = runtime.replan_safety_gate
    if gate is None:
        msg = "stale-context runtime omitted its replan safety gate"
        raise RuntimeError(msg)
    streams.stderr.write("session requires stale-context replan; inspect the current workspace before proposing work\n")
    planning_result = asyncio.run(
        runtime.run(
            CodingAgentSessionCommand(
                workspace_root=command.workspace_root,
                prompt=(
                    "The durable session context is stale. Inspect the current workspace using read_files or "
                    "search_codebase, then provide a concise refreshed plan. Do not attempt commands or patches "
                    "in this planning turn. Original request: "
                    f"{prompt}"
                ),
            )
        )
    )
    if gate.state is ReplanSafetyState.INSPECTION_REQUIRED:
        streams.stderr.write("stale-context replan blocked: fresh workspace inspection was not completed\n")
        return 3
    summary = planning_result.tool_loop_result.output_text
    if summary is None or not summary.strip():
        streams.stderr.write("stale-context replan blocked: refreshed plan was not produced\n")
        return 3
    plan_digest = f"sha256:{hashlib.sha256(summary.encode()).hexdigest()}"
    acknowledged = TerminalStaleContextReplanAcknowledgement(context.stdin, context.stdout, gate).acknowledge(
        summary=summary,
        plan_digest=plan_digest,
    )
    if not acknowledged:
        streams.stderr.write("stale-context replan acknowledgement was not granted\n")
        return 3
    return run_coding_agent_session_cli_command(
        CliCodingAgentSessionCommand(workspace_root=command.workspace_root, prompt=prompt),
        streams=streams,
        runtime=runtime,
    )


def _warn_when_session_records_are_not_git_ignored(workspace_root: Path, stderr: TextIO) -> None:
    """Warn for a Git workspace whose repository ignore file lacks a session-record entry."""
    repository_root = _git_repository_root(workspace_root)
    if repository_root is None or _gitignore_excludes_fabrica(repository_root / ".gitignore"):
        return
    stderr.write(
        "warning: .fabrica/ contains sensitive session records and is not Git-ignored; add .fabrica/ to .gitignore\n"
    )


def _git_repository_root(workspace_root: Path) -> Path | None:
    for candidate in (workspace_root, *workspace_root.parents):
        if (candidate / ".git").is_dir():
            return candidate
    return None


def _gitignore_excludes_fabrica(path: Path) -> bool:
    if not path.exists():
        return False
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except OSError:
        return False
    return any(line.strip() in {".fabrica", ".fabrica/", "/.fabrica", "/.fabrica/"} for line in lines)


__all__ = ["run_coding_agent_session_command"]
