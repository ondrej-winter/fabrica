"""Tests for the product CLI shell and feature command registrations."""

from __future__ import annotations

import sys
from dataclasses import FrozenInstanceError, dataclass
from io import StringIO
from pathlib import Path
from typing import TYPE_CHECKING, Any, cast

import pytest

from fabrica.adapters.inbound import cli
from fabrica.adapters.inbound.cli import (
    CliCommandRegistry,
    CliCommandSpec,
    CliExecutionContext,
    CliGlobalOptions,
    CliRegistrationError,
    CliUsageError,
    run_cli_shell,
    shell,
)
from fabrica.bootstrap.cli import create_cli_command_registrars, run_cli
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
    from collections.abc import Callable

    from fabrica.adapters.inbound.cli.contracts import CliCommandRegistrar

ARGPARSE_USAGE_ERROR = 2
SYNTHETIC_HANDLER_EXIT_CODE = 7
EXPECTED_CLI_PACKAGE_EXPORTS = [
    "CliCommandRegistrar",
    "CliCommandRegistry",
    "CliCommandSpec",
    "CliExecutionContext",
    "CliGlobalOptions",
    "CliRegistrationError",
    "CliUsageError",
    "run_cli_shell",
]
EXPECTED_CLI_SHELL_EXPORTS = ["run_cli_shell"]


def test_cli_package_exports_curated_command_shell_api() -> None:
    assert cli.__all__ == EXPECTED_CLI_PACKAGE_EXPORTS
    assert not hasattr(cli, "parse_cli_invocation")
    assert not hasattr(cli, "build_parser")
    assert not hasattr(cli, "execute_cli_invocation")


def test_cli_shell_exports_only_supported_shell_boundary() -> None:
    assert shell.__all__ == EXPECTED_CLI_SHELL_EXPORTS
    assert not hasattr(shell, "build_parser")
    assert not hasattr(shell, "parse_cli_invocation")


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


def parse_args(args: tuple[str, ...] | list[str]) -> ParsedInvocation:
    handlers = RecordingHandlers()
    exit_code = run_cli_shell(
        args,
        command_registrars=_recording_command_registrars(handlers),
        stdin=StringIO(),
        stdout=sys.stdout,
        stderr=sys.stderr,
    )

    if exit_code != 0:
        raise SystemExit(exit_code)
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


def test_run_cli_shell_round_trips_bound_handler() -> None:
    handlers = RecordingHandlers()
    exit_code = run_cli_shell(
        ("synthetic",),
        command_registrars=(_synthetic_command_registrar(handlers),),
        stdin=StringIO(),
        stdout=StringIO(),
        stderr=StringIO(),
    )

    assert exit_code == 0
    assert handlers.invocation == ParsedInvocation(
        command="synthetic",
        global_options=CliGlobalOptions(),
        composition_options=None,
    )


def _synthetic_command_registrar(handlers: RecordingHandlers) -> CliCommandRegistrar:
    def register(commands: CliCommandRegistry) -> None:
        commands.register(
            _synthetic_command_with_handler(_synthetic_handler(handlers)),
        )

    return register


def _register_synthetic_command(commands: CliCommandRegistry) -> None:
    commands.register(_synthetic_command_spec())


def _synthetic_command_spec() -> CliCommandSpec[str]:
    return CliCommandSpec(
        name="synthetic",
        summary="synthetic command",
        configure_parser=_configure_noop_synthetic_parser,
        decode=_decode_synthetic_command,
        handler=_noop_synthetic_handler,
    )


def _synthetic_command_with_parser(
    configure_parser: Callable[[argparse.ArgumentParser], None],
) -> CliCommandSpec[str]:
    return CliCommandSpec(
        name="synthetic",
        summary="synthetic command",
        configure_parser=configure_parser,
        decode=_decode_synthetic_command,
        handler=_noop_synthetic_handler,
    )


def _synthetic_command_with_decode(decode: Callable[[argparse.Namespace], str]) -> CliCommandSpec[str]:
    return CliCommandSpec(
        name="synthetic",
        summary="synthetic command",
        configure_parser=_configure_noop_synthetic_parser,
        decode=decode,
        handler=_noop_synthetic_handler,
    )


def _synthetic_command_with_handler(handler: Callable[[str, CliExecutionContext], int]) -> CliCommandSpec[str]:
    return CliCommandSpec(
        name="synthetic",
        summary="synthetic command",
        configure_parser=_configure_noop_synthetic_parser,
        decode=_decode_synthetic_command,
        handler=handler,
    )


def _configure_noop_synthetic_parser(parser: argparse.ArgumentParser) -> None:
    _ = parser


def _decode_synthetic_command(namespace: argparse.Namespace) -> str:
    assert not hasattr(namespace, "cli_decoder")
    assert not hasattr(namespace, "cli_handler")
    assert not hasattr(namespace, "_fabrica_cli_command")
    assert not hasattr(namespace, "_fabrica_cli_print_usage")
    assert not hasattr(namespace, "_fabrica_cli_print_prices")
    assert not hasattr(namespace, "_fabrica_cli_verbose_diagnostics")
    return "synthetic"


def _noop_synthetic_handler(command: str, context: CliExecutionContext) -> int:
    _ = (command, context)
    return 0


def _system_exit_synthetic_handler(command: str, context: CliExecutionContext) -> int:
    _ = (command, context)
    raise SystemExit(SYNTHETIC_HANDLER_EXIT_CODE)


def _synthetic_handler(handlers: RecordingHandlers) -> Callable[[str, CliExecutionContext], int]:
    def run(command: str, context: CliExecutionContext) -> int:
        handlers.invocation = ParsedInvocation(
            command=command,
            global_options=context.global_options,
            composition_options=None,
        )
        return 0

    return run


def test_run_cli_shell_rejects_duplicate_command_registration() -> None:
    with pytest.raises(CliRegistrationError, match="CLI command 'synthetic' is already registered"):
        run_cli_shell(
            ("synthetic",),
            command_registrars=(_register_duplicate_synthetic_commands,),
            stdin=StringIO(),
            stdout=StringIO(),
            stderr=StringIO(),
        )


def _register_duplicate_synthetic_commands(commands: CliCommandRegistry) -> None:
    commands.register(_synthetic_command_spec())
    commands.register(_synthetic_command_spec())


def test_run_cli_shell_translates_argparse_registration_conflicts() -> None:
    def configure_conflicting_parser(parser: argparse.ArgumentParser) -> None:
        parser.add_argument("--print-usage")

    def register(commands: CliCommandRegistry) -> None:
        commands.register(_synthetic_command_with_parser(configure_conflicting_parser))

    with pytest.raises(CliRegistrationError, match="CLI command registration failed"):
        run_cli_shell(
            ("synthetic",),
            command_registrars=(register,),
            stdin=StringIO(),
            stdout=StringIO(),
            stderr=StringIO(),
        )


@pytest.mark.parametrize(
    "reserved_dest",
    [
        "_fabrica_cli_command",
        "_fabrica_cli_print_usage",
        "_fabrica_cli_print_prices",
        "_fabrica_cli_verbose_diagnostics",
    ],
)
def test_run_cli_shell_rejects_feature_arguments_using_reserved_shell_destinations(reserved_dest: str) -> None:
    def configure_reserved_parser(parser: argparse.ArgumentParser) -> None:
        parser.add_argument("--feature-value", dest=reserved_dest)

    def register(commands: CliCommandRegistry) -> None:
        commands.register(_synthetic_command_with_parser(configure_reserved_parser))

    with pytest.raises(CliRegistrationError, match="uses reserved parser destination"):
        run_cli_shell(
            ("synthetic",),
            command_registrars=(register,),
            stdin=StringIO(),
            stdout=StringIO(),
            stderr=StringIO(),
        )


def test_run_cli_does_not_swallow_handler_system_exit() -> None:
    def register(commands: CliCommandRegistry) -> None:
        commands.register(_synthetic_command_with_handler(_system_exit_synthetic_handler))

    with pytest.raises(SystemExit) as exc_info:
        run_cli_shell(
            ("synthetic",),
            command_registrars=(register,),
            stdin=StringIO(),
            stdout=StringIO(),
            stderr=StringIO(),
        )

    assert exc_info.value.code == SYNTHETIC_HANDLER_EXIT_CODE


def test_run_cli_shell_treats_cli_usage_error_as_usage_error() -> None:
    stderr = StringIO()

    def decode_user_error(namespace: argparse.Namespace) -> str:
        _ = namespace
        msg = "synthetic user error"
        raise CliUsageError(msg)

    def register(commands: CliCommandRegistry) -> None:
        commands.register(_synthetic_command_with_decode(decode_user_error))

    exit_code = run_cli_shell(
        ("synthetic",),
        command_registrars=(register,),
        stdin=StringIO(),
        stdout=StringIO(),
        stderr=stderr,
    )

    assert exit_code == ARGPARSE_USAGE_ERROR
    assert "synthetic user error" in stderr.getvalue()


def test_run_cli_shell_propagates_unexpected_decoder_value_error() -> None:
    def decode_programmer_error(namespace: argparse.Namespace) -> str:
        _ = namespace
        msg = "synthetic programmer error"
        raise ValueError(msg)

    def register(commands: CliCommandRegistry) -> None:
        commands.register(_synthetic_command_with_decode(decode_programmer_error))

    with pytest.raises(ValueError, match="synthetic programmer error"):
        run_cli_shell(
            ("synthetic",),
            command_registrars=(register,),
            stdin=StringIO(),
            stdout=StringIO(),
            stderr=StringIO(),
        )


def test_run_cli_routes_help_to_injected_stdout_without_raising() -> None:
    stdout = StringIO()
    stderr = StringIO()

    exit_code = run_cli(("--help",), stdout=stdout, stderr=stderr)

    assert exit_code == 0
    assert "Run local Fabrica workflows." in stdout.getvalue()
    assert "run" in stdout.getvalue()
    assert stderr.getvalue() == ""


def test_run_cli_routes_usage_errors_to_injected_stderr_without_raising() -> None:
    stdout = StringIO()
    stderr = StringIO()

    exit_code = run_cli(("run",), stdout=stdout, stderr=stderr)

    assert exit_code == ARGPARSE_USAGE_ERROR
    assert stdout.getvalue() == ""
    assert "error:" in stderr.getvalue()
    assert "--prompt" in stderr.getvalue()


def test_run_cli_routes_unknown_command_to_injected_stderr_without_raising() -> None:
    stdout = StringIO()
    stderr = StringIO()

    exit_code = run_cli(("unknown-command",), stdout=stdout, stderr=stderr)

    assert exit_code == ARGPARSE_USAGE_ERROR
    assert stdout.getvalue() == ""
    assert "invalid choice: 'unknown-command'" in stderr.getvalue()


def test_run_cli_shell_renders_help_without_runtime_side_effects() -> None:
    _clear_bootstrap_composition_modules()
    stdout = StringIO()
    stderr = StringIO()

    exit_code = run_cli_shell(
        ("--help",),
        command_registrars=create_cli_command_registrars(),
        stdin=StringIO(),
        stdout=stdout,
        stderr=stderr,
    )

    assert exit_code == 0
    assert stderr.getvalue() == ""
    assert "run" in stdout.getvalue()
    assert "commit" in stdout.getvalue()
    assert "commit-message" in stdout.getvalue()
    assert "script-policy" in stdout.getvalue()
    assert "script-execute" in stdout.getvalue()
    assert "--print-usage" in stdout.getvalue()
    assert "--print-prices" in stdout.getvalue()
    assert "--verbose-diagnostics" in stdout.getvalue()
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
    ("register", "expected_message"),
    [
        (
            lambda commands: commands.register(
                CliCommandSpec(
                    name="",
                    summary="synthetic command",
                    configure_parser=_configure_noop_synthetic_parser,
                    decode=_decode_synthetic_command,
                    handler=_noop_synthetic_handler,
                ),
            ),
            "name must be a non-empty trimmed value",
        ),
        (
            lambda commands: commands.register(
                CliCommandSpec(
                    name=" synthetic",
                    summary="synthetic command",
                    configure_parser=_configure_noop_synthetic_parser,
                    decode=_decode_synthetic_command,
                    handler=_noop_synthetic_handler,
                ),
            ),
            "name must be a non-empty trimmed value",
        ),
        (
            lambda commands: commands.register(
                CliCommandSpec(
                    name="Synthetic",
                    summary="synthetic command",
                    configure_parser=_configure_noop_synthetic_parser,
                    decode=_decode_synthetic_command,
                    handler=_noop_synthetic_handler,
                ),
            ),
            "name must be lowercase kebab-case",
        ),
        (
            lambda commands: commands.register(
                CliCommandSpec(
                    name="synthetic",
                    summary="",
                    configure_parser=_configure_noop_synthetic_parser,
                    decode=_decode_synthetic_command,
                    handler=_noop_synthetic_handler,
                ),
            ),
            "summary must be a non-empty trimmed value",
        ),
        (
            lambda commands: commands.register(
                CliCommandSpec(
                    name="synthetic",
                    summary="synthetic command",
                    configure_parser=_configure_noop_synthetic_parser,
                    decode=_decode_synthetic_command,
                    handler=_noop_synthetic_handler,
                    description=" synthetic description",
                ),
            ),
            "description must be a non-empty trimmed value",
        ),
        (
            lambda commands: commands.register(
                CliCommandSpec(
                    name="synthetic",
                    summary="synthetic command",
                    configure_parser=cast("Any", None),
                    decode=_decode_synthetic_command,
                    handler=_noop_synthetic_handler,
                ),
            ),
            "parser configurer must be callable",
        ),
        (
            lambda commands: commands.register(
                CliCommandSpec(
                    name="synthetic",
                    summary="synthetic command",
                    configure_parser=_configure_noop_synthetic_parser,
                    decode=cast("Any", None),
                    handler=_noop_synthetic_handler,
                ),
            ),
            "decoder must be callable",
        ),
        (
            lambda commands: commands.register(
                CliCommandSpec(
                    name="synthetic",
                    summary="synthetic command",
                    configure_parser=_configure_noop_synthetic_parser,
                    decode=_decode_synthetic_command,
                    handler=cast("Any", None),
                ),
            ),
            "handler must be callable",
        ),
    ],
)
def test_cli_command_registration_rejects_invalid_values(
    register: Callable[[CliCommandRegistry], None],
    expected_message: str,
) -> None:
    with pytest.raises(CliRegistrationError, match=expected_message):
        run_cli_shell(
            ("synthetic",),
            command_registrars=(register,),
            stdin=StringIO(),
            stdout=StringIO(),
            stderr=StringIO(),
        )


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


def test_commit_command_help_documents_mutating_pre_commit_gate() -> None:
    stdout = StringIO()
    stderr = StringIO()

    exit_code = run_cli_shell(
        ("commit", "--help"),
        command_registrars=create_cli_command_registrars(),
        stdin=StringIO(),
        stdout=stdout,
        stderr=stderr,
    )

    assert exit_code == 0
    assert stderr.getvalue() == ""
    assert "Run the staged pre-commit quality gate before message generation" in stdout.getvalue()
    assert "create a git commit only after approval" in stdout.getvalue()


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
