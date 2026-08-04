---
name: split-python-module
description: Split a growing Python module or package while preserving behavior, boundaries, imports, public APIs, and reviewability when code has mixed responsibilities or needs clearer ownership.
metadata:
  version: "1.1.0"
  dependencies:
    tools: []
    skills: []
---

# Split a Python Module

Use this skill when a Python file or package has become too large, mixes
responsibilities, or needs clearer structure without changing its intended
behavior.

## When to use this skill

Use this skill when:

- one module has multiple responsibilities
- a file is hard to review or navigate
- helpers, validators, serializers, or formatters need clearer ownership
- a package API must be preserved while internals are reorganized

Do not use this skill for broad speculative rewrites. Keep the split justified
and proportional. Do not split cohesive code only to satisfy a line-count target.

## Steps

### 1. Confirm the reason for the split

Identify what makes the current module hard to maintain, for example:

- mixed orchestration and implementation
- unrelated helper groups in one file
- repeated private sections that want separate ownership
- public API and internal details tangled together

State the target structure and intended dependency direction before editing.

### 2. Choose the split pattern

Prefer one of these patterns:

- orchestration vs implementation
- by responsibility, such as validators, formatters, serialization, exceptions
- by domain concept
- by layer concern, such as types vs logic

Use names that describe responsibility rather than generic `utils` or
`helpers` buckets. Prefer focused names such as `validators.py`,
`formatters.py`, `serialization.py`, or `exceptions.py` when those names match
the actual responsibility.

### 3. Preserve boundaries and imports

Before moving code, identify:

- public import paths that callers may rely on
- package-level exports that should remain stable
- string-based references in configuration, plugin registration, or dynamic imports
- test patch targets and other references to module-qualified names
- import-time initialization or registration that callers may rely on
- any risk of circular imports after the split

Preserve public import paths only when they are intentionally stable. If you
keep them stable, update `__init__.py` or a dedicated compatibility module
intentionally.

Keep dependencies flowing in the intended direction. When two target modules
need the same types or constants, prefer a small shared leaf module over
reciprocal imports.

### 4. Move code in small, reviewable steps

Prefer a sequence like this:

1. create the new target modules
2. move one responsibility at a time
3. update imports immediately after each move
4. keep names clear and ownership visible
5. remove dead code and redundant re-exports

Avoid mixing the structural split with unrelated behavior changes.

### 5. Re-check package mechanics

When splitting into a package:

- keep `__init__.py` lightweight
- re-export only intentional public symbols
- use `__all__` only when it clarifies the curated surface
- avoid import-time side effects

### 6. Validate compatibility-sensitive surfaces

If the module exposes a public API, verify:

- imports still work as intended
- call sites use the expected paths
- dynamic imports, plugin registrations, and test patch targets still resolve
- import-time behavior remains intentional
- documentation or examples still match the visible surface

If a compatibility break is intentional, document it clearly.

### 7. Run focused validation

Run the narrowest checks that prove the split is safe:

- import smoke tests for preserved public paths
- impacted tests
- lint or type checks for touched modules
- a search for stale references to moved module-qualified names
- broader quality gate before handoff when appropriate

In the handoff, summarize the new module boundaries, compatibility decisions,
and exact validation commands and results.

## Output checklist

- each new module has one clear responsibility
- imports are updated and non-circular
- package exports are intentional
- dynamic and module-qualified references are updated or preserved intentionally
- no unrelated behavior changes were mixed into the split
- compatibility-sensitive surfaces are preserved or documented
- validation commands and results are reported
