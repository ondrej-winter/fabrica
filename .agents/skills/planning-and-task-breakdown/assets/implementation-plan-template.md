# Implementation Plan: [Feature/Project Name]

## Outcome and basis

[Desired behavior and relevant current behavior.]

**Requirements source:** [Canonical spec, issue, or user instruction; revision
when available.]

**Readiness:** [Ready | Needs revision | Blocked — choose one, with rationale.]

**Next action:** [Ready task IDs or the exact condition needed to proceed. State
any existing execution boundary that applies.]

## Scope and decisions

- **In scope:** [Required outcomes.]
- **Out of scope:** [Non-goals and authorized deferrals.]
- **Binding constraints:** [Compatibility, interfaces, data, or execution limits.]
- **Implementation decisions:** [Choices and their evidence or rationale.]

## Assumptions and unresolved questions

| ID | Assumption or question | Affected tasks and blocking point | Resolution or evidence needed | Owner or source when known |
| --- | --- | --- | --- | --- |
| Q1 | [Decision, technical uncertainty, or working assumption] | [Tasks; what can proceed meanwhile] | [How and when to resolve; discovery task if needed] | [Known resolver or unassigned] |

[Write "None" when no material unknowns remain. Do not use N/A for unresolved
questions.]

## Requirement coverage

| Requirement or requested outcome | Tasks | Acceptance and verification |
| --- | --- | --- |
| [Existing ID or brief outcome reference] | T1 | T1-AC1, T1-V1 |

[For short plans, task basis fields can supply this mapping instead.]

## Progress Tracking

Mirror every detailed task, acceptance, verification, and checkpoint checkbox
here with the same ID, meaning, and state. Each ID labels one checkbox here and
one in the details. Preserve IDs when reordering; add fresh IDs for new work.

- [ ] `T1` — [Task title]
  - [ ] `T1-AC1` — [Observable acceptance condition]
  - [ ] `T1-V1` — [Focused verification and expected result]
- [ ] `CP1` — [Integration or risk checkpoint and pass condition]
- [ ] `CP-FINAL-1` — All required acceptance criteria met
- [ ] `CP-FINAL-2` — Final handoff checks resolved with evidence

After each completed task or meaningful change, update both views and the status
notes. Check items only with evidence or an explicit `Not applicable — <reason>`;
N/A records applicability, not a passing check. Complete a parent only when all
required child items are resolved. Unknown, failed, unverified, blocked, and
unapproved deferred items remain unchecked. Move authorized deferrals out of
required scope in both views and record their disposition without marking them
completed. Reopen items whose evidence is invalidated by later changes.

## Task details

[Repeat this task block as needed, adding its IDs to the dashboard. Group tasks
into phases only when the boundaries help execution.]

### T1: [Short outcome title]

- [ ] `T1` — [Task title; complete when all required child items are resolved]

**Outcome and basis:** [What this accomplishes; requirement reference or the task
it enables. Explain a separate prerequisite task when needed.]

**Dependencies and entry conditions:** [None, or task IDs with the required
artifact/condition; include external prerequisites and unresolved questions.]

**Files or components:** [Confirmed project-relative targets and labeled proposed
new files; distinguish source from generated or installed copies.]

**Estimated scope:** [XS / S / M / L / XL, with rationale for uncertainty or a
retained large atomic task.]

**Acceptance criteria:**

- [ ] `T1-AC1` — [Given conditions/input, when an action occurs, observable result;
      include relevant failure behavior as additional criteria.]

**Verification:**

- [ ] `T1-V1` — [Confirmed command or manual procedure; expected result. Include
      source, working directory, and prerequisites when needed.]

[Add checks only when applicable. For unknown commands, specify the intended
evidence and use "Unknown — discover in <task ID> before <task or checkpoint>".
Distinguish planned checks from executed results. Reference shared checks below
instead of repeating broad suites in every task.]

**Evidence and status:** [Pending initially; later record results, evidence
location, blockers, or an explicit N/A reason.]

[For a discovery task, also state its question, investigation limit, evidence
deliverable, and decision needed to unlock dependent work.]

### CP1: [Meaningful integration or risk boundary]

**Prerequisites:** [Task IDs and entry conditions.]

- [ ] `CP1` — [Check or procedure and observable pass condition.]

**Evidence and status:** [Pending; record results when executed.]

[Add checkpoints at actual boundaries, or remove CP1 here and in the dashboard
if final handoff is the only useful checkpoint.]

### Final handoff

**Prerequisites:** [All required task IDs and preceding checkpoint IDs.]

- [ ] `CP-FINAL-1` — Every in-scope requirement is covered and all required
      acceptance criteria have supporting evidence.
- [ ] `CP-FINAL-2` — [Confirmed final commands or manual procedures and pass
      conditions; required checks pass or are explicitly N/A with reasons.]

**Evidence and status:** [Pending; unresolved required checks prevent completion.]

## Parallel execution

[Omit when execution is sequential. Identify actual independence, including tests
and docs, before assigning work. Branch acceptance must be achievable before the
join; reserve combined behavior for the integration check.]

| Tasks | Entry contract or artifact | Owner and write boundaries | Shared state constraints | Integration task, owner, and check |
| --- | --- | --- | --- | --- |
| [Concurrent task IDs] | [Prerequisite] | [Known assignment or unassigned; paths/components] | [Serialized operations, if any] | [Explicit join and combined verification] |

## Risks and fallback

[Include material risks only; identify affected tasks and the trigger for a
mitigation, fallback, or recovery action. For data changes, distinguish data
recovery from reverting code. Omit when no additional risks need tracking.]

## Status and scope changes

[After each task or meaningful change, record affected IDs, evidence or blocker,
deviation and its basis, any authorized deferral, and the next action. Update
readiness and both checkbox views when needed; do not renumber existing IDs.]
