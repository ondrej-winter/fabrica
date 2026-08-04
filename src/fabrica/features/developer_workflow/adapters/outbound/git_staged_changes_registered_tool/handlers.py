"""Tool handlers for read-only staged git inspection."""

from collections.abc import Mapping

from fabrica.features.agent_runtime.application.dtos import SafeRuntimeMetadataValue
from fabrica.features.developer_workflow.application.ports import (
    GitStagedChangesLoader,
    GitStagedChangesLoadError,
)

_STAGED_GIT_TOOL_FAILURE_MESSAGE = "staged git changes could not be loaded"


def handle_staged_files(loader: GitStagedChangesLoader, arguments: Mapping[str, SafeRuntimeMetadataValue]) -> str:
    """Return staged file status and path lines for a registered tool call."""
    _require_no_arguments(arguments)
    try:
        staged_files = loader.list_files()
    except GitStagedChangesLoadError as err:
        raise RuntimeError(_STAGED_GIT_TOOL_FAILURE_MESSAGE) from err
    return "\n".join(f"{file.status.value}\t{file.path}" for file in staged_files.files)


def handle_staged_diff(loader: GitStagedChangesLoader, arguments: Mapping[str, SafeRuntimeMetadataValue]) -> str:
    """Return the full staged diff text for a registered tool call."""
    _require_no_arguments(arguments)
    try:
        return loader.load_diff().text
    except GitStagedChangesLoadError as err:
        raise RuntimeError(_STAGED_GIT_TOOL_FAILURE_MESSAGE) from err


def handle_staged_file_diff(loader: GitStagedChangesLoader, arguments: Mapping[str, SafeRuntimeMetadataValue]) -> str:
    """Return the staged diff text for one registered-tool path argument."""
    if set(arguments) != {"path"}:
        msg = "git_staged_file_diff requires exactly the path argument"
        raise ValueError(msg)
    path = arguments["path"]
    if not isinstance(path, str):
        msg = "git_staged_file_diff path argument must be a string"
        raise TypeError(msg)
    try:
        return loader.load_file_diff(path).text
    except GitStagedChangesLoadError as err:
        raise RuntimeError(_STAGED_GIT_TOOL_FAILURE_MESSAGE) from err


def _require_no_arguments(arguments: Mapping[str, SafeRuntimeMetadataValue]) -> None:
    if arguments:
        msg = "staged git tool does not accept arguments"
        raise ValueError(msg)
