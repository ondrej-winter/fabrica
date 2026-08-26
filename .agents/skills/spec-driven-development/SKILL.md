---
name: spec-driven-development
description: Creates and confirms the canonical specification that defines requirements, constraints, boundaries, and success criteria before implementation planning. Use when starting a project, feature, integration, workflow, migration, or significant change with unclear or incomplete requirements.
metadata:
  version: "1.5.0"
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

Write and confirm a structured specification before implementation planning. The
spec is the canonical source of truth between the agent and the human engineer:
what is being built, why it matters, which constraints apply, and how completion
will be verified. Code without a spec is guessing.

The spec can be short for small changes. Its value is not length; its value is
making assumptions, success criteria, and boundaries explicit before work starts.

Use `planning-and-task-breakdown` after the spec is accepted to derive the
implementation approach, ordered tasks, task sizing, dependency mapping, and
parallelization plan. Use `review-implementation-plan` before implementation when
the resulting plan is non-trivial, risky, or needs an independent readiness
check. The plan is a derived execution artifact and must not redefine the spec.

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

This skill ends with an accepted canonical specification or an explicitly labeled
unconfirmed draft. It does not create the implementation plan, task list, or code.

If no live user is available, stop at a draft spec and label unconfirmed
assumptions and blocking questions clearly. Do not treat an unreviewed draft as
accepted or hand it off as implementation-ready.

```text
CONTEXT: inspect the request, existing system, constraints, and conventions.
SPECIFY: define requirements, assumptions, boundaries, and success criteria.
RESOLVE: surface and settle questions that materially affect the required outcome.
CONFIRM: obtain acceptance or label the specification as an unconfirmed draft.
HAND OFF: derive planning artifacts separately from the accepted specification.
```

## Create the specification

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
2. Status: whether the spec is a draft, accepted, or superseded, plus acceptance
   and revision details when applicable.
3. Current context: relevant existing behavior, files, workflows, constraints, and
   dependencies.
4. Assumptions: unconfirmed beliefs that affect requirements or implementation.
5. Desired behavior: user-visible behavior, interfaces, data changes,
   operational behavior, or workflow changes.
6. Scope: required capabilities and related work intentionally excluded.
7. Commands and validation: exact build, test, lint, documentation, migration, or
   manual verification commands where known.
8. Project structure: where implementation, tests, docs, and configuration belong.
9. Style and conventions: naming, formatting, error handling, logging, API,
   accessibility, security, or platform conventions that matter for the change.
10. Testing strategy: which test levels or checks prove the behavior works.
11. Execution boundaries: what to always do, ask before doing, and never do.
12. Success criteria: specific, testable conditions for completion.
13. Open questions: unresolved decisions, their impact, owner, and whether they
    block acceptance or implementation.

### Specification template

Use `assets/specification-template.md` as the starting structure. Adapt its level
of detail to the change, but preserve the sections that communicate requirements,
status, scope, constraints, boundaries, success criteria, assumptions, and
unresolved questions.

Remove placeholder text from the resulting specification. Do not silently remove
a section because its answer is unknown; record the unknown as an assumption or
open question instead. Mark conditionally applicable concerns as not applicable
only when repository evidence or user confirmation supports that conclusion.

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

## Confirm the specification

Before handoff, ask the user to accept or correct the specification. Acceptance
may cover the complete spec in one review; it does not require separate approval
of every section when no material ambiguity remains.

Record the result in the specification's status section so later sessions can
distinguish a draft from an accepted or superseded revision. For an accepted
specification, record the accepting person or role and acceptance date when
known. Do not infer acceptance from the absence of questions or from subsequent
implementation activity.

Classify every unresolved question as blocking or non-blocking. If a blocking
question remains, keep the specification labeled as a draft and do not describe
it as ready for implementation planning. A non-blocking question may remain in
an accepted specification only when its permitted impact is explicit. If no live
user is available, record the missing decision, its impact, owner when known,
and any safe options without choosing one silently.

## Handoff to planning

The accepted specification is the canonical source for downstream planning and
implementation. Use `planning-and-task-breakdown` to create a separate derived
plan under `docs/plans/<name>-plan.md` by default, unless project conventions or
the user specify another location.

The derived plan may choose implementation details, sequencing, task boundaries,
and verification checkpoints, but it must preserve the specification's objective,
requirements, constraints, boundaries, and success criteria.

If a plan conflicts with the specification:

1. Treat the specification as authoritative.
2. Stop planning or implementation at the conflict.
3. Resolve whether the plan is wrong or the requirement has changed.
4. Update and re-confirm the specification before accepting a material requirement
   change.
5. Revise the derived plan to match the accepted specification.

## Keeping the spec alive

- Update and re-confirm the spec when accepted scope, behavior, data, interfaces,
  constraints, or success criteria change materially.
- Link implementation work back to the relevant spec section when useful.
- Record durable architectural decisions in an ADR when the choice will matter to
  future maintainers.
- Keep rejected options or unresolved questions visible until resolved.
- Do not let a plan or implementation silently become the new source of truth.

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
- allowing a derived plan to redefine requirements or success criteria
- implementing behavior not present in the accepted spec
- skipping clarification when requirements conflict
- treating an outdated spec as irrelevant instead of updating it

## Verification

Before handing the spec to planning, confirm:

- [ ] assumptions and open questions are visible
- [ ] every open question records its impact and blocking status
- [ ] blocking questions are resolved
- [ ] the spec defines objective, desired behavior, constraints, and boundaries
- [ ] in-scope and out-of-scope work are explicit
- [ ] success criteria are specific and testable
- [ ] validation commands or manual checks are recorded where known
- [ ] the spec is identified as the canonical source for downstream work
- [ ] the spec status and acceptance details are recorded durably
- [ ] the user has accepted the spec, or it is explicitly labeled as an
      unconfirmed draft that is not ready for implementation planning
