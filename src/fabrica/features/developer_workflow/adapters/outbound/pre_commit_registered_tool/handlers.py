"""Tool handlers for explicit pre-commit execution."""

from collections.abc import Mapping

from fabrica.features.agent_runtime.application.dtos import SafeRuntimeMetadataValue
from fabrica.features.developer_workflow.application.dtos import (
    PreCommitRunCommand,
    PreCommitRunResult,
)
from fabrica.features.developer_workflow.application.ports import PreCommitRunError, PreCommitRunner

_PRE_COMMIT_TOOL_FAILURE_MESSAGE = "pre-commit could not be run"


def handle_run_pre_commit(runner: PreCommitRunner, arguments: Mapping[str, SafeRuntimeMetadataValue]) -> str:
    """Return deterministic text output for one pre-commit tool call."""
    hook_id = _optional_string_argument(arguments, "hook_id", tool_name="run_pre_commit")
    all_files = _optional_bool_argument(arguments, "all_files", tool_name="run_pre_commit") or False
    _reject_unknown_arguments(arguments, allowed_names={"hook_id", "all_files"}, tool_name="run_pre_commit")
    try:
        return _format_result(runner.run_pre_commit(PreCommitRunCommand(hook_id=hook_id, all_files=all_files)))
    except PreCommitRunError as err:
        raise RuntimeError(_PRE_COMMIT_TOOL_FAILURE_MESSAGE) from err


def _format_result(result: PreCommitRunResult) -> str:
    lines = [
        f"status\t{result.status.value}",
        f"returncode\t{'' if result.returncode is None else result.returncode}",
    ]
    if "duration_seconds" in result.metadata:
        lines.append(f"duration_seconds\t{result.metadata['duration_seconds']}")
    lines.append("side_effects\tpre-commit hooks may modify files or caches")
    if result.stdout:
        lines.extend(("stdout", result.stdout))
    if result.stderr:
        lines.extend(("stderr", result.stderr))
    return "\n".join(lines)


def _reject_unknown_arguments(
    arguments: Mapping[str, SafeRuntimeMetadataValue], *, allowed_names: set[str], tool_name: str
) -> None:
    unknown_names = set(arguments) - allowed_names
    if unknown_names:
        msg = f"{tool_name} received unsupported argument(s): {', '.join(sorted(unknown_names))}"
        raise ValueError(msg)


def _optional_string_argument(
    arguments: Mapping[str, SafeRuntimeMetadataValue], name: str, *, tool_name: str
) -> str | None:
    if name not in arguments:
        return None
    value = arguments[name]
    if not isinstance(value, str):
        msg = f"{tool_name} {name} argument must be a string"
        raise TypeError(msg)
    return value


def _optional_bool_argument(
    arguments: Mapping[str, SafeRuntimeMetadataValue], name: str, *, tool_name: str
) -> bool | None:
    if name not in arguments:
        return None
    value = arguments[name]
    if not isinstance(value, bool):
        msg = f"{tool_name} {name} argument must be a boolean"
        raise TypeError(msg)
    return value
