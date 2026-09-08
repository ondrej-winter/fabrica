"""Tests for coding-agent-session application port ownership."""

import inspect

from fabrica.features.coding_agent_session.application import ports


def test_session_runtime_port_is_application_owned_without_bootstrap_or_adapter_dependencies() -> None:
    """Keep the session boundary independent from its terminal and composition details."""
    assert ports.__all__ == ["CodingAgentSessionRuntime"]

    source = inspect.getsource(ports)
    implementation_source = inspect.getsource(ports.CodingAgentSessionRuntime)
    assert ".adapters" not in source
    assert ".bootstrap" not in source
    assert ".adapters" not in implementation_source
    assert ".bootstrap" not in implementation_source
