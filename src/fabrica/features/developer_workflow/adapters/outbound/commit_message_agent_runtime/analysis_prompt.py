"""Prompt text for staged-file commit-message evidence analysis."""

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
