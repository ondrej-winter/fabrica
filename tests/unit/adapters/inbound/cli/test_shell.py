"""Tests for the product CLI shell and feature command registrations."""

from __future__ import annotations

import argparse
import sys
from dataclasses import FrozenInstanceError, dataclass
from io import StringIO
from pathlib import Path
from typing import TYPE_CHECKING, Any, TextIO, cast, get_type_hints

import pytest

from fabrica.adapters.inbound import cli
from fabrica.adapters.inbound.cli import (
    Command,
    CommandContext,
    CommandDecoder,
    CommandRegistrar,
    CommandRegistry,
    CommandRunner,
    GlobalOptions,
    ParserConfigurer,
    RegistrationError,
    UsageError,
)
from fabrica.adapters.inbound.cli import (
    run_cli as run_product_cli,
)
from fabrica.adapters.inbound.cli.registry import ArgparseCommandRegistry
from fabrica.adapters.inbound.cli.runtime import command_name_from_namespace
from fabrica.bootstrap.cli import create_cli_command_registrars
from fabrica.bootstrap.cli import run_cli as run_bootstrap_cli
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
    from collections.abc import Callable

ARGPARSE_USAGE_ERROR = 2
SYNTHETIC_HANDLER_EXIT_CODE = 7
EXPECTED_CLI_PACKAGE_EXPORTS = [
    "Command",
    "CommandContext",
    "CommandDecoder",
    "CommandRegistrar",
    "CommandRegistry",
    "CommandRunner",
    "GlobalOptions",
    "ParserConfigurer",
    "RegistrationError",
    "UsageError",
    "run_cli",
]


def test_cli_package_exports_curated_command_shell_api() -> None:
    assert cli.__all__ == EXPECTED_CLI_PACKAGE_EXPORTS
    assert not hasattr(cli, "parse_cli_invocation")
    assert not hasattr(cli, "build_parser")
    assert not hasattr(cli, "execute_cli_invocation")
    assert not hasattr(cli, "Invocation")
    assert not hasattr(cli, "parse_invocation")


def test_cli_registration_contract_annotations_are_runtime_resolvable() -> None:
    assert get_type_hints(Command)
    assert get_type_hints(CommandContext)["stdout"] is TextIO
    assert get_type_hints(run_product_cli)["return"] is int
    assert ParserConfigurer.__value__
    assert CommandDecoder.__value__
    assert CommandRunner.__value__


def test_cli_command_spec_requires_keyword_arguments() -> None:
    command_spec_factory = cast("Any", Command)

    with pytest.raises(TypeError, match="positional argument"):
        command_spec_factory(
            "synthetic",
            "synthetic command",
            _configure_noop_synthetic_parser,
            _decode_synthetic_command,
            _noop_synthetic_handler,
        )


@dataclass(frozen=True, slots=True)
class ParsedInvocation:
    """Test-only view of what a parser-attached handler receives."""

    command: object
    global_options: GlobalOptions
    composition_options: object


@dataclass(frozen=True, slots=True)
class SyntheticDecodedCommand:
    """Test-only immutable command decoded from a feature-only namespace."""

    global_options: GlobalOptions
    feature_value: str | None = None


@dataclass(slots=True)
class RecordingHandlers:
    """Record one parsed command without running real composition."""

    invocation: ParsedInvocation | None = None

    def record_agent_runtime_command(
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

    def record_developer_workflow_command(
        self,
        command: CliCommitMessageCommand | CliCommitCommand,
        composition_options: CliDeveloperWorkflowCompositionOptions,
        context: CommandContext,
    ) -> int:
        self.invocation = ParsedInvocation(
            command=command,
            global_options=context.global_options,
            composition_options=composition_options,
        )
        return 0


def parse_args(args: tuple[str, ...] | list[str]) -> ParsedInvocation:
    handlers = RecordingHandlers()
    exit_code = run_product_cli(
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


def _recording_command_registrars(handlers: RecordingHandlers) -> tuple[CommandRegistrar, ...]:
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


def test_run_cli_round_trips_bound_handler() -> None:
    handlers = RecordingHandlers()
    exit_code = run_product_cli(
        ("synthetic",),
        command_registrars=(_synthetic_command_registrar(handlers),),
        stdin=StringIO(),
        stdout=StringIO(),
        stderr=StringIO(),
    )

    assert exit_code == 0
    assert handlers.invocation == ParsedInvocation(
        command="synthetic",
        global_options=GlobalOptions(),
        composition_options=None,
    )


def _synthetic_command_registrar(handlers: RecordingHandlers) -> CommandRegistrar:
    def register(commands: CommandRegistry) -> None:
        commands.register(
            _synthetic_command_with_handler(_synthetic_handler(handlers)),
        )

    return register


def _register_synthetic_command(commands: CommandRegistry) -> None:
    commands.register(_synthetic_command_spec())


def _synthetic_command_spec() -> Command[str]:
    return Command(
        name="synthetic",
        summary="synthetic command",
        configure=_configure_noop_synthetic_parser,
        decode=_decode_synthetic_command,
        run=_noop_synthetic_handler,
    )


def _synthetic_command_with_parser(
    configure_parser: Callable[[argparse.ArgumentParser], None],
) -> Command[str]:
    return Command(
        name="synthetic",
        summary="synthetic command",
        configure=configure_parser,
        decode=_decode_synthetic_command,
        run=_noop_synthetic_handler,
    )


def _synthetic_command_with_decode(decode: Callable[[argparse.Namespace], str]) -> Command[str]:
    return Command(
        name="synthetic",
        summary="synthetic command",
        configure=_configure_noop_synthetic_parser,
        decode=decode,
        run=_noop_synthetic_handler,
    )


def _synthetic_decoded_command_with_parser(
    configure_parser: Callable[[argparse.ArgumentParser], None],
) -> Command[SyntheticDecodedCommand]:
    return Command(
        name="synthetic",
        summary="synthetic command",
        configure=configure_parser,
        decode=_decode_synthetic_boundary_command,
        run=_synthetic_boundary_handler,
    )


def _synthetic_command_with_handler(handler: Callable[[str, CommandContext], int]) -> Command[str]:
    return Command(
        name="synthetic",
        summary="synthetic command",
        configure=_configure_noop_synthetic_parser,
        decode=_decode_synthetic_command,
        run=handler,
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


def _decode_synthetic_boundary_command(namespace: argparse.Namespace) -> SyntheticDecodedCommand:
    return SyntheticDecodedCommand(
        global_options=GlobalOptions(
            print_usage=hasattr(namespace, "_fabrica_cli_print_usage"),
            print_prices=hasattr(namespace, "_fabrica_cli_print_prices"),
            verbose_diagnostics=hasattr(namespace, "_fabrica_cli_verbose_diagnostics"),
        ),
        feature_value=namespace.feature_value,
    )


def _noop_synthetic_handler(command: str, context: CommandContext) -> int:
    _ = (command, context)
    return 0


def _system_exit_synthetic_handler(command: str, context: CommandContext) -> int:
    _ = (command, context)
    raise SystemExit(SYNTHETIC_HANDLER_EXIT_CODE)


def _synthetic_handler(handlers: RecordingHandlers) -> Callable[[str, CommandContext], int]:
    def run(command: str, context: CommandContext) -> int:
        handlers.invocation = ParsedInvocation(
            command=command,
            global_options=context.global_options,
            composition_options=None,
        )
        return 0

    return run


def _synthetic_boundary_handler(command: SyntheticDecodedCommand, context: CommandContext) -> int:
    assert command.global_options == GlobalOptions()
    assert context.global_options == GlobalOptions(print_usage=True, print_prices=True, verbose_diagnostics=True)
    return 0


def test_run_cli_rejects_duplicate_command_registration() -> None:
    with pytest.raises(RegistrationError, match="CLI command 'synthetic' is already registered"):
        run_product_cli(
            ("synthetic",),
            command_registrars=(_register_duplicate_synthetic_commands,),
            stdin=StringIO(),
            stdout=StringIO(),
            stderr=StringIO(),
        )


def _register_duplicate_synthetic_commands(commands: CommandRegistry) -> None:
    commands.register(_synthetic_command_spec())
    commands.register(_synthetic_command_spec())


def test_run_cli_translates_argparse_registration_conflicts() -> None:
    def configure_conflicting_parser(parser: argparse.ArgumentParser) -> None:
        parser.add_argument("--feature-value")
        parser.add_argument("--feature-value")

    def register(commands: CommandRegistry) -> None:
        commands.register(_synthetic_command_with_parser(configure_conflicting_parser))

    with pytest.raises(RegistrationError, match="CLI command registration failed") as exc_info:
        run_product_cli(
            ("synthetic",),
            command_registrars=(register,),
            stdin=StringIO(),
            stdout=StringIO(),
            stderr=StringIO(),
        )

    assert isinstance(exc_info.value.__cause__, argparse.ArgumentError)


def test_argparse_command_registry_rejects_missing_registration_lookup() -> None:
    parser = argparse.ArgumentParser()
    subparsers = parser.add_subparsers()
    registry = ArgparseCommandRegistry(subparsers.add_parser)

    with pytest.raises(RegistrationError, match="CLI command 'synthetic' is not registered") as exc_info:
        registry.registration_for("synthetic")

    assert isinstance(exc_info.value.__cause__, KeyError)


@pytest.mark.parametrize("command_value", [None, "", 42])
def test_command_name_from_namespace_rejects_invalid_shell_command_destinations(command_value: object) -> None:
    namespace = argparse.Namespace(_fabrica_cli_command=command_value)

    with pytest.raises(RegistrationError, match="CLI parser did not capture the selected command name"):
        command_name_from_namespace(namespace)


@pytest.mark.parametrize(
    "reserved_dest",
    [
        "_fabrica_cli_command",
        "_fabrica_cli_print_usage",
        "_fabrica_cli_print_prices",
        "_fabrica_cli_verbose_diagnostics",
    ],
)
def test_run_cli_rejects_feature_arguments_using_reserved_shell_destinations(reserved_dest: str) -> None:
    def configure_reserved_parser(parser: argparse.ArgumentParser) -> None:
        parser.add_argument("--feature-value", dest=reserved_dest)

    def register(commands: CommandRegistry) -> None:
        commands.register(_synthetic_command_with_parser(configure_reserved_parser))

    with pytest.raises(RegistrationError, match="uses reserved parser destination"):
        run_product_cli(
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
def test_run_cli_rejects_feature_defaults_using_reserved_shell_destinations(reserved_dest: str) -> None:
    def configure_reserved_parser_default(parser: argparse.ArgumentParser) -> None:
        parser.set_defaults(**{reserved_dest: "feature-owned"})

    def register(commands: CommandRegistry) -> None:
        commands.register(_synthetic_command_with_parser(configure_reserved_parser_default))

    with pytest.raises(RegistrationError) as exc_info:
        run_product_cli(
            ("synthetic",),
            command_registrars=(register,),
            stdin=StringIO(),
            stdout=StringIO(),
            stderr=StringIO(),
        )

    assert "uses reserved parser default destination(s)" in str(exc_info.value)
    assert reserved_dest in str(exc_info.value)


@pytest.mark.parametrize(
    "reserved_dest",
    [
        "_fabrica_cli_command",
        "_fabrica_cli_print_usage",
        "_fabrica_cli_print_prices",
        "_fabrica_cli_verbose_diagnostics",
    ],
)
def test_run_cli_rejects_nested_feature_arguments_using_reserved_shell_destinations(reserved_dest: str) -> None:
    def configure_nested_parser(parser: argparse.ArgumentParser) -> None:
        nested_subparsers = parser.add_subparsers(dest="feature_action")
        child_parser = nested_subparsers.add_parser("child")
        child_parser.add_argument("--feature-value", dest=reserved_dest)

    def register(commands: CommandRegistry) -> None:
        commands.register(_synthetic_command_with_parser(configure_nested_parser))

    with pytest.raises(RegistrationError) as exc_info:
        run_product_cli(
            ("synthetic", "child"),
            command_registrars=(register,),
            stdin=StringIO(),
            stdout=StringIO(),
            stderr=StringIO(),
        )

    assert "uses reserved parser destination(s)" in str(exc_info.value)
    assert reserved_dest in str(exc_info.value)


def test_run_cli_rejects_nested_parser_default_that_overwrites_selected_command() -> None:
    def configure_nested_parser(parser: argparse.ArgumentParser) -> None:
        nested_subparsers = parser.add_subparsers(dest="feature_action")
        child_parser = nested_subparsers.add_parser("child")
        child_parser.set_defaults(_fabrica_cli_command="other-command")

    def register(commands: CommandRegistry) -> None:
        commands.register(_synthetic_command_with_parser(configure_nested_parser))

    with pytest.raises(RegistrationError) as exc_info:
        run_product_cli(
            ("synthetic", "child"),
            command_registrars=(register,),
            stdin=StringIO(),
            stdout=StringIO(),
            stderr=StringIO(),
        )

    assert "uses reserved parser default destination(s)" in str(exc_info.value)
    assert "_fabrica_cli_command" in str(exc_info.value)


def test_run_cli_rejects_absent_reserved_feature_default_set_to_none() -> None:
    def configure_reserved_parser_default(parser: argparse.ArgumentParser) -> None:
        parser.set_defaults(_fabrica_cli_command=None)

    def register(commands: CommandRegistry) -> None:
        commands.register(_synthetic_command_with_parser(configure_reserved_parser_default))

    with pytest.raises(RegistrationError) as exc_info:
        run_product_cli(
            ("synthetic",),
            command_registrars=(register,),
            stdin=StringIO(),
            stdout=StringIO(),
            stderr=StringIO(),
        )

    assert "uses reserved parser default destination(s)" in str(exc_info.value)
    assert "_fabrica_cli_command" in str(exc_info.value)


def test_run_cli_splits_shell_options_from_feature_decoder_namespace() -> None:
    def configure_parser(parser: argparse.ArgumentParser) -> None:
        parser.add_argument("--feature-value", required=True)

    def register(commands: CommandRegistry) -> None:
        commands.register(_synthetic_decoded_command_with_parser(configure_parser))

    exit_code = run_product_cli(
        (
            "--print-usage",
            "--print-prices",
            "--verbose-diagnostics",
            "synthetic",
            "--feature-value",
            "feature-owned",
        ),
        command_registrars=(register,),
        stdin=StringIO(),
        stdout=StringIO(),
        stderr=StringIO(),
    )

    assert exit_code == 0


def test_run_cli_does_not_swallow_handler_system_exit() -> None:
    def register(commands: CommandRegistry) -> None:
        commands.register(_synthetic_command_with_handler(_system_exit_synthetic_handler))

    with pytest.raises(SystemExit) as exc_info:
        run_product_cli(
            ("synthetic",),
            command_registrars=(register,),
            stdin=StringIO(),
            stdout=StringIO(),
            stderr=StringIO(),
        )

    assert exc_info.value.code == SYNTHETIC_HANDLER_EXIT_CODE


def test_run_cli_treats_cli_usage_error_as_usage_error() -> None:
    stderr = StringIO()

    def decode_user_error(namespace: argparse.Namespace) -> str:
        _ = namespace
        msg = "synthetic user error"
        raise UsageError(msg)

    def register(commands: CommandRegistry) -> None:
        commands.register(_synthetic_command_with_decode(decode_user_error))

    exit_code = run_product_cli(
        ("synthetic",),
        command_registrars=(register,),
        stdin=StringIO(),
        stdout=StringIO(),
        stderr=stderr,
    )

    assert exit_code == ARGPARSE_USAGE_ERROR
    assert "synthetic user error" in stderr.getvalue()


def test_run_cli_treats_argparse_decoder_type_error_as_usage_error() -> None:
    stderr = StringIO()

    def decode_user_error(namespace: argparse.Namespace) -> str:
        _ = namespace
        msg = "synthetic type error"
        raise argparse.ArgumentTypeError(msg)

    def register(commands: CommandRegistry) -> None:
        commands.register(_synthetic_command_with_decode(decode_user_error))

    exit_code = run_product_cli(
        ("synthetic",),
        command_registrars=(register,),
        stdin=StringIO(),
        stdout=StringIO(),
        stderr=stderr,
    )

    assert exit_code == ARGPARSE_USAGE_ERROR
    assert "synthetic type error" in stderr.getvalue()


def test_run_cli_propagates_unexpected_decoder_value_error() -> None:
    def decode_programmer_error(namespace: argparse.Namespace) -> str:
        _ = namespace
        msg = "synthetic programmer error"
        raise ValueError(msg)

    def register(commands: CommandRegistry) -> None:
        commands.register(_synthetic_command_with_decode(decode_programmer_error))

    with pytest.raises(ValueError, match="synthetic programmer error"):
        run_product_cli(
            ("synthetic",),
            command_registrars=(register,),
            stdin=StringIO(),
            stdout=StringIO(),
            stderr=StringIO(),
        )


def test_run_cli_routes_help_to_injected_stdout_without_raising() -> None:
    stdout = StringIO()
    stderr = StringIO()

    exit_code = run_bootstrap_cli(("--help",), stdout=stdout, stderr=stderr)

    assert exit_code == 0
    assert "Run local Fabrica workflows." in stdout.getvalue()
    assert "run" in stdout.getvalue()
    assert stderr.getvalue() == ""


def test_run_cli_routes_usage_errors_to_injected_stderr_without_raising() -> None:
    stdout = StringIO()
    stderr = StringIO()

    exit_code = run_bootstrap_cli(("run",), stdout=stdout, stderr=stderr)

    assert exit_code == ARGPARSE_USAGE_ERROR
    assert stdout.getvalue() == ""
    assert "error:" in stderr.getvalue()
    assert "--prompt" in stderr.getvalue()


def test_run_cli_routes_unknown_command_to_injected_stderr_without_raising() -> None:
    stdout = StringIO()
    stderr = StringIO()

    exit_code = run_bootstrap_cli(("unknown-command",), stdout=stdout, stderr=stderr)

    assert exit_code == ARGPARSE_USAGE_ERROR
    assert stdout.getvalue() == ""
    assert "invalid choice: 'unknown-command'" in stderr.getvalue()


def test_run_cli_renders_help_without_runtime_side_effects() -> None:
    _clear_bootstrap_composition_modules()
    stdout = StringIO()
    stderr = StringIO()

    exit_code = run_product_cli(
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
        global_options=GlobalOptions(print_usage=True, print_prices=True, verbose_diagnostics=True),
        composition_options=AgentRuntimeCliCompositionOptions(skill_roots=(Path("./skills"),)),
    )


def test_parse_run_command_uses_empty_explicit_context_defaults() -> None:
    invocation = parse_args(["run", "--prompt", "Reply with pong"])

    assert invocation == ParsedInvocation(
        command=CliRunCommand(prompt="Reply with pong"),
        global_options=GlobalOptions(),
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
        global_options=GlobalOptions(),
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
        global_options=GlobalOptions(verbose_diagnostics=True),
        composition_options=CliDeveloperWorkflowCompositionOptions(
            model="gpt-5.6-sol",
            reasoning_effort="medium",
            skill_roots=(Path("./skills"),),
        ),
    )


@pytest.mark.parametrize("global_option", ["--print-usage", "--print-prices", "--verbose-diagnostics"])
def test_parse_command_rejects_global_options_after_subcommand(global_option: str) -> None:
    with pytest.raises(SystemExit) as exc_info:
        parse_args(["commit-message", global_option])

    assert exc_info.value.code == ARGPARSE_USAGE_ERROR


@pytest.mark.parametrize(
    ("register", "expected_message"),
    [
        (
            lambda commands: commands.register(
                Command(
                    name="",
                    summary="synthetic command",
                    configure=_configure_noop_synthetic_parser,
                    decode=_decode_synthetic_command,
                    run=_noop_synthetic_handler,
                ),
            ),
            "name must be a non-empty trimmed value",
        ),
        (
            lambda commands: commands.register(
                Command(
                    name=" synthetic",
                    summary="synthetic command",
                    configure=_configure_noop_synthetic_parser,
                    decode=_decode_synthetic_command,
                    run=_noop_synthetic_handler,
                ),
            ),
            "name must be a non-empty trimmed value",
        ),
        (
            lambda commands: commands.register(
                Command(
                    name="Synthetic",
                    summary="synthetic command",
                    configure=_configure_noop_synthetic_parser,
                    decode=_decode_synthetic_command,
                    run=_noop_synthetic_handler,
                ),
            ),
            "name must be lowercase kebab-case",
        ),
        (
            lambda commands: commands.register(
                Command(
                    name="synthetic",
                    summary="",
                    configure=_configure_noop_synthetic_parser,
                    decode=_decode_synthetic_command,
                    run=_noop_synthetic_handler,
                ),
            ),
            "summary must be a non-empty trimmed value",
        ),
        (
            lambda commands: commands.register(
                Command(
                    name="synthetic",
                    summary="synthetic command",
                    configure=_configure_noop_synthetic_parser,
                    decode=_decode_synthetic_command,
                    run=_noop_synthetic_handler,
                    description=" synthetic description",
                ),
            ),
            "description must be a non-empty trimmed value",
        ),
        (
            lambda commands: commands.register(
                Command(
                    name="synthetic",
                    summary="synthetic command",
                    configure=cast("Any", None),
                    decode=_decode_synthetic_command,
                    run=_noop_synthetic_handler,
                ),
            ),
            "parser configurer must be callable",
        ),
        (
            lambda commands: commands.register(
                Command(
                    name="synthetic",
                    summary="synthetic command",
                    configure=_configure_noop_synthetic_parser,
                    decode=cast("Any", None),
                    run=_noop_synthetic_handler,
                ),
            ),
            "decoder must be callable",
        ),
        (
            lambda commands: commands.register(
                Command(
                    name="synthetic",
                    summary="synthetic command",
                    configure=_configure_noop_synthetic_parser,
                    decode=_decode_synthetic_command,
                    run=cast("Any", None),
                ),
            ),
            "runner must be callable",
        ),
    ],
)
def test_cli_command_registration_rejects_invalid_values(
    register: Callable[[CommandRegistry], None],
    expected_message: str,
) -> None:
    with pytest.raises(RegistrationError, match=expected_message):
        run_product_cli(
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
        global_options=GlobalOptions(print_usage=True, print_prices=True),
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
        global_options=GlobalOptions(),
        composition_options=CliDeveloperWorkflowCompositionOptions(),
    )


def test_commit_command_help_documents_mutating_pre_commit_gate() -> None:
    stdout = StringIO()
    stderr = StringIO()

    exit_code = run_product_cli(
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
        global_options=GlobalOptions(verbose_diagnostics=True),
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
        global_options=GlobalOptions(verbose_diagnostics=True),
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
        global_options=GlobalOptions(verbose_diagnostics=True),
        composition_options=AgentRuntimeCliCompositionOptions(skill_roots=(Path("./skills"),)),
    )


def test_parse_script_execute_command_rejects_missing_approval_metadata() -> None:
    with pytest.raises(SystemExit) as exc_info:
        parse_args(["script-execute", "--skill-id", "python-testing", "--script-id", "scripts/check.py"])

    assert exc_info.value.code == ARGPARSE_USAGE_ERROR


def test_parsed_commands_are_immutable_boundary_values() -> None:
    run_invocation = parse_args(["run", "--prompt", "Reply with pong"])
    context_invocation = parse_args(
        [
            "run",
            "--prompt",
            "Reply with pong",
            "--skill",
            "python-testing",
            "--resource",
            "python-testing:references/example.md",
            "--skill-root",
            "./skills",
        ],
    )
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
    assert isinstance(context_invocation.command, CliRunCommand)
    assert isinstance(context_invocation.command.skill_ids, tuple)
    assert isinstance(context_invocation.command.resources, tuple)
    assert isinstance(context_invocation.composition_options, AgentRuntimeCliCompositionOptions)
    assert isinstance(context_invocation.composition_options.skill_roots, tuple)
    with pytest.raises(FrozenInstanceError):
        setattr(context_invocation.composition_options, "skill_roots", ())  # noqa: B010
    with pytest.raises(FrozenInstanceError):
        setattr(policy_invocation.command, "script_id", "changed")  # noqa: B010
    with pytest.raises(FrozenInstanceError):
        setattr(execution_invocation.command, "script_id", "changed")  # noqa: B010
    with pytest.raises(FrozenInstanceError):
        setattr(commit_message_invocation.command, "skill_id", "changed")  # noqa: B010
    with pytest.raises(FrozenInstanceError):
        setattr(commit_invocation.command, "skill_id", "changed")  # noqa: B010
