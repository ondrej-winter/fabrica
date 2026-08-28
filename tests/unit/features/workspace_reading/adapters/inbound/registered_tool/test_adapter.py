"""Tests for the model-facing read-files registered-tool adapter."""

import json
from asyncio import run
from dataclasses import dataclass
from typing import cast

import pytest

from fabrica.features.agent_runtime.application.dtos import (
    MAX_TOOL_CONTENT_PARTS,
    RegisteredToolOutcome,
    ToolArgumentSchemaValue,
    ToolArgumentValue,
    ToolExecutionContext,
    ToolImageContent,
    ToolMutationGuarantee,
    ToolOutcomeStatus,
    ToolTextContent,
    canonical_tool_arguments_digest,
)
from fabrica.features.workspace_reading.adapters.inbound.registered_tool import (
    READ_FILES_TOOL_DEFINITION,
    READ_FILES_TOOL_DESCRIPTION,
    READ_FILES_TOOL_NAME,
    ReadFilesRegisteredToolAdapter,
    create_read_files_registered_tool,
)
from fabrica.features.workspace_reading.application.dtos import (
    ImageContent,
    ImageFileResult,
    ReadFileError,
    ReadFileErrorCode,
    ReadFileFailure,
    ReadFilesCommand,
    ReadFilesLimits,
    ReadFilesResult,
    TextFileResult,
)
from fabrica.features.workspace_reading.application.ports import WorkspaceReadContext

FIRST_START_LINE = 2
LAST_END_LINE = 3


def test_read_files_registered_tool_exposes_the_canonical_schema_and_description() -> None:
    tool = create_read_files_registered_tool(_FakeReadFiles(_text_result()))

    assert tool.definition == READ_FILES_TOOL_DEFINITION
    assert tool.definition.name == READ_FILES_TOOL_NAME
    assert tool.definition.argument_schema == READ_FILES_TOOL_DEFINITION.argument_schema
    schema = cast("dict[str, ToolArgumentSchemaValue]", tool.definition.argument_schema)
    properties = cast("dict[str, ToolArgumentSchemaValue]", schema["properties"])
    files = cast("dict[str, ToolArgumentSchemaValue]", properties["files"])
    assert schema["required"] == ("files",)
    assert schema["additionalProperties"] is False
    assert files["minItems"] == 1
    assert files["maxItems"] == 20  # noqa: PLR2004
    items = cast("dict[str, ToolArgumentSchemaValue]", files["items"])
    assert items["additionalProperties"] is False
    assert READ_FILES_TOOL_DESCRIPTION.startswith("Read one or more files from the workspace.")
    assert "Prefer read_files over shell commands" in READ_FILES_TOOL_DESCRIPTION


def test_read_files_registered_tool_maps_arguments_and_runtime_context_to_the_use_case() -> None:
    use_case = _FakeReadFiles(_text_result())
    limits = ReadFilesLimits(max_read_lines=10)
    adapter = ReadFilesRegisteredToolAdapter(
        use_case=use_case,
        limits=limits,
        external_read_authorized=True,
        image_input_supported=True,
    )
    arguments = {"files": ({"path": "src/example.py", "start_line": FIRST_START_LINE, "end_line": LAST_END_LINE},)}

    outcome = run(adapter.handle(arguments, _context()))

    assert use_case.command is not None
    assert use_case.command.files[0].path == "src/example.py"
    assert use_case.command.files[0].start_line == FIRST_START_LINE
    assert use_case.command.files[0].end_line == LAST_END_LINE
    assert use_case.context == WorkspaceReadContext(
        external_read_authorized=True,
        image_input_supported=True,
        cancellation=_NeverCancelled(),
        deadline_at=None,
        limits=limits,
    )
    assert outcome.status is ToolOutcomeStatus.SUCCESS
    assert outcome.mutation_guarantee is ToolMutationGuarantee.NO_MUTATION
    assert json.loads(_text_part(outcome).text)["content"] == "2 | second\n3 | third"


def test_read_files_registered_tool_rejects_invalid_arguments_before_use_case_execution() -> None:
    use_case = _FakeReadFiles(_text_result())
    adapter = ReadFilesRegisteredToolAdapter(use_case=use_case, limits=ReadFilesLimits())

    outcome = run(adapter.handle({"files": ({"path": "src/example.py", "unexpected": True},)}, _context()))

    assert use_case.command is None
    assert outcome.status is ToolOutcomeStatus.REJECTED
    assert outcome.error_code == "INVALID_ARGUMENTS"


@pytest.mark.parametrize(
    "arguments",
    [
        {"unexpected": "value"},
        {"files": ()},
        {"files": tuple({"path": f"file-{index}.py"} for index in range(21))},
        {"files": ("not an object",)},
        {"files": ({"path": 1},)},
        {"files": ({"path": "src/example.py", "start_line": False},)},
    ],
)
def test_read_files_registered_tool_rejects_each_invalid_canonical_argument_shape_before_execution(
    arguments: dict[str, object],
) -> None:
    use_case = _FakeReadFiles(_text_result())
    adapter = ReadFilesRegisteredToolAdapter(use_case=use_case, limits=ReadFilesLimits())

    outcome = run(adapter.handle(cast("dict[str, ToolArgumentValue]", arguments), _context()))

    assert use_case.command is None
    assert outcome.status is ToolOutcomeStatus.REJECTED
    assert outcome.error_code == "INVALID_ARGUMENTS"


def test_read_files_registered_tool_returns_ordered_text_image_and_failure_parts() -> None:
    result = ReadFilesResult(
        results=(
            TextFileResult(
                path="src/example.py",
                content="1 | text",
                start_line=1,
                end_line=1,
                complete=True,
                next_start_line=None,
                total_lines=1,
                total_lines_exact=True,
            ),
            ImageFileResult(
                path="diagram.png",
                image=ImageContent(path="diagram.png", media_type="image/png", data=b"\x89PNG\r\n\x1a\nimage"),
            ),
            ReadFileFailure("missing.py", ReadFileError(ReadFileErrorCode.NOT_FOUND)),
        ),
    )

    adapter = ReadFilesRegisteredToolAdapter(_FakeReadFiles(result), ReadFilesLimits())
    outcome = run(adapter.handle(_arguments(), _context()))

    assert tuple(type(part) for part in outcome.content) == (
        ToolTextContent,
        ToolTextContent,
        ToolImageContent,
        ToolTextContent,
    )
    first, image_metadata, image, failure = outcome.content
    assert isinstance(first, ToolTextContent)
    assert isinstance(image_metadata, ToolTextContent)
    assert isinstance(image, ToolImageContent)
    assert isinstance(failure, ToolTextContent)
    assert json.loads(first.text)["path"] == "src/example.py"
    assert json.loads(image_metadata.text)["media_type"] == "image/png"
    assert image.data == b"\x89PNG\r\n\x1a\nimage"
    assert json.loads(failure.text)["error"]["code"] == "NOT_FOUND"


def test_read_files_registered_tool_supports_the_full_twenty_image_batch_with_metadata() -> None:
    result = ReadFilesResult(
        results=tuple(
            ImageFileResult(
                path=f"image-{index}.png",
                image=ImageContent(path=f"image-{index}.png", media_type="image/png", data=b"\x89PNG\r\n\x1a\nimage"),
            )
            for index in range(20)
        ),
    )

    adapter = ReadFilesRegisteredToolAdapter(_FakeReadFiles(result), ReadFilesLimits())
    outcome = run(adapter.handle(_arguments(20), _context()))

    assert len(outcome.content) == MAX_TOOL_CONTENT_PARTS


def _text_result() -> ReadFilesResult:
    return ReadFilesResult(
        results=(
            TextFileResult(
                path="src/example.py",
                content="2 | second\n3 | third",
                start_line=2,
                end_line=3,
                complete=True,
                next_start_line=None,
                total_lines=3,
                total_lines_exact=True,
            ),
        ),
    )


def _arguments(count: int = 1) -> dict[str, tuple[dict[str, str], ...]]:
    return {"files": tuple({"path": f"file-{index}.py"} for index in range(count))}


def _text_part(outcome: RegisteredToolOutcome) -> ToolTextContent:
    content = outcome.content
    assert isinstance(content[0], ToolTextContent)
    return content[0]


@dataclass(slots=True)
class _FakeReadFiles:
    result: ReadFilesResult
    command: ReadFilesCommand | None = None
    context: WorkspaceReadContext | None = None

    async def read(self, command: ReadFilesCommand, context: WorkspaceReadContext) -> ReadFilesResult:
        self.command = command
        self.context = context
        return self.result


def _context() -> ToolExecutionContext:
    arguments = _arguments()
    return ToolExecutionContext(
        call_id="call-1",
        argument_digest=canonical_tool_arguments_digest(arguments),
        cancellation=_NeverCancelled(),
    )


@dataclass(frozen=True, slots=True)
class _NeverCancelled:
    @property
    def is_cancelled(self) -> bool:
        return False

    async def wait_until_cancelled(self) -> None:
        return None
