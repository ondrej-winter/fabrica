---
name: code-simplification
description: Simplify working code without changing behavior by reducing unnecessary complexity, improving names and structure, preserving project conventions, and validating each refactoring step.
metadata:
  version: "1.1.2"
  dependencies:
    tools: []
    skills: []
---

# Code Simplification

Use this skill when code already works but is harder to read, maintain, test, or
extend than it needs to be. The goal is clearer expression of the same behavior,
not fewer lines for their own sake.

Every simplification must preserve inputs, outputs, side effects, ordering, error
behavior, and compatibility-sensitive contracts unless the user explicitly asks
for a behavior change.

## When to use this skill

Use this skill when:

- a working implementation feels heavier than the problem requires
- review identifies readability, duplication, or unnecessary abstraction
- logic is deeply nested, scattered, or poorly named
- refactoring code written under time pressure
- consolidating related behavior while preserving existing semantics

Do not use this skill when:

- the code is already clear enough
- you do not yet understand why the code exists
- a simpler version would weaken required performance, reliability, or security
- the code is about to be replaced entirely
- the simplification would broaden scope beyond the requested task

## Principles

### Preserve behavior exactly

Before each change, ask:

- Does this produce the same observable result for every relevant input?
- Does it preserve error behavior, side effects, ordering, and timing-sensitive
  assumptions?
- Does it keep public contracts, configuration surfaces, and data formats stable?
- Do existing tests still pass without changing expectations?

If the answer is unclear, gather more context or add characterization tests before
editing.

### Follow local conventions

Simplification means making code more consistent with the project, not imposing a
new style. Before editing, read the relevant rules, neighboring files, tests, and
similar implementations.

Check local conventions for:

- module and file organization
- naming and error handling
- dependency direction and layering
- formatting and documentation style
- test shape and fixture patterns
- type, schema, or contract strictness when applicable

### Prefer clarity over cleverness

Choose code that a future maintainer can understand quickly. Compact code is not
simpler when it hides intent, combines unrelated decisions, or requires unusual
language knowledge.

Prefer:

- named intermediate values for important concepts
- guard clauses that reduce nesting
- small helpers with domain-relevant names
- direct control flow over dense conditional expressions
- comments that explain why, not what the syntax already says

### Keep scope narrow

Default to simplifying code touched by the current task. Avoid drive-by
refactors, broad renames, and mixed feature/refactor changes unless the user asks
for them or the simplification is necessary for the requested work.

## Steps

### 1. Understand before changing

Apply Chesterton’s Fence: do not remove or rewrite something until you understand
why it might exist.

Answer:

- What is this code responsible for?
- What calls it, and what does it call?
- What behavior do tests, examples, or docs require?
- What edge cases and error paths matter?
- Is there a historical, performance, compatibility, or platform reason for the
  current shape?

If you cannot answer these questions, read more context before simplifying.

### 2. Identify concrete simplification opportunities

Look for specific signals:

- deep nesting that can become guard clauses or named predicates
- long functions with multiple responsibilities
- repeated conditionals or duplicated logic
- generic, misleading, or abbreviated names
- wrappers or abstractions that add no behavior or useful name
- dead code, unreachable branches, obsolete comments, or unused configuration
- mixed responsibilities across layers or modules
- temporary compatibility code with no remaining caller

Avoid vague claims such as “clean this up” without naming what will become easier
to understand.

### 3. Make one reviewable change at a time

Apply simplifications incrementally.

For each simplification:

1. Make the smallest behavior-preserving change.
2. Run the narrowest relevant check.
3. If validation fails, revert or diagnose before continuing.
4. Keep unrelated formatting or mechanical churn separate when practical.

When a refactor would touch many files or many similar call sites, consider a
scripted or tool-assisted transformation and keep behavior changes out of the
same diff.

### 4. Prefer tests before risky simplification

If behavior is underspecified or poorly covered, add or identify tests before
refactoring. Characterization tests are useful when the current behavior is
intentional but not documented.

Do not modify tests merely to make a simplification pass. Test expectation
changes usually mean behavior changed.

### 5. Review the result as a whole

After simplifying, compare before and after:

- Is the new version easier to understand?
- Is the result easier to review than the original implementation?
- Did the change preserve local patterns?
- Did it remove useful names or abstractions?
- Did validation cover the affected behavior?

If the “simplified” version is harder to understand or riskier to review, revert
or choose a smaller change.

## Example patterns

Use concrete examples only as patterns, not as required syntax.

### Replace nested conditionals with early exits

```python
# Before
def process(record):
    if record is not None:
        if record.is_valid():
            if record.is_allowed():
                return handle(record)
            raise PermissionError("not allowed")
        raise ValueError("invalid record")
    raise TypeError("record is required")

# After
def process(record):
    if record is None:
        raise TypeError("record is required")
    if not record.is_valid():
        raise ValueError("invalid record")
    if not record.is_allowed():
        raise PermissionError("not allowed")
    return handle(record)
```

### Name repeated decisions

```python
# Before
if user.is_active and user.email_verified and not user.is_locked:
    send_notification(user)

# After
can_receive_notification = (
    user.is_active and user.email_verified and not user.is_locked
)
if can_receive_notification:
    send_notification(user)
```

## Red flags

- tests must be changed to preserve the simplification
- error handling, validation, logging, or authorization is removed for neatness
- unrelated files are refactored without request or need
- new abstractions are added before there is a clear repeated concept
- names are changed to personal preference rather than local convention
- many simplifications are batched without intermediate validation
- the final diff is harder to review than the original code

## Output checklist

- behavior-preservation assumptions are explicit
- relevant existing code and tests were read first
- simplifications are scoped to the task
- each change follows local conventions
- tests or characterization checks protect risky behavior
- validation passed without changing expected behavior
- no unrelated cleanup is mixed into the diff
