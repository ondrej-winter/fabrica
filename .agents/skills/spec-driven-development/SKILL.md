---
name: spec-driven-development
description: Creates a specification before implementation. Use when starting a project, feature, integration, workflow, migration, or significant change with unclear or incomplete requirements.
metadata:
  version: "1.3.0"
  dependencies:
    tools: []
    skills:
      - name: planning-and-task-breakdown
        purpose: Break confirmed requirements into ordered, verifiable implementation tasks.
        required: false
      - name: review-implementation-plan
        purpose: Review implementation plans derived from a specification before coding begins.
        required: false
      - name: interview-me
        purpose: Clarify unclear user intent before writing a specification.
        required: false
      - name: idea-refine
        purpose: Refine rough concepts into a clearer direction before defining requirements.
        required: false
---

# Spec-Driven Development

## Overview

Write a structured specification before implementation. The spec is the shared
source of truth between the agent and the human engineer: what is being built,
why it matters, which constraints apply, and how completion will be verified.
Code without a spec is guessing.

The spec can be short for small changes. Its value is not length; its value is
making assumptions, success criteria, and boundaries explicit before work starts.

Use `planning-and-task-breakdown` after the spec is accepted when the work needs a
deeper ordered task list, task sizing, dependency mapping, or parallelization
plan. Use `review-implementation-plan` before implementation when the resulting
plan is non-trivial, risky, or needs an independent readiness check.

Use `interview-me` first when the underlying intent is not yet confirmed. Use
`idea-refine` first when the intent is understood but the concept, option space,
or MVP boundary still needs exploration. Use this skill when there is a chosen
project, feature, workflow, integration, migration, or change that needs concrete
requirements and verification criteria before implementation.

## When to use this skill

Use this skill when:

- starting a new project, feature, workflow, integration, or migration
- requirements are ambiguous, incomplete, or spread across conversation and files
- the change touches multiple modules, teams, systems, or user workflows
- implementation requires architectural, data, interface, operational, or
  dependency decisions
- the task needs a durable definition of done before implementation begins

Do not use this skill for unambiguous single-line fixes, typo corrections, or
small documentation edits where the requested outcome is already precise.

## The gated workflow

Spec-driven development has four phases. Do not advance until the current phase
is reviewed or clearly accepted by the user.

If no live user is available, stop at a draft spec, plan, or task list and label
unconfirmed assumptions clearly. Do not treat an unreviewed draft as accepted.

```text
SPECIFY: define requirements, assumptions, constraints, and success criteria.
PLAN: choose the technical approach and verification checkpoints.
TASKS: break the plan into small, ordered, verifiable work items.
IMPLEMENT: execute tasks and keep the spec current when decisions change.
```

## Phase 1: Specify

Start by surfacing assumptions. Do not silently fill requirement gaps.

Create or update the spec in `docs/specs/<name>-spec.md` by default, where
`<name>` is a short kebab-case project, feature, workflow, integration,
migration, or change name. Create `docs/specs/` if it does not exist. Use a
different location only when the project already has a clear spec convention or
the user asks for one.

```text
ASSUMPTIONS
1. The primary user is <user_or_actor>.
2. The change affects <system_or_workflow>.
3. The expected compatibility target is <target_environment>.
4. The project's existing <constraint_or_convention> remains in force.
```

Ask clarifying questions for assumptions that materially affect scope, user
experience, data, security, operations, compatibility, or architecture.

### Spec contents

Cover these areas at the appropriate level of detail:

1. Objective: what is being built, who it is for, and why it matters.
2. Current context: relevant existing behavior, files, workflows, constraints, and
   dependencies.
3. Assumptions: unconfirmed beliefs that affect requirements or implementation.
4. Desired behavior: user-visible behavior, interfaces, data changes,
   operational behavior, or workflow changes.
5. Commands and validation: exact build, test, lint, documentation, migration, or
   manual verification commands where known.
6. Project structure: where implementation, tests, docs, and configuration belong.
7. Style and conventions: naming, formatting, error handling, logging, API,
   accessibility, security, or platform conventions that matter for the change.
8. Testing strategy: which test levels or checks prove the behavior works.
9. Boundaries: what to always do, ask before doing, and never do.
10. Success criteria: specific, testable conditions for completion.
11. Open questions: unresolved decisions that need user input.

### Spec template

```markdown
# Spec: <project_or_feature_name>

## Objective

<What is being built, for whom, and why.>

## Current context

<Existing behavior, constraints, files, systems, and dependencies.>

## Assumptions

- <Assumption that must be confirmed or tested.>

## Desired behavior

<Functional, operational, data, interface, or workflow requirements.>

## Commands and validation

- Build: `<build_command>`
- Test: `<test_command>`
- Lint or static checks: `<lint_command>`
- Manual verification: `<manual_check>`

## Project structure

- Spec: `docs/specs/<name>-spec.md`
- `<source_location>`: <implementation responsibility>
- `<test_location>`: <test responsibility>
- `<docs_location>`: <documentation responsibility>

## Conventions

<Relevant style, naming, error-handling, security, accessibility, logging, or API conventions.>

## Testing strategy

<Test levels, fixtures, edge cases, and acceptance checks.>

## Boundaries

- Always: <required practices>
- Ask first: <scope-expanding or risky actions>
- Never: <prohibited actions>

## Success criteria

- <specific verifiable outcome>

## Open questions

- <question requiring user input>
```

### Reframe vague requests as success criteria

Turn broad goals into measurable outcomes before planning.

```text
REQUEST
"Make the import workflow more reliable."

PROPOSED SUCCESS CRITERIA
- Invalid input produces a clear user-facing error.
- Duplicate records are handled according to <deduplication_rule>.
- The import can be retried without corrupting existing state.
- `<test_command>` includes regression coverage for malformed and duplicate input.
```

Ask the user to correct the proposed criteria before implementation depends on
them.

## Phase 2: Plan

With the spec validated, create a technical implementation plan:

1. Identify the main components, files, interfaces, data paths, or workflows.
2. Determine implementation order based on dependencies.
3. Note risks and mitigation strategies.
4. Identify what can be parallelized and what must be sequential.
5. Define verification checkpoints between phases.

The plan should be reviewable. The user should be able to approve it or identify
specific changes.

## Phase 3: Tasks

Break the plan into discrete tasks:

- each task should fit in one focused implementation pass
- each task has acceptance criteria
- each task includes a verification step
- tasks are ordered by dependency
- tasks should avoid broad, unrelated file churn

Task template:

```markdown
- [ ] Task: <description>
  - Acceptance: <what must be true when done>
  - Verify: `<verification_command_or_manual_check>`
  - Likely files: `<file_or_directory>`
```

## Phase 4: Implement

Execute tasks one at a time. Keep context focused on the current task, write or
update tests before changing behavior where practical, and validate after each
meaningful slice.

If implementation reveals that the spec is wrong or incomplete, update the spec
before continuing. Do not let the implementation silently become the new source of
truth.

## Keeping the spec alive

- Update the spec when scope, data, interfaces, constraints, or decisions change.
- Link implementation work back to the relevant spec section when useful.
- Record durable architectural decisions in an ADR when the choice will matter to
  future maintainers.
- Keep rejected options or unresolved questions visible until resolved.

## Common rationalizations

| Rationalization                  | Reality                                                            |
| -------------------------------- | ------------------------------------------------------------------ |
| "This is simple."                | Simple tasks still need clear acceptance criteria.                 |
| "I'll document it after coding." | That is documentation, not specification.                          |
| "The user knows what they want." | Clear requests still contain implicit assumptions.                 |
| "The spec will slow us down."    | A short spec prevents rework caused by misunderstood requirements. |
| "Requirements will change."      | A living spec makes change explicit instead of accidental.         |

## Red flags

- starting implementation without written success criteria
- making architectural or data decisions without recording the rationale
- implementing features not mentioned in the spec or accepted tasks
- skipping clarification when requirements conflict
- treating an outdated spec as irrelevant instead of updating it

## Verification

Before implementation begins, confirm:

- [ ] assumptions and open questions are visible
- [ ] blocking questions are resolved
- [ ] the spec defines objective, desired behavior, constraints, and boundaries
- [ ] success criteria are specific and testable
- [ ] validation commands or manual checks are recorded where known
- [ ] the user has accepted the spec, plan, and task list
