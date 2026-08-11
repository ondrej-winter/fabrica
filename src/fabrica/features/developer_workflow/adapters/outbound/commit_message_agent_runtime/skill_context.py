"""Skill-context decorator for agent-runtime-backed commit-message synthesis."""

import asyncio
from dataclasses import dataclass
from typing import Protocol

from fabrica.features.agent_runtime.application.dtos import LocalAgentContextBlock, SelectedSkill
from fabrica.features.agent_runtime.application.ports import SkillContextLoadError
from fabrica.features.developer_workflow.application.dtos import (
    CommitMessageRecommendation,
    SynthesizeCommitMessageCommand,
)
from fabrica.features.developer_workflow.application.ports import (
    AsyncCommitMessageSynthesizer,
    CommitMessageSkillContextLoadError,
)


class CommitMessageSkillContextLoader(Protocol):
    """Loader protocol required by commit-message skill-context synthesis."""

    def load(self, selections: tuple[SelectedSkill, ...]) -> tuple[LocalAgentContextBlock, ...]:
        """Load selected skill markdown for commit-message synthesis."""


@dataclass(frozen=True, slots=True)
class SkillContextCommitMessageSynthesizer:
    """Synthesizer decorator that loads selected skill markdown before synthesis."""

    synthesizer: AsyncCommitMessageSynthesizer
    skill_context_loader: CommitMessageSkillContextLoader

    async def synthesize_async(self, command: SynthesizeCommitMessageCommand) -> CommitMessageRecommendation:
        """Load selected skill context, translate failures, and delegate final synthesis."""
        try:
            skill_context = await asyncio.to_thread(
                self.skill_context_loader.load,
                (SelectedSkill(skill_id=command.skill_id),),
            )
        except SkillContextLoadError as err:
            raise CommitMessageSkillContextLoadError(
                str(err),
                category=err.category,
                metadata=err.metadata,
            ) from err
        skill_markdown = skill_context[0].text if skill_context else None
        return await self.synthesizer.synthesize_async(
            SynthesizeCommitMessageCommand(
                evidence_bundle=command.evidence_bundle,
                skill_id=command.skill_id,
                skill_markdown=skill_markdown,
            ),
        )
