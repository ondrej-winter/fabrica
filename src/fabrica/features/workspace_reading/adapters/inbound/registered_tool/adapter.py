"""Expose bounded workspace file reading as one model-facing registered tool."""

import json
from collections.abc import Mapping
from dataclasses import dataclass

from fabrica.features.agent_runtime.application.dtos import (
    RegisteredToolOutcome,
    ToolArgumentValue,
    ToolDefinition,
    ToolExecutionContext,
    ToolImageContent,
    ToolMutationGuarantee,
    ToolTextContent,
)
from fabrica.features.agent_runtime.application.ports import AsyncRegisteredTool
from fabrica.features.workspace_reading.application.dtos import (
    DEFAULT_MAX_FILES_PER_CALL,
    ImageFileResult,
    ReadFileFailure,
    ReadFileRequest,
    ReadFilesCommand,
    ReadFilesLimits,
    ReadFilesResult,
    TextFileResult,
)
from fabrica.features.workspace_reading.application.ports import ReadFilesPort, WorkspaceReadContext

READ_FILES_TOOL_NAME = "read_files"
READ_FILES_TOOL_DESCRIPTION = """Read one or more files from the workspace.

Each file entry requires a workspace-relative path and may include
inclusive one-based start_line/end_line bounds.

Read multiple independent files together in one call.

Text results include line numbers and pagination metadata. Large reads are
bounded; use next_start_line or a narrower range to continue reading.

Supported image files are returned as image input when the current model
supports images.

Prefer read_files over shell commands when you only need file contents."""
READ_FILES_TOOL_DEFINITION = ToolDefinition(
    name=READ_FILES_TOOL_NAME,
    description=READ_FILES_TOOL_DESCRIPTION,
    argument_schema={
        "type": "object",
        "properties": {
            "files": {
                "type": "array",
                "minItems": 1,
                "maxItems": DEFAULT_MAX_FILES_PER_CALL,
                "items": {
                    "type": "object",
                    "properties": {
                        "path": {"type": "string", "minLength": 1},
                        "start_line": {"type": ("integer", "null"), "minimum": 1},
                        "end_line": {"type": ("integer", "null"), "minimum": 1},
                    },
                    "required": ("path",),
                    "additionalProperties": False,
                },
            },
        },
        "required": ("files",),
        "additionalProperties": False,
    },
)


@dataclass(frozen=True, slots=True)
class ReadFilesRegisteredToolAdapter:
    """Map canonical model arguments to the workspace-reading inbound port."""

    use_case: ReadFilesPort
    limits: ReadFilesLimits
    external_read_authorized: bool = False
    image_input_supported: bool = False

    async def handle(
        self,
        arguments: Mapping[str, ToolArgumentValue],
        context: ToolExecutionContext,
    ) -> RegisteredToolOutcome:
        """Validate a canonical request and return ordered provider-neutral content."""
        try:
            command = _command_from_arguments(arguments)
        except (TypeError, ValueError) as err:
            return RegisteredToolOutcome.recoverable_rejection(
                error_code="INVALID_ARGUMENTS",
                error_message=str(err),
            )

        result = await self.use_case.read(
            command,
            WorkspaceReadContext(
                external_read_authorized=self.external_read_authorized,
                image_input_supported=self.image_input_supported,
                cancellation=context.cancellation,
                deadline_at=context.phase_deadline("read_files"),
                limits=self.limits,
            ),
        )
        return read_files_result_to_tool_outcome(result)


def create_read_files_registered_tool(
    use_case: ReadFilesPort,
    *,
    limits: ReadFilesLimits | None = None,
    external_read_authorized: bool = False,
    image_input_supported: bool = False,
) -> AsyncRegisteredTool:
    """Create the sole model-facing registered tool for workspace reading."""
    adapter = ReadFilesRegisteredToolAdapter(
        use_case=use_case,
        limits=limits or ReadFilesLimits(),
        external_read_authorized=external_read_authorized,
        image_input_supported=image_input_supported,
    )
    return AsyncRegisteredTool(definition=READ_FILES_TOOL_DEFINITION, handler=adapter.handle)


def read_files_result_to_tool_outcome(result: ReadFilesResult) -> RegisteredToolOutcome:
    """Translate bounded application outcomes to ordered text and image parts."""
    content = tuple(part for file_result in result.results for part in _content_parts(file_result))
    return RegisteredToolOutcome.model_continue_success(
        mutation_guarantee=ToolMutationGuarantee.NO_MUTATION,
        content=content,
    )


def _command_from_arguments(arguments: Mapping[str, ToolArgumentValue]) -> ReadFilesCommand:
    if set(arguments) != {"files"}:
        msg = "read_files requires exactly one `files` argument"
        raise ValueError(msg)
    raw_files = arguments["files"]
    if not isinstance(raw_files, tuple) or not raw_files:
        msg = "read_files requires a non-empty `files` array"
        raise ValueError(msg)
    if len(raw_files) > DEFAULT_MAX_FILES_PER_CALL:
        msg = f"read_files accepts at most {DEFAULT_MAX_FILES_PER_CALL} files"
        raise ValueError(msg)
    return ReadFilesCommand(files=tuple(_request_from_value(value) for value in raw_files))


def _request_from_value(value: ToolArgumentValue) -> ReadFileRequest:
    if not isinstance(value, Mapping) or not value:
        msg = "each files entry must be an object"
        raise ValueError(msg)
    if set(value) - {"path", "start_line", "end_line"}:
        msg = "files entries must not include additional properties"
        raise ValueError(msg)
    path = value.get("path")
    if not isinstance(path, str):
        msg = "each files entry requires a string `path`"
        raise TypeError(msg)
    return ReadFileRequest(
        path=path,
        start_line=_line_number(value.get("start_line"), field_name="start_line"),
        end_line=_line_number(value.get("end_line"), field_name="end_line"),
    )


def _line_number(value: ToolArgumentValue | None, *, field_name: str) -> int | None:
    if value is None:
        return None
    if isinstance(value, bool) or not isinstance(value, int) or value < 1:
        msg = f"{field_name} must be a positive integer or null"
        raise ValueError(msg)
    return value


def _content_parts(
    result: TextFileResult | ImageFileResult | ReadFileFailure,
) -> tuple[ToolTextContent | ToolImageContent, ...]:
    payload = _result_payload(result)
    text = ToolTextContent(text=json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False))
    if isinstance(result, ImageFileResult):
        return (text, ToolImageContent(data=result.image.data, media_type=result.image.media_type))
    return (text,)


def _result_payload(result: TextFileResult | ImageFileResult | ReadFileFailure) -> dict[str, object]:
    if isinstance(result, TextFileResult):
        return {
            "path": result.path,
            "success": True,
            "type": result.type.value,
            "content": result.content,
            "start_line": result.start_line,
            "end_line": result.end_line,
            "complete": result.complete,
            "next_start_line": result.next_start_line,
            "total_lines": result.total_lines,
            "total_lines_exact": result.total_lines_exact,
            "truncated_lines": list(result.truncated_lines),
        }
    if isinstance(result, ImageFileResult):
        return {
            "path": result.path,
            "success": True,
            "type": result.type.value,
            "media_type": result.image.media_type,
        }
    return {
        "path": result.path,
        "success": False,
        "error": {
            "code": result.error.code.value,
            "message": result.error.message,
            "metadata": dict(result.error.metadata),
        },
    }


__all__ = [
    "READ_FILES_TOOL_DEFINITION",
    "READ_FILES_TOOL_DESCRIPTION",
    "READ_FILES_TOOL_NAME",
    "ReadFilesRegisteredToolAdapter",
    "create_read_files_registered_tool",
    "read_files_result_to_tool_outcome",
]
