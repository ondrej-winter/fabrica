# Implementation Plan: [Feature/Project Name]

## Overview

[One paragraph summary of what is being built.]

## Scope

### In scope

- [Behavior, component, workflow, or artifact included in this plan.]

### Out of scope

- [Explicit non-goal or deferred work.]

## Assumptions

- [Assumption that affects implementation, and how or when it will be confirmed.]

## Architecture Decisions

- [Key decision and rationale.]

## Progress Tracking

This dashboard mirrors every task, acceptance criterion, verification item, and
checkpoint checkbox in the detailed plan. Keep both copies synchronized whenever
either copy changes. The detailed sections remain the source of context; this
dashboard is the at-a-glance completion view.

Mark a parent task complete only when all required child items are resolved.
Items explicitly marked not applicable do not block completion. Unknown,
unresolved, or unapproved deferred items remain unchecked and block completion.

### Phase 1: [First coherent slice or necessary prerequisite]

- [ ] `T1` — [Task 1 title]
  - [ ] `T1-AC1` — [Acceptance criterion]
  - [ ] `T1-V1` — [Focused verification]
  - [ ] `T1-V2` — [Final or broader verification]
  - [ ] `T1-V3` — [Manual verification]
- [ ] `CP1` — [Meaningful checkpoint]

### Phase 2: [Next coherent slice]

- [ ] `T2` — [Task 2 title]
  - [ ] `T2-AC1` — [Acceptance criterion]
  - [ ] `T2-V1` — [Focused verification]
  - [ ] `T2-V2` — [Final or broader verification]
  - [ ] `T2-V3` — [Manual verification]

### Completion

- [ ] `CP-FINAL-1` — All acceptance criteria met
- [ ] `CP-FINAL-2` — Focused and final handoff checks resolved
- [ ] `CP-FINAL-3` — Ready for review

After each completed task or meaningful plan change, update this dashboard and
the matching detailed checkboxes, add newly discovered work, adjust sequencing,
and note blockers or deviations without waiting for the user to ask.

## Task List

### Phase 1: [First coherent slice or necessary prerequisite]

#### Task 1: [Short descriptive title]

**Task completion:**

- [ ] `T1` — All required acceptance and verification items are resolved

**Description:** [What this task accomplishes and why it is sequenced here.]

**Acceptance criteria:**

- [ ] `T1-AC1` — [Specific, testable condition.]

**Verification:**

- [ ] `T1-V1` — Focused check: `<confirmed_test_or_check_command>`
- [ ] `T1-V2` — Final or broader check when applicable: `<confirmed_command>`
- [ ] `T1-V3` — Manual check when applicable: [description]

**Dependencies:** [None or task numbers]

**Files likely touched:**

- `<project-relative-path>`

**Estimated scope:** [XS | S | M | L | XL, with rationale when L]

### Checkpoint: [Meaningful boundary]

- [ ] `CP1` — [Relevant integration, quality, approval, or risk check.]

### Phase 2: [Next coherent slice]

#### Task 2: [Short descriptive title]

**Task completion:**

- [ ] `T2` — All required acceptance and verification items are resolved

**Description:** [What this task accomplishes and why it is sequenced here.]

**Acceptance criteria:**

- [ ] `T2-AC1` — [Specific, testable condition.]

**Verification:**

- [ ] `T2-V1` — Focused check: `<confirmed_test_or_check_command>`
- [ ] `T2-V2` — Final or broader check when applicable: `<confirmed_command>`
- [ ] `T2-V3` — Manual check when applicable: [description]

**Dependencies:** [None or task numbers]

**Files likely touched:**

- `<project-relative-path>`

**Estimated scope:** [XS | S | M | L | XL, with rationale when L]

### Checkpoint: Complete

- [ ] `CP-FINAL-1` — All acceptance criteria met
- [ ] `CP-FINAL-2` — Focused and final handoff checks pass or are explicitly not
      applicable; no required check remains unknown
- [ ] `CP-FINAL-3` — Ready for review

## Risks and Mitigations

| Risk   | Impact         | Mitigation |
| ------ | -------------- | ---------- |
| [Risk] | [High/Med/Low] | [Strategy] |

## Open Questions

- [Question needing human input.]
