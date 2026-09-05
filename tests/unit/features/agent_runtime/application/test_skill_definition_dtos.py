"""Tests for canonical Agent Skill definition DTOs."""

from hashlib import sha256

import pytest

from fabrica.features.agent_runtime.application.dtos import MAX_SKILL_INSTRUCTION_CHARS, SkillDefinition


def test_skill_definition_computes_exact_byte_sha256_revision() -> None:
    source_bytes = b"---\nname: review-pr\ndescription: Review pull requests.\n---\n\n# Review\n"

    definition = SkillDefinition.from_skill_file_bytes(
        name="review-pr",
        description="Review pull requests.",
        instructions="# Review\n",
        skill_file_bytes=source_bytes,
    )

    assert definition.revision == f"sha256:{sha256(source_bytes).hexdigest()}"
    assert '"instructions":"# Review\\n"' in definition.activation_content_json()


@pytest.mark.parametrize(
    ("kwargs", "message"),
    [
        ({"name": "Review-PR"}, "kebab-case"),
        ({"description": " "}, "description must not be empty"),
        ({"instructions": "\n\t"}, "instructions must not be empty"),
        ({"instructions": "x" * (MAX_SKILL_INSTRUCTION_CHARS + 1)}, "instructions exceed"),
        ({"revision": "sha256:UPPER"}, "lowercase sha256"),
    ],
)
def test_skill_definition_rejects_invalid_canonical_values(kwargs: dict[str, str], message: str) -> None:
    with pytest.raises(ValueError, match=message):
        SkillDefinition(
            name=kwargs.get("name", "review-pr"),
            description=kwargs.get("description", "Review pull requests."),
            instructions=kwargs.get("instructions", "# Review"),
            revision=kwargs.get("revision", "sha256:" + "0" * 64),
        )
