"""Tests for the product CLI command runner."""

from __future__ import annotations

from dataclasses import dataclass
from io import StringIO
from typing import TYPE_CHECKING

import pytest

from fabrica.adapters.inbound.cli.contracts import CliDispatchError
from fabrica.adapters.inbound.cli.contributions import CliContribution
from fabrica.adapters.inbound.cli.options import CliGlobalOptions
from fabrica.adapters.inbound.cli.parser import CliInvocation
from fabrica.adapters.inbound.cli.runner import CliCommandExecutionOptions, run_cli_command

if TYPE_CHECKING:
    from fabrica.adapters.inbound.cli.contracts import CliSubparsers
    from fabrica.adapters.inbound.cli.contributions import CliExecutionContext

SYNTHETIC_EXIT_CODE = 42


def test_run_cli_command_dispatches_invocation_to_owning_contribution() -> None:
    stdout = StringIO()
    stderr = StringIO()
    stdin = StringIO("approved\n")
    command = _SyntheticCommand(name="synthetic")
    contribution = _synthetic_contribution(stdout=stdout, stderr=stderr)

    exit_code = run_cli_command(
        CliInvocation(
            command=command,
            global_options=CliGlobalOptions(print_usage=True),
            composition_options=_SyntheticCompositionOptions(label="test"),
        ),
        options=CliCommandExecutionOptions(
            contributions=(contribution.to_cli_contribution(),),
            stdin=stdin,
            stdout=stdout,
            stderr=stderr,
        ),
    )

    assert exit_code == SYNTHETIC_EXIT_CODE
    assert contribution.calls == [
        _SyntheticCall(
            command=command,
            print_usage=True,
            composition_label="test",
            stdin_value="approved\n",
            stdout_is_injected=True,
            stderr_is_injected=True,
        ),
    ]


def test_run_cli_command_reports_unowned_invocation() -> None:
    with pytest.raises(CliDispatchError, match="no CLI contribution registered for command: _SyntheticCommand"):
        run_cli_command(
            CliInvocation(command=_SyntheticCommand(name="synthetic")),
            options=CliCommandExecutionOptions(contributions=()),
        )


@dataclass(frozen=True, slots=True)
class _SyntheticCommand:
    name: str


@dataclass(frozen=True, slots=True)
class _SyntheticCompositionOptions:
    label: str


@dataclass(frozen=True, slots=True)
class _SyntheticCall:
    command: _SyntheticCommand
    print_usage: bool
    composition_label: str
    stdin_value: str
    stdout_is_injected: bool
    stderr_is_injected: bool


@dataclass(slots=True)
class _RecordingSyntheticContribution:
    calls: list[_SyntheticCall]
    stdout: StringIO
    stderr: StringIO

    def to_cli_contribution(self) -> CliContribution:
        return CliContribution(
            name="synthetic",
            command_names=("synthetic",),
            command_types=(_SyntheticCommand,),
            register_commands=_ignore_registration,
            run_command=self.run,
        )

    def run(self, command: object, context: CliExecutionContext) -> int:
        assert isinstance(command, _SyntheticCommand)
        assert isinstance(context.composition_options, _SyntheticCompositionOptions)
        self.calls.append(
            _SyntheticCall(
                command=command,
                print_usage=context.global_options.print_usage,
                composition_label=context.composition_options.label,
                stdin_value=context.stdin.read(),
                stdout_is_injected=context.stdout is self.stdout,
                stderr_is_injected=context.stderr is self.stderr,
            ),
        )
        return SYNTHETIC_EXIT_CODE


def _synthetic_contribution(*, stdout: StringIO, stderr: StringIO) -> _RecordingSyntheticContribution:
    return _RecordingSyntheticContribution(calls=[], stdout=stdout, stderr=stderr)


def _ignore_registration(subparsers: CliSubparsers) -> None:
    _ = subparsers
