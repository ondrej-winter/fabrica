"""Tests for the local agent runtime CLI parser."""

from dataclasses import FrozenInstanceError
from pathlib import Path

import pytest

from fabrica.features.agent_runtime.adapters.inbound.cli import (
    CliCommitCommand,
    CliCommitMessageCommand,
    CliGlobalOptions,
    CliInvocation,
    CliRunCommand,
    CliScriptExecuteCommand,
    CliScriptPolicyCommand,
    CliSelectedResource,
    build_parser,
    parse_args,
)
from fabrica.features.agent_runtime.application.dtos import SkillScriptType

ARGPARSE_USAGE_ERROR = 2


def test_build_parser_renders_help_without_runtime_side_effects(capsys: pytest.CaptureFixture[str]) -> None:
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


def test_parse_run_command_supports_prompt_model_and_explicit_context() -> None:
    command = parse_args(
        [
            "--print-usage",
            "--print-prices",
            "--verbose-diagnostics",
            "run",
            "--prompt",
            "Reply with pong",
            "--model",
            "codex-compatible",
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

    assert command == CliInvocation(
        command=CliRunCommand(
            prompt="Reply with pong",
            model_hint="codex-compatible",
            skill_ids=("python-testing", "code-review"),
            resources=(CliSelectedResource(skill_id="python-testing", resource_id="references/example.md"),),
            skill_roots=(Path("./skills"),),
        ),
        global_options=CliGlobalOptions(print_usage=True, print_prices=True, verbose_diagnostics=True),
    )


def test_parse_run_command_uses_empty_explicit_context_defaults() -> None:
    command = parse_args(["run", "--prompt", "Reply with pong"])

    assert command == CliInvocation(command=CliRunCommand(prompt="Reply with pong"))


def test_parse_commit_message_command_defaults_to_conventional_commits_skill() -> None:
    command = parse_args(["commit-message"])

    assert command == CliInvocation(command=CliCommitMessageCommand(skill_id="conventional-commits"))


def test_parse_commit_message_command_supports_skill_root_and_diagnostics_overrides() -> None:
    command = parse_args(
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
    assert command == CliInvocation(
        command=CliCommitMessageCommand(
            skill_id="team-style",
            model="gpt-5.6-sol",
            reasoning_effort="medium",
            skill_roots=(Path("./skills"),),
        ),
        global_options=CliGlobalOptions(verbose_diagnostics=True),
    )


def test_parse_command_rejects_global_options_after_subcommand() -> None:
    with pytest.raises(SystemExit) as exc_info:
        parse_args(
            [
                "commit-message",
                "--verbose-diagnostics",
            ],
        )

    assert exc_info.value.code == ARGPARSE_USAGE_ERROR


def test_parse_commit_message_command_supports_usage_and_price_reporting() -> None:
    command = parse_args(["--print-usage", "--print-prices", "commit-message"])

    assert command == CliInvocation(
        command=CliCommitMessageCommand(skill_id="conventional-commits"),
        global_options=CliGlobalOptions(print_usage=True, print_prices=True),
    )


def test_parse_commit_message_command_rejects_unknown_reasoning_effort() -> None:
    with pytest.raises(SystemExit) as exc_info:
        parse_args(["commit-message", "--reasoning-effort", "very-high"])

    assert exc_info.value.code == ARGPARSE_USAGE_ERROR


def test_parse_commit_command_defaults_to_conventional_commits_skill() -> None:
    command = parse_args(["commit"])

    assert command == CliInvocation(command=CliCommitCommand(skill_id="conventional-commits"))


def test_parse_commit_command_supports_commit_message_generation_options() -> None:
    command = parse_args(
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

    assert command == CliInvocation(
        command=CliCommitCommand(
            skill_id="team-style",
            model="gpt-5.6-sol",
            reasoning_effort="medium",
            skill_roots=(Path("./skills"),),
        ),
        global_options=CliGlobalOptions(verbose_diagnostics=True),
    )


def test_parse_commit_command_rejects_unknown_reasoning_effort() -> None:
    with pytest.raises(SystemExit) as exc_info:
        parse_args(["commit", "--reasoning-effort", "very-high"])

    assert exc_info.value.code == ARGPARSE_USAGE_ERROR


def test_parse_run_command_rejects_malformed_resource_selection() -> None:
    with pytest.raises(SystemExit) as exc_info:
        parse_args(["run", "--prompt", "Reply with pong", "--resource", "python-testing"])

    assert exc_info.value.code == ARGPARSE_USAGE_ERROR


def test_parse_script_policy_command_supports_explicit_selected_script() -> None:
    command = parse_args(
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

    assert command == CliInvocation(
        command=CliScriptPolicyCommand(
            skill_id="python-testing",
            script_id="scripts/check.py",
            skill_roots=(Path("./skills"),),
        ),
        global_options=CliGlobalOptions(verbose_diagnostics=True),
    )


def test_parse_script_execute_command_requires_metadata_bound_approval() -> None:
    command = parse_args(
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

    assert command == CliInvocation(
        command=CliScriptExecuteCommand(
            skill_id="python-testing",
            script_id="scripts/check.py",
            approval_script_type=SkillScriptType.PYTHON,
            approval_suffix=".py",
            approval_byte_size=128,
            approval_content_digest="sha256:abc123",
            skill_roots=(Path("./skills"),),
        ),
        global_options=CliGlobalOptions(verbose_diagnostics=True),
    )


def test_parse_script_execute_command_rejects_missing_approval_metadata() -> None:
    with pytest.raises(SystemExit) as exc_info:
        parse_args(["script-execute", "--skill-id", "python-testing", "--script-id", "scripts/check.py"])

    assert exc_info.value.code == ARGPARSE_USAGE_ERROR


def test_parsed_commands_are_immutable_boundary_values() -> None:
    run_command = parse_args(["run", "--prompt", "Reply with pong"])
    policy_command = parse_args(
        ["script-policy", "--skill-id", "python-testing", "--script-id", "scripts/check.py"],
    )
    execution_command = parse_args(
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
    commit_message_command = parse_args(["commit-message"])
    commit_command = parse_args(["commit"])

    with pytest.raises(FrozenInstanceError):
        setattr(run_command, "command", CliRunCommand(prompt="changed"))  # noqa: B010
    with pytest.raises(FrozenInstanceError):
        setattr(policy_command.command, "script_id", "changed")  # noqa: B010
    with pytest.raises(FrozenInstanceError):
        setattr(execution_command.command, "script_id", "changed")  # noqa: B010
    with pytest.raises(FrozenInstanceError):
        setattr(commit_message_command.command, "skill_id", "changed")  # noqa: B010
    with pytest.raises(FrozenInstanceError):
        setattr(commit_command.command, "skill_id", "changed")  # noqa: B010
