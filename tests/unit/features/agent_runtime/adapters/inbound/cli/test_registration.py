"""Tests for agent-runtime CLI command registration and decoding."""

from __future__ import annotations

import sys
from dataclasses import FrozenInstanceError, dataclass
from io import StringIO
from pathlib import Path
from typing import TYPE_CHECKING

import pytest

from fabrica.adapters.inbound.cli import CommandContext, CommandRegistrar, CommandRegistry, GlobalOptions, run_cli
from fabrica.features.agent_runtime.adapters.inbound.cli.command_models import (
    AgentRuntimeCliCompositionOptions,
    CliRunCommand,
    CliScriptExecuteCommand,
    CliScriptPolicyCommand,
    CliSelectedResource,
)
from fabrica.features.agent_runtime.adapters.inbound.cli.registration import register_agent_runtime_cli_commands
from fabrica.features.agent_runtime.application.dtos import SkillScriptApprovalBinding, SkillScriptType

if TYPE_CHECKING:
    from collections.abc import Sequence

ARGPARSE_USAGE_ERROR = 2


@dataclass(frozen=True, slots=True)
class ParsedInvocation:
    command: object
    global_options: GlobalOptions
    composition_options: AgentRuntimeCliCompositionOptions


@dataclass(slots=True)
class RecordingHandlers:
    invocation: ParsedInvocation | None = None

    def record_command(
        self,
        command: CliRunCommand | CliScriptPolicyCommand | CliScriptExecuteCommand,
        composition_options: AgentRuntimeCliCompositionOptions,
        context: CommandContext,
    ) -> int:
        self.invocation = ParsedInvocation(
            command=command,
            global_options=context.global_options,
            composition_options=composition_options,
        )
        return 0


def parse_args(args: Sequence[str]) -> ParsedInvocation:
    handlers = RecordingHandlers()
    exit_code = run_cli(
        args,
        command_registrars=(_recording_command_registrar(handlers),),
        stdin=StringIO(),
        stdout=sys.stdout,
        stderr=sys.stderr,
    )
    if exit_code != 0:
        raise SystemExit(exit_code)
    assert handlers.invocation is not None
    return handlers.invocation


def _recording_command_registrar(handlers: RecordingHandlers) -> CommandRegistrar:
    def register(commands: CommandRegistry) -> None:
        register_agent_runtime_cli_commands(
            commands,
            run_command=handlers.record_command,
            script_policy_command=handlers.record_command,
            script_execute_command=handlers.record_command,
        )

    return register


def test_parse_run_command_supports_prompt_and_explicit_context() -> None:
    invocation = parse_args(
        (
            "--print-usage",
            "--print-prices",
            "--verbose-diagnostics",
            "run",
            "--prompt",
            "Reply with pong",
            "--skill",
            "python-testing",
            "--skill",
            "code-review",
            "--resource",
            "python-testing:references/example.md",
            "--skill-root",
            "./skills",
        ),
    )

    assert invocation == ParsedInvocation(
        command=CliRunCommand(
            prompt="Reply with pong",
            skill_ids=("python-testing", "code-review"),
            resources=(CliSelectedResource(skill_id="python-testing", resource_id="references/example.md"),),
        ),
        global_options=GlobalOptions(print_usage=True, print_prices=True, verbose_diagnostics=True),
        composition_options=AgentRuntimeCliCompositionOptions(skill_roots=(Path("./skills"),)),
    )


def test_parse_run_command_uses_empty_explicit_context_defaults() -> None:
    invocation = parse_args(("run", "--prompt", "Reply with pong"))

    assert invocation == ParsedInvocation(
        command=CliRunCommand(prompt="Reply with pong"),
        global_options=GlobalOptions(),
        composition_options=AgentRuntimeCliCompositionOptions(),
    )


def test_parse_run_command_rejects_unsupported_model_override() -> None:
    with pytest.raises(SystemExit) as exc_info:
        parse_args(("run", "--prompt", "Reply with pong", "--model", "codex-compatible"))

    assert exc_info.value.code == ARGPARSE_USAGE_ERROR


def test_parse_run_command_rejects_malformed_resource_selection() -> None:
    with pytest.raises(SystemExit) as exc_info:
        parse_args(("run", "--prompt", "Reply with pong", "--resource", "python-testing"))

    assert exc_info.value.code == ARGPARSE_USAGE_ERROR


@pytest.mark.parametrize(
    ("args", "expected_message"),
    [
        (("run", "--prompt", ""), "prompt must not be empty"),
        (("run", "--prompt", "pong", "--skill", "../unsafe"), "skill_id must not contain traversal segments"),
        (
            ("run", "--prompt", "pong", "--resource", "python-testing:../unsafe"),
            "resource_id must not contain traversal segments",
        ),
        (
            ("script-policy", "--skill-id", "python-testing", "--script-id", "../unsafe.py"),
            "script_id must not contain traversal segments",
        ),
        (
            (
                "script-execute",
                "--skill-id",
                "python-testing",
                "--script-id",
                "scripts/check.py",
                "--approve-script-type",
                "python",
                "--approve-suffix",
                ".rb",
                "--approve-byte-size",
                "128",
                "--approve-content-digest",
                "sha256:abc123",
            ),
            "script suffix is not supported",
        ),
        (
            (
                "script-execute",
                "--skill-id",
                "python-testing",
                "--script-id",
                "scripts/check.py",
                "--approve-script-type",
                "python",
                "--approve-suffix",
                ".py",
                "--approve-byte-size",
                "128",
                "--approve-content-digest",
                "sha256:bad digest",
            ),
            "content_digest contains unsupported characters",
        ),
        (
            (
                "script-execute",
                "--skill-id",
                "python-testing",
                "--script-id",
                "scripts/check.py",
                "--approve-script-type",
                "python",
                "--approve-suffix",
                ".py",
                "--approve-byte-size",
                "not-an-int",
                "--approve-content-digest",
                "sha256:abc123",
            ),
            "invalid literal for int",
        ),
    ],
)
def test_parse_agent_runtime_commands_reject_invalid_boundary_values(
    args: tuple[str, ...],
    expected_message: str,
    capsys: pytest.CaptureFixture[str],
) -> None:
    with pytest.raises(SystemExit) as exc_info:
        parse_args(args)

    assert exc_info.value.code == ARGPARSE_USAGE_ERROR
    assert expected_message in capsys.readouterr().err


def test_parse_script_policy_command_supports_explicit_selected_script() -> None:
    invocation = parse_args(
        (
            "--verbose-diagnostics",
            "script-policy",
            "--skill-id",
            "python-testing",
            "--script-id",
            "scripts/check.py",
            "--skill-root",
            "./skills",
        ),
    )

    assert invocation == ParsedInvocation(
        command=CliScriptPolicyCommand(skill_id="python-testing", script_id="scripts/check.py"),
        global_options=GlobalOptions(verbose_diagnostics=True),
        composition_options=AgentRuntimeCliCompositionOptions(skill_roots=(Path("./skills"),)),
    )


def test_parse_script_execute_command_requires_metadata_bound_approval() -> None:
    invocation = parse_args(
        (
            "--verbose-diagnostics",
            "script-execute",
            "--skill-id",
            "python-testing",
            "--script-id",
            "scripts/check.py",
            "--approve-script-type",
            "python",
            "--approve-suffix",
            ".py",
            "--approve-byte-size",
            "128",
            "--approve-content-digest",
            "sha256:abc123",
            "--skill-root",
            "./skills",
        ),
    )

    assert invocation == ParsedInvocation(
        command=CliScriptExecuteCommand(
            skill_id="python-testing",
            script_id="scripts/check.py",
            approval_binding=SkillScriptApprovalBinding(
                skill_id="python-testing",
                script_id="scripts/check.py",
                script_type=SkillScriptType.PYTHON,
                suffix=".py",
                byte_size=128,
                content_digest="sha256:abc123",
            ),
        ),
        global_options=GlobalOptions(verbose_diagnostics=True),
        composition_options=AgentRuntimeCliCompositionOptions(skill_roots=(Path("./skills"),)),
    )


def test_parse_script_execute_command_rejects_missing_approval_metadata() -> None:
    with pytest.raises(SystemExit) as exc_info:
        parse_args(("script-execute", "--skill-id", "python-testing", "--script-id", "scripts/check.py"))

    assert exc_info.value.code == ARGPARSE_USAGE_ERROR


def test_parsed_agent_runtime_commands_are_immutable_boundary_values() -> None:
    run_invocation = parse_args(("run", "--prompt", "Reply with pong"))
    context_invocation = parse_args(
        (
            "run",
            "--prompt",
            "Reply with pong",
            "--skill",
            "python-testing",
            "--resource",
            "python-testing:references/example.md",
            "--skill-root",
            "./skills",
        ),
    )
    policy_invocation = parse_args(
        ("script-policy", "--skill-id", "python-testing", "--script-id", "scripts/check.py"),
    )
    execution_invocation = parse_args(
        (
            "script-execute",
            "--skill-id",
            "python-testing",
            "--script-id",
            "scripts/check.py",
            "--approve-script-type",
            "python",
            "--approve-suffix",
            ".py",
            "--approve-byte-size",
            "128",
            "--approve-content-digest",
            "sha256:abc123",
        ),
    )

    with pytest.raises(FrozenInstanceError):
        setattr(run_invocation.command, "prompt", "changed")  # noqa: B010
    assert isinstance(context_invocation.command, CliRunCommand)
    assert isinstance(context_invocation.command.skill_ids, tuple)
    assert isinstance(context_invocation.command.resources, tuple)
    assert isinstance(context_invocation.composition_options.skill_roots, tuple)
    with pytest.raises(FrozenInstanceError):
        setattr(context_invocation.composition_options, "skill_roots", ())  # noqa: B010
    with pytest.raises(FrozenInstanceError):
        setattr(policy_invocation.command, "script_id", "changed")  # noqa: B010
    with pytest.raises(FrozenInstanceError):
        setattr(execution_invocation.command, "script_id", "changed")  # noqa: B010
