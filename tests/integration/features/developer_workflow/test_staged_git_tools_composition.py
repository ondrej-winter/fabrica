"""Offline integration tests for optional staged git tool composition."""

import subprocess
from dataclasses import dataclass, field
from pathlib import Path

from fabrica.bootstrap import (
    StagedGitToolOptions,
    create_staged_git_registered_tools,
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


@dataclass
class StagedGitToolAwareModel:
    """Fake model that records explicitly exposed staged git tools."""

    requested_tool_name: str | None = None
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
                tool_calls=(ToolCallRequest(call_id="call-1", tool_name=self.requested_tool_name, arguments={}),),
            )
        if tool_results:
            return ToolAwareModelResponse(output_text=f"final:{tool_results[0].result_text}")
        return ToolAwareModelResponse(output_text="final:no-tools")


def test_staged_git_tool_helper_returns_exact_optional_tools_without_git_io(tmp_path: Path) -> None:
    missing_repository = tmp_path / "not-a-repository"

    tools = create_staged_git_registered_tools(
        StagedGitToolOptions(
            working_directory=missing_repository,
            timeout_seconds=1.0,
        ),
    )

    assert tuple(tool.definition.name for tool in tools) == (
        "git_staged_files",
        "git_staged_diff",
        "git_staged_file_diff",
    )


def test_staged_git_tools_are_exposed_only_when_explicitly_supplied(tmp_path: Path) -> None:
    tools = create_staged_git_registered_tools(StagedGitToolOptions(working_directory=tmp_path))
    model = StagedGitToolAwareModel()

    runtime = create_tool_loop_runtime(model=model, tools=tools)
    empty_runtime = create_tool_loop_runtime(model=StagedGitToolAwareModel(), tools=())

    assert tuple(tool.name for tool in runtime.available_tools) == (
        "git_staged_files",
        "git_staged_diff",
        "git_staged_file_diff",
    )
    assert empty_runtime.available_tools == ()


def test_explicitly_composed_staged_git_tool_runs_through_tool_loop(tmp_path: Path) -> None:
    git_repository = _create_repository_with_staged_file(tmp_path)
    model = StagedGitToolAwareModel(requested_tool_name="git_staged_files")
    runtime = create_tool_loop_runtime(
        model=model,
        tools=create_staged_git_registered_tools(StagedGitToolOptions(working_directory=git_repository)),
        limits=ToolLoopLimits(max_tool_iterations=2, max_tool_result_chars=200),
    )

    result = runtime.run(LocalAgentRunCommand(prompt="Inspect staged files."))

    assert result.status is ToolLoopRunStatus.SUCCESS
    assert result.output_text == "final:A\texample.txt"
    assert model.calls[0][1] == runtime.available_tools
    assert model.calls[1][2] == result.tool_results


def _create_repository_with_staged_file(tmp_path: Path) -> Path:
    git_repository = tmp_path / "repo"
    git_repository.mkdir()
    _run_git(("git", "init"), cwd=git_repository)
    (git_repository / "example.txt").write_text("example\n", encoding="utf-8")
    _run_git(("git", "add", "example.txt"), cwd=git_repository)
    return git_repository


def _run_git(argv: tuple[str, ...], *, cwd: Path) -> None:
    subprocess.run(argv, cwd=cwd, check=True, capture_output=True)  # noqa: S603
