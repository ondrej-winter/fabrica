"""Use case for preparing a selected-skill commit-message runtime run."""

from fabrica.features.agent_runtime.application.dtos import (
    LocalAgentContextBlock,
    LocalAgentRunCommand,
    SelectedSkill,
)
from fabrica.features.agent_runtime.application.use_cases.load_skill_context import LoadSkillContext
from fabrica.features.developer_workflow.application.dtos import STAGED_DIFF_CONTEXT_LABEL, GitStagedDiff
from fabrica.features.developer_workflow.application.ports import GitStagedDiffLoader

DEFAULT_COMMIT_MESSAGE_SKILL_ID = "conventional-commits"
COMMIT_MESSAGE_PROMPT = """Use the selected Agent Skill and the staged git diff context to propose commit-message text.

Analyze the staged changes evidence-first before writing the final recommendation:

1. File-level evidence pass: inspect each staged file independently. Briefly identify the relevant change,
   classify it when useful as behavior, tests, docs, configuration, architecture, refactor, or maintenance,
   and note public contract impact, migration concerns, validation relevance, or breaking risk only when the
   staged evidence supports it.
2. Intent grouping pass: group the file-level observations into higher-level change themes, separate primary
   behavior or contract changes from supporting tests, docs, wiring, or maintenance edits, and identify the
   dominant intent of the staged change set.
3. Conventional Commit synthesis pass: after the dominant intent is clear, apply the selected Agent Skill to
   choose the Conventional Commit type, optional scope, subject, body, and any required BREAKING CHANGE footer.

The final recommendation must center the dominant change intent. Do not make the final message a vague activity summary
or a file-by-file changelog. Use intermediate evidence to make Summary and Rationale specific, but keep the user-facing
output concise and do not include a full per-file evidence report by default.

Return plain text that is easy to read in terminal output. Use exactly these labels:

Summary:
A concise summary of the staged changes.

Rationale:
Why this commit message fits the staged changes.

Commit message:
A single recommended commit message line, suitable for copying into git commit.

Do not use markdown headings, fenced code blocks, bullets, or decorative formatting.
Do not run git commands, write files, create commits, or assume unstaged changes are included.
"""


class PrepareCommitMessageRun:
    """Prepare a local agent command for selected-skill commit-message generation."""

    def __init__(self, staged_changes_loader: GitStagedDiffLoader, skill_context_loader: LoadSkillContext) -> None:
        self._staged_changes_loader = staged_changes_loader
        self._skill_context_loader = skill_context_loader

    def prepare(self, *, skill_id: str = DEFAULT_COMMIT_MESSAGE_SKILL_ID) -> LocalAgentRunCommand:
        """Return a runtime command with selected skill and staged diff context."""
        staged_diff = self._staged_changes_loader.load_diff()
        command = LocalAgentRunCommand(
            prompt=COMMIT_MESSAGE_PROMPT,
            context=(_staged_diff_context_block(staged_diff),),
        )
        return self._skill_context_loader.augment_command(command, (SelectedSkill(skill_id=skill_id),))


def _staged_diff_context_block(staged_diff: GitStagedDiff) -> LocalAgentContextBlock:
    """Map staged git diff evidence into local-agent runtime context."""
    return LocalAgentContextBlock(
        text=staged_diff.text,
        label=STAGED_DIFF_CONTEXT_LABEL,
        metadata={
            "source": "git_staged_diff",
            "char_count": len(staged_diff.text),
            **staged_diff.metadata,
        },
    )
