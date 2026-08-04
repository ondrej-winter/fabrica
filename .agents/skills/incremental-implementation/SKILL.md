---
name: incremental-implementation
description: Guide agents to deliver changes incrementally. Use when implementing a feature or change that touches more than one file, when a task feels too large to land in one step, or before writing a large amount of code at once.
metadata:
  version: "1.1.5"
  dependencies:
    tools: []
    skills: []
---

# Incremental Implementation

## Overview

Build in thin vertical slices: implement one piece, test it, verify it, then expand. Avoid implementing an entire feature in one pass. Each increment should leave the system in a working, testable state. This execution discipline makes large features manageable.

## When to use

- Implementing any multi-file change
- Building a new feature from a task breakdown
- Refactoring existing code
- Any time an agent is tempted to write more than about 100 lines before testing

Do not use this skill for single-file, single-function changes where the scope is already minimal.

## Steps

Use this increment cycle for each implementation slice:

```text
Implement -> Test -> Verify -> Checkpoint -> Next slice
Repeat the cycle for each slice.
```

For each slice:

1. **Implement**: complete the smallest useful piece of functionality.
2. **Test**: run the narrowest relevant tests, or add a test when coverage is missing.
3. **Verify**: confirm the slice works as expected through applicable tests, builds,
   checks, or focused manual verification.
4. **Checkpoint**: save progress with the project's normal checkpoint or handoff
   mechanism, such as a descriptive commit when appropriate or an explicit
   progress note.
5. **Move to the next slice**: carry forward; do not restart.

## Slicing strategies

### Vertical slices (preferred)

Build one complete path through the stack:

```text
Slice 1: Create a record (<data_store> + <interface> + basic <user_surface>)
    Result: Tests pass, user can create a record through the primary surface

Slice 2: List records (<read_path> + <interface> + <user_surface>)
    Result: Tests pass, user can see saved records

Slice 3: Edit a record (<update_path> + <interface> + <user_surface>)
    Result: Tests pass, user can modify records

Slice 4: Delete a record (<delete_path> + <interface> + confirmation)
    Result: Tests pass, the complete lifecycle works
```

Each slice delivers working end-to-end functionality.

### Contract-first slicing

When producers and consumers need to develop in parallel:

```text
Slice 0: Define the contract artifact (<schema>, <interface>, <protocol>, or <spec>)
Slice 1a: Implement the producer against the contract + contract tests
Slice 1b: Implement the consumer against representative test data
Slice 2: Integrate and test the complete path
```

### Risk-first slicing

Tackle the riskiest or most uncertain piece first:

```text
Slice 1: Prove the riskiest integration point works
Slice 2: Build the first user-visible behavior on the proven integration
Slice 3: Add resilience behavior such as retry, fallback, or recovery
```

If Slice 1 fails, you discover it before investing in Slices 2 and 3.

## Implementation rules

### Rule 0: Simplicity first

Before writing any code, ask: "What is the simplest thing that could work?"

After writing code, review it against these checks:

- Can this be done in fewer lines?
- Are these abstractions earning their complexity?
- Would an experienced reviewer ask why this was not implemented more directly?
- Am I building for hypothetical future requirements, or the current task?

```text
SIMPLICITY CHECK:
Avoid: Generic event pipeline for one notification
Prefer: Direct call or the simplest local coordination mechanism

Avoid: Abstract factory pattern for two similar implementations
Prefer: Two straightforward implementations with shared helpers only where useful

Avoid: Config-driven builder for three small variants
Prefer: Three clear variants with duplication removed only when the shared concept is proven
```

Three similar lines of code is better than a premature abstraction. Implement the naive, obviously-correct version first. Optimize only after correctness is proven with tests.

### Rule 0.5: Scope discipline

Touch only what the task requires.

Do not:

- "Clean up" code adjacent to your change
- Refactor imports in files you're not modifying
- Remove comments you don't fully understand
- Add features not in the spec because they "seem useful"
- Modernize syntax in files you're only reading

If you notice something worth improving outside your task scope, note it instead of fixing it:

```text
NOTICED BUT NOT TOUCHING:
- <module_path> has an unused dependency (unrelated to this task)
- The <boundary_or_component> could use clearer error messages (separate task)
```

Capture these as follow-up notes or separate tasks only if requested.

### Rule 1: One thing at a time

Each increment changes one logical thing. Don't mix concerns:

Avoid: One checkpoint that adds a new component, refactors an existing one, and updates the build config.

Prefer: Three separate checkpoints, one for each change.

### Rule 2: Keep it working

After each increment, run the checks affected by the change and keep the project in
a working state. Run broader tests and builds when the slice can affect them. Do not
leave the codebase broken between slices.

### Rule 3: Feature flags for incomplete features

If a feature isn't ready for users but you need to merge increments:

```text
if feature flag is enabled:
    show the new behavior
else:
    keep the existing behavior
```

This lets you merge small increments to the main branch without exposing incomplete work.

### Rule 4: Safe defaults

New code should default to safe, conservative behavior:

```text
create record with notify defaulting to false:
    save the record
    send notification only when notify is explicitly enabled
```

### Rule 5: Rollback-friendly

Each increment should be independently revertible:

- Additive changes (new files, new functions) are easy to revert
- Modifications to existing code should be minimal and focused
- Data migrations should have corresponding rollback or recovery plans
- Avoid deleting something in one commit and replacing it in the same commit — separate them

## Working with agents

When directing an agent to implement incrementally:

```text
"Let's implement Task 3 from the plan.

Start with just the storage change and the external interface.
Don't touch the user-facing surface yet — we'll do that in the next increment.

After implementing, run `<test_command>` and `<build_command>` to verify
nothing is broken."
```

Be explicit about what is in scope and what is not in scope for each increment.

## Increment checklist

After each increment, verify:

- [ ] The change does one thing and does it completely
- [ ] Relevant tests pass (`<test_command>`)
- [ ] The build succeeds when applicable (`<build_command>`)
- [ ] Type or contract checking passes when applicable (`<type_check_command>`)
- [ ] Linting or static analysis passes when applicable (`<lint_command>`)
- [ ] The new functionality works as expected
- [ ] The change is checkpointed with a descriptive message or handoff note

**Note:** Run each verification command after a change that could affect it. After a successful run, don't repeat the same command unless the code has changed since — re-running on unchanged code adds no information.

## Common rationalizations

- "I'll test it all at the end." Bugs compound. A bug in Slice 1 makes
  Slices 2-5 wrong. Test each slice.
- "It's faster to do it all at once." It feels faster until something breaks
  and you can't find which of 500 changed lines caused it.
- "These changes are too small to checkpoint separately." Small checkpoints are
  cheap. Large checkpoints hide bugs and make rollbacks painful.
- "I'll add the feature flag later." If the feature isn't complete, it
  shouldn't be user-visible. Add the flag now.
- "This refactor is small enough to include." Refactors mixed with features make
  both harder to review and debug. Separate them.
- "Let me run the build command again just to be sure." After a successful run,
  repeating the same command adds nothing unless the code has changed since. Run
  it again after subsequent edits, not as reassurance.

## Red flags

- More than 100 lines of code written without running tests
- Multiple unrelated changes in a single increment
- "Let me just quickly add this too" scope expansion
- Skipping the test/verify step to move faster
- Build or tests broken between increments
- Large uncommitted changes accumulating
- Building abstractions before the third use case demands it
- Touching files outside the task scope "while I'm here"
- Creating new utility files for one-time operations
- Running the same build/test command twice in a row without any intervening code change

## Verification

After completing all increments for a task:

- [ ] Each increment was individually tested and checkpointed
- [ ] The full test suite passes when practical and relevant to the change
- [ ] The build is clean when the project has an applicable build step
- [ ] The feature works end-to-end as specified
- [ ] The final handoff clearly explains any uncommitted or uncheckpointed changes
