"""Tests for the staged git registered-tool bridge."""

from dataclasses import dataclass, field

import pytest

from fabrica.features.agent_runtime.adapters.outbound.registered_tool import RegisteredToolExecutor
from fabrica.features.agent_runtime.application.dtos import (
    SafeRuntimeMetadataValue,
    ToolCallRequest,
    ToolCallResultStatus,
    ToolDefinition,
    ToolLoopLimits,
)
from fabrica.features.developer_workflow.adapters.outbound.git_registered_tool import (
    create_git_staged_changes_registered_tools,
)
from fabrica.features.developer_workflow.application.dtos import (
    GitStagedChangesFailureCategory,
    GitStagedDiff,
    GitStagedFile,
    GitStagedFileList,
    GitStagedFileStatus,
)
from fabrica.features.developer_workflow.application.ports import GitStagedChangesLoadError


@dataclass
class FakeGitStagedChangesLoader:
    staged_files: GitStagedFileList = field(
        default_factory=lambda: GitStagedFileList(
            files=(
                GitStagedFile(path="src/file.py", status=GitStagedFileStatus.MODIFIED),
                GitStagedFile(path="docs/readme.md", status=GitStagedFileStatus.ADDED),
            ),
        ),
    )
    diff: GitStagedDiff = field(default_factory=lambda: GitStagedDiff(text="diff --git a/src/file.py b/src/file.py\n"))
    file_diffs: dict[str, GitStagedDiff] = field(default_factory=dict)
    error: GitStagedChangesLoadError | None = None
    calls: list[tuple[str, str | None]] = field(default_factory=list)

    def list_files(self) -> GitStagedFileList:
        self.calls.append(("list_files", None))
        if self.error is not None:
            raise self.error
        return self.staged_files

    def load_diff(self) -> GitStagedDiff:
        self.calls.append(("load_diff", None))
        if self.error is not None:
            raise self.error
        return self.diff

    def load_file_diff(self, path: str) -> GitStagedDiff:
        self.calls.append(("load_file_diff", path))
        if self.error is not None:
            raise self.error
        return self.file_diffs.get(path, GitStagedDiff(text=f"diff --git a/{path} b/{path}\n"))

    def load(self) -> GitStagedDiff:
        return self.load_diff()


def test_factory_creates_exact_staged_git_tool_definitions() -> None:
    tools = create_git_staged_changes_registered_tools(FakeGitStagedChangesLoader())

    assert tuple(tool.definition.name for tool in tools) == (
        "git_staged_files",
        "git_staged_diff",
        "git_staged_file_diff",
    )
    assert tools[0].definition == ToolDefinition(
        name="git_staged_files",
        description="List currently staged git files and their staged statuses.",
        argument_schema={"type": "object", "properties": {}, "additionalProperties": False},
    )
    assert tools[1].definition == ToolDefinition(
        name="git_staged_diff",
        description="Return the bounded full staged git diff.",
        argument_schema={"type": "object", "properties": {}, "additionalProperties": False},
    )
    assert tools[2].definition.argument_schema == {
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


def test_git_staged_files_returns_deterministic_status_path_lines() -> None:
    loader = FakeGitStagedChangesLoader()
    result = _execute("git_staged_files", loader=loader)

    assert result.status is ToolCallResultStatus.SUCCESS
    assert result.result_text == "M\tsrc/file.py\nA\tdocs/readme.md"
    assert loader.calls == [("list_files", None)]


def test_git_staged_diff_returns_full_diff_text() -> None:
    loader = FakeGitStagedChangesLoader(diff=GitStagedDiff(text="diff --git a/app.py b/app.py\n+change\n"))
    result = _execute("git_staged_diff", loader=loader)

    assert result.status is ToolCallResultStatus.SUCCESS
    assert result.result_text == "diff --git a/app.py b/app.py\n+change\n"
    assert loader.calls == [("load_diff", None)]


def test_git_staged_file_diff_requires_single_string_path_argument() -> None:
    loader = FakeGitStagedChangesLoader()

    assert _execute("git_staged_file_diff", loader=loader).status is ToolCallResultStatus.INVALID_ARGUMENTS
    assert (
        _execute("git_staged_file_diff", loader=loader, arguments={"path": "src/file.py", "extra": "nope"}).status
        is ToolCallResultStatus.INVALID_ARGUMENTS
    )
    assert (
        _execute("git_staged_file_diff", loader=loader, arguments={"path": 123}).status
        is ToolCallResultStatus.INVALID_ARGUMENTS
    )
    assert loader.calls == []


def test_git_staged_file_diff_returns_one_file_diff_text() -> None:
    loader = FakeGitStagedChangesLoader(
        file_diffs={"src/file.py": GitStagedDiff(text="diff --git a/src/file.py b/src/file.py\n+one\n")},
    )

    result = _execute("git_staged_file_diff", loader=loader, arguments={"path": "src/file.py"})

    assert result.status is ToolCallResultStatus.SUCCESS
    assert result.result_text == "diff --git a/src/file.py b/src/file.py\n+one\n"
    assert loader.calls == [("load_file_diff", "src/file.py")]


@pytest.mark.parametrize("tool_name", ["git_staged_files", "git_staged_diff"])
def test_empty_schema_tools_reject_arguments(tool_name: str) -> None:
    loader = FakeGitStagedChangesLoader()

    result = _execute(tool_name, loader=loader, arguments={"unexpected": "value"})

    assert result.status is ToolCallResultStatus.INVALID_ARGUMENTS
    assert loader.calls == []


def test_loader_failures_map_to_safe_tool_failure_without_private_details() -> None:
    loader = FakeGitStagedChangesLoader(
        error=GitStagedChangesLoadError(
            "private stderr /Users/example/project secret diff",
            category=GitStagedChangesFailureCategory.GIT_FAILED,
            metadata={"working_directory": "/Users/example/project", "raw_stderr": "secret"},
        ),
    )

    result = _execute("git_staged_diff", loader=loader)

    assert result.status is ToolCallResultStatus.TOOL_FAILURE
    assert result.error_message == "registered tool execution failed"
    assert "/Users/example/project" not in str(result)
    assert "secret" not in str(result)
    assert "private stderr" not in str(result)


def test_tool_result_limit_remains_governed_by_registered_tool_executor() -> None:
    loader = FakeGitStagedChangesLoader(diff=GitStagedDiff(text="abcdef"))

    result = _execute(
        "git_staged_diff",
        loader=loader,
        limits=ToolLoopLimits(max_tool_iterations=1, max_tool_result_chars=3),
    )

    assert result.status is ToolCallResultStatus.LIMIT_EXCEEDED
    assert result.result_text == "abc"
    assert result.error_message == "registered tool result exceeded output limit"


def _execute(
    tool_name: str,
    *,
    loader: FakeGitStagedChangesLoader,
    arguments: dict[str, SafeRuntimeMetadataValue] | None = None,
    limits: ToolLoopLimits | None = None,
):
    executor = RegisteredToolExecutor(create_git_staged_changes_registered_tools(loader))
    return executor.execute_tool(
        ToolCallRequest(call_id="call-1", tool_name=tool_name, arguments=arguments or {}),
        limits or ToolLoopLimits(),
    )
