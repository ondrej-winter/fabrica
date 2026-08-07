"""Offline integration tests for optional read-only git context tool composition."""

import subprocess
from dataclasses import dataclass, field
from pathlib import Path

from fabrica.bootstrap.composition import (
    ReadOnlyGitContextToolOptions,
    create_read_only_git_context_registered_tools,
    create_tool_loop_runtime,
)
from fabrica.features.agent_runtime.application.dtos import (
    LocalAgentRunCommand,
    ToolAwareModelResponse,
    ToolCallRequest,
    ToolCallResult,
    ToolDefinition,
    ToolLoopLimits,
    ToolLoopRunStatus,
)

EXPECTED_READ_ONLY_GIT_CONTEXT_TOOL_NAMES = (
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


@dataclass
class ReadOnlyGitContextToolAwareModel:
    """Fake model that records explicitly exposed read-only git context tools."""

    requested_tool_name: str | None = None
    requested_arguments: dict[str, str | int | float | bool | None] = field(default_factory=dict)
    calls: list[tuple[LocalAgentRunCommand, tuple[ToolDefinition, ...], tuple[ToolCallResult, ...]]] = field(
        default_factory=list,
    )

    def run_turn(
        self,
        command: LocalAgentRunCommand,
        available_tools: tuple[ToolDefinition, ...],
        tool_results: tuple[ToolCallResult, ...] = (),
    ) -> ToolAwareModelResponse:
        """Request one configured tool, then return the tool result."""
        self.calls.append((command, available_tools, tool_results))
        if self.requested_tool_name is not None and not tool_results:
            return ToolAwareModelResponse(
                tool_calls=(
                    ToolCallRequest(
                        call_id="call-1",
                        tool_name=self.requested_tool_name,
                        arguments=self.requested_arguments,
                    ),
                ),
            )
        if tool_results:
            return ToolAwareModelResponse(output_text=f"final:{tool_results[0].result_text}")
        return ToolAwareModelResponse(output_text="final:no-tools")


def test_read_only_git_context_tool_helper_returns_exact_optional_tools_without_git_io(tmp_path: Path) -> None:
    missing_repository = tmp_path / "not-a-repository"

    tools = create_read_only_git_context_registered_tools(
        ReadOnlyGitContextToolOptions(
            working_directory=missing_repository,
            timeout_seconds=1.0,
        ),
    )

    assert tuple(tool.definition.name for tool in tools) == EXPECTED_READ_ONLY_GIT_CONTEXT_TOOL_NAMES


def test_read_only_git_context_tools_are_exposed_only_when_explicitly_supplied(tmp_path: Path) -> None:
    tools = create_read_only_git_context_registered_tools(ReadOnlyGitContextToolOptions(working_directory=tmp_path))
    model = ReadOnlyGitContextToolAwareModel()

    runtime = create_tool_loop_runtime(model=model, tools=tools)
    empty_runtime = create_tool_loop_runtime(model=ReadOnlyGitContextToolAwareModel(), tools=())

    assert tuple(tool.name for tool in runtime.available_tools) == EXPECTED_READ_ONLY_GIT_CONTEXT_TOOL_NAMES
    assert empty_runtime.available_tools == ()


def test_explicitly_composed_read_only_git_context_tool_runs_through_tool_loop(tmp_path: Path) -> None:
    git_repository = _create_repository_with_unstaged_file(tmp_path)
    model = ReadOnlyGitContextToolAwareModel(requested_tool_name="git_unstaged_files")
    runtime = create_tool_loop_runtime(
        model=model,
        tools=create_read_only_git_context_registered_tools(
            ReadOnlyGitContextToolOptions(working_directory=git_repository),
        ),
        limits=ToolLoopLimits(max_tool_iterations=2, max_tool_result_chars=200),
    )

    result = runtime.run(LocalAgentRunCommand(prompt="Inspect unstaged files."))

    assert result.status is ToolLoopRunStatus.SUCCESS
    assert result.output_text == "final:M\texample.txt"
    assert model.calls[0][1] == runtime.available_tools
    assert model.calls[1][2] == result.tool_results


def _create_repository_with_unstaged_file(tmp_path: Path) -> Path:
    git_repository = tmp_path / "repo"
    git_repository.mkdir()
    _run_git(("git", "init"), cwd=git_repository)
    _run_git(("git", "config", "user.email", "test@example.com"), cwd=git_repository)
    _run_git(("git", "config", "user.name", "Test User"), cwd=git_repository)
    (git_repository / "example.txt").write_text("before\n", encoding="utf-8")
    _run_git(("git", "add", "example.txt"), cwd=git_repository)
    _run_git(("git", "commit", "-m", "Initial commit"), cwd=git_repository)
    (git_repository / "example.txt").write_text("after\n", encoding="utf-8")
    return git_repository


def _run_git(argv: tuple[str, ...], *, cwd: Path) -> None:
    subprocess.run(argv, cwd=cwd, check=True, capture_output=True)  # noqa: S603
