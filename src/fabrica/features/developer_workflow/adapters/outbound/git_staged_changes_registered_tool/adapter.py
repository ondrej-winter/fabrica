"""Bridge staged git change loading into application-owned registered tools."""

from collections.abc import Mapping

from fabrica.features.agent_runtime.application.dtos import (
    SafeRuntimeMetadataValue,
    ToolArgumentSchemaValue,
    ToolDefinition,
)
from fabrica.features.agent_runtime.application.ports import RegisteredTool
from fabrica.features.developer_workflow.application.ports import (
    GitStagedChangesLoader,
    GitStagedChangesLoadError,
)

GIT_STAGED_FILES_TOOL_NAME = "git_staged_files"
GIT_STAGED_DIFF_TOOL_NAME = "git_staged_diff"
GIT_STAGED_FILE_DIFF_TOOL_NAME = "git_staged_file_diff"
_EMPTY_ARGUMENT_SCHEMA: Mapping[str, ToolArgumentSchemaValue] = {
    "type": "object",
    "properties": {},
    "additionalProperties": False,
}
_FILE_DIFF_ARGUMENT_SCHEMA: Mapping[str, ToolArgumentSchemaValue] = {
    "type": "object",
    "properties": {
        "path": {
            "type": "string",
            "description": "Relative path of a staged file to inspect. Must be listed by git_staged_files.",
        },
    },
    "required": ("path",),
    "additionalProperties": False,
}
_STAGED_GIT_TOOL_FAILURE_MESSAGE = "staged git changes could not be loaded"


def create_git_staged_changes_registered_tools(loader: GitStagedChangesLoader) -> tuple[RegisteredTool, ...]:
    """Create model-callable tools for explicitly supplied staged git loading."""
    return (
        RegisteredTool(
            definition=ToolDefinition(
                name=GIT_STAGED_FILES_TOOL_NAME,
                description="List currently staged git files and their staged statuses.",
                argument_schema=_EMPTY_ARGUMENT_SCHEMA,
            ),
            handler=lambda arguments: _handle_staged_files(loader, arguments),
        ),
        RegisteredTool(
            definition=ToolDefinition(
                name=GIT_STAGED_DIFF_TOOL_NAME,
                description="Return the bounded full staged git diff.",
                argument_schema=_EMPTY_ARGUMENT_SCHEMA,
            ),
            handler=lambda arguments: _handle_staged_diff(loader, arguments),
        ),
        RegisteredTool(
            definition=ToolDefinition(
                name=GIT_STAGED_FILE_DIFF_TOOL_NAME,
                description="Return the bounded staged git diff for one staged file path.",
                argument_schema=_FILE_DIFF_ARGUMENT_SCHEMA,
            ),
            handler=lambda arguments: _handle_staged_file_diff(loader, arguments),
        ),
    )


def _handle_staged_files(loader: GitStagedChangesLoader, arguments: Mapping[str, SafeRuntimeMetadataValue]) -> str:
    _require_no_arguments(arguments)
    try:
        staged_files = loader.list_files()
    except GitStagedChangesLoadError as err:
        raise RuntimeError(_STAGED_GIT_TOOL_FAILURE_MESSAGE) from err
    return "\n".join(f"{file.status.value}\t{file.path}" for file in staged_files.files)


def _handle_staged_diff(loader: GitStagedChangesLoader, arguments: Mapping[str, SafeRuntimeMetadataValue]) -> str:
    _require_no_arguments(arguments)
    try:
        return loader.load_diff().text
    except GitStagedChangesLoadError as err:
        raise RuntimeError(_STAGED_GIT_TOOL_FAILURE_MESSAGE) from err


def _handle_staged_file_diff(loader: GitStagedChangesLoader, arguments: Mapping[str, SafeRuntimeMetadataValue]) -> str:
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
