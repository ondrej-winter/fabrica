---
name: spec-driven-development
description: Create, review, or revise a canonical specification with observable requirements, scope boundaries, acceptance checks, and explicit unresolved decisions. Use when requirements are incomplete, conflicting, spread across sources, or need a durable agreement before planning or changing implementation.
metadata:
  version: "2.0.0"
  dependencies:
    tools: []
    skills:
      - name: planning-and-task-breakdown
        purpose: Derive ordered, verifiable implementation tasks from settled requirements.
        required: false
      - name: review-implementation-plan
        purpose: Check a derived plan's scope, sequencing, and verification before implementation.
        required: false
      - name: interview-me
        purpose: Resolve uncertainty about the user's underlying intent when focused clarification is insufficient.
        required: false
      - name: idea-refine
        purpose: Explore options when the intent is understood but the concept or scope is undecided.
        required: false
---

# Spec-Driven Development

Make the required outcome clear enough that another person or agent can plan,
implement, and assess it without inventing product decisions. The specification
defines what must hold, why it matters, and how conformance will be checked. The
implementation plan derives tasks and technical choices from that agreement.

Use this skill to create a missing specification, consolidate scattered
requirements, review an existing spec, or revise it when the requested behavior
changes. For a precise fix or small edit with clear acceptance criteria, work
directly from the request; a separate specification adds no necessary decision.

The deliverable is a canonical specification with an honest status and a clear
next step. A request for a spec ends there. When specification is one phase of
authorized implementation work, continue into that work once the relevant
requirements are settled; do not introduce an extra approval solely because a
document was created.

## 1. Establish context and the source of truth

Read the request, prior decisions, existing specification, and relevant code,
tests, documentation, or contracts before asking the user to repeat information.
Identify the actor, problem, current behavior, desired change, and binding
constraints. Inspect enough to distinguish an observed fact from an assumption;
do not turn specification work into an unrelated repository audit.

Reuse the established canonical artifact and location. When creating a new file
without a project convention, use `docs/specs/<name>-spec.md`, with a short
kebab-case name. Respect a requested format or location. Link supporting issues,
designs, and decisions instead of creating competing copies of the requirements.

For each material requirement or constraint, preserve its basis: an explicit
user instruction, an accepted decision, an existing contract, or a proposal that
still needs resolution. Existing code establishes current behavior; it does not
override a requested change or prove that behavior is correct. Resolve conflicts
between sources explicitly, using the user's current instructions to update
superseded decisions.

Use `interview-me` when the underlying intent needs deeper discovery, or
`idea-refine` when the goal is understood but options or scope remain undecided.
These are optional routes, not prerequisites for every spec. If unavailable,
ask the focused question needed to settle the outcome and continue with the
available context.

## 2. Choose the smallest useful specification

For a bounded change, a short document can contain:

- objective and relevant current behavior
- status and the decisions or instructions it rests on
- required outcomes with acceptance checks
- scope, exclusions, binding constraints, and execution boundaries
- assumptions and unresolved decisions, or an explicit statement that none remain

For broader changes, adapt [assets/specification-template.md](assets/specification-template.md).
Add detail where interfaces, data, compatibility, operations, or other affected
concerns introduce decisions. Merge or omit sections that do not apply. Record
material unknowns as questions rather than hiding them by deleting a section or
marking it not applicable.

Keep implementation file choices, task sequencing, estimates, parallelization,
and detailed test construction in the derived plan. Record technical choices in
the spec when they are binding constraints or externally observable contracts;
label suggested approaches as suggestions. Reference established project
conventions instead of copying entire style guides into each specification.

## 3. Define observable requirements and acceptance checks

Write one independently assessable requirement per item. Give requirements and
acceptance criteria stable identifiers such as `R1` and `AC1` when they will be
referenced by a plan, tests, or later revisions. Preserve existing identifiers;
do not renumber unrelated items during an update.

For each requirement, state the actor or system, trigger or input, observable
outcome, and relevant conditions. Include failure behavior and invariants that
could otherwise lead to different implementations. Consider boundaries, retries,
partial failure, permissions, and compatibility only where they affect the
requested behavior. Keep optional enhancements outside the required scope.

Connect every required outcome to an acceptance check that states:

- the starting conditions and action
- the observable result that distinguishes pass from fail
- how that result will be assessed, such as a test, contract check, measurement,
  or manual procedure

For a quantitative target, include units and measurement conditions such as
workload and environment. Identify proposed targets as proposals; do not invent
a threshold and present it as an agreed requirement. Replace vague goals such
as "fast", "reliable", or "user-friendly" with observable outcomes or a question
about the intended result.

For example, **if all-or-nothing import behavior is an agreed requirement**:

```text
R1: If any input row is invalid, reject the entire import, identify the invalid
    row and field, and leave stored records unchanged.
AC1 -> R1: Given an existing record and an import containing one valid row and
           one invalid row, submit the import. Verify that the response identifies
           the invalid row and field and that stored records match the pre-import
           state. Assess with an integration check of the response and storage.
```

This example does not decide atomicity or duplicate handling for other imports.
Those rules must come from the task's requirements or a recorded decision.

Record known validation commands with their repository source when useful.
Otherwise state the procedure or evidence needed and leave command discovery to
planning. An unknown command is not itself a requirement blocker; an undefined
pass condition or unresolved feasibility constraint may be. "Tests pass" and
"Tests were added" do not substitute for observable acceptance criteria.

## 4. Resolve uncertainty without repeating settled decisions

Separate confirmed requirements, working assumptions, and open questions. For
each material unknown, record the affected requirement or work, its impact, who
or what can resolve it, and when it must be resolved. Do not invent an owner.

Classify a question by what it blocks:

- **Requirement acceptance:** the answer changes the outcome, scope, external
  contract, data guarantees, or another binding constraint.
- **Affected planning or implementation:** the outcome is settled, but a technical
  choice, feasibility check, dependency, or execution permission remains.
- **Non-blocking:** a stated working assumption permits progress within a bounded
  impact; record when it must be checked and what would trigger reconsideration.

Resolve questions from available evidence first. Ask the user only for material
choices that the evidence and existing authority do not settle. Present the
concrete proposed behavior, alternatives where helpful, and why the decision
matters. Continue independent work while a question is pending; pause the work
that depends on its answer. Silence or elapsed time does not resolve a required
decision.

Reuse prior acceptance and explicit instructions that already settle the
requirements. Decisions within explicitly delegated authority can also settle
requirements; record that basis instead of claiming the user reviewed the spec.
General permission to work does not mean that later invented requirements have
been accepted. For a new material proposal outside existing authority, prepare
the reviewable specification before asking for acceptance.

Execution boundaries come from the user, project, and environment. Record the
applicable limits; do not create generic "ask first" gates or request an already
granted permission again. Specification acceptance does not grant permission for
additional external actions.

## 5. Record status and hand off

Use the project's lifecycle if one exists; otherwise use these states:

- **Draft:** proposed requirements or requirement decisions still need acceptance.
- **Accepted:** requirements are settled by recorded instructions, acceptance, or
  explicit delegated authority, with no blocking requirement questions.
- **Superseded:** another identified revision or artifact replaces this one.

Record the revision, acceptance basis, accepting person or role and date when
known, and any superseding link. Do not fabricate acceptance details. Lack of a
live reviewer does not undo recorded acceptance; missing required decisions
remain explicit in a draft.

Acceptance of requirements is separate from implementation readiness or verified
completion. An accepted spec may still have a planning dependency or an execution
permission to resolve. Identify the affected work in the handoff instead of
labeling all implementation ready or blocked without qualification.

When planning is requested or is the next phase of authorized work, use
`planning-and-task-breakdown` if available to derive a separate plan, by default
at `docs/plans/<name>-plan.md`. Link the plan to the spec revision and relevant
requirements. Use `review-implementation-plan` when the resulting plan needs an
independent readiness check. If these skills are unavailable, preserve the same
requirements-to-plan boundary in the handoff.

Return the specification location, status and basis, unresolved decisions with
their impact, and the next authorized step. Do not stop a broader implementation
request merely because this phase's artifact is complete.

## 6. Maintain the agreement through changes

When reviewing or revising a spec, preserve valid requirements, identifiers,
acceptance evidence, and unresolved issues. Correct wording or add supporting
evidence without reopening settled product decisions.

For a material change, record what changes, why, its source of authority, and the
affected requirements, acceptance checks, and downstream work. Keep the accepted
baseline identifiable while a proposal is under review, using revision history
or a clearly separated proposed amendment. Do not overwrite accepted requirements
with an unaccepted proposal or maintain two competing canonical specs.

If a plan or implementation conflicts with the spec, pause affected work and
determine whether the implementation is wrong or the requirement has changed.
Use existing authorization for a directed change; otherwise resolve the material
decision before adopting it. Update the spec and derived plan together so neither
silently redefines the agreement.

## Verification

Before handoff, check that:

- the canonical artifact is identifiable and its status has recorded evidence
- required outcomes, exclusions, and binding constraints are unambiguous
- every required outcome has an acceptance check with an observable pass condition
- relevant failure cases and compatibility obligations are covered
- proposals, assumptions, and confirmed decisions are distinguishable
- every material unknown identifies its impact and the work or decision it blocks
- commands, targets, owners, and acceptance details have not been invented
- implementation mechanics remain in the plan unless they are binding constraints
- the next step respects existing authorization and any unresolved decisions
