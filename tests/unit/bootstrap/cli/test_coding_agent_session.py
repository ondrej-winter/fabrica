"""Tests for bootstrap registration of the coding-agent session command."""

from dataclasses import dataclass, field
from io import StringIO
from pathlib import Path

from fabrica.bootstrap.cli import CliDependencyOverrides, run_cli
from fabrica.bootstrap.cli.features import coding_agent_session as coding_agent_session_bootstrap
from fabrica.features.agent_runtime.application.dtos import ToolCancellationSignal, ToolLoopRunResult, ToolLoopRunStatus
from fabrica.features.coding_agent_session.application.dtos import (
    CodingAgentSessionCommand,
    CodingAgentSessionRuntimeResult,
    MutationDisposition,
    MutationDispositionStatus,
    MutationGateEvidence,
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
        ("agent", "--workspace", str(tmp_path), "--prompt", "Inspect this workspace"),
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
        ("agent", "--workspace", "missing-workspace", "--prompt", "Inspect this workspace"),
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
        ("agent", "--workspace", str(tmp_path), "--prompt", "Inspect this workspace"),
        stdin=StringIO(),
        stdout=StringIO(),
        stderr=StringIO(),
    )

    assert exit_code == 0
    assert calls == [(tmp_path.resolve(), ())]
    assert runtime.calls == [
        CodingAgentSessionCommand(workspace_root=tmp_path.resolve(), prompt="Inspect this workspace")
    ]
