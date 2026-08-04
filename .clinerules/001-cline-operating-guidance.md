# Cline operating guidance: read first, edit narrowly, validate proportionally

Use these rules to keep Cline-driven changes accurate, minimal, and easy to review in any workspace.

This rule is intentionally reusable. It defines operating behavior for Cline rather than project architecture, language conventions, or repository-specific maintenance workflow.

## Working style

- **Must** read the relevant files before proposing or making changes; do not guess from filenames alone.
- **Should** search for existing patterns, helper modules, and neighboring conventions before introducing a new approach.
- **Must** prefer the smallest change that fully satisfies the request.
- **Must not** change unrelated files just because nearby cleanup is tempting.
- **Should** preserve established local patterns unless they conflict with a stronger rule or the user asks for a change.

## Scope control

- **Must** call out assumptions when requirements are incomplete or inferred.
- **Should** ask for clarification before making architectural, schema, dependency, or workflow changes that materially expand scope.
- **Must** keep fixes targeted; separate opportunistic refactors from the requested change unless the broader refactor is necessary.
- **Must** surface follow-up issues separately rather than silently expanding the task.

## Editing discipline

- **Should** update the smallest viable set of files needed to keep behavior, documentation, and tests aligned.
- **Must** preserve compatibility-sensitive surfaces intentionally. If an import path, CLI, config surface, or contract changes, document it clearly.
- **Should** keep diffs easy to review by avoiding mixed mechanical and behavioral changes in the same step when possible.

## Validation discipline

- **Must** validate changes with the narrowest relevant check first when iterating locally.
- **Should** run broader project validation before handoff when code, behavior, or tooling-affecting files changed.
- **Must not** claim success without running the relevant checks or clearly stating what was not validated.
- **Should** include concise handoff notes covering assumptions, files changed, and validation performed.
