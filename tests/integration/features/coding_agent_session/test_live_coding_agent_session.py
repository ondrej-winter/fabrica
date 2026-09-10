"""Opt-in live smoke coverage for the terminal coding-agent session."""

import asyncio
import os
from io import StringIO
from pathlib import Path

import pytest

from fabrica.bootstrap.composition.coding_agent_session import create_terminal_workspace_coding_agent_session_runtime
from fabrica.features.coding_agent_session.application.dtos import CodingAgentSessionCommand

_RUN_LIVE_CODEX_TESTS_ENV = "FABRICA_RUN_LIVE_CODEX_TESTS"
_LIVE_TEST_ENABLED_VALUE = "1"


@pytest.mark.live_codex
def test_live_terminal_session_reads_disposable_workspace_file_when_explicitly_enabled(tmp_path: Path) -> None:
    """Verify the assembled tool-aware session can use read_files without mutation."""
    if os.environ.get(_RUN_LIVE_CODEX_TESTS_ENV) != _LIVE_TEST_ENABLED_VALUE:
        pytest.skip(f"set {_RUN_LIVE_CODEX_TESTS_ENV}=1 to run live coding-agent session tests")

    sentinel = tmp_path / "sentinel.txt"
    sentinel.write_text("fabrica-session-sentinel\n", encoding="utf-8")
    runtime = asyncio.run(
        create_terminal_workspace_coding_agent_session_runtime(
            workspace_root=tmp_path,
            stdin=StringIO(),
            stdout=StringIO(),
        )
    )

    result = asyncio.run(
        runtime.run(
            CodingAgentSessionCommand(
                workspace_root=tmp_path,
                prompt=(
                    "Use read_files to read sentinel.txt. Do not run commands, ask questions, or modify files. "
                    "Then reply with its exact contents."
                ),
            )
        )
    )

    if not result.tool_loop_result.succeeded:
        pytest.fail(
            f"live coding-agent session failed with redacted observations: {result.tool_loop_result.observations}"
        )
    assert "read_files" in tuple(tool_result.tool_name for tool_result in result.tool_loop_result.tool_results)
    assert result.tool_loop_result.output_text is not None
    assert "fabrica-session-sentinel" in result.tool_loop_result.output_text
    assert sentinel.read_text(encoding="utf-8") == "fabrica-session-sentinel\n"
