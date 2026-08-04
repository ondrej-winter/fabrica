---
name: using-agnostic-software-development-skills
description: Discover and invoke technology-agnostic software development skills. Use when starting general engineering work or deciding which reusable workflow skill applies to a task.
metadata:
  version: "2.1.0"
  dependencies:
    tools: []
    skills:
      - name: add-observability
        purpose: Route observability, logging, metrics, tracing, profiling, and dashboard work.
        required: false
      - name: api-and-interface-design
        purpose: Route API and interface contract design work.
        required: false
      - name: author-agent-skill
        purpose: Route Agent Skill creation, update, and review work.
        required: false
      - name: browser-runtime-verification
        purpose: Route browser-based verification of UI behavior.
        required: false
      - name: ci-cd-and-automation
        purpose: Route CI/CD pipeline and automation work.
        required: false
      - name: code-review-and-quality
        purpose: Route code review and quality gate work.
        required: false
      - name: code-simplification
        purpose: Route behavior-preserving complexity reduction work.
        required: false
      - name: conventional-commits
        purpose: Route Conventional Commits message writing, review, and validation work.
        required: false
      - name: context-engineering
        purpose: Route work that needs better task context before implementation.
        required: false
      - name: debugging-and-error-recovery
        purpose: Route broken behavior, error recovery, and root-cause analysis work.
        required: false
      - name: deprecation-and-migration
        purpose: Route deprecation, migration, and old-system removal work.
        required: false
      - name: documentation-and-adrs
        purpose: Route documentation and architecture decision work.
        required: false
      - name: doubt-driven-development
        purpose: Route high-stakes or unfamiliar implementation decisions for adversarial review.
        required: false
      - name: frontend-ui-engineering
        purpose: Route browser-facing UI implementation and refinement work.
        required: false
      - name: git-workflow-and-versioning
        purpose: Route branch, commit, and version-control workflow work.
        required: false
      - name: hexagonal-vertical-slices
        purpose: Route architecture design, review, or refactoring work involving hexagonal architecture and vertical feature slices.
        required: false
      - name: idea-refine
        purpose: Route rough concepts that need structured refinement.
        required: false
      - name: incremental-implementation
        purpose: Route implementation work that should be built and verified in slices.
        required: false
      - name: interview-me
        purpose: Route unclear user intent that needs discovery before planning.
        required: false
      - name: performance-optimization
        purpose: Route measurement-driven performance investigation and optimization work.
        required: false
      - name: planning-and-task-breakdown
        purpose: Route work that needs decomposition into verifiable tasks.
        required: false
      - name: review-implementation-plan
        purpose: Route implementation plan review work.
        required: false
      - name: run-local-quality-gate
        purpose: Route local formatting, linting, static analysis, test, and build validation work.
        required: false
      - name: security-and-hardening
        purpose: Route security review and hardening work.
        required: false
      - name: shipping-and-launch
        purpose: Route deployment, launch, monitoring, and rollback-readiness work.
        required: false
      - name: source-driven-development
        purpose: Route implementation that needs verification against authoritative sources.
        required: false
      - name: spec-driven-development
        purpose: Route requirements and acceptance criteria definition before code.
        required: false
      - name: test-driven-development
        purpose: Route work that should be driven by tests or test additions.
        required: false
      - name: update-project-docs
        purpose: Route project documentation updates.
        required: false
      - name: write-adr
        purpose: Route architecture decision record creation and updates.
        required: false
---

# Using Agnostic Software Development Skills

## Overview

The agnostic software development collection contains reusable engineering
workflow skills organized by development phase. This catalog helps you discover
and apply the right technology-independent skill for the current task. Use a
technology-specific collection catalog alongside this one when the task also
needs language or platform mechanics.

## Steps

At the start of a task, identify the development phase and apply the corresponding
skill.

1. Classify the task by the user's current need.
2. Select the primary skill that matches the first applicable phase.
3. Add secondary skills only when their trigger is directly present.
4. Confirm that each selected skill is available in the current environment. If it
   is unavailable, report that limitation instead of inventing its instructions.
5. Follow each selected skill's steps, including verification.
6. Report the selected skills, validation evidence, and any remaining limitations
   in the task handoff.

Use this routing guide:

```
Task arrives
- User does not know what they want yet: interview-me
- Have a rough concept and need variants: idea-refine
- New project, feature, or change: spec-driven-development
- Have a spec and need tasks: planning-and-task-breakdown
  - Need plan review before coding: review-implementation-plan
- Implementing code: incremental-implementation
  - Hexagonal architecture or vertical-slice boundary work: hexagonal-vertical-slices
  - UI work: frontend-ui-engineering
  - API work: api-and-interface-design
  - Need better context: context-engineering
  - Need doc-verified code: source-driven-development
  - Stakes high or unfamiliar code: doubt-driven-development
- Writing or running tests: test-driven-development
  - Browser-based testing: browser-runtime-verification
  - Need full local quality checks: run-local-quality-gate
- Adding logs, metrics, traces, profiling, or dashboards: add-observability
- Something broke: debugging-and-error-recovery
- Reviewing code: code-review-and-quality
  - Too complex: code-simplification
  - Security concerns: security-and-hardening
  - Performance concerns: performance-optimization
- Committing or branching: git-workflow-and-versioning
  - Need Conventional Commits syntax or review: conventional-commits
- CI/CD pipeline work: ci-cd-and-automation
- Deprecating or migrating: deprecation-and-migration
- Writing docs or ADRs: documentation-and-adrs
  - Need a project documentation update: update-project-docs
  - Need an architecture decision record: write-adr
- Creating, updating, or reviewing skills: author-agent-skill
- Deploying or launching: shipping-and-launch
```

## Core Operating Behaviors

These behaviors apply at all times, across all skills. They are non-negotiable.

### 1. Surface Assumptions

Before implementing anything non-trivial, explicitly state your assumptions:

```
Assumptions I am making:
1. [assumption about requirements]
2. [assumption about architecture]
3. [assumption about scope]
Correct me now or I will proceed with these.
```

Don't silently fill in ambiguous requirements. The most common failure mode is making wrong assumptions and running with them unchecked. Surface uncertainty early — it's cheaper than rework.

### 2. Manage Confusion Actively

When you encounter inconsistencies, conflicting requirements, or unclear specifications:

1. Stop and do not proceed with a guess.
2. Name the specific confusion.
3. Present the tradeoff or ask the clarifying question.
4. Wait for resolution before continuing.

**Bad:** Silently picking one interpretation and hoping it's right.
**Good:** "I see X in the spec but Y in the existing code. Which takes precedence?"

### 3. Push Back When Warranted

You are not a yes-machine. When an approach has clear problems:

- Point out the issue directly
- Explain the concrete downside (quantify when possible — "this adds ~200ms latency" not "this might be slower")
- Propose an alternative
- Accept the human's decision if they override with full information

Sycophancy is a failure mode. "Of course!" followed by implementing a bad idea helps no one. Honest technical disagreement is more valuable than false agreement.

### 4. Enforce Simplicity

Your natural tendency is to overcomplicate. Actively resist it.

Before finishing any implementation, ask:

- Can this be done in fewer lines?
- Are these abstractions earning their complexity?
- Would a staff engineer look at this and say "why didn't you just..."?

If you build 1000 lines and 100 would suffice, you have failed. Prefer the boring, obvious solution. Cleverness is expensive.

### 5. Maintain Scope Discipline

Touch only what you're asked to touch.

Do not:

- Remove comments you don't understand
- "Clean up" code orthogonal to the task
- Refactor adjacent systems as a side effect
- Delete code that seems unused without explicit approval
- Add features not in the spec because they "seem useful"

Your job is surgical precision, not unsolicited renovation.

### 6. Verify, Don't Assume

Every skill includes a verification step. A task is not complete until verification passes. "Seems right" is never sufficient — there must be evidence (passing tests, build output, runtime data).

## Failure Modes to Avoid

These are the subtle errors that look like productivity but create problems:

1. Making wrong assumptions without checking
2. Not managing your own confusion — plowing ahead when lost
3. Not surfacing inconsistencies you notice
4. Not presenting tradeoffs on non-obvious decisions
5. Being sycophantic ("Of course!") to approaches with clear problems
6. Overcomplicating code and APIs
7. Modifying code or comments orthogonal to the task
8. Removing things you don't fully understand
9. Building without a spec because "it's obvious"
10. Skipping verification because "it looks right"

## Skill Rules

1. **Check for an applicable skill before starting work.** Skills encode processes that prevent common mistakes.

2. **Skills are workflows, not suggestions.** Follow the steps in order. Don't skip verification steps.

3. **Multiple skills can apply.** A feature implementation might involve `idea-refine`, then `spec-driven-development`, then `planning-and-task-breakdown`, then `incremental-implementation`, then `test-driven-development`, then `code-review-and-quality`, then `code-simplification`, then `shipping-and-launch`.

4. **When in doubt, start with a spec.** If the task is non-trivial and there's no spec, begin with `spec-driven-development`.

## Lifecycle Sequence

For a complete feature, the typical skill sequence is:

```
1.  interview-me: Extract what the user actually wants
2.  idea-refine: Refine vague ideas
3.  spec-driven-development: Define what we're building
4.  planning-and-task-breakdown: Break into verifiable chunks
5.  context-engineering: Load the right context
6.  source-driven-development: Verify against official docs
7.  incremental-implementation: Build slice by slice
8.  doubt-driven-development: Cross-examine non-trivial decisions in-flight
9.  test-driven-development: Prove each slice works
10. code-review-and-quality: Review before merge
11. code-simplification: Reduce unnecessary complexity while preserving behavior
12. git-workflow-and-versioning: Clean commit history
13. conventional-commits: Write or review Conventional Commits messages when used
14. documentation-and-adrs: Document decisions
15. deprecation-and-migration: Retire old systems and move users safely when needed
16. shipping-and-launch: Deploy safely
```

Not every task needs every skill. A bug fix might only need `debugging-and-error-recovery`, then `test-driven-development`, then `code-review-and-quality`.

## Quick Reference

| Phase  | Skill                        | One-Line Summary                                                                                     |
| ------ | ---------------------------- | ---------------------------------------------------------------------------------------------------- |
| Define | interview-me                 | Surface what the user actually wants before any plan, spec, or code exists                           |
| Define | idea-refine                  | Refine ideas through structured divergent and convergent thinking                                    |
| Define | spec-driven-development      | Requirements and acceptance criteria before code                                                     |
| Plan   | planning-and-task-breakdown  | Decompose into small, verifiable tasks                                                               |
| Plan   | review-implementation-plan   | Review a plan for gaps, risks, sequencing, dependencies, and validation readiness                    |
| Build  | incremental-implementation   | Thin vertical slices, test each before expanding                                                     |
| Build  | source-driven-development    | Verify against official docs before implementing                                                     |
| Build  | doubt-driven-development     | Adversarial fresh-context review of every non-trivial decision                                       |
| Build  | context-engineering          | Right context at the right time                                                                      |
| Build  | frontend-ui-engineering      | Production-quality UI with accessibility                                                             |
| Build  | api-and-interface-design     | Stable interfaces with clear contracts                                                               |
| Build  | hexagonal-vertical-slices    | Hexagonal architecture with business-owned vertical feature slices                                   |
| Verify | test-driven-development      | Failing test first, then make it pass                                                                |
| Verify | browser-runtime-verification | Real-browser verification of UI behavior, console output, network activity, and accessibility basics |
| Verify | run-local-quality-gate       | Discover and run local formatting, linting, static analysis, test, and build checks                  |
| Verify | debugging-and-error-recovery | Reproduce, localize, fix, and guard                                                                  |
| Review | add-observability            | Add useful logs, metrics, traces, profiling, alerts, or dashboards                                   |
| Review | code-review-and-quality      | Five-axis review with quality gates                                                                  |
| Review | code-simplification          | Preserve behavior while reducing unnecessary complexity                                              |
| Review | security-and-hardening       | OWASP prevention, input validation, least privilege                                                  |
| Review | performance-optimization     | Measure first, optimize only what matters                                                            |
| Ship   | git-workflow-and-versioning  | Atomic commits, clean history                                                                        |
| Ship   | conventional-commits         | Conventional Commits message syntax, semantics, and breaking-change notation                         |
| Ship   | ci-cd-and-automation         | Automated quality gates on every change                                                              |
| Ship   | deprecation-and-migration    | Remove old systems and migrate users safely                                                          |
| Ship   | documentation-and-adrs       | Document the why, not just the what                                                                  |
| Ship   | update-project-docs          | Keep project-facing documentation aligned with behavior, configuration, or workflow changes          |
| Ship   | write-adr                    | Record durable architectural decisions with context and consequences                                 |
| Ship   | shipping-and-launch          | Pre-launch checklist, monitoring, rollback plan                                                      |
| Skill  | author-agent-skill           | Create, update, or review Agent Skill directories and SKILL.md files                                 |
