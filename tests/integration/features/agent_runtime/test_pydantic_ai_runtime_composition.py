"""Offline integration tests for PydanticAI runtime composition."""

import json
from dataclasses import dataclass, field
from pathlib import Path

import httpx

from fabrica.bootstrap import (
    SkillContextAugmentationOptions,
    create_codex_pydantic_ai_runtime,
    create_pydantic_ai_runtime,
    create_skill_context_augmented_local_agent_command,
)
from fabrica.features.agent_runtime.adapters.outbound.pydantic_ai_model import PydanticAICompletionRequest
from fabrica.features.agent_runtime.application.dtos import (
    LocalAgentContextBlock,
    LocalAgentRunCommand,
    LocalAgentRunStatus,
    SelectedSkill,
)


@dataclass
class FakeCompletion:
    output_text: str = "pong"
    calls: list[PydanticAICompletionRequest] = field(default_factory=list)

    def complete(self, request: PydanticAICompletionRequest) -> str:
        self.calls.append(request)
        return self.output_text


def test_pydantic_ai_runtime_composition_runs_with_fake_completion() -> None:
    completion = FakeCompletion(output_text="pong")
    runtime = create_pydantic_ai_runtime(completion=completion)

    result = runtime.run(LocalAgentRunCommand(prompt="Reply with the single word: pong"))

    assert result.status is LocalAgentRunStatus.SUCCESS
    assert result.succeeded is True
    assert result.output_text == "pong"
    assert completion.calls[0].prompt == "Reply with the single word: pong"


def test_pydantic_ai_runtime_factory_does_not_call_completion_during_construction() -> None:
    completion = FakeCompletion()

    runtime = create_pydantic_ai_runtime(completion=completion)

    assert completion.calls == []

    runtime.run(LocalAgentRunCommand(prompt="ping"))

    assert len(completion.calls) == 1


def test_pydantic_ai_runtime_composition_preserves_context_mapping() -> None:
    completion = FakeCompletion()
    runtime = create_pydantic_ai_runtime(completion=completion, model_name="codex-compatible")

    result = runtime.run(
        LocalAgentRunCommand(
            prompt="Answer from context only",
            context=(LocalAgentContextBlock(text="The answer is pong.", label="note"),),
        ),
    )

    assert result.status is LocalAgentRunStatus.SUCCESS
    assert completion.calls[0].prompt == "Context:\n[note]\nThe answer is pong.\n\nPrompt:\nAnswer from context only"
    assert result.observations[0].metadata["model_name"] == "codex-compatible"


def test_pydantic_ai_runtime_accepts_skill_augmented_command_without_pydanticai_application_types(
    tmp_path: Path,
) -> None:
    _write_skill(tmp_path, "python-testing", "# Python Testing\n\nUse focused pytest tests.")
    completion = FakeCompletion()
    runtime = create_pydantic_ai_runtime(completion=completion)
    command = create_skill_context_augmented_local_agent_command(
        LocalAgentRunCommand(prompt="Use the selected skill."),
        SkillContextAugmentationOptions(
            skill_selections=(SelectedSkill(skill_id="python-testing"),),
            skill_roots=(tmp_path,),
        ),
    )

    result = runtime.run(command)

    assert result.status is LocalAgentRunStatus.SUCCESS
    assert "# Python Testing" in completion.calls[0].prompt
    assert "Use focused pytest tests." in completion.calls[0].prompt


def test_codex_pydantic_ai_runtime_composition_runs_with_mock_transport(tmp_path: Path) -> None:
    auth_file_path = tmp_path / "auth.json"
    auth_file_path.write_text(
        json.dumps(
            {
                "auth_mode": "chatgpt",
                "tokens": {
                    "access_token": "synthetic-access-token",
                    "account_id": "synthetic-account",
                },
            },
        ),
        encoding="utf-8",
    )

    def handler(request: httpx.Request) -> httpx.Response:
        assert request.method == "POST"
        assert str(request.url) == "https://chatgpt.com/backend-api/codex/responses"
        assert request.headers["Authorization"] == "Bearer synthetic-access-token"
        assert request.headers["ChatGPT-Account-ID"] == "synthetic-account"
        assert b"Reply with the single word: pong" in request.content
        return httpx.Response(200, json={"output_text": "pong"})

    runtime = create_codex_pydantic_ai_runtime(
        auth_file_path=auth_file_path,
        http_client=httpx.Client(transport=httpx.MockTransport(handler)),
    )

    result = runtime.run(LocalAgentRunCommand(prompt="Reply with the single word: pong"))

    assert result.status is LocalAgentRunStatus.SUCCESS
    assert result.output_text == "pong"
    assert result.observations[0].metadata["model_name"] == "codex-transport"
    assert "synthetic-access-token" not in str(result.observations)
    assert "synthetic-account" not in str(result.observations)


def test_codex_pydantic_ai_runtime_factory_does_not_read_credentials_during_construction(
    tmp_path: Path,
) -> None:
    runtime = create_codex_pydantic_ai_runtime(auth_file_path=tmp_path / "missing-auth.json")

    result = runtime.run(LocalAgentRunCommand(prompt="Reply with the single word: pong"))

    assert result.status is LocalAgentRunStatus.CONFIGURATION_ERROR
    assert result.output_text is None


def _write_skill(root: Path, skill_id: str, markdown: str) -> Path:
    skill_file = root / skill_id / "SKILL.md"
    skill_file.parent.mkdir(parents=True, exist_ok=True)
    skill_file.write_text(markdown, encoding="utf-8")
    return skill_file
