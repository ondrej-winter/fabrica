---
name: planning-and-task-breakdown
description: Create or revise an implementation plan from clear requirements, with ordered tasks, acceptance criteria, dependencies, verification, and progress tracking. Use when scope needs decomposition, sequencing is uncertain, or work must be coordinated across agents or sessions.
metadata:
  version: "2.0.0"
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

Turn agreed outcomes into small, verifiable tasks that another person or agent
can execute without inventing requirements or rediscovering dependencies. Prefer
complete feature slices, explicit evidence of completion, and a plan that remains
useful across sessions.

For a small change with obvious scope and checks, a short task list is enough;
do not create a separate plan merely because several files are involved. When an
existing spec or plan already has executable tasks, reuse and repair that
breakdown instead of creating a competing document.

A planning-only request ends with the plan and its handoff. When planning is a
phase of authorized implementation, finish the relevant planning first, then
continue with ready tasks under the existing authorization. Creating a plan does
not introduce an additional approval gate or authorize new external actions.

## Steps

### 1. Establish the outcome and canonical sources

Read the request, prior decisions, specification, and relevant code, tests, and
repository guidance. Inspect enough context to establish:

- the desired behavior, scope boundaries, and binding constraints
- the canonical requirements source and revision when available
- existing implementation patterns, affected contracts, and relevant checks
- source files versus generated or installed copies, and how derived files update
- assumptions and unresolved decisions that affect the work

Use `spec-driven-development` when available if required outcomes or scope need
resolution. A clear request can supply the requirements directly; do not require
a separate spec for every plan. Resolve technical details from available evidence
before asking the user to repeat settled information.

Reuse the established plan path. For a new plan without a requested location or
repository convention, use `docs/plans/<kebab-case-name>-plan.md`. Respect a
requested inline format. Link requirements and decisions rather than copying
them into a second specification.

### 2. Map requirements, unknowns, and dependencies

Associate each task with the requirement it fulfills or the prerequisite it
enables. Preserve existing requirement IDs; for a short request without IDs, a
brief reference to the requested outcome is enough. Check coverage in both
directions: every in-scope requirement has work and verification, and every task
has a scope basis. Keep optional enhancements and unrelated cleanup outside the
required work.

For each material unknown, identify the affected tasks, how it can be resolved,
who or what can resolve it when known, and the point by which it must be settled:

- **Outcome or scope decision:** resolve before implementing the affected
  behavior. Record a proposal separately from an agreed requirement.
- **Technical uncertainty:** inspect available evidence or add a bounded
  discovery task with a question, investigation limit, evidence to produce, and
  decision that unlocks dependent work. A spike delivers a finding, not an
  implied production implementation.
- **Working assumption:** state its basis, impact if false, and when to check it.
  It permits progress only where its uncertainty does not invalidate that work.

Use stable task IDs for dependencies. Name the actual prerequisite artifact or
condition, including external dependencies, instead of writing only "after T1".
Check for missing references and cycles. If tasks depend on each other, extract
the shared prerequisite or combine them into one justified atomic task. Resolve
questions from evidence or existing authority; ask for a material decision only
when neither settles it, and continue independent planning while it is pending.

### 3. Slice and size the work

Prefer one complete, testable behavior per task, including its relevant failure
cases. For example, given agreed requirements for a record workflow:

```text
T1: Create a valid record; reject invalid input without persisting it.
    Includes the storage path, interface, user entry point, and focused checks.
T2: List saved records, including the agreed empty-state behavior.
    Depends on the record contract established in T1.
T3: Edit a record while preserving the agreed validation rules.
    Depends on T1; depends on T2 only if listing is the required entry point.
```

Avoid tasks that build all models, then all services, then all interfaces and
leave integration to the end. A shared contract, migration, setup task, or
feasibility spike may precede the first slice when it is a true prerequisite;
record why it cannot be included in that slice.

Size by cohesion, uncertainty, review effort, and verification cost:

| Size | Meaning | Planning action |
| --- | --- | --- |
| XS / S | Localized change with known checks | Keep it concise. |
| M | One coherent slice with understood boundaries | Identify interfaces and integration checks. |
| L | Broad, costly to verify, or materially uncertain | Split or investigate; justify retaining an atomic task. |
| XL | Several outcomes or too little knowledge to execute | Decompose before treating it as ready. |

More than about five independently edited files is a prompt to review the split,
not a hard limit. Generated or mechanical changes may add little independent
work. Do not split a coherent task solely because its title contains "and", it
needs several acceptance criteria, or it crosses layers. If estimates are
requested, state their basis and uncertainty; file counts and size labels are
not elapsed-time estimates.

### 4. Make each task executable and verifiable

Use [assets/implementation-plan-template.md](assets/implementation-plan-template.md)
as the starting structure for a written plan. Adapt task count and phases to the
work; omit inapplicable optional sections. Each task needs:

- a stable ID, outcome, and requirement or prerequisite basis
- observable acceptance criteria, including relevant boundaries and failures
- verification steps with expected results
- dependencies and entry conditions, or an explicit statement that none apply
- likely project-relative files or components and estimated scope

Distinguish paths confirmed by inspection from proposed new files. Use component
names or labeled placeholders where paths are unknown; do not present guessed
paths as existing files. Add ownership and write boundaries when delegating.

Acceptance criteria describe what must hold; verification explains how to prove
it. "Tests added" or "tests pass" alone does not establish the requested outcome.
For a behavior fix, include a check that distinguishes the corrected behavior
from the original failure. Use tests, inspection, measurements, or manual checks
in proportion to the change; do not prescribe new tests for every task.

Use commands confirmed from repository documentation, configuration, or existing
scripts. Record their source, working directory, prerequisites, and expected
result where needed to reproduce them. A confirmed command has been found, not
necessarily run. For an unknown check, specify the intended evidence and write
`Unknown — discover in <task ID> before <dependent task or checkpoint>`.
Discovery may proceed; the unknown check prevents claiming verified completion.
Use `Not applicable — <reason>` only when a check truly does not apply.
Plan new coverage under an existing confirmed check when possible. Proposed test
files do not need to exist yet for their runner command to be known.

Keep focused iteration checks with their tasks. Put shared build, static, or
integration checks at meaningful checkpoints and final handoff, referencing them
from affected tasks when appropriate. Required task-level verification must be
resolved before that task is complete; a later shared integration checkpoint
still gates overall completion. Do not run a broad suite after every task by
default or treat a failed or unavailable required check as not applicable.

### 5. Order work and coordinate parallel execution

Follow dependencies while testing the riskiest assumptions early. Each completed
slice should leave a working, reviewable state. Include compatibility, migration,
recovery, and rollout work when the requested change requires them; do not assume
that reverting code reverses a data change.

Add checkpoints at meaningful integration, risk, or phase boundaries, plus final
handoff. Each checkpoint states its prerequisite tasks, check, and pass condition.
Identify a human review or execution permission only when the user, project, or
environment actually requires it. Preserve permissions already granted.

For work that can run concurrently, record:

- the tasks, shared contract or fixture, and conditions for starting each branch
- ownership or assignment needs, including disjoint write boundaries or an
  explicit coordination arrangement for shared files
- shared state or environment constraints that require serialized operations
- the integration task, its owner when known, and the combined verification

Different task names or worktrees do not establish independence. Tests and
documentation can depend on unfinished behavior or edit the same files. Contract
design may unblock parallel producers and consumers; combining their results
still needs an explicit integration step. Do not invent people, assignments, or
availability.

When splitting a slice into parallel branches, define branch completion against
the established contract and fixtures, and put combined behavior at the join.
If a branch's acceptance requires a shared entry point, schedule that wiring
before branch completion. A join cannot both depend on completed branches and
supply work required for those branches to be complete.

### 6. Review readiness and hand off

Use the project's lifecycle when one exists; otherwise assign one plan readiness
label with a brief rationale:

- **Ready:** required outcomes, sequencing, and validation are specific enough
  to execute, with no unresolved blocking decisions.
- **Needs revision:** gaps remain, but evidence gathering or independent tasks
  can proceed; identify those tasks and what must be settled for the rest.
- **Blocked:** the next executable work requires a missing decision, dependency,
  or permission; name the condition that would unblock it.

Readiness describes the plan, not implementation progress or permission to take
an external action. Label affected tasks explicitly so a downstream blocker does
not freeze independent work. Do not label the whole plan ready while concealing
unknown validation or unresolved requirements.

Use `review-implementation-plan` when available and an independent readiness
check would help with sequencing, dependencies, risk, or validation. Otherwise
perform the final checklist below directly. Keep this review within the requested
scope and existing authorization.

Return the plan location or inline plan, readiness and rationale, the next
executable tasks, unresolved decisions and their impact, and required validation.
For planning-only requests, stop there. For broader authorized work, continue
with ready tasks and pause only the work that depends on unresolved decisions.

## Maintain progress during implementation

Give every task, acceptance criterion, verification item, and checkpoint checkbox
a stable ID. Each ID labels exactly two checkboxes: one in the detailed plan and
one in the Progress Tracking dashboard, with matching meaning and state. The details
carry context and evidence; the dashboard mirrors completion. Preserve IDs on
reorder and revision, and allocate new IDs for newly discovered work.

After each completed task or meaningful change, synchronize both copies, record
brief evidence or blockers, and update dependencies, scope, and the next action.
Do not wait for a progress request. Check an item only when its condition holds
with evidence, or it is explicitly `Not applicable — <reason>`. A checked N/A
item records applicability, not a successful test. Mark a parent task complete
only when all its required acceptance and verification items are resolved.

Unknown, failed, unverified, blocked, or unapproved deferred items stay unchecked
and block completion of the affected task or checkpoint. An authorized deferral
must record its basis and move the item out of required scope in both views;
retain its ID and disposition without representing it as completed work. Update
the canonical requirements if the deferral changes the agreed outcome.

Preserve completed work and evidence when revising a plan. If a change invalidates
an earlier check, reopen the affected items in both views and explain why. Record
material deviations and changed assumptions so the next session can resume
without repeating completed work or trusting stale verification.

## Final checklist

- The canonical plan and requirements basis are identifiable; existing IDs,
  decisions, and valid progress have been preserved.
- Every required outcome maps to tasks and observable checks; every task has a
  scope basis, dependencies, likely targets, and proportionate sizing.
- Unknowns have resolution steps and identify the work they block; no paths,
  commands, owners, approvals, or completion evidence have been invented.
- Dependencies are acyclic, prerequisites are actionable, and parallel work has
  write boundaries and an integration step.
- Focused and final checks have pass conditions; unknown or unavailable required
  verification remains unresolved.
- Every progress ID has one detailed checkbox and one matching dashboard
  checkbox; parent completion follows required child completion.
- Readiness, affected blockers, and the next authorized action are explicit.
