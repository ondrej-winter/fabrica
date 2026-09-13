"""Tests for bootstrap registration of the coding-agent session command."""

from dataclasses import dataclass, field
from io import StringIO
from pathlib import Path

from fabrica.bootstrap.cli import CliDependencyOverrides, run_cli
from fabrica.bootstrap.cli.features import coding_agent_session as coding_agent_session_bootstrap
from fabrica.bootstrap.composition.coding_agent_session import (
    WorkspaceCodingAgentSessionRuntime,
    WorkspaceSessionResumeRuntimePreparation,
)
from fabrica.features.agent_runtime.application.dtos import (
    ToolCancellationSignal,
    ToolDefinition,
    ToolLoopRunResult,
    ToolLoopRunStatus,
)
from fabrica.features.agent_session.adapters.outbound.posix_filesystem import PosixSessionRecordStore
from fabrica.features.agent_session.application import ResumeDisposition, SessionResumePreparation
from fabrica.features.agent_session.application.dtos import SessionEvent
from fabrica.features.coding_agent_session.adapters.inbound.cli.output import EXIT_CODE_BY_SESSION_STATUS
from fabrica.features.coding_agent_session.application.dtos import (
    CodingAgentSessionCommand,
    CodingAgentSessionRuntimeResult,
    MutationDisposition,
    MutationDispositionStatus,
    MutationGateEvidence,
    SessionStatus,
)

ARGPARSE_USAGE_ERROR_EXIT_CODE = 2


@dataclass
class FakeSessionRuntime:
    """Record the public entrypoint command without constructing production dependencies."""

    calls: list[CodingAgentSessionCommand] = field(default_factory=list)

    async def run(
        self,
        command: CodingAgentSessionCommand,
        *,
        cancellation: ToolCancellationSignal | None = None,
    ) -> CodingAgentSessionRuntimeResult:
        del cancellation
        self.calls.append(command)
        return CodingAgentSessionRuntimeResult(
            tool_loop_result=ToolLoopRunResult(status=ToolLoopRunStatus.SUCCESS, output_text="Session complete."),
            mutation_gate=MutationGateEvidence(mutation_enabled=True),
            mutation_disposition=MutationDisposition(MutationDispositionStatus.NOT_ATTEMPTED),
        )


def test_public_cli_registers_agent_and_invokes_injected_session_runtime(tmp_path: Path) -> None:
    runtime = FakeSessionRuntime()
    stdout = StringIO()

    exit_code = run_cli(
        ("agent", "start", "--workspace", str(tmp_path), "--prompt", "Inspect this workspace"),
        overrides=CliDependencyOverrides(coding_agent_session_runtime=runtime),
        stdin=StringIO(),
        stdout=stdout,
        stderr=StringIO(),
    )

    assert exit_code == 0
    assert runtime.calls == [
        CodingAgentSessionCommand(workspace_root=tmp_path.resolve(), prompt="Inspect this workspace")
    ]
    assert stdout.getvalue() == "Session complete.\nMutation disposition: not_attempted\nSession status: completed\n"


def test_invalid_agent_workspace_does_not_construct_or_invoke_session_runtime() -> None:
    runtime = FakeSessionRuntime()
    stderr = StringIO()

    exit_code = run_cli(
        ("agent", "start", "--workspace", "missing-workspace", "--prompt", "Inspect this workspace"),
        overrides=CliDependencyOverrides(coding_agent_session_runtime=runtime),
        stdin=StringIO(),
        stdout=StringIO(),
        stderr=stderr,
    )

    assert exit_code == ARGPARSE_USAGE_ERROR_EXIT_CODE
    assert "workspace cannot be resolved" in stderr.getvalue()
    assert runtime.calls == []


def test_agent_uses_default_runtime_factory_when_no_override_is_supplied(monkeypatch, tmp_path: Path) -> None:
    runtime = FakeSessionRuntime()
    calls: list[tuple[Path, tuple[Path, ...]]] = []

    def create_runtime(*, workspace_root: Path, skill_roots: tuple[Path, ...], **_kwargs: object) -> FakeSessionRuntime:
        calls.append((workspace_root, skill_roots))
        return runtime

    monkeypatch.setattr(coding_agent_session_bootstrap, "_create_default_runtime", create_runtime)

    exit_code = run_cli(
        ("agent", "start", "--workspace", str(tmp_path), "--prompt", "Inspect this workspace"),
        stdin=StringIO(),
        stdout=StringIO(),
        stderr=StringIO(),
    )

    assert exit_code == 0
    assert calls == [(tmp_path.resolve(), ())]
    assert runtime.calls == [
        CodingAgentSessionCommand(workspace_root=tmp_path.resolve(), prompt="Inspect this workspace")
    ]


def test_public_cli_lists_workspace_local_durable_sessions(tmp_path: Path) -> None:
    PosixSessionRecordStore(tmp_path).append_event(SessionEvent("session-one", 0, "completed"))
    stdout = StringIO()

    exit_code = run_cli(
        ("agent", "sessions", "list", "--workspace", str(tmp_path)),
        stdin=StringIO(),
        stdout=stdout,
        stderr=StringIO(),
    )

    assert exit_code == 0
    assert stdout.getvalue() == "session-one\n"


def test_public_cli_warns_when_session_records_are_not_git_ignored(tmp_path: Path) -> None:
    (tmp_path / ".git").mkdir()
    stderr = StringIO()

    exit_code = run_cli(
        ("agent", "sessions", "list", "--workspace", str(tmp_path)),
        stdin=StringIO(),
        stdout=StringIO(),
        stderr=stderr,
    )

    assert exit_code == 0
    assert stderr.getvalue() == (
        "warning: .fabrica/ contains sensitive session records and is not Git-ignored; add .fabrica/ to .gitignore\n"
    )


def test_public_cli_does_not_warn_without_a_git_repository_or_with_an_ignore_entry(tmp_path: Path) -> None:
    no_repository_stderr = StringIO()
    no_repository_exit_code = run_cli(
        ("agent", "sessions", "list", "--workspace", str(tmp_path)),
        stdin=StringIO(),
        stdout=StringIO(),
        stderr=no_repository_stderr,
    )
    (tmp_path / ".git").mkdir()
    (tmp_path / ".gitignore").write_text(".fabrica/\n", encoding="utf-8")
    ignored_stderr = StringIO()
    ignored_exit_code = run_cli(
        ("agent", "sessions", "list", "--workspace", str(tmp_path)),
        stdin=StringIO(),
        stdout=StringIO(),
        stderr=ignored_stderr,
    )

    assert (no_repository_exit_code, ignored_exit_code) == (0, 0)
    assert no_repository_stderr.getvalue() == ""
    assert ignored_stderr.getvalue() == ""


def test_public_cli_fails_closed_for_stale_resume_without_running_a_session(monkeypatch, tmp_path: Path) -> None:
    runtime = FakeSessionRuntime()

    async def prepare_resume(**_kwargs: object):
        return WorkspaceSessionResumeRuntimePreparation(
            preparation=SessionResumePreparation(
                ResumeDisposition.STALE_CONTEXT,
                stale_context_reason="workspace fingerprint changed",
            ),
            runtime=WorkspaceCodingAgentSessionRuntime(
                workspace_root=tmp_path,
                runtime=_FakeInteractiveRuntime(),
                mutation_gate=MutationGateEvidence(mutation_enabled=True),
            ),
        )

    monkeypatch.setattr(
        coding_agent_session_bootstrap, "prepare_terminal_workspace_coding_agent_session_resume_runtime", prepare_resume
    )
    stderr = StringIO()

    exit_code = run_cli(
        (
            "agent",
            "sessions",
            "resume",
            "session-one",
            "--workspace",
            str(tmp_path),
            "--prompt",
            "Continue safely",
        ),
        overrides=CliDependencyOverrides(coding_agent_session_runtime=runtime),
        stdin=StringIO(),
        stdout=StringIO(),
        stderr=stderr,
    )

    assert exit_code == EXIT_CODE_BY_SESSION_STATUS[SessionStatus.FAILED]
    assert stderr.getvalue() == "session requires stale-context replan: workspace fingerprint changed\n"
    assert runtime.calls == []


class _FakeInteractiveRuntime:
    @property
    def available_tools(self) -> tuple[ToolDefinition, ...]:
        return ()

    async def run(
        self,
        command: object,
        *,
        cancellation: ToolCancellationSignal | None = None,
    ) -> ToolLoopRunResult:
        del command, cancellation
        return ToolLoopRunResult(status=ToolLoopRunStatus.SUCCESS)
