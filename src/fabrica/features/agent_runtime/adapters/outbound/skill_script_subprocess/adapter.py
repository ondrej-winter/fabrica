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

from fabrica.features.agent_runtime.application.dtos import (
    SafeRuntimeMetadataValue,
    SkillScriptApprovalBinding,
    SkillScriptExecutionCommand,
    SkillScriptExecutionObservation,
    SkillScriptExecutionOutput,
    SkillScriptExecutionResult,
    SkillScriptExecutionStatus,
    SkillScriptType,
)
from fabrica.features.agent_runtime.application.ports import SkillScriptExecutionError, SkillScriptMetadataLoader

if TYPE_CHECKING:
    from collections.abc import Iterator, Mapping

_PATH_OUTSIDE_ROOT_MESSAGE = "selected skill script path is outside the configured skill root"
_MISSING_SCRIPT_MESSAGE = "selected skill script was not found"
_AMBIGUOUS_SCRIPT_MESSAGE = "selected skill script matched more than one configured skill root"
_INVALID_SCRIPT_FILE_MESSAGE = "selected skill script path is not a readable file"
_BINDING_MISMATCH_MESSAGE = "approved script binding does not match current script metadata"
_UNSUPPORTED_SCRIPT_TYPE_MESSAGE = "selected script type is not supported for subprocess execution"
_MISSING_INTERPRETER_MESSAGE = "selected script interpreter is unavailable"
_SUBPROCESS_OS_ERROR_MESSAGE = "selected script subprocess execution failed"


@dataclass(frozen=True, slots=True)
class SkillScriptSubprocessExecutionSettings:
    """Execution settings for the selected script subprocess adapter."""

    python_interpreter: str | Path | None = None
    shell_interpreter: str | Path = "/bin/sh"
    working_directory: Path | None = None
    verbose_diagnostics: bool = False


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
        metadata_loader: SkillScriptMetadataLoader,
        skill_roots: tuple[Path, ...],
        settings: SkillScriptSubprocessExecutionSettings | None = None,
    ) -> None:
        execution_settings = settings or SkillScriptSubprocessExecutionSettings()
        self._skill_roots = tuple(skill_roots)
        self._metadata_loader = metadata_loader
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
        metadata = self._metadata_loader.load_metadata(command.selection)
        if metadata.binding != approved_binding:
            return self._result(
                command,
                approved_binding,
                SkillScriptExecutionStatus.ADAPTER_ERROR,
                _BINDING_MISMATCH_MESSAGE,
                category="binding_mismatch",
            )

        script_file = self._find_selected_file(command)
        argv = self._argv_for_binding(metadata.binding, script_file)
        if argv is None:
            return self._result(
                command,
                approved_binding,
                SkillScriptExecutionStatus.UNSUPPORTED,
                _UNSUPPORTED_SCRIPT_TYPE_MESSAGE,
                category="unsupported_script_type",
            )
        if not Path(argv[0]).is_file():
            return self._result(
                command,
                approved_binding,
                SkillScriptExecutionStatus.UNSUPPORTED,
                _MISSING_INTERPRETER_MESSAGE,
                category="missing_interpreter",
            )

        started = monotonic()
        with self._execution_working_directory() as working_directory:
            try:
                # Intentional constrained execution: selected script path, explicit interpreter argv, no shell.
                completed = subprocess.run(  # noqa: S603
                    argv,
                    check=False,
                    capture_output=True,
                    cwd=working_directory,
                    env={},
                    shell=False,
                    text=True,
                    timeout=command.sandbox_policy.timeout_seconds,
                )
            except subprocess.TimeoutExpired as err:
                duration = monotonic() - started
                return self._result(
                    command,
                    approved_binding,
                    SkillScriptExecutionStatus.TIMED_OUT,
                    "selected script execution timed out",
                    category="timed_out",
                    stdout=self._output(err.stdout, command.sandbox_policy.max_stdout_chars),
                    stderr=self._output(err.stderr, command.sandbox_policy.max_stderr_chars),
                    duration_seconds=duration,
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
            status,
            message,
            category=category,
            stdout=self._output(completed.stdout, command.sandbox_policy.max_stdout_chars),
            stderr=self._output(completed.stderr, command.sandbox_policy.max_stderr_chars),
            exit_code=completed.returncode,
            duration_seconds=duration,
        )

    def _find_selected_file(self, command: SkillScriptExecutionCommand) -> Path:
        skill_relative_path = _relative_path_from_id(command.selection.skill_id)
        script_relative_path = _relative_path_from_id(command.selection.script_id)
        matches: list[Path] = []
        for skill_root in self._skill_roots:
            root = skill_root.resolve(strict=False)
            skill_directory = (root / skill_relative_path).resolve(strict=False)
            candidate = (skill_directory / script_relative_path).resolve(strict=False)
            if not skill_directory.is_relative_to(root) or not candidate.is_relative_to(skill_directory):
                raise self._execution_error(command, _PATH_OUTSIDE_ROOT_MESSAGE, category="invalid_script_path")
            if candidate.exists():
                if not candidate.is_file():
                    raise self._execution_error(command, _INVALID_SCRIPT_FILE_MESSAGE, category="invalid_script_file")
                matches.append(candidate)

        if len(matches) > 1:
            raise self._execution_error(command, _AMBIGUOUS_SCRIPT_MESSAGE, category="ambiguous_script")
        if matches:
            return matches[0]
        raise self._execution_error(command, _MISSING_SCRIPT_MESSAGE, category="missing_script")

    def _argv_for_binding(self, binding: SkillScriptApprovalBinding, script_file: Path) -> list[str] | None:
        if binding.script_type is SkillScriptType.PYTHON:
            return [self._python_interpreter, str(script_file)]
        if binding.script_type is SkillScriptType.SHELL:
            return [self._shell_interpreter, str(script_file)]
        return None

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
    def _result(  # noqa: PLR0913
        command: SkillScriptExecutionCommand,
        binding: SkillScriptApprovalBinding,
        status: SkillScriptExecutionStatus,
        message: str,
        *,
        category: str,
        stdout: SkillScriptExecutionOutput | None = None,
        stderr: SkillScriptExecutionOutput | None = None,
        exit_code: int | None = None,
        duration_seconds: float | None = None,
        metadata: Mapping[str, SafeRuntimeMetadataValue] | None = None,
    ) -> SkillScriptExecutionResult:
        observation_metadata: dict[str, SafeRuntimeMetadataValue] = {
            "skill_id": command.selection.skill_id,
            "script_id": command.selection.script_id,
            "category": category,
        }
        if metadata is not None:
            observation_metadata.update(metadata)
        return SkillScriptExecutionResult(
            status=status,
            selection=command.selection,
            binding=binding,
            stdout=stdout or SkillScriptExecutionOutput(max_chars=command.sandbox_policy.max_stdout_chars),
            stderr=stderr or SkillScriptExecutionOutput(max_chars=command.sandbox_policy.max_stderr_chars),
            exit_code=exit_code,
            duration_seconds=duration_seconds,
            observations=(
                SkillScriptExecutionObservation(
                    message=message,
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


def _relative_path_from_id(identifier: str) -> Path:
    relative_path = Path(identifier)
    if relative_path.is_absolute():
        msg = "selected skill script identifiers must be relative"
        raise SkillScriptExecutionError(
            msg,
            skill_id=identifier,
            script_id=identifier,
            category="invalid_script_path",
            metadata={"diagnostic_mode": "safe"},
        )
    return relative_path
