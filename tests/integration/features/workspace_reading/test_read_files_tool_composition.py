"""Offline integration tests for explicit read-files tool-loop composition."""

import asyncio
import json
import sys
from pathlib import Path

import pytest

from fabrica.bootstrap import create_read_files_registered_tool_adapter, create_tool_loop_runtime
from fabrica.features.agent_runtime.application.dtos import (
    LocalAgentRunCommand,
    ToolCallRequest,
    ToolLoopLimits,
    ToolLoopRunStatus,
    ToolTextContent,
)
from fabrica.features.workspace_reading.adapters.inbound.registered_tool import READ_FILES_TOOL_NAME
from fabrica.features.workspace_reading.application.dtos import ReadFilesLimits
from tests.integration.support.agent_runtime_tool_loop import SingleToolCallThenFinalModel

pytestmark = pytest.mark.skipif(sys.platform not in {"darwin", "linux"}, reason="POSIX adapter targets macOS/Linux")

EXPECTED_TOOL_LOOP_TURN_COUNT = 2


def test_read_files_tool_factory_composes_an_explicit_offline_tool_loop_without_reading_on_construction(
    tmp_path: Path,
) -> None:
    """Defer workspace access until the model has invoked the registered tool."""
    model = SingleToolCallThenFinalModel(
        ToolCallRequest(
            call_id="call-1",
            tool_name=READ_FILES_TOOL_NAME,
            arguments={"files": ({"path": "source.txt"},)},
        )
    )

    tool = create_read_files_registered_tool_adapter(
        tmp_path,
        external_read_authorized=True,
        image_input_supported=False,
        limits=ReadFilesLimits(max_parallel_reads=1),
    )
    runtime = create_tool_loop_runtime(
        model=model,
        tools=(tool,),
        limits=ToolLoopLimits(max_tool_iterations=2, max_tool_result_chars=500),
    )

    assert tuple(definition.name for definition in runtime.available_tools) == (READ_FILES_TOOL_NAME,)
    assert model.calls == []
    assert not (tmp_path / "source.txt").exists()

    (tmp_path / "source.txt").write_text("first\nsecond\n", encoding="utf-8")
    result = asyncio.run(runtime.run(LocalAgentRunCommand(prompt="Read source.txt.")))

    assert result.status is ToolLoopRunStatus.SUCCESS
    assert len(result.tool_results) == 1
    assert result.output_text is not None
    assert result.output_text.startswith("final:")
    assert len(model.calls) == EXPECTED_TOOL_LOOP_TURN_COUNT
    assert model.calls[0][1] == runtime.available_tools
    assert model.calls[1][2] == result.tool_results
    assert result.tool_results[0].content
    payload_part = result.tool_results[0].content[0]
    assert isinstance(payload_part, ToolTextContent)
    payload = json.loads(payload_part.text)
    assert payload == {
        "complete": True,
        "content": "1 | first\n2 | second",
        "end_line": 2,
        "next_start_line": None,
        "path": "source.txt",
        "start_line": 1,
        "success": True,
        "total_lines": 2,
        "total_lines_exact": True,
        "truncated_lines": [],
        "type": "text",
    }
