# Documentation standards: clear, concise, useful

Use these rules to keep documentation useful without being verbose.

This file governs documentation written inside source code. Requirements for README updates, ADRs, and changelog notes live in `005-docs-and-adr.md`.
Use the `write-python-docstrings` skill when you need templates or a drafting
workflow for module, class, function, or inline documentation.

## Documentation principles

- Prefer concise explanations of contracts, invariants, side effects, and intent.
- Use docstrings to add information that names and type hints do not already make obvious.
- Use Google-style docstrings.
- Public APIs and non-obvious behavior deserve better documentation than trivial private helpers.
- Document units, timezones, encodings, mutability/ownership expectations, or security/trust-boundary assumptions when callers need them to use the API correctly.

## Module docstrings

- Use a short summary for public modules or modules with non-obvious responsibilities.
- Add a short paragraph only when callers need context, invariants, or usage constraints.
- Keep module docstrings free of changelogs, feature lists, and ADR-style rationale.

## Class docstrings

- Describe the class responsibility and key invariants/lifecycle expectations when they are not obvious.
- Omit implementation details unless consumers must know them.
- Small private data holders may omit docstrings when names and types are already sufficient.

## Function and method docstrings

- Document public callables and any private callable with non-obvious behavior, side effects, concurrency rules, or tricky contracts.
- Start with a short summary sentence.
- Document **Args**, **Returns**, **Raises**, **Yields**, or **Examples** only when they add real value for callers.
- Call out side effects, blocking/async behavior, cancellation semantics, idempotency, and important invariants when relevant.
- Document deprecation, backward-compatibility, retry, or partial-failure behavior when it affects callers.
- Avoid repeating type hints in prose unless clarification is needed.

## Examples in documentation

- Keep examples minimal, executable when practical, and synchronized with real behavior.
- Prefer tested examples or snippets copied from working code over illustrative pseudocode that can silently go stale.

## Inline comments

- Use sparingly for non-obvious logic only.
- Explain **why**, not **what**.
- Prefer self-documenting code (clear names, simple logic) over explanatory noise.
- Tag temporary workarounds with an issue or reference when possible.

## What NOT to document in code

- Feature lists → belongs in README
- Architecture patterns → belongs in ADRs
- Performance claims → belongs in benchmarks/docs
- Marketing language ("rich", "powerful", "advanced")
- Redundant restatements of type hints or parameter names
