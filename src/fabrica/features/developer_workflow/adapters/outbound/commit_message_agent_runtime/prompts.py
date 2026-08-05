"""Prompt text for agent-runtime-backed commit-message adapters."""

ANALYZE_STAGED_FILE_PROMPT = """Analyze exactly one staged file diff for commit-message evidence.

Return factual evidence only. Do not write, recommend, draft, or synthesize a final commit message.
Do not infer unstaged changes, run git commands, write files, or create commits.

Return strict JSON only, with no markdown, comments, code fences, or extra text. The JSON object must contain
these string fields:

- summary: concise factual summary of the staged change in this file.
- category: one of behavior, tests, docs, configuration, architecture, refactor, maintenance, or other.
- public_contract_impact: public API, CLI, configuration, schema, or user-visible contract impact; use
  "No public contract impact identified." when unsupported by the diff.
- validation_relevance: tests, checks, or validation implications visible from this file; use
  "No validation relevance identified." when unsupported by the diff.
- migration_concern: migration, rollout, compatibility, or operational concern; use
  "No migration concern identified." when unsupported by the diff.
- breaking_risk: breaking-change risk visible from this file; use
  "No breaking risk identified." when unsupported by the diff.
- impact: optional broader impact, only when directly supported by the staged diff.
"""

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
