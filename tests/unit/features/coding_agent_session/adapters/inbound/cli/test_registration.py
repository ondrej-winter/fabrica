"""Tests for coding-agent-session CLI registration and workspace decoding."""

import sys
from dataclasses import dataclass
from io import StringIO
from pathlib import Path

import pytest

from fabrica.adapters.inbound.cli import CommandContext, CommandRegistrar, CommandRegistry, run_cli
from fabrica.features.coding_agent_session.adapters.inbound.cli import (
    CliCodingAgentSessionCommand,
    CliSelectedResource,
    CodingAgentSessionCliCompositionOptions,
    register_coding_agent_session_cli_commands,
)

ARGPARSE_USAGE_ERROR = 2


@dataclass(frozen=True, slots=True)
class ParsedInvocation:
    """Recorded feature command data for CLI decoding assertions."""

    command: CliCodingAgentSessionCommand
    composition_options: CodingAgentSessionCliCompositionOptions


@dataclass(slots=True)
class RecordingHandler:
    """Capture valid commands and fail if invalid parsing invokes the handler."""

    invocation: ParsedInvocation | None = None

    def run(
        self,
        command: CliCodingAgentSessionCommand,
        composition_options: CodingAgentSessionCliCompositionOptions,
        _context: CommandContext,
    ) -> int:
        self.invocation = ParsedInvocation(command=command, composition_options=composition_options)
        return 0


def test_agent_command_decodes_canonical_workspace_and_explicit_context(tmp_path: Path) -> None:
    handler = RecordingHandler()

    exit_code = _run(
        (
            "agent",
            "--workspace",
            str(tmp_path),
            "--prompt",
            "Inspect the parser",
            "--skill",
            "python-testing",
            "--resource",
            "python-testing:references/example.md",
            "--skill-root",
            "./skills",
        ),
        handler=handler,
    )

    assert exit_code == 0
    assert handler.invocation == ParsedInvocation(
        command=CliCodingAgentSessionCommand(
            workspace_root=tmp_path.resolve(),
            prompt="Inspect the parser",
            skill_ids=("python-testing",),
            resources=(CliSelectedResource(skill_id="python-testing", resource_id="references/example.md"),),
        ),
        composition_options=CodingAgentSessionCliCompositionOptions(skill_roots=(Path("./skills"),)),
    )


@pytest.mark.parametrize(
    ("args", "expected_message"),
    [
        (("agent", "--prompt", "Inspect"), "the following arguments are required: --workspace"),
        (("agent", "--workspace", "missing", "--prompt", "Inspect"), "workspace cannot be resolved"),
    ],
)
def test_agent_command_rejects_missing_or_unresolvable_workspace_before_handler_invocation(
    args: tuple[str, ...],
    expected_message: str,
    capsys: pytest.CaptureFixture[str],
) -> None:
    handler = RecordingHandler()

    exit_code = _run_with_process_streams(args, handler=handler)

    assert exit_code == ARGPARSE_USAGE_ERROR
    assert expected_message in capsys.readouterr().err
    assert handler.invocation is None


def test_agent_command_rejects_a_workspace_file_before_handler_invocation(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    workspace_file = tmp_path / "workspace-file"
    workspace_file.write_text("not a directory", encoding="utf-8")
    handler = RecordingHandler()

    exit_code = _run_with_process_streams(
        ("agent", "--workspace", str(workspace_file), "--prompt", "Inspect"), handler=handler
    )

    assert exit_code == ARGPARSE_USAGE_ERROR
    assert "workspace must be an existing directory" in capsys.readouterr().err
    assert handler.invocation is None


def _run(args: tuple[str, ...], *, handler: RecordingHandler) -> int:
    return run_cli(
        args,
        command_registrars=(_registrar(handler),),
        stdin=StringIO(),
        stdout=StringIO(),
        stderr=StringIO(),
    )


def _run_with_process_streams(args: tuple[str, ...], *, handler: RecordingHandler) -> int:
    return run_cli(
        args,
        command_registrars=(_registrar(handler),),
        stdin=StringIO(),
        stdout=sys.stdout,
        stderr=sys.stderr,
    )


def _registrar(handler: RecordingHandler) -> CommandRegistrar:
    def register(commands: CommandRegistry) -> None:
        register_coding_agent_session_cli_commands(commands, agent_command=handler.run)

    return register
