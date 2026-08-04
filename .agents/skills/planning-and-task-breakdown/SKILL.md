---
name: planning-and-task-breakdown
description: Breaks work into ordered tasks. Use when you have a spec or clear requirements and need to break work into implementable tasks. Use when a task feels too large to start, when you need to estimate scope, or when parallel work is possible.
metadata:
  version: "1.3.1"
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
- risks, assumptions, and open questions that affect safe implementation
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

Implementation order follows dependencies from foundations outward: build each
prerequisite before the work that depends on it.

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

Each vertical slice delivers working, testable functionality.

### Step 4: Write tasks

Each task follows this structure:

```markdown
## Task [N]: [Short descriptive title]

**Description:** One paragraph explaining what this task accomplishes.

**Acceptance criteria:**

- [ ] [Specific, testable condition]
- [ ] [Specific, testable condition]

**Verification:**

- [ ] Tests pass: `<test_command>`
- [ ] Build succeeds when applicable: `<build_command>`
- [ ] Manual check: [description of what to verify]

**Dependencies:** [Task numbers this depends on, or "None"]

**Files likely touched:**

- `<module_path>`
- `<test_path>`

**Estimated scope:** [XS: 1 file | Small: 2 files | Medium: 3-5 files | Large: 6-8 files | XL: 9+ files]
```

### Step 5: Order and checkpoint

Arrange tasks so that:

1. Dependencies are satisfied (build foundation first)
2. Each task leaves the system in a working state
3. Verification checkpoints occur after every 2-3 tasks
4. High-risk tasks are early (fail fast)

Add explicit checkpoints:

```markdown
## Checkpoint: After Tasks 1-3

- [ ] All tests pass
- [ ] Relevant build or static checks pass without errors
- [ ] Core user flow works end-to-end
- [ ] Review before proceeding when risk, scope, or uncertainty is high
```

## Task Sizing Guidelines

| Size   | Files | Scope                                      | Example                                          |
| ------ | ----- | ------------------------------------------ | ------------------------------------------------ |
| **XS** | 1     | Single function or config change           | Add a validation rule                            |
| **S**  | 2     | One component, interface, or workflow step | Add a new command handler or interface operation |
| **M**  | 3-5   | One feature slice                          | User registration flow                           |
| **L**  | 6-8   | Multi-component feature                    | Search with filtering and pagination             |
| **XL** | 9+    | **Too large - break it down further**      | Break into smaller tasks                         |

If a task is L or larger, it should be broken into smaller tasks. An agent performs best on S and M tasks.

**When to break a task down further:**

- It would take more than one focused session (roughly 2+ hours of agent work)
- You cannot describe the acceptance criteria in 3 or fewer bullet points
- It touches two or more independent subsystems, such as identity and payment processing
- You find yourself writing "and" in the task title (a sign it is two tasks)

## Plan Document Template

Write the plan to `docs/plans/<kebab-case-name>-plan.md` by default unless the
user or repository conventions specify another location.

Treat the plan as a living document during implementation. Update task and
checkpoint checkboxes as work is completed, and keep unfinished or unverified
items unchecked. Record brief status notes, blockers, deviations, changed
sequencing, and newly discovered work when they affect the remaining plan. Make
these updates after each completed task or meaningful plan change without
waiting for the user to ask for progress updates.

```markdown
# Implementation Plan: [Feature/Project Name]

## Overview

[One paragraph summary of what we're building]

## Architecture Decisions

- [Key decision 1 and rationale]
- [Key decision 2 and rationale]

## Progress Tracking

Treat this plan as a living document throughout implementation. After each
completed task or meaningful change:

- check off completed tasks, acceptance criteria, verification items, and
  checkpoints
- leave unfinished or unverified items unchecked
- add newly discovered work and update sequencing when scope or dependencies
  change
- note blockers, deviations, and decisions that affect the remaining work

Keep this section and the task list current without waiting for the user to ask
for progress updates.

## Task List

### Phase 1: Foundation

- [ ] Task 1: ...
- [ ] Task 2: ...

### Checkpoint: Foundation

- [ ] Tests pass, builds clean

### Phase 2: Core Features

- [ ] Task 3: ...
- [ ] Task 4: ...

### Checkpoint: Core Features

- [ ] End-to-end flow works

### Phase 3: Polish

- [ ] Task 5: ...
- [ ] Task 6: ...

### Checkpoint: Complete

- [ ] All acceptance criteria met
- [ ] Ready for review

## Risks and Mitigations

| Risk   | Impact         | Mitigation |
| ------ | -------------- | ---------- |
| [Risk] | [High/Med/Low] | [Strategy] |

## Open Questions

- [Question needing human input]
```

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
- validation commands or manual checks for each task
- open questions that need human input before work can proceed safely
- assumptions that an implementer should confirm or preserve

## Verification

Before starting implementation, confirm:

- [ ] Every task has acceptance criteria
- [ ] Every task has a verification step
- [ ] Task dependencies are identified and ordered correctly
- [ ] No task touches more than ~5 files
- [ ] Checkpoints exist between major phases
- [ ] The plan says how and when its checkboxes and status will be updated during implementation
- [ ] Required reviews or approvals are identified before implementation starts
- [ ] Open questions and assumptions are captured or marked not applicable
