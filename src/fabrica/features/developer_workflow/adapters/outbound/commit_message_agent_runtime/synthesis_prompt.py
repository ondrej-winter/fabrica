"""Prompt text for final commit-message recommendation synthesis."""

SYNTHESIZE_COMMIT_MESSAGE_PROMPT = """Use the structured staged-file evidence to propose one Conventional Commit
recommendation.

Apply the selected Agent Skill instructions when skill context is provided. Center the dominant change intent.
Do not make the final message a file-by-file changelog. Do not run git commands, write files, create commits,
or assume unstaged changes are included.

Use only the structured evidence context for staged changes. Do not require or invent raw staged diffs.

Return plain text that is easy to read in terminal output. Use exactly these labels:

Summary:
A concise summary of the staged changes.

Rationale:
Why this commit message fits the staged changes.

Commit message:
A single recommended commit message line, suitable for copying into git commit.

Do not use markdown headings, fenced code blocks, bullets, or decorative formatting.
"""
