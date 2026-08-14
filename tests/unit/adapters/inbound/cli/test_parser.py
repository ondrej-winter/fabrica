"""Tests for the product CLI parser and feature command registrations."""

from __future__ import annotations

import sys
from dataclasses import FrozenInstanceError, dataclass
from io import StringIO
from pathlib import Path
from typing import TYPE_CHECKING

import pytest

from fabrica.adapters.inbound import cli
from fabrica.adapters.inbound.cli import (
    CliCommandHandler,
    CliCommandRegistration,
    CliCommandRegistry,
    CliConfigurationError,
    CliExecutionContext,
    CliGlobalOptions,
)
from fabrica.adapters.inbound.cli.parser import (
    build_parser as _build_parser,
)
from fabrica.adapters.inbound.cli.parser import (
    parse_cli_invocation as _parse_cli_invocation,
)
from fabrica.bootstrap.cli import create_cli_command_registrars
from fabrica.features.agent_runtime.adapters.inbound.cli.command_models import (
    AgentRuntimeCliCompositionOptions,
    CliRunCommand,
    CliScriptApprovalOptions,
    CliScriptExecuteCommand,
    CliScriptPolicyCommand,
    CliSelectedResource,
)
from fabrica.features.agent_runtime.adapters.inbound.cli.registration import register_agent_runtime_cli_commands
from fabrica.features.agent_runtime.application.dtos import SkillScriptApprovalBinding, SkillScriptType
from fabrica.features.developer_workflow.adapters.inbound.cli.command_models import (
    CliCommitCommand,
    CliCommitMessageCommand,
    CliDeveloperWorkflowCompositionOptions,
)
from fabrica.features.developer_workflow.adapters.inbound.cli.registration import (
    register_developer_workflow_cli_commands,
)

if TYPE_CHECKING:
    import argparse

    from fabrica.adapters.inbound.cli.contracts import CliCommandRegistrar

ARGPARSE_USAGE_ERROR = 2
EXPECTED_CLI_PACKAGE_EXPORTS = [
    "CliArgumentConfigurer",
    "CliCommandDecoder",
    "CliCommandHandler",
    "CliCommandRegistrar",
    "CliCommandRegistration",
    "CliCommandRegistry",
    "CliConfigurationError",
    "CliError",
    "CliExecutionContext",
    "CliGlobalOptions",
    "CliInvocation",
]


def test_cli_package_exports_only_registration_contracts() -> None:
    assert cli.__all__ == EXPECTED_CLI_PACKAGE_EXPORTS
    assert not hasattr(cli, "build_parser")
    assert not hasattr(cli, "parse_cli_invocation")


@dataclass(frozen=True, slots=True)
class ParsedInvocation:
    """Test-only view of what a parser-attached handler receives."""

    command: object
    global_options: CliGlobalOptions
    composition_options: object


@dataclass(slots=True)
class RecordingHandlers:
    """Record one parsed command without running real composition."""

    invocation: ParsedInvocation | None = None

    def record_agent_runtime_command(
        self,
        command: CliRunCommand | CliScriptPolicyCommand | CliScriptExecuteCommand,
        composition_options: AgentRuntimeCliCompositionOptions,
        context: CliExecutionContext,
    ) -> int:
        self.invocation = ParsedInvocation(
            command=command,
            global_options=context.global_options,
            composition_options=composition_options,
        )
        return 0

    def record_developer_workflow_command(
        self,
        command: CliCommitMessageCommand | CliCommitCommand,
        composition_options: CliDeveloperWorkflowCompositionOptions,
        context: CliExecutionContext,
    ) -> int:
        self.invocation = ParsedInvocation(
            command=command,
            global_options=context.global_options,
            composition_options=composition_options,
        )
        return 0


def build_parser():
    return _build_parser(create_cli_command_registrars())


def parse_args(args: tuple[str, ...] | list[str]) -> ParsedInvocation:
    handlers = RecordingHandlers()
    invocation = _parse_cli_invocation(args, command_registrars=_recording_command_registrars(handlers))
    exit_code = invocation.execute(stdin=StringIO(), stdout=StringIO(), stderr=StringIO())

    assert exit_code == 0
    assert handlers.invocation is not None
    return handlers.invocation


def _recording_command_registrars(handlers: RecordingHandlers) -> tuple[CliCommandRegistrar, ...]:
    return (
        lambda subparsers: register_agent_runtime_cli_commands(
            subparsers,
            run_command=handlers.record_agent_runtime_command,
            script_policy_command=handlers.record_agent_runtime_command,
            script_execute_command=handlers.record_agent_runtime_command,
        ),
        lambda subparsers: register_developer_workflow_cli_commands(
            subparsers,
            commit_message_command=handlers.record_developer_workflow_command,
            commit_command=handlers.record_developer_workflow_command,
        ),
    )


def test_parse_cli_invocation_round_trips_bound_handler() -> None:
    handlers = RecordingHandlers()
    invocation = _parse_cli_invocation(
        ("synthetic",),
        command_registrars=(_synthetic_command_registrar(handlers),),
    )
    exit_code = invocation.execute(stdin=StringIO(), stdout=StringIO(), stderr=StringIO())

    assert exit_code == 0
    assert handlers.invocation == ParsedInvocation(
        command="synthetic",
        global_options=CliGlobalOptions(),
        composition_options=None,
    )


def _synthetic_command_registrar(handlers: RecordingHandlers) -> CliCommandRegistrar:
    def register(commands: CliCommandRegistry) -> None:
        commands.register_command(
            CliCommandRegistration(
                name="synthetic",
                summary="synthetic command",
                configure_parser=_configure_noop_synthetic_parser,
                decode=_decode_synthetic_command,
                handler=_synthetic_handler(handlers),
            ),
        )

    return register


def _register_synthetic_command(commands: CliCommandRegistry) -> None:
    commands.register_command(
        CliCommandRegistration(
            name="synthetic",
            summary="synthetic command",
            configure_parser=_configure_noop_synthetic_parser,
            decode=_decode_synthetic_command,
            handler=_noop_synthetic_handler,
        ),
    )


def _configure_noop_synthetic_parser(parser: argparse.ArgumentParser) -> None:
    _ = parser


def _decode_synthetic_command(namespace: argparse.Namespace) -> str:
    _ = namespace
    return "synthetic"


def _noop_synthetic_handler(command: str, context: CliExecutionContext) -> int:
    _ = (command, context)
    return 0


def _synthetic_handler(handlers: RecordingHandlers) -> CliCommandHandler[str]:
    def run(command: str, context: CliExecutionContext) -> int:
        handlers.invocation = ParsedInvocation(
            command=command,
            global_options=context.global_options,
            composition_options=None,
        )
        return 0

    return run


def test_parse_cli_invocation_rejects_duplicate_command_registration() -> None:
    with pytest.raises(CliConfigurationError, match="CLI command registration failed"):
        _parse_cli_invocation(("synthetic",), command_registrars=(_register_duplicate_synthetic_commands,))


def _register_duplicate_synthetic_commands(commands: CliCommandRegistry) -> None:
    commands.register_command(
        CliCommandRegistration(
            name="synthetic",
            summary="synthetic command",
            configure_parser=_configure_noop_synthetic_parser,
            decode=_decode_synthetic_command,
            handler=_noop_synthetic_handler,
        ),
    )
    commands.register_command(
        CliCommandRegistration(
            name="synthetic",
            summary="synthetic command",
            configure_parser=_configure_noop_synthetic_parser,
            decode=_decode_synthetic_command,
            handler=_noop_synthetic_handler,
        ),
    )


def test_build_parser_renders_help_without_runtime_side_effects(capsys: pytest.CaptureFixture[str]) -> None:
    _clear_bootstrap_composition_modules()
    parser = build_parser()

    with pytest.raises(SystemExit) as exc_info:
        parser.parse_args(["--help"])

    assert exc_info.value.code == 0
    captured = capsys.readouterr()
    assert "run" in captured.out
    assert "commit" in captured.out
    assert "commit-message" in captured.out
    assert "script-policy" in captured.out
    assert "script-execute" in captured.out
    assert "--print-usage" in captured.out
    assert "--print-prices" in captured.out
    assert "--verbose-diagnostics" in captured.out
    assert "fabrica.bootstrap.composition.codex_runtime" not in sys.modules
    assert "fabrica.bootstrap.composition.developer_workflow" not in sys.modules
    assert "fabrica.bootstrap.composition.skill_context" not in sys.modules
    assert "fabrica.bootstrap.composition.skill_scripts" not in sys.modules


def _clear_bootstrap_composition_modules() -> None:
    for module_name in tuple(sys.modules):
        if module_name.startswith("fabrica.bootstrap.composition"):
            del sys.modules[module_name]


def test_parse_run_command_supports_prompt_model_and_explicit_context() -> None:
    invocation = parse_args(
        [
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
        ],
    )

    assert invocation == ParsedInvocation(
        command=CliRunCommand(
            prompt="Reply with pong",
            skill_ids=("python-testing", "code-review"),
            resources=(CliSelectedResource(skill_id="python-testing", resource_id="references/example.md"),),
        ),
        global_options=CliGlobalOptions(print_usage=True, print_prices=True, verbose_diagnostics=True),
        composition_options=AgentRuntimeCliCompositionOptions(skill_roots=(Path("./skills"),)),
    )


def test_parse_run_command_uses_empty_explicit_context_defaults() -> None:
    invocation = parse_args(["run", "--prompt", "Reply with pong"])

    assert invocation == ParsedInvocation(
        command=CliRunCommand(prompt="Reply with pong"),
        global_options=CliGlobalOptions(),
        composition_options=AgentRuntimeCliCompositionOptions(),
    )


def test_parse_run_command_rejects_unsupported_model_override() -> None:
    with pytest.raises(SystemExit) as exc_info:
        parse_args(["run", "--prompt", "Reply with pong", "--model", "codex-compatible"])

    assert exc_info.value.code == ARGPARSE_USAGE_ERROR


def test_parse_commit_message_command_defaults_to_conventional_commits_skill() -> None:
    invocation = parse_args(["commit-message"])

    assert invocation == ParsedInvocation(
        command=CliCommitMessageCommand(skill_id="conventional-commits"),
        global_options=CliGlobalOptions(),
        composition_options=CliDeveloperWorkflowCompositionOptions(),
    )


def test_parse_commit_message_command_supports_skill_root_and_diagnostics_overrides() -> None:
    invocation = parse_args(
        [
            "--verbose-diagnostics",
            "commit-message",
            "--skill",
            "team-style",
            "--model",
            "gpt-5.6-sol",
            "--reasoning-effort",
            "medium",
            "--skill-root",
            "./skills",
        ],
    )
    assert invocation == ParsedInvocation(
        command=CliCommitMessageCommand(skill_id="team-style"),
        global_options=CliGlobalOptions(verbose_diagnostics=True),
        composition_options=CliDeveloperWorkflowCompositionOptions(
            model="gpt-5.6-sol",
            reasoning_effort="medium",
            skill_roots=(Path("./skills"),),
        ),
    )


def test_parse_command_accepts_global_options_after_subcommand() -> None:
    invocation = parse_args(["commit-message", "--verbose-diagnostics"])

    assert invocation == ParsedInvocation(
        command=CliCommitMessageCommand(skill_id="conventional-commits"),
        global_options=CliGlobalOptions(verbose_diagnostics=True),
        composition_options=CliDeveloperWorkflowCompositionOptions(),
    )


@pytest.mark.parametrize(
    ("registration", "expected_message"),
    [
        (
            CliCommandRegistration(
                name="",
                summary="synthetic command",
                configure_parser=_configure_noop_synthetic_parser,
                decode=_decode_synthetic_command,
                handler=_noop_synthetic_handler,
            ),
            "name must be a non-empty trimmed value",
        ),
        (
            CliCommandRegistration(
                name=" synthetic",
                summary="synthetic command",
                configure_parser=_configure_noop_synthetic_parser,
                decode=_decode_synthetic_command,
                handler=_noop_synthetic_handler,
            ),
            "name must be a non-empty trimmed value",
        ),
        (
            CliCommandRegistration(
                name="synthetic",
                summary="",
                configure_parser=_configure_noop_synthetic_parser,
                decode=_decode_synthetic_command,
                handler=_noop_synthetic_handler,
            ),
            "summary must be a non-empty trimmed value",
        ),
    ],
)
def test_parse_cli_invocation_rejects_invalid_command_registration(
    registration: CliCommandRegistration,
    expected_message: str,
) -> None:
    def register_invalid_command(commands: CliCommandRegistry) -> None:
        commands.register_command(registration)

    with pytest.raises(CliConfigurationError, match=expected_message):
        _parse_cli_invocation(("synthetic",), command_registrars=(register_invalid_command,))


def test_parse_commit_message_command_supports_usage_and_price_reporting() -> None:
    invocation = parse_args(["--print-usage", "--print-prices", "commit-message"])

    assert invocation == ParsedInvocation(
        command=CliCommitMessageCommand(skill_id="conventional-commits"),
        global_options=CliGlobalOptions(print_usage=True, print_prices=True),
        composition_options=CliDeveloperWorkflowCompositionOptions(),
    )


def test_parse_commit_message_command_rejects_unknown_reasoning_effort() -> None:
    with pytest.raises(SystemExit) as exc_info:
        parse_args(["commit-message", "--reasoning-effort", "very-high"])

    assert exc_info.value.code == ARGPARSE_USAGE_ERROR


@pytest.mark.parametrize(
    ("args", "expected_message"),
    [
        (("commit-message", "--skill", ""), "skill_id must not be empty"),
        (("commit", "--skill", "   "), "skill_id must not be empty"),
    ],
)
def test_parse_developer_workflow_commands_reject_invalid_boundary_values(
    args: tuple[str, ...],
    expected_message: str,
    capsys: pytest.CaptureFixture[str],
) -> None:
    with pytest.raises(SystemExit) as exc_info:
        parse_args(args)

    assert exc_info.value.code == ARGPARSE_USAGE_ERROR
    assert expected_message in capsys.readouterr().err


def test_parse_commit_command_defaults_to_conventional_commits_skill() -> None:
    invocation = parse_args(["commit"])

    assert invocation == ParsedInvocation(
        command=CliCommitCommand(skill_id="conventional-commits"),
        global_options=CliGlobalOptions(),
        composition_options=CliDeveloperWorkflowCompositionOptions(),
    )


def test_commit_command_help_documents_mutating_pre_commit_gate(capsys: pytest.CaptureFixture[str]) -> None:
    parser = build_parser()

    with pytest.raises(SystemExit) as exc_info:
        parser.parse_args(["commit", "--help"])

    assert exc_info.value.code == 0
    captured = capsys.readouterr()
    assert "Run the staged pre-commit quality gate before message generation" in captured.out
    assert "create a git commit only after approval" in captured.out


def test_parse_commit_command_supports_commit_message_generation_options() -> None:
    invocation = parse_args(
        [
            "--verbose-diagnostics",
            "commit",
            "--skill",
            "team-style",
            "--model",
            "gpt-5.6-sol",
            "--reasoning-effort",
            "medium",
            "--skill-root",
            "./skills",
        ],
    )

    assert invocation == ParsedInvocation(
        command=CliCommitCommand(skill_id="team-style"),
        global_options=CliGlobalOptions(verbose_diagnostics=True),
        composition_options=CliDeveloperWorkflowCompositionOptions(
            model="gpt-5.6-sol",
            reasoning_effort="medium",
            skill_roots=(Path("./skills"),),
        ),
    )


def test_parse_commit_command_rejects_unknown_reasoning_effort() -> None:
    with pytest.raises(SystemExit) as exc_info:
        parse_args(["commit", "--reasoning-effort", "very-high"])

    assert exc_info.value.code == ARGPARSE_USAGE_ERROR


def test_parse_run_command_rejects_malformed_resource_selection() -> None:
    with pytest.raises(SystemExit) as exc_info:
        parse_args(["run", "--prompt", "Reply with pong", "--resource", "python-testing"])

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
        [
            "--verbose-diagnostics",
            "script-policy",
            "--skill-id",
            "python-testing",
            "--script-id",
            "scripts/check.py",
            "--skill-root",
            "./skills",
        ],
    )

    assert invocation == ParsedInvocation(
        command=CliScriptPolicyCommand(skill_id="python-testing", script_id="scripts/check.py"),
        global_options=CliGlobalOptions(verbose_diagnostics=True),
        composition_options=AgentRuntimeCliCompositionOptions(skill_roots=(Path("./skills"),)),
    )


def test_parse_script_execute_command_requires_metadata_bound_approval() -> None:
    invocation = parse_args(
        [
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
        ],
    )

    assert invocation == ParsedInvocation(
        command=CliScriptExecuteCommand(
            skill_id="python-testing",
            script_id="scripts/check.py",
            approval_options=CliScriptApprovalOptions(
                script_type=SkillScriptType.PYTHON,
                suffix=".py",
                byte_size=128,
                content_digest="sha256:abc123",
            ),
            approval_binding=SkillScriptApprovalBinding(
                skill_id="python-testing",
                script_id="scripts/check.py",
                script_type=SkillScriptType.PYTHON,
                suffix=".py",
                byte_size=128,
                content_digest="sha256:abc123",
            ),
        ),
        global_options=CliGlobalOptions(verbose_diagnostics=True),
        composition_options=AgentRuntimeCliCompositionOptions(skill_roots=(Path("./skills"),)),
    )


def test_parse_script_execute_command_rejects_missing_approval_metadata() -> None:
    with pytest.raises(SystemExit) as exc_info:
        parse_args(["script-execute", "--skill-id", "python-testing", "--script-id", "scripts/check.py"])

    assert exc_info.value.code == ARGPARSE_USAGE_ERROR


def test_parsed_commands_are_immutable_boundary_values() -> None:
    run_invocation = parse_args(["run", "--prompt", "Reply with pong"])
    policy_invocation = parse_args(
        ["script-policy", "--skill-id", "python-testing", "--script-id", "scripts/check.py"],
    )
    execution_invocation = parse_args(
        [
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
        ],
    )
    commit_message_invocation = parse_args(["commit-message"])
    commit_invocation = parse_args(["commit"])

    with pytest.raises(FrozenInstanceError):
        setattr(run_invocation.command, "prompt", "changed")  # noqa: B010
    with pytest.raises(FrozenInstanceError):
        setattr(policy_invocation.command, "script_id", "changed")  # noqa: B010
    with pytest.raises(FrozenInstanceError):
        setattr(execution_invocation.command, "script_id", "changed")  # noqa: B010
    with pytest.raises(FrozenInstanceError):
        setattr(commit_message_invocation.command, "skill_id", "changed")  # noqa: B010
    with pytest.raises(FrozenInstanceError):
        setattr(commit_invocation.command, "skill_id", "changed")  # noqa: B010
