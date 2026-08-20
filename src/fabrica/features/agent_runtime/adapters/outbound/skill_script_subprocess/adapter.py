"""Local subprocess execution adapter for selected Agent Skill scripts."""

from __future__ import annotations

import subprocess
import sys
import tempfile
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
from time import monotonic
from typing import TYPE_CHECKING

from fabrica.adapters.outbound.process_group_subprocess import ProcessGroupCommandSettings, run_process_group_command
from fabrica.features.agent_runtime.application.dtos import (
    SafeRuntimeMetadataValue,
    SkillScriptApprovalBinding,
    SkillScriptExecutionCommand,
    SkillScriptExecutionObservation,
    SkillScriptExecutionOutput,
    SkillScriptExecutionResult,
    SkillScriptExecutionStatus,
    SkillScriptSnapshot,
    SkillScriptType,
)
from fabrica.features.agent_runtime.application.ports import SkillScriptExecutionError, SkillScriptSnapshotLoader

if TYPE_CHECKING:
    from collections.abc import Iterator, Mapping

_BINDING_MISMATCH_MESSAGE = "approved script binding does not match current script metadata"
_UNSUPPORTED_SCRIPT_TYPE_MESSAGE = "selected script type is not supported for subprocess execution"
_MISSING_INTERPRETER_MESSAGE = "selected script interpreter is unavailable"
_SUBPROCESS_OS_ERROR_MESSAGE = "selected script subprocess execution failed"
_SNAPSHOT_FILE_NAME = "selected-skill-script"


@dataclass(frozen=True, slots=True)
class SkillScriptSubprocessExecutionSettings:
    """Execution settings for the selected script subprocess adapter."""

    python_interpreter: str | Path | None = None
    shell_interpreter: str | Path = "/bin/sh"
    working_directory: Path | None = None
    verbose_diagnostics: bool = False


@dataclass(frozen=True, slots=True)
class _ExecutionResultDetails:
    status: SkillScriptExecutionStatus
    message: str
    category: str
    stdout: SkillScriptExecutionOutput | None = None
    stderr: SkillScriptExecutionOutput | None = None
    exit_code: int | None = None
    duration_seconds: float | None = None
    metadata: Mapping[str, SafeRuntimeMetadataValue] | None = None


class SkillScriptSubprocessExecutor:
    """Execute approved selected local Agent Skill scripts with conservative defaults.

    This adapter performs local process execution only for explicitly selected
    scripts under configured skill roots. It uses explicit interpreter argument
    lists, ``shell=False``, an empty inherited environment, bounded output, and a
    temporary working directory by default. These constraints are not a production
    sandbox or OS/container isolation.
    """

    def __init__(
        self,
        *,
        snapshot_loader: SkillScriptSnapshotLoader,
        settings: SkillScriptSubprocessExecutionSettings | None = None,
    ) -> None:
        execution_settings = settings or SkillScriptSubprocessExecutionSettings()
        self._snapshot_loader = snapshot_loader
        self._python_interpreter = str(execution_settings.python_interpreter or sys.executable)
        self._shell_interpreter = str(execution_settings.shell_interpreter)
        self._working_directory = execution_settings.working_directory
        self._verbose_diagnostics = execution_settings.verbose_diagnostics

    def execute(
        self,
        command: SkillScriptExecutionCommand,
        approved_binding: SkillScriptApprovalBinding,
    ) -> SkillScriptExecutionResult:
        """Execute a selected script when the current metadata matches approval."""
        snapshot = self._snapshot_loader.load_snapshot(command.selection)
        if snapshot.binding != approved_binding:
            return self._result(
                command,
                approved_binding,
                _ExecutionResultDetails(
                    status=SkillScriptExecutionStatus.ADAPTER_ERROR,
                    message=_BINDING_MISMATCH_MESSAGE,
                    category="binding_mismatch",
                ),
            )

        interpreter = self._interpreter_for_binding(snapshot.binding)
        if interpreter is None:
            return self._result(
                command,
                approved_binding,
                _ExecutionResultDetails(
                    status=SkillScriptExecutionStatus.UNSUPPORTED,
                    message=_UNSUPPORTED_SCRIPT_TYPE_MESSAGE,
                    category="unsupported_script_type",
                ),
            )
        if not Path(interpreter).is_file():
            return self._result(
                command,
                approved_binding,
                _ExecutionResultDetails(
                    status=SkillScriptExecutionStatus.UNSUPPORTED,
                    message=_MISSING_INTERPRETER_MESSAGE,
                    category="missing_interpreter",
                ),
            )

        started = monotonic()
        with (
            self._execution_working_directory() as working_directory,
            self._snapshot_script_file(snapshot) as script_file,
        ):
            try:
                completed = run_process_group_command(
                    [interpreter, str(script_file)],
                    cwd=working_directory,
                    timeout_seconds=command.sandbox_policy.timeout_seconds,
                    settings=ProcessGroupCommandSettings(env={}, text=True),
                )
            except subprocess.TimeoutExpired as err:
                duration = monotonic() - started
                return self._result(
                    command,
                    approved_binding,
                    _ExecutionResultDetails(
                        status=SkillScriptExecutionStatus.TIMED_OUT,
                        message="selected script execution timed out",
                        category="timed_out",
                        stdout=self._output(err.stdout, command.sandbox_policy.max_stdout_chars),
                        stderr=self._output(err.stderr, command.sandbox_policy.max_stderr_chars),
                        duration_seconds=duration,
                    ),
                )
            except OSError as err:
                msg = _SUBPROCESS_OS_ERROR_MESSAGE
                raise SkillScriptExecutionError(
                    msg,
                    skill_id=command.selection.skill_id,
                    script_id=command.selection.script_id,
                    category="subprocess_os_error",
                ) from err

        duration = monotonic() - started
        status = (
            SkillScriptExecutionStatus.SUCCESS
            if completed.returncode == 0
            else SkillScriptExecutionStatus.EXECUTION_FAILED
        )
        message = "selected script executed"
        category = "executed"
        if status is SkillScriptExecutionStatus.EXECUTION_FAILED:
            message = "selected script exited non-zero"
            category = "non_zero_exit"
        return self._result(
            command,
            approved_binding,
            _ExecutionResultDetails(
                status=status,
                message=message,
                category=category,
                stdout=self._output(completed.stdout, command.sandbox_policy.max_stdout_chars),
                stderr=self._output(completed.stderr, command.sandbox_policy.max_stderr_chars),
                exit_code=completed.returncode,
                duration_seconds=duration,
            ),
        )

    def _interpreter_for_binding(self, binding: SkillScriptApprovalBinding) -> str | None:
        if binding.script_type is SkillScriptType.PYTHON:
            return self._python_interpreter
        if binding.script_type is SkillScriptType.SHELL:
            return self._shell_interpreter
        return None

    @contextmanager
    def _snapshot_script_file(self, snapshot: SkillScriptSnapshot) -> Iterator[Path]:
        with tempfile.TemporaryDirectory(prefix="fabrica-skill-script-snapshot-") as directory:
            script_file = Path(directory) / f"{_SNAPSHOT_FILE_NAME}{snapshot.binding.suffix}"
            script_file.write_bytes(snapshot.content)
            script_file.chmod(0o600)
            yield script_file

    @contextmanager
    def _execution_working_directory(self) -> Iterator[Path]:
        if self._working_directory is not None:
            self._working_directory.mkdir(parents=True, exist_ok=True)
            yield self._working_directory
            return
        with tempfile.TemporaryDirectory(prefix="fabrica-skill-script-") as directory:
            yield Path(directory)

    def _execution_error(
        self,
        command: SkillScriptExecutionCommand,
        message: str,
        *,
        category: str,
    ) -> SkillScriptExecutionError:
        return SkillScriptExecutionError(
            message,
            skill_id=command.selection.skill_id,
            script_id=command.selection.script_id,
            category=category,
            metadata={"diagnostic_mode": "verbose" if self._verbose_diagnostics else "safe"},
        )

    @staticmethod
    def _result(
        command: SkillScriptExecutionCommand,
        binding: SkillScriptApprovalBinding,
        details: _ExecutionResultDetails,
    ) -> SkillScriptExecutionResult:
        observation_metadata: dict[str, SafeRuntimeMetadataValue] = {
            "skill_id": command.selection.skill_id,
            "script_id": command.selection.script_id,
            "category": details.category,
        }
        if details.metadata is not None:
            observation_metadata.update(details.metadata)
        return SkillScriptExecutionResult(
            status=details.status,
            selection=command.selection,
            binding=binding,
            stdout=details.stdout or SkillScriptExecutionOutput(max_chars=command.sandbox_policy.max_stdout_chars),
            stderr=details.stderr or SkillScriptExecutionOutput(max_chars=command.sandbox_policy.max_stderr_chars),
            exit_code=details.exit_code,
            duration_seconds=details.duration_seconds,
            observations=(
                SkillScriptExecutionObservation(
                    message=details.message,
                    metadata=observation_metadata,
                ),
            ),
        )

    @staticmethod
    def _output(value: str | bytes | None, max_chars: int) -> SkillScriptExecutionOutput:
        text = _safe_text(value)
        truncated = len(text) > max_chars
        if truncated:
            text = text[:max_chars]
        return SkillScriptExecutionOutput(text=text, truncated=truncated, max_chars=max_chars)


def _safe_text(value: str | bytes | None) -> str:
    if value is None:
        return ""
    if isinstance(value, bytes):
        return value.decode("utf-8", errors="replace")
    return value
