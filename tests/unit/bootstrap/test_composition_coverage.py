"""Focused composition-root coverage for bootstrap wiring branches."""

from io import StringIO
from pathlib import Path

import fabrica.bootstrap.cli.features.developer_workflow as developer_workflow_bootstrap
from fabrica.adapters.inbound.cli import CommandContext, GlobalOptions
from fabrica.bootstrap.composition import codex_runtime, skill_context, skill_registry
from fabrica.features.agent_runtime.application.dtos import LocalAgentRunCommand, SelectedSkillResource
from fabrica.features.developer_workflow.adapters.inbound.cli.command_models import (
    CliCommitCommand,
    CliCommitMessageCommand,
    CliDeveloperWorkflowCompositionOptions,
)

COMMIT_MESSAGE_EXIT_CODE = 11
CONFIRMED_COMMIT_EXIT_CODE = 12


def test_creates_default_developer_workflows_with_cli_options(monkeypatch) -> None:
    context = CommandContext(
        global_options=GlobalOptions(verbose_diagnostics=True),
        stdin=StringIO(),
        stdout=StringIO(),
        stderr=StringIO(),
    )
    composition_options = CliDeveloperWorkflowCompositionOptions(
        model="codex-test",
        reasoning_effort="high",
        skill_roots=(Path("skills"),),
    )
    commit_workflow = object()
    confirmed_workflow = object()
    captured: list[object] = []

    monkeypatch.setattr(
        developer_workflow_bootstrap,
        "create_codex_commit_message_workflow",
        lambda options: captured.append(options) or commit_workflow,
    )
    monkeypatch.setattr(
        developer_workflow_bootstrap,
        "create_codex_confirmed_commit_workflow",
        lambda options: captured.append(options) or confirmed_workflow,
    )

    assert (
        developer_workflow_bootstrap._create_default_commit_message_workflow(  # noqa: SLF001
            context=context,
            composition_options=composition_options,
        )
        is commit_workflow
    )
    assert (
        developer_workflow_bootstrap._create_default_confirmed_commit_workflow(  # noqa: SLF001
            context=context,
            composition_options=composition_options,
        )
        is confirmed_workflow
    )
    assert (
        captured
        == [
            developer_workflow_bootstrap.CommitMessageWorkflowOptions(
                codex_model="codex-test",
                codex_reasoning_effort="high",
                skill_roots=(Path("skills"),),
                verbose_diagnostics=True,
            ),
        ]
        * 2
    )


def test_developer_workflow_handlers_delegate_with_injected_workflows(monkeypatch) -> None:
    context = CommandContext(
        global_options=GlobalOptions(print_usage=True, print_prices=True),
        stdin=StringIO(),
        stdout=StringIO(),
        stderr=StringIO(),
    )
    composition_options = CliDeveloperWorkflowCompositionOptions()
    commit_workflow = object()
    confirmed_workflow = object()
    captured: list[dict[str, object]] = []

    def run_commit_message(*_args: object, **kwargs: object) -> int:
        captured.append(kwargs)
        return COMMIT_MESSAGE_EXIT_CODE

    def run_confirmed_commit(*_args: object, **kwargs: object) -> int:
        captured.append(kwargs)
        return CONFIRMED_COMMIT_EXIT_CODE

    monkeypatch.setattr(developer_workflow_bootstrap, "run_commit_message_cli_command", run_commit_message)
    monkeypatch.setattr(developer_workflow_bootstrap, "run_confirmed_commit_cli_command", run_confirmed_commit)

    assert (
        developer_workflow_bootstrap.run_commit_message_command(commit_workflow)(  # ty: ignore[invalid-argument-type]
            CliCommitMessageCommand(),
            composition_options,
            context,
        )
        == COMMIT_MESSAGE_EXIT_CODE
    )
    assert (
        developer_workflow_bootstrap.run_confirmed_commit_command(confirmed_workflow)(  # ty: ignore[invalid-argument-type]
            CliCommitCommand(),
            composition_options,
            context,
        )
        == CONFIRMED_COMMIT_EXIT_CODE
    )
    assert captured[0]["workflow"] is commit_workflow
    assert captured[1]["workflow"] is confirmed_workflow


def test_creates_codex_runtimes_with_explicit_timeouts(monkeypatch) -> None:
    backends: list[dict[str, object]] = []

    class Backend:
        def __init__(self, **kwargs: object) -> None:
            backends.append(kwargs)

    monkeypatch.setattr(codex_runtime, "CodexBackendHttpAdapter", Backend)
    monkeypatch.setattr(codex_runtime, "CompleteWithCodexTransport", lambda **_kwargs: object())
    monkeypatch.setattr(codex_runtime, "CodexAuthFileCredentialStore", lambda _path: object())

    timeout = 2.0
    codex_runtime.create_codex_runtime(timeout=timeout)
    codex_runtime.create_codex_pydantic_ai_runtime(timeout=timeout)

    assert backends[0]["completion_timeout"] == timeout
    assert backends[0]["usage_timeout"] == timeout
    assert backends[1]["completion_timeout"] == timeout


def test_creates_selected_context_runtime_when_no_selections_are_configured() -> None:
    runtime = object()

    composed = skill_context.create_selected_context_local_agent_runtime(
        runtime=runtime,  # ty: ignore[invalid-argument-type]
        options=skill_context.SkillContextAugmentationOptions(),
    )

    assert composed._runtime is runtime  # noqa: SLF001


def test_augments_only_selected_skill_resources(monkeypatch) -> None:
    command = LocalAgentRunCommand(prompt="Use one resource.")
    selection = SelectedSkillResource(skill_id="python-testing", resource_id="references/example.md")
    augmented_command = LocalAgentRunCommand(prompt="Augmented with resource.")
    captured: dict[str, object] = {}

    def augment_resources(
        received_command: LocalAgentRunCommand,
        selections: tuple[SelectedSkillResource, ...],
        **_kwargs: object,
    ) -> LocalAgentRunCommand:
        captured["command"] = received_command
        captured["selections"] = selections
        return augmented_command

    monkeypatch.setattr(skill_context, "create_skill_resource_augmented_local_agent_command", augment_resources)

    augmented = skill_context.create_skill_context_augmented_local_agent_command(
        command,
        skill_context.SkillContextAugmentationOptions(resource_selections=(selection,)),
    )

    assert augmented is augmented_command
    assert captured == {"command": command, "selections": (selection,)}


def test_creates_skill_registry_with_global_and_workspace_providers() -> None:
    builder = skill_registry.create_skill_registry_snapshot_builder(
        global_skill_root=Path("global-skills"),
        workspace_skill_root=Path("workspace-skills"),
    )

    assert tuple(provider.source.value for provider in builder._providers) == ("global", "workspace")  # noqa: SLF001


def test_creates_skill_registry_without_configured_roots() -> None:
    builder = skill_registry.create_skill_registry_snapshot_builder()

    assert builder._providers == ()  # noqa: SLF001
