---
name: review-implementation-plan
description: Review and update an existing implementation plan for completeness, ambiguity, sequencing, risks, dependencies, validation, readiness labeling, and handoff before coding.
metadata:
  version: "1.2.0"
  dependencies:
    tools: []
    skills:
      - name: spec-driven-development
        purpose: Clarify requirements, success criteria, assumptions, and scope boundaries before reviewing a plan.
        required: false
      - name: planning-and-task-breakdown
        purpose: Decompose clear requirements into ordered, verifiable implementation tasks before reviewing a plan.
        required: false
---

# Review Implementation Plan

Use this skill before implementation begins, after an implementation plan exists
or is being proposed for a non-trivial change. The goal is to catch ambiguity,
missing work, unsafe sequencing, and validation gaps before code or content
changes begin.

When those optional skills are available, use `spec-driven-development` first
when the plan lacks clear requirements, success criteria, assumptions, or scope
boundaries. Use `planning-and-task-breakdown` first when requirements are clear
but the plan is too coarse and needs to be decomposed into ordered, verifiable
implementation tasks.

## When to use this skill

Use this skill when:

- a plan spans multiple files, modules, systems, or teams
- implementation order affects safety or reviewability
- dependencies, migrations, data changes, or compatibility risks exist
- testing and validation strategy need to be explicit
- the user asks for deep planning, audit, or review before coding

For simple one-file edits, use only the relevant parts and keep the review brief.

## Expected output

Review and update the existing implementation plan in place. Preserve valid
content, decisions, task identifiers, and completed progress while making the
smallest revisions needed to resolve gaps in scope, sequencing, dependencies,
risks, ownership, validation, and handoff.

Use the plan path supplied by the user or established by repository context. Do
not assume a filename or invent a repository path. If no plan file can be
identified, ask for its location. When no plan exists and requirements are clear,
use `planning-and-task-breakdown` to create one before reviewing it.

Record unresolved decisions explicitly in the plan rather than inventing
answers. Every updated plan must include one readiness label:

- `Ready`: the plan is specific enough to implement with known validation
- `Needs revision`: the plan has gaps, but they can be resolved without changing
  the core goal
- `Blocked`: implementation should not start until a missing decision,
  requirement, dependency, or approval is resolved

After updating the plan, return a concise handoff organized as:

1. readiness label and brief rationale
2. plan path and sections changed
3. unresolved questions and decisions, with an owner when known
4. required validation checks
5. deferred work

When a finding cannot be resolved safely, add it to the plan as an explicit
question, blocker, risk, or deferred item. Distinguish missing plan evidence from
reviewer uncertainty, and do not invent repository paths, commands, owners, or
requirements.

## Steps

### 1. Confirm the goal and scope

Restate the requested outcome in concrete terms. Identify:

- what will change
- what will not change
- where the plan, specification, issue, or decision record lives
- who or what is affected
- assumptions that need confirmation
- constraints from architecture, compatibility, policy, or tooling

Ask clarifying questions before implementation when scope or constraints are
unclear.

### 2. Check file and ownership specificity

A good plan should identify the likely files, modules, components, or documents
that need work. For each important target, check whether the plan explains:

- why it is in scope
- what kind of change is expected
- whether it is source, generated, synced, or derived content
- whether there are ownership or portability constraints
- whether another source of truth should be edited instead

### 3. Check interface and dependency impact

Review whether the plan accounts for affected public surfaces, contracts, and
callers.

Look for:

- API, command, schema, event, configuration, or data format changes
- dependency additions, removals, or version constraints
- migration, compatibility, or rollback implications
- generated files, documentation, or examples that must stay aligned
- security, privacy, or operational implications
- source-of-truth or ownership decisions that should be settled before editing

### 4. Check sequencing and reviewability

Ensure the implementation order reduces risk and keeps review manageable.

Prefer sequences that:

1. establish or confirm source-of-truth decisions
2. add tests or validation coverage where useful
3. make the smallest coherent implementation changes
4. update docs, generated files, and metadata
5. run focused validation before broader validation
6. summarize deferred work explicitly

Flag plans that mix unrelated refactors with behavior changes or attempt too much
in one pass.

### 5. Check test and validation strategy

Verify that the plan names the checks that prove the work is complete. Consider:

- unit, integration, end-to-end, contract, snapshot, or manual checks
- linting, formatting, type checking, static analysis, build, or docs checks
- migration or compatibility validation
- failure cases and regression coverage
- project-defined commands and what to do if an expected check is unavailable

A plan should distinguish focused iteration checks from final handoff checks.

### 6. Check risks and fallback options

Identify material risks and how the implementation should respond.

Common risks include:

- unclear ownership or source of truth
- accidental breaking changes
- large review surface
- flaky or expensive validation
- hidden generated artifacts
- data loss, security, privacy, or operational exposure

For each significant risk, note a mitigation, fallback, or question.

### 7. Update the plan and report the result

Apply the review findings directly to the identified plan file:

- preserve valid requirements, decisions, task identifiers, and progress state
- clarify ambiguous text only when repository evidence supports the revision
- add omitted tasks, dependencies, risks, validation, or handoff information
- record unresolved questions without guessing their answers
- reorder tasks only when the dependency or safety rationale is clear
- assign exactly one readiness label based on the unresolved findings
- do not implement any task from the plan

Re-read the updated plan and verify that the review findings are represented
accurately. Then return a concise handoff that includes:

- readiness assessment
- updated plan path and changed sections
- intended implementation owner or handoff audience when relevant
- unresolved clarifying questions, blockers, and decisions
- required validation commands or checks
- deferred backlog items that should not block the first pass

Do not recommend implementation while blocking questions remain unresolved.
Follow the repository or execution environment's approval policy before moving
from planning to implementation. If no approver is available, hand off the
updated plan with assumptions and blockers labeled explicitly.

## Output checklist

- goal, scope, and non-goals are clear
- target files or modules are specific enough to act on
- dependencies and public interfaces are accounted for
- implementation sequence is reviewable
- validation strategy is explicit
- risks, fallback options, and deferred work are documented
- the identified plan file was updated in place
- valid existing content, task identifiers, and progress state were preserved
- unresolved questions were recorded without invented answers
- review findings are reflected in the plan, not only in the handoff
- the updated plan was re-read after editing
- exactly one readiness label is present and supported by the findings
- no implementation work was started
