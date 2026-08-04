---
name: code-review-and-quality
description: Review code, tests, documentation, and configuration across correctness, readability, architecture, security, performance, maintainability, and verification before merging or handing off a change.
metadata:
  version: "1.1.3"
  dependencies:
    tools: []
    skills:
      - name: security-and-hardening
        purpose: Review security-sensitive changes involving untrusted input, secrets, permissions, or attack surface.
        required: false
      - name: performance-optimization
        purpose: Review performance-sensitive changes that need measurement, profiling, or scalability analysis.
        required: false
      - name: code-simplification
        purpose: Reduce unnecessary complexity found during review without changing behavior.
        required: false
---

# Code Review and Quality

Use this skill when reviewing a change written by yourself, another agent, or a
human. The goal is to decide whether the change improves the project, identify
issues with clear severity, and verify that the author’s evidence matches the
risk of the change.

Approve when the change improves overall code health and satisfies the project’s
requirements and conventions. Do not block on personal preference, but do block
on correctness, safety, maintainability, or verification gaps.

## When to use this skill

Use this skill when:

- reviewing a proposed change before merge or handoff
- reviewing generated code or agent-written code
- checking a bug fix and its regression coverage
- reviewing refactoring, migration, dependency, configuration, or documentation
  changes
- deciding whether a large change should be split

## Review axes

Use the local checklists for focused review prompts. Escalate to related skills
when review findings need deeper follow-up work:

- Use `security-and-hardening` when the review identifies security-sensitive
  design, implementation, or remediation work that needs deeper analysis than the
  checklist.
- Use `performance-optimization` when the review identifies a suspected
  bottleneck, regression, or performance requirement that needs
  measurement-driven diagnosis.
- Use `code-simplification` when the review identifies unnecessary complexity
  that should be reduced while preserving behavior.

### 1. Correctness

Check whether the change does what it claims to do.

- Does it match the task, specification, or acceptance criteria?
- Are edge cases handled, such as empty, missing, boundary, repeated, malformed,
  or concurrent inputs?
- Are error paths handled, not only the happy path?
- Do tests or examples cover the intended behavior?
- Are there race conditions, ordering issues, state inconsistencies, or migration
  hazards?

### 2. Readability and simplicity

Check whether a future maintainer can understand the change without the author
explaining it.

- Are names descriptive and consistent with local conventions?
- Is control flow straightforward?
- Is related behavior grouped behind clear module, component, or workflow
  boundaries?
- Are comments used for non-obvious intent rather than obvious mechanics?
- Are abstractions earning their complexity?
- Is dead code, stale compatibility glue, or temporary scaffolding left behind?

### 3. Architecture and maintainability

Check whether the change fits the system design.

- Does it preserve established boundaries and dependency direction?
- Does it introduce a new pattern, and is that pattern justified?
- Is duplication acceptable, or should shared behavior be extracted?
- Are public interfaces compatible or covered by a migration plan?
- Does the change remain testable and observable?
- Are configuration, secrets, generated files, and documentation kept in sync?

### 4. Security

Use `references/security-checklist.md` for detailed security prompts when the
change touches trust boundaries, credentials, identity, input handling,
dependencies, storage, networking, or deployment configuration.

At minimum, check:

- untrusted input is validated, encoded, or rejected at the right boundary
- authorization is enforced where needed
- secrets are not committed, logged, returned, or exposed in artifacts
- external data is treated as untrusted before use in logic or rendering
- dependency or runtime changes do not introduce known vulnerable versions
- errors do not leak sensitive internals

### 5. Performance

Use `references/performance-checklist.md` for detailed performance prompts when
the change affects hot paths, data volume, rendering, storage access, background
work, startup, caching, or artifacts.

At minimum, check:

- repeated work, network calls, storage reads, or computations are bounded
- loops, joins, queries, and data transformations scale with expected volume
- list or stream operations have limits, pagination, batching, or backpressure
- hot paths avoid unnecessary blocking work
- caches have clear invalidation, size bounds, and fallback behavior
- performance-sensitive claims include measurement or a stated rationale

### 6. Verification

Check whether the evidence matches the risk.

- Which tests, builds, checks, or manual verification were run?
- Would the verification catch a realistic regression?
- Are screenshots, logs, benchmark notes, or migration dry runs included when
  relevant?
- Were failures investigated rather than ignored?
- Is any skipped validation explicitly documented with a reason?

## Steps

### 1. Understand the intent

Before reviewing details, identify:

- what problem the change solves
- what behavior should change
- what should stay unchanged
- what constraints or project conventions apply
- what files, modules, interfaces, data, or workflows are affected

If the intent is unclear, ask for clarification before reviewing style details.

### 2. Review tests and verification first

Tests and validation reveal what the author believes matters.

Check:

- tests exist when behavior changes
- tests focus on observable behavior rather than implementation details
- important edge cases and failure paths are covered
- test names describe the behavior being protected
- the reported validation commands are relevant and recent

### 3. Review the implementation across the axes

Walk through changed files and assess correctness, readability, architecture,
security, performance, and verification. Prefer concrete findings over vague
opinions.

Good review comments include:

- what is wrong or risky
- why it matters
- where it occurs
- a suggested fix or decision path when useful
- severity or whether the comment is optional

### 4. Categorize findings

Label feedback so the author knows what must change.

Use simple severity labels such as:

- `Critical`: blocks merge because it can cause security exposure, data loss,
  broken behavior, or severe operational risk
- `Required`: must be addressed before merge or handoff
- `Suggestion`: likely improvement, but not required
- `Nit`: minor style or wording issue the author may ignore
- `FYI`: informational context only

Avoid ambiguous comments that make optional preferences look mandatory.

### 5. Check change size and split risk

Small focused changes are easier to review and safer to deploy.

Ask for a split when:

- the change combines unrelated behavior
- refactoring and feature work are mixed in ways that obscure behavior
- multiple reviewers or domains are needed
- generated or mechanical changes hide hand-written behavior changes
- the diff is too large to review confidently

Accept large changes only when the review strategy is clear, such as complete
file deletion, generated output, or a mechanical refactor with representative
verification.

### 6. Review dependency changes

Before accepting a new dependency or runtime requirement, check:

- whether the existing stack can solve the problem
- maintenance activity and community health
- license compatibility
- security advisories or known vulnerable versions
- size, startup, deployment, or operational impact
- whether the dependency becomes part of a public or compatibility-sensitive
  surface

Prefer standard library, platform features, and existing project utilities when
they solve the problem clearly.

### 7. Check dead code and cleanup

After refactoring or migration, identify unreachable or unused code, stale docs,
obsolete tests, deprecated configuration, and no-op compatibility shims.

Do not delete uncertain code silently. List what appears unused and ask for
confirmation or evidence when ownership is unclear.

Example:

```text
Potential dead code:
- `<old_helper>` appears replaced by `<new_helper>`
- `<legacy_config_key>` has no remaining references

Should these be removed in this change or tracked as follow-up cleanup?
```

### 8. Decide and document the verdict

End the review with a clear outcome:

- approve when the change is safe enough and improves the project
- request changes when required issues remain
- defer judgment when context or verification is missing

Include the validation evidence you considered and any accepted risks.

## Review checklist

```md
## Review: <change title>

### Context

- [ ] I understand what this change does and why
- [ ] Affected boundaries, workflows, or interfaces are clear

### Correctness

- [ ] Change matches requirements
- [ ] Edge cases and error paths are handled
- [ ] Tests or examples cover changed behavior

### Readability and architecture

- [ ] Names and structure follow project conventions
- [ ] No unnecessary complexity or coupling
- [ ] Public interfaces remain compatible or have a migration plan

### Security and performance

- [ ] Trust boundaries and secrets are handled safely
- [ ] External data is validated before use
- [ ] Hot paths and data-volume risks are bounded

### Verification

- [ ] Relevant validation was run
- [ ] Skipped validation is explained
- [ ] Manual evidence is included when needed

### Verdict

- [ ] Approve
- [ ] Request changes
- [ ] Need more context
```

## See also

- For focused security review guidance, see `references/security-checklist.md`.
- For focused performance review guidance, see
  `references/performance-checklist.md`.

## Red flags

- approval without evidence of review
- review that only checks whether tests passed
- generated or agent-written code accepted without extra scrutiny
- security-sensitive change without security-focused review
- large change that cannot be reviewed confidently
- missing regression coverage for a bug fix
- optional preferences presented as blockers
- deferred cleanup accepted without ownership or follow-up
- skipped validation omitted from the handoff

## Output checklist

- review intent and affected boundaries are clear
- tests and verification were reviewed before implementation details
- findings are concrete and severity-labeled
- security and performance risks were considered where relevant
- dependency and dead-code concerns were checked
- final verdict is explicit
- accepted risks and skipped validation are documented
