"""Tests for agent-runtime bootstrap CLI composition helpers."""

from pathlib import Path

import fabrica.bootstrap.cli.features.agent_runtime as agent_runtime_bootstrap
from fabrica.features.agent_runtime.adapters.inbound.cli.command_models import AgentRuntimeCliCompositionOptions


def test_creates_selected_context_runtime_with_composition_options(monkeypatch) -> None:
    runtime = object()
    selected_context_runtime = object()
    captured: dict[str, object] = {}

    def create_selected_context_runtime(*, runtime: object, options: object) -> object:
        captured["runtime"] = runtime
        captured["options"] = options
        return selected_context_runtime

    monkeypatch.setattr(
        agent_runtime_bootstrap,
        "create_selected_context_local_agent_runtime",
        create_selected_context_runtime,
    )

    result = agent_runtime_bootstrap._create_default_selected_context_runtime(  # noqa: SLF001
        runtime,  # ty: ignore[invalid-argument-type]
        composition_options=AgentRuntimeCliCompositionOptions(skill_roots=(Path("skills"),)),
        verbose_diagnostics=True,
    )

    assert result is selected_context_runtime
    assert captured["runtime"] is runtime
    assert captured["options"] == agent_runtime_bootstrap.SkillContextAugmentationOptions(
        skill_roots=(Path("skills"),),
        verbose_diagnostics=True,
    )


def test_creates_default_codex_runtime(monkeypatch) -> None:
    runtime = object()
    monkeypatch.setattr(agent_runtime_bootstrap, "create_codex_runtime", lambda: runtime)

    assert agent_runtime_bootstrap._create_default_runtime() is runtime  # noqa: SLF001
