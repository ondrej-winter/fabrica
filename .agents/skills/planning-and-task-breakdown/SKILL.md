---
name: planning-and-task-breakdown
description: Breaks work into ordered tasks. Use when you have a spec or clear requirements and need to break work into implementable tasks. Use when a task feels too large to start, when you need to estimate scope, or when parallel work is possible.
metadata:
  version: "1.4.1"
  dependencies:
    tools: []
    skills:
      - name: spec-driven-development
        purpose: Clarify requirements, success criteria, and scope boundaries before task breakdown.
        required: false
      - name: review-implementation-plan
        purpose: Review sequencing, dependencies, risks, and validation strategy after drafting a plan.
        required: false
---

# Planning and Task Breakdown

## Overview

Decompose work into small, verifiable tasks with explicit acceptance criteria. Good task breakdown helps an agent complete work reliably without turning related changes into one tangled implementation pass. Every task should be small enough to implement, test, and verify in a single focused session.

Use `spec-driven-development` first when requirements, success criteria, or scope
boundaries are unclear. Use `review-implementation-plan` after drafting the plan
when sequencing, dependencies, risk, or validation strategy need an independent
readiness check.

## When to use this skill

- You have a spec and need to break it into implementable units
- A task feels too large or vague to start
- Work needs to be parallelized across multiple agents or sessions
- You need to communicate scope to a human
- The implementation order isn't obvious

Do not use this skill for single-file changes with obvious scope, or when the spec already contains well-defined tasks.

## Expected output

Produce a written implementation plan that includes:

- ordered tasks with acceptance criteria and verification steps
- dependencies, checkpoints, and sequencing constraints
- likely files or components touched, using portable placeholders when needed
- scope boundaries, risks, assumptions, and open questions that affect safe
  implementation
- explicit instructions to keep the plan current during implementation by
  updating checkboxes, status, scope changes, and newly discovered work

By default, create the plan at `docs/plans/<kebab-case-name>-plan.md`, where
`<kebab-case-name>` is a short name derived from the feature, project, or task.

## Steps

### Step 1: Gather context before planning

Before writing any code or content changes, inspect enough context to understand the requested outcome and likely constraints:

- Read the spec and relevant codebase sections
- Identify existing patterns and conventions
- Map dependencies between components
- Note risks and unknowns
- Capture assumptions and open questions that affect sequencing or scope

Do not implement while drafting the plan. The output is a plan document, not code or content changes.

### Step 2: Identify the dependency graph

Map what depends on what:

```
Foundational data or state model
  - Shared contract or interface
    - Producer or service behavior
      - Consumer or user-facing workflow
    - Validation or policy logic
  - Supporting setup, migration, or seed data
```

Implementation order follows dependencies from foundations outward, but only add
prerequisite work that cannot safely belong to the first complete feature slice.
Use the graph to order work within and between slices; do not build every lower
layer before delivering any working behavior.

### Step 3: Slice vertically

Instead of building every foundation layer, then every interface, then every user-facing surface, build one complete feature path at a time:

Bad horizontal slicing:

```
Task 1: Build the entire data or state model
Task 2: Build all external interfaces
Task 3: Build all user-facing surfaces
Task 4: Connect everything
```

Good vertical slicing:

```
Task 1: User can create a record (state model + interface + creation surface)
Task 2: User can authenticate or identify themselves (identity model + interface + entry surface)
Task 3: User can add an item (item model + interface + creation workflow)
Task 4: User can view item history (query path + interface + list or report surface)
```

Each vertical slice delivers working, testable functionality. A small enabling
foundation, shared contract, migration, or risk-reduction spike may come first
when it is a true prerequisite; record why it cannot be included in the first
slice.

### Step 4: Write tasks

Each task follows this structure:

```markdown
### Task [N]: [Short descriptive title]

**Task completion:**

- [ ] `T<N>` — All required acceptance and verification items are resolved

**Description:** One paragraph explaining what this task accomplishes.

**Acceptance criteria:**

- [ ] `T<N>-AC1` — [Specific, testable condition]
- [ ] `T<N>-AC2` — [Specific, testable condition]

**Verification:**

- [ ] `T<N>-V1` — Focused check: `<confirmed_test_or_check_command>`
- [ ] `T<N>-V2` — Build, static, or integration check when applicable: `<confirmed_command>`
- [ ] `T<N>-V3` — Manual check when applicable: [description of what to verify]

Use only commands confirmed from repository documentation or configuration. If a
needed command is not yet known, write `Unknown — discover before implementation`.
For an inapplicable check, write `Not applicable — <reason>` rather than inventing
a command. Distinguish focused iteration checks from final handoff checks.

**Dependencies:** [Task numbers this depends on, or "None"]

**Files likely touched:**

- `<module_path>`
- `<test_path>`

**Estimated scope:** [XS: 1 file | S: 1-2 files | M: 3-5 files | L: 6-8 files | XL: 9+ files]
```

### Step 5: Order and checkpoint

Arrange tasks so that:

1. Dependencies are satisfied with the smallest necessary prerequisite work
2. Each task leaves the system in a working state
3. Checkpoints follow meaningful integration, risk, approval, or phase boundaries
4. High-risk tasks are early (fail fast)

For a long plan with no natural boundary, add a checkpoint after a few tasks.

Add explicit checkpoints:

```markdown
## Checkpoint: After Tasks 1-3

- [ ] All tests pass
- [ ] Relevant build or static checks pass without errors
- [ ] Core user flow works end-to-end
- [ ] Review before proceeding when risk, scope, or uncertainty is high
```

## Task Sizing Guidelines

| Size   | Typical files | Scope                                      | Example                                          |
| ------ | ------------- | ------------------------------------------ | ------------------------------------------------ |
| **XS** | 1             | Single function or config change           | Add a validation rule                            |
| **S**  | 1-2           | One component, interface, or workflow step | Add a new command handler or interface operation |
| **M**  | 3-5           | One coherent feature slice                 | User registration flow                           |
| **L**  | 6-8           | Multi-component or uncertain change        | Search with filtering and pagination             |
| **XL** | 9+             | Likely too large; review for decomposition | Break into smaller tasks                         |

Size tasks by logical cohesion, uncertainty, reviewability, and verification
cost—not file count alone. More than about five independently edited files should
trigger a decomposition review, not automatically invalidate a task. Exclude
generated or mechanical updates when they do not add independent implementation
or verification work.

If a task is L or larger, break it down unless it is an atomic change that cannot
be safely separated. Record the reason when retaining an L task. An agent performs
best on S and M tasks.

**When to break a task down further:**

- It would take more than one focused session (roughly 2+ hours of agent work)
- You cannot describe the acceptance criteria in 3 or fewer bullet points
- It touches two or more independent subsystems, such as identity and payment processing
- You find yourself writing "and" in the task title (a sign it is two tasks)

## Plan Document Template

Write the plan to `docs/plans/<kebab-case-name>-plan.md` by default unless the
user or repository conventions specify another location.

Use `assets/implementation-plan-template.md` as the starting structure. Adapt its
phases and task count to the work, and remove or mark placeholder sections that
are not applicable. Keep the task fields defined in Step 4 even when the plan is
short.

Give every task, acceptance criterion, verification item, and checkpoint
checkbox a stable progress ID. Duplicate each detailed checkbox in the Progress
Tracking dashboard with the same ID, and update both copies together whenever
status or scope changes. The detailed sections remain the source of context; the
dashboard is the at-a-glance completion view.

Mark a parent task complete only when all required acceptance and verification
items are resolved. Items explicitly marked not applicable do not block
completion. Unknown, unresolved, or unapproved deferred items remain unchecked
and block completion.

Treat the plan as a living document during implementation. Update task and
checkpoint checkboxes as work is completed, and keep unfinished or unverified
items unchecked. Record brief status notes, blockers, deviations, changed
sequencing, and newly discovered work when they affect the remaining plan. Make
these updates after each completed task or meaningful plan change without
waiting for the user to ask for progress updates.

## Parallelization Opportunities

When multiple agents or sessions are available:

- **Safe to parallelize:** Independent feature slices, tests for already-implemented features, documentation
- **Must be sequential:** state migrations, shared contract changes, dependency chains
- **Needs coordination:** features that share a contract or interface (define the contract first, then parallelize)

## Common Rationalizations

| Rationalization                | Reality                                                                                      |
| ------------------------------ | -------------------------------------------------------------------------------------------- |
| "I'll figure it out as I go"   | That's how you end up with a tangled mess and rework. 10 minutes of planning saves hours.    |
| "The tasks are obvious"        | Write them down anyway. Explicit tasks surface hidden dependencies and forgotten edge cases. |
| "Planning is overhead"         | Planning is the task. Implementation without a plan is just typing.                          |
| "I can hold it all in my head" | Context windows are finite. Written plans survive session boundaries and compaction.         |

## Red Flags

- Starting implementation without a written task list
- Tasks that say "implement the feature" without acceptance criteria
- No verification steps in the plan
- All tasks are XL-sized
- No checkpoints between tasks
- Dependency order isn't considered

## Handoff before implementation

Before handing the plan to an implementer or starting implementation yourself, include:

- the ordered task list
- dependencies and sequencing constraints
- acceptance criteria for each task
- likely files or components touched, using portable project-relative placeholders when needed
- confirmed validation commands or manual checks for each task, plus explicit
  unknown or not-applicable states where necessary
- open questions that need human input before work can proceed safely
- assumptions that an implementer should confirm or preserve
- explicit in-scope and out-of-scope work

## Verification

Before starting implementation, confirm:

- [ ] Every task has acceptance criteria
- [ ] Every task has a verification step
- [ ] Task dependencies are identified and ordered correctly
- [ ] Tasks are small enough to implement, review, and verify coherently; tasks
      with more than ~5 independently edited files have a recorded decomposition
      review or atomicity rationale
- [ ] Checkpoints exist between major phases
- [ ] The plan says how and when its checkboxes and status will be updated during implementation
- [ ] Every detailed task, acceptance, verification, and checkpoint checkbox has
      a matching Progress Tracking checkbox with the same unique ID
- [ ] Parent tasks are complete only when all required child items are resolved
- [ ] Required reviews or approvals are identified before implementation starts
- [ ] Open questions and assumptions are captured or marked not applicable
- [ ] Scope boundaries and non-goals are captured or marked not applicable
