"""Tests for the read-only git context registered-tool bridge."""

from dataclasses import dataclass, field

import pytest

from fabrica.features.agent_runtime.adapters.outbound.registered_tool import RegisteredTool, RegisteredToolExecutor
from fabrica.features.agent_runtime.application.dtos import (
    SafeRuntimeMetadataValue,
    ToolCallRequest,
    ToolCallResult,
    ToolCallResultStatus,
    ToolDefinition,
    ToolLoopLimits,
)
from fabrica.features.developer_workflow.adapters.outbound.git_registered_tool import (
    create_git_context_registered_tools,
)
from fabrica.features.developer_workflow.application.dtos import (
    GitBranchAheadBehind,
    GitCommitDetails,
    GitCommitLog,
    GitCommitSummary,
    GitContextChangedFile,
    GitContextChangedFileList,
    GitContextChangedFileStatus,
    GitContextDiff,
    GitContextFailureCategory,
    GitContextLogCount,
    GitMergeBase,
    GitStatusSummary,
)
from fabrica.features.developer_workflow.application.ports import GitContextLoadError


@dataclass
class FakeGitContextLoader:
    status_summary: GitStatusSummary = field(
        default_factory=lambda: GitStatusSummary(
            branch="main",
            head_short_hash="abc1234",
            upstream="origin/main",
            staged_count=1,
            unstaged_count=2,
            untracked_count=1,
            staged_paths=("src/staged.py",),
            unstaged_paths=("src/unstaged.py",),
            untracked_paths=("notes.txt",),
        ),
    )
    changed_files: GitContextChangedFileList = field(
        default_factory=lambda: GitContextChangedFileList(
            files=(
                GitContextChangedFile(path="src/app.py", status=GitContextChangedFileStatus.MODIFIED),
                GitContextChangedFile(
                    path="docs/new.md",
                    status=GitContextChangedFileStatus.RENAMED,
                    old_path="docs/old.md",
                ),
            ),
        ),
    )
    diff: GitContextDiff = field(default_factory=lambda: GitContextDiff(text="diff --git a/src/app.py b/src/app.py\n"))
    commit_log: GitCommitLog = field(
        default_factory=lambda: GitCommitLog(
            commits=(
                GitCommitSummary(
                    commit_hash="abcdef1234567890",
                    short_hash="abcdef1",
                    subject="Add thing",
                    author_date="2026-08-07T19:00:00+00:00",
                    refs=("HEAD -> main",),
                ),
            ),
        ),
    )
    commit_details: GitCommitDetails = field(
        default_factory=lambda: GitCommitDetails(
            commit_hash="abcdef1234567890",
            short_hash="abcdef1",
            parents=("1234567890abcdef",),
            author="Ada Lovelace <ada@example.com>",
            author_date="2026-08-07T19:00:00+00:00",
            committer_date="2026-08-07T19:01:00+00:00",
            subject="Add thing",
            body="Body text",
            refs=("HEAD -> main",),
        ),
    )
    ahead_behind: GitBranchAheadBehind = field(
        default_factory=lambda: GitBranchAheadBehind(
            current_branch="feature",
            base_ref="origin/main",
            ahead_count=3,
            behind_count=1,
        ),
    )
    merge_base: GitMergeBase = field(
        default_factory=lambda: GitMergeBase(commit_hash="1234567890abcdef", short_hash="1234567"),
    )
    error: GitContextLoadError | None = None
    calls: list[tuple[str, tuple[object, ...]]] = field(default_factory=list)

    def load_status_summary(self) -> GitStatusSummary:
        self.calls.append(("load_status_summary", ()))
        self._raise_error_if_configured()
        return self.status_summary

    def list_unstaged_files(self) -> GitContextChangedFileList:
        self.calls.append(("list_unstaged_files", ()))
        self._raise_error_if_configured()
        return self.changed_files

    def load_unstaged_diff(self) -> GitContextDiff:
        self.calls.append(("load_unstaged_diff", ()))
        self._raise_error_if_configured()
        return self.diff

    def load_unstaged_file_diff(self, path: str) -> GitContextDiff:
        self.calls.append(("load_unstaged_file_diff", (path,)))
        self._raise_error_if_configured()
        return GitContextDiff(text=f"diff --git a/{path} b/{path}\n")

    def list_commits(self, count: GitContextLogCount | None = None) -> GitCommitLog:
        self.calls.append(("list_commits", (count.count if count is not None else None,)))
        self._raise_error_if_configured()
        return self.commit_log

    def load_commit_details(self, commit: str) -> GitCommitDetails:
        self.calls.append(("load_commit_details", (commit,)))
        self._raise_error_if_configured()
        return self.commit_details

    def list_commit_changed_files(self, commit: str) -> GitContextChangedFileList:
        self.calls.append(("list_commit_changed_files", (commit,)))
        self._raise_error_if_configured()
        return self.changed_files

    def load_commit_diff(self, commit: str) -> GitContextDiff:
        self.calls.append(("load_commit_diff", (commit,)))
        self._raise_error_if_configured()
        return self.diff

    def load_commit_file_diff(self, commit: str, path: str) -> GitContextDiff:
        self.calls.append(("load_commit_file_diff", (commit, path)))
        self._raise_error_if_configured()
        return GitContextDiff(text=f"diff --git a/{path} b/{path}\n")

    def list_ref_changed_files(self, base_ref: str, head_ref: str) -> GitContextChangedFileList:
        self.calls.append(("list_ref_changed_files", (base_ref, head_ref)))
        self._raise_error_if_configured()
        return self.changed_files

    def load_ref_diff(self, base_ref: str, head_ref: str) -> GitContextDiff:
        self.calls.append(("load_ref_diff", (base_ref, head_ref)))
        self._raise_error_if_configured()
        return self.diff

    def load_ref_file_diff(self, base_ref: str, head_ref: str, path: str) -> GitContextDiff:
        self.calls.append(("load_ref_file_diff", (base_ref, head_ref, path)))
        self._raise_error_if_configured()
        return GitContextDiff(text=f"diff --git a/{path} b/{path}\n")

    def load_branch_ahead_behind(self, base_ref: str | None = None) -> GitBranchAheadBehind:
        self.calls.append(("load_branch_ahead_behind", (base_ref,)))
        self._raise_error_if_configured()
        return self.ahead_behind

    def load_merge_base(self, base_ref: str, head_ref: str) -> GitMergeBase:
        self.calls.append(("load_merge_base", (base_ref, head_ref)))
        self._raise_error_if_configured()
        return self.merge_base

    def _raise_error_if_configured(self) -> None:
        if self.error is not None:
            raise self.error


def test_factory_creates_exact_read_only_git_context_tool_names_and_empty_schema_definition() -> None:
    tools = _create_tools(FakeGitContextLoader())

    assert tuple(tool.definition.name for tool in tools) == (
        "git_status_summary",
        "git_unstaged_files",
        "git_unstaged_diff",
        "git_unstaged_file_diff",
        "git_commit_log",
        "git_commit_details",
        "git_commit_changed_files",
        "git_commit_diff",
        "git_commit_file_diff",
        "git_ref_changed_files",
        "git_ref_diff",
        "git_ref_file_diff",
        "git_branch_ahead_behind",
        "git_merge_base",
    )
    assert tools[0].definition == ToolDefinition(
        name="git_status_summary",
        description="Return a bounded summary of the current git worktree state without raw diffs.",
        argument_schema={"type": "object", "properties": {}, "additionalProperties": False},
    )


def test_factory_uses_narrow_json_schemas_without_additional_properties() -> None:
    tools = _create_tools(FakeGitContextLoader())
    definitions = {tool.definition.name: tool.definition for tool in tools}

    assert definitions["git_unstaged_file_diff"].argument_schema == {
        "type": "object",
        "properties": {
            "path": {
                "type": "string",
                "description": (
                    "Relative path of a changed file to inspect. Must be listed by the matching changed-files tool."
                ),
            },
        },
        "required": ("path",),
        "additionalProperties": False,
    }
    assert definitions["git_commit_log"].argument_schema["additionalProperties"] is False
    assert definitions["git_commit_file_diff"].argument_schema["required"] == ("commit", "path")
    assert definitions["git_ref_file_diff"].argument_schema["required"] == ("base_ref", "head_ref", "path")
    assert definitions["git_branch_ahead_behind"].argument_schema["additionalProperties"] is False


def test_worktree_tools_return_deterministic_structured_text() -> None:
    loader = FakeGitContextLoader()

    status = _execute("git_status_summary", loader=loader)
    files = _execute("git_unstaged_files", loader=loader)
    diff = _execute("git_unstaged_diff", loader=loader)
    file_diff = _execute("git_unstaged_file_diff", loader=loader, arguments={"path": "src/app.py"})

    assert status.status is ToolCallResultStatus.SUCCESS
    assert status.result_text == (
        "branch\tmain\n"
        "head_short_hash\tabc1234\n"
        "upstream\torigin/main\n"
        "staged_count\t1\n"
        "unstaged_count\t2\n"
        "untracked_count\t1\n"
        "staged\tsrc/staged.py\n"
        "unstaged\tsrc/unstaged.py\n"
        "untracked\tnotes.txt"
    )
    assert files.result_text == "M\tsrc/app.py\nR\tdocs/new.md\told_path=docs/old.md"
    assert diff.result_text == "diff --git a/src/app.py b/src/app.py\n"
    assert file_diff.result_text == "diff --git a/src/app.py b/src/app.py\n"
    assert loader.calls == [
        ("load_status_summary", ()),
        ("list_unstaged_files", ()),
        ("load_unstaged_diff", ()),
        ("load_unstaged_file_diff", ("src/app.py",)),
    ]


def test_commit_tools_pass_validated_arguments_and_return_structured_text() -> None:
    loader = FakeGitContextLoader()

    log = _execute("git_commit_log", loader=loader, arguments={"count": 3})
    details = _execute("git_commit_details", loader=loader, arguments={"commit": "HEAD"})
    files = _execute("git_commit_changed_files", loader=loader, arguments={"commit": "HEAD"})
    diff = _execute("git_commit_diff", loader=loader, arguments={"commit": "HEAD"})
    file_diff = _execute("git_commit_file_diff", loader=loader, arguments={"commit": "HEAD", "path": "src/app.py"})

    assert log.result_text == "abcdef1\t2026-08-07T19:00:00+00:00\tAdd thing\trefs=HEAD -> main"
    assert details.result_text == (
        "commit\tabcdef1234567890\n"
        "short_hash\tabcdef1\n"
        "parents\t1234567890abcdef\n"
        "author\tAda Lovelace <ada@example.com>\n"
        "author_date\t2026-08-07T19:00:00+00:00\n"
        "committer_date\t2026-08-07T19:01:00+00:00\n"
        "refs\tHEAD -> main\n"
        "subject\tAdd thing\n"
        "body\n"
        "Body text"
    )
    assert files.result_text == "M\tsrc/app.py\nR\tdocs/new.md\told_path=docs/old.md"
    assert diff.status is ToolCallResultStatus.SUCCESS
    assert file_diff.result_text == "diff --git a/src/app.py b/src/app.py\n"
    assert loader.calls == [
        ("list_commits", (3,)),
        ("load_commit_details", ("HEAD",)),
        ("list_commit_changed_files", ("HEAD",)),
        ("load_commit_diff", ("HEAD",)),
        ("load_commit_file_diff", ("HEAD", "src/app.py")),
    ]


def test_ref_tools_pass_validated_arguments_and_return_structured_text() -> None:
    loader = FakeGitContextLoader()

    files = _execute("git_ref_changed_files", loader=loader, arguments={"base_ref": "main", "head_ref": "HEAD"})
    diff = _execute("git_ref_diff", loader=loader, arguments={"base_ref": "main", "head_ref": "HEAD"})
    file_diff = _execute(
        "git_ref_file_diff",
        loader=loader,
        arguments={"base_ref": "main", "head_ref": "HEAD", "path": "src/app.py"},
    )
    ahead_behind = _execute("git_branch_ahead_behind", loader=loader, arguments={"base_ref": "origin/main"})
    merge_base = _execute("git_merge_base", loader=loader, arguments={"base_ref": "main", "head_ref": "HEAD"})

    assert files.result_text == "M\tsrc/app.py\nR\tdocs/new.md\told_path=docs/old.md"
    assert diff.status is ToolCallResultStatus.SUCCESS
    assert file_diff.result_text == "diff --git a/src/app.py b/src/app.py\n"
    assert ahead_behind.result_text == (
        "current_branch\tfeature\nbase_ref\torigin/main\nahead_count\t3\nbehind_count\t1"
    )
    assert merge_base.result_text == "commit\t1234567890abcdef\nshort_hash\t1234567"
    assert loader.calls == [
        ("list_ref_changed_files", ("main", "HEAD")),
        ("load_ref_diff", ("main", "HEAD")),
        ("load_ref_file_diff", ("main", "HEAD", "src/app.py")),
        ("load_branch_ahead_behind", ("origin/main",)),
        ("load_merge_base", ("main", "HEAD")),
    ]


@pytest.mark.parametrize(
    ("tool_name", "arguments"),
    [
        ("git_status_summary", {"unexpected": "value"}),
        ("git_unstaged_file_diff", {}),
        ("git_unstaged_file_diff", {"path": "src/app.py", "extra": "nope"}),
        ("git_unstaged_file_diff", {"path": 123}),
        ("git_commit_log", {"count": True}),
        ("git_commit_log", {"count": 999}),
        ("git_commit_details", {"commit": 123}),
        ("git_commit_file_diff", {"commit": "HEAD"}),
        ("git_ref_changed_files", {"base_ref": "main"}),
        ("git_ref_file_diff", {"base_ref": "main", "head_ref": "HEAD", "path": 123}),
        ("git_branch_ahead_behind", {"base_ref": 123}),
    ],
)
def test_invalid_arguments_map_to_safe_invalid_request_without_calling_loaders(
    tool_name: str,
    arguments: dict[str, SafeRuntimeMetadataValue],
) -> None:
    loader = FakeGitContextLoader()

    result = _execute(tool_name, loader=loader, arguments=arguments)

    assert result.status is ToolCallResultStatus.INVALID_ARGUMENTS
    assert loader.calls == []


def test_loader_failures_map_to_safe_tool_failure_without_private_details() -> None:
    loader = FakeGitContextLoader(
        error=GitContextLoadError(
            "private stderr /Users/example/project secret diff",
            category=GitContextFailureCategory.GIT_FAILED,
            metadata={"working_directory": "/Users/example/project", "raw_stderr": "secret"},
        ),
    )

    result = _execute("git_ref_diff", loader=loader, arguments={"base_ref": "main", "head_ref": "HEAD"})

    assert result.status is ToolCallResultStatus.TOOL_FAILURE
    assert result.error_message == "registered tool execution failed"
    assert "/Users/example/project" not in str(result)
    assert "secret" not in str(result)
    assert "private stderr" not in str(result)


def test_tool_result_limit_remains_governed_by_registered_tool_executor() -> None:
    loader = FakeGitContextLoader(diff=GitContextDiff(text="abcdef"))

    result = _execute(
        "git_unstaged_diff",
        loader=loader,
        limits=ToolLoopLimits(max_tool_iterations=1, max_tool_result_chars=3),
    )

    assert result.status is ToolCallResultStatus.LIMIT_EXCEEDED
    assert result.result_text == "abc"
    assert result.error_message == "registered tool result exceeded output limit"


def _create_tools(loader: FakeGitContextLoader) -> tuple[RegisteredTool, ...]:
    return create_git_context_registered_tools(
        worktree_loader=loader,
        commit_loader=loader,
        ref_loader=loader,
    )


def _execute(
    tool_name: str,
    *,
    loader: FakeGitContextLoader,
    arguments: dict[str, SafeRuntimeMetadataValue] | None = None,
    limits: ToolLoopLimits | None = None,
) -> ToolCallResult:
    executor = RegisteredToolExecutor(_create_tools(loader))
    return executor.execute_tool(
        ToolCallRequest(call_id="call-1", tool_name=tool_name, arguments=arguments or {}),
        limits or ToolLoopLimits(),
    )
