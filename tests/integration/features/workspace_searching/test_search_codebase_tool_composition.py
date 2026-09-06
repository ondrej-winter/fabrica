"""Offline integration tests for explicit search-codebase tool-loop composition."""

import asyncio
import json
from pathlib import Path

from fabrica.bootstrap import create_search_codebase_registered_tool_adapter, create_tool_loop_runtime
from fabrica.features.agent_runtime.application.dtos import (
    LocalAgentRunCommand,
    ToolCallRequest,
    ToolLoopLimits,
    ToolTextContent,
)
from fabrica.features.workspace_searching.adapters.inbound.registered_tool import SEARCH_CODEBASE_TOOL_NAME
from fabrica.features.workspace_searching.application.dtos import SearchLimits
from tests.integration.support.agent_runtime_tool_loop import SingleToolCallThenFinalModel

EXPECTED_TOOL_LOOP_TURN_COUNT = 2


def test_search_codebase_tool_factory_composes_an_explicit_offline_tool_loop_without_workspace_inspection(
    tmp_path: Path,
) -> None:
    model = SingleToolCallThenFinalModel(
        ToolCallRequest(
            call_id="call-1",
            tool_name=SEARCH_CODEBASE_TOOL_NAME,
            arguments={"queries": ({"pattern": "needle"},)},
        )
    )

    tool = create_search_codebase_registered_tool_adapter(
        tmp_path,
        limits=SearchLimits(max_parallel_searches=1),
    )
    runtime = create_tool_loop_runtime(
        model=model,
        tools=(tool,),
        limits=ToolLoopLimits(max_tool_iterations=2, max_tool_result_chars=500),
    )

    assert tuple(definition.name for definition in runtime.available_tools) == (SEARCH_CODEBASE_TOOL_NAME,)
    assert model.calls == []
    assert not (tmp_path / "source.txt").exists()

    (tmp_path / "source.txt").write_text("before\nneedle\nafter\n", encoding="utf-8")
    result = asyncio.run(runtime.run(LocalAgentRunCommand(prompt="Find needle.")))
    assert len(result.tool_results) == 1
    assert result.output_text is not None
    assert result.output_text.startswith("final:")
    assert len(model.calls) == EXPECTED_TOOL_LOOP_TURN_COUNT
    assert model.calls[0][1] == runtime.available_tools
    assert model.calls[1][2] == result.tool_results
    payload_part = result.tool_results[0].content[0]
    assert isinstance(payload_part, ToolTextContent)
    payload = json.loads(payload_part.text)
    assert payload["results"][0]["query"] == {
        "case_sensitive": False,
        "glob": None,
        "path": ".",
        "pattern": "needle",
    }
    assert isinstance(payload["results"][0]["success"], bool)
