# Evidence-First Commit Message Generation

## Problem Statement

How might we improve generated commit messages so they accurately describe the intent of the staged changes instead of becoming vague summaries or file-by-file changelogs?

## Recommended Direction

Use an evidence-first workflow before invoking the Conventional Commits skill. The agent should first inspect the staged diff, summarize each changed file independently, group those file-level observations into intent-level themes, and only then synthesize a Conventional Commit message.

The per-file summaries are intermediate evidence, not the default final commit body. The final commit message should describe the dominant change intent, with supporting details only when they help explain behavior, motivation, validation, migration impact, or breaking changes.

## Proposed Workflow

Analyze the staged diff in three passes:

1. **File-level evidence pass**
   - Inspect each staged file independently.
   - Summarize what changed in that file.
   - Classify the change as behavior, tests, docs, configuration, architecture, refactor, or maintenance.
   - Note public contract impact, migration concerns, and possible breaking changes.

2. **Intent grouping pass**
   - Combine file summaries into higher-level themes.
   - Identify the dominant intent of the commit.
   - Separate primary behavior changes from supporting tests, docs, or wiring updates.
   - Avoid treating the final commit as a list of touched files.

3. **Conventional Commit synthesis pass**
   - Use the Conventional Commits skill after the intent is clear.
   - Choose the correct type, such as `feat`, `fix`, `docs`, `test`, `refactor`, or `chore`.
   - Choose an optional scope based on the affected capability or module.
   - Write a concise subject that summarizes the dominant intent.
   - Add a body only when it provides useful context.
   - Add a `BREAKING CHANGE:` footer when the evidence requires it.

## Candidate Context Shape

```text
Staged change overview:
- Files changed: N
- Dominant change type: feature | fix | docs | refactor | test | chore
- Candidate scope: <scope>

Per-file observations:
- path/to/file.py
  - Summary: ...
  - Change category: application behavior
  - Public contract impact: yes/no
  - Breaking risk: yes/no

Grouped intent:
- Main intent: ...
- Supporting changes: ...
- Validation changes: ...

Commit message requirements:
- Follow Conventional Commits v1.0.0
- Prefer one dominant type and optional scope
- Include body only if it adds useful context
- Include breaking-change footer when required
```

## Why This Should Improve Quality

Directly generating a commit message from a raw diff can overemphasize incidental file edits or miss the larger reason the files changed together. A structured evidence step gives the model a cleaner input:

```text
raw staged diff
→ per-file factual summaries
→ intent-level grouped summary
→ Conventional Commit message
```

This should produce commit messages that are more accurate, less file-oriented, better aligned with Conventional Commits, and easier for humans to review.

## Important Constraint

The generated final commit message should not normally include a file-by-file changelog. File summaries belong in the analysis context. A file list belongs in the commit body only when it helps explain a broad mechanical change, migration, or architectural split.

## Open Questions

- How much per-file detail is enough before the context becomes noisy?
- Should the workflow expose the intermediate evidence to the user for review before final synthesis?
- Should the commit-message command support both concise and explanatory output modes?
- How should very large diffs be chunked while preserving cross-file intent?
- Should generated commit messages include validation notes by default or only when requested?
