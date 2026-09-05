# Plan: Skills Tool Version 1

## Status

- State: Planned.
- Derived from: `docs/specs/tools-skills-tool-spec.md`.
- Specification status: Accepted on September 5, 2026.
- Implementation status: Not started.

## Objective

Implement the accepted Version 1 `skills` orchestration tool as Fabrica's
canonical skill-loading path. It must activate trusted global and workspace
procedural instructions during a model tool loop without adding capabilities,
executing scripts, or exposing `@skill/...` resources.

## Scope Guardrails

### In Scope

- Canonical YAML-frontmatter parsing for `SKILL.md`.
- Migration of selected-context skill loading to that parser.
- Global/workspace registry providers and immutable run snapshots.
- Model-callable activation, trust evaluation, revision integrity, audit events,
  active-skill state, and compaction persistence.
- Deterministic 1,000-character catalog advertisement and bounded structured
  activation-content transport.

### Out of Scope

- Plugin or managed providers.
- `@skill/...` resource routing and workspace-tool contract changes.
- Skill-root command sandbox mounts.
- Automatic script execution, dynamic tool registration, installation, editing,
  or compatibility handling for heading-only skill files.

## Constraints and Design Decisions

- Preserve generic `ToolDefinition` and generic `result_text` limits.
- Return activated instructions as bounded `ToolTextContent`, never by silently
  truncating a generic result string.
- Keep filesystem I/O in adapters and expose application-safe DTOs and ports.
- Keep default tests synthetic, local, deterministic, and offline.
- Guarantee that activated bytes equal the snapshot's approved revision. Choose
  the simpler safe mechanism during implementation: retained validated bytes or
  safe reread-and-hash verification.
- Update this plan's progress and task checkboxes after every completed task or
  material sequencing change.

## Dependency Graph

```text
Canonical parser and definition DTOs
    ↓
Selected-context migration + global/workspace provider adapters
    ↓
Registry snapshots + trust and revision-integrity policy
    ↓
Activation + ActiveSkillSet
    ↓
Registered-tool transport
    ↓
Compaction integration + full validation
```

## Progress Tracking

- [ ] T1 Canonical skill definition and parser
- [ ] T2 Selected-context migration
- [ ] T3 Registry snapshots and provider adapters
- [ ] T4 Trust and revision-integrity contract
- [ ] T5 Activation and active-skill state
- [ ] T6 Model-facing tool and bounded transport
- [ ] T7 Compaction integration
- [ ] T8 Documentation and full quality gate
- [ ] C1 Parser migration review
- [ ] C2 Security and boundary review
- [ ] C3 Runtime integration readiness

## Ordered Tasks

### T1 — Canonical skill definition and parser

**Likely files:** `src/fabrica/features/agent_runtime/application/dtos/`,
`application/ports/`, `adapters/outbound/skill_markdown_file/`, and focused tests.

1. Define canonical skill-definition and validation DTOs plus an application port.
2. Replace heading-only validation with UTF-8, BOM, YAML-frontmatter, required
   name/description, non-empty body, kebab-case, directory/name, and size checks.
3. Compute exact-byte `sha256:` revisions and reject definitions whose serialized
   activation content cannot fit the structured-content bound.

**Acceptance and verification**

- [ ] T1.A Valid files produce canonical definitions and exact revisions.
- [ ] T1.B Invalid encoding, frontmatter, fields, names, directory matches, and
  size cases fail through application-safe errors.
- [ ] T1.C Heading-only files without frontmatter are rejected.
- [ ] T1.V Run focused parser/DTO tests and `uv run ruff format .` plus
  `uv run ruff check .`.

### T2 — Migrate selected-context loading

**Depends on:** T1

**Likely files:** selected-context use cases, `bootstrap/composition/skill_context.py`,
README examples, and selected-context tests.

1. Make explicit host-selected context consume the canonical definition loader.
2. Preserve existing context bounds and safe diagnostics while replacing the file
   format contract.
3. Update documentation that describes the heading-only requirement.

**Acceptance and verification**

- [ ] T2.A Selected context and activation share parser behavior.
- [ ] T2.B No compatibility fallback accepts a legacy heading-only file.
- [ ] T2.C Selected resources and policy-gated scripts retain their current,
  explicit non-model-callable boundaries.
- [ ] T2.V Run selected-context unit/integration tests and documentation review.

### T3 — Registry snapshots and provider adapters

**Depends on:** T1

**Likely files:** new registry DTOs, ports, use cases, filesystem provider adapters,
composition, and tests.

1. Define strict `global:<name>` and `workspace:<name>` IDs and immutable
   run-scoped registry snapshots.
2. Discover/validate configured global and workspace skills before a run.
3. Omit invalid/unavailable entries fail-closed from model-visible metadata.
4. Generate deterministic complete-entry catalog descriptions within 1,000 chars.

**Acceptance and verification**

- [ ] T3.A Snapshots remain stable despite later provider changes.
- [ ] T3.B Canonical and unique bare-name resolution work; ambiguity is explicit.
- [ ] T3.C Plugin and managed sources are unavailable in V1.
- [ ] T3.D Catalog ordering and capping are deterministic and bounded.
- [ ] T3.V Run provider/registry unit tests and global/workspace composition tests.

### T4 — Trust and revision integrity

**Depends on:** T3

1. Define decisions bound to workspace identity, canonical ID, source, revision,
   and run ID; implement allowlist and enabled-state checks.
2. Choose and document retained-bytes or safe-reread-and-hash integrity strategy.
3. Map denied and hidden states to stable errors without metadata disclosure.

**Acceptance and verification**

- [ ] T4.A Workspace approval cannot authorize another workspace, run, skill, or revision.
- [ ] T4.B Changed bytes cannot activate under a stale trusted revision.
- [ ] T4.V Run trust, allowlist, revision-integrity tests and `uv run ty check src tests`.

### T5 — Activation and ActiveSkillSet

**Depends on:** T3, T4

1. Implement resolution, policy checks, exact-definition loading, atomic active-set
   registration, idempotence, timeout, cancellation, and privacy-safe audit events.
2. Keep arguments as data separate from instructions.

**Acceptance and verification**

- [ ] T5.A Failed, cancelled, timed-out, or mismatched activation leaves state unchanged.
- [ ] T5.B Same ID/revision returns `already_active` without reinjection.
- [ ] T5.C Activation neither executes scripts nor changes tool permissions.
- [ ] T5.V Run activation, cancellation, timeout, and active-set unit tests.

### T6 — Model-facing tool and bounded transport

**Depends on:** T3, T5

1. Add the `skills` registered-tool adapter and generated snapshot catalog.
2. Map activation results to one bounded `ToolTextContent` JSON part rather than
   generic `result_text`.
3. Map input and domain errors to stable structured recoverable results.

**Acceptance and verification**

- [ ] T6.A Public input is exactly `skill` plus nullable `args`.
- [ ] T6.B Valid complete instructions reach the model without silent truncation.
- [ ] T6.C Disabled, denied, ambiguous, malformed, and missing cases are stable.
- [ ] T6.V Run registered-tool and tool-loop tests; assert catalog <= 1,000 chars.

### T7 — Compaction integration

**Depends on:** T5, T6

1. Persist ordered active skills with compacted run state.
2. Rehydrate each instruction once after system/runtime and user context but before
   ordinary retrieved data.
3. Fail closed with `ACTIVE_SKILL_CONTEXT_OVERFLOW` on insufficient or malformed
   required active state.

**Acceptance and verification**

- [ ] T7.A Compaction preserves instruction order and exact revisions.
- [ ] T7.B Missing/malformed active state cannot silently resume empty.
- [ ] T7.C Context overflow fails before the next model turn.
- [ ] T7.V Run focused multi-skill compaction integration tests.

### T8 — Documentation and quality gate

**Depends on:** T1-T7

1. Update README and specification status to match parser, sources, trust, and
   non-escalation behavior.
2. Remove claims of heading-only support or Version 1 resource routing.
3. Record implementation evidence in this plan.

**Acceptance and verification**

- [ ] T8.A Documentation matches the implemented public behavior.
- [ ] T8.B No docs claim V1 supports `@skill`, plugins/managed providers, or automatic scripts.
- [ ] T8.V Run `uv run ruff format .`.
- [ ] T8.V Run `uv run ruff check .`.
- [ ] T8.V Run `uv run ty check src tests`.
- [ ] T8.V Run `uv run lint-imports`.
- [ ] T8.V Run `uv run pytest`.

## Checkpoints

### C1 — Parser migration review

- [ ] C1 Parser behavior, selected-context migration, and documentation agree.
- [ ] C1 No heading-only compatibility path remains.

### C2 — Security and boundary review

- [ ] C2 Revision-integrity design is documented and tested.
- [ ] C2 Filesystem I/O remains adapter-owned.
- [ ] C2 Resource routing, scripts, and capability escalation remain out of scope.

### C3 — Runtime integration readiness

- [ ] C3 Catalog and activation results comply with existing generic tool limits.
- [ ] C3 Compaction and tool-loop behavior have focused integration coverage.
- [ ] C3 Full quality-gate evidence is recorded.

## Parallelization

- T1 precedes T2 and T3.
- T3 precedes T4 because trust binds snapshot identity and revision behavior.
- T5 and adapter scaffolding for T6 may overlap only after shared contracts are stable.
- T7 is sequential after active-state contracts are complete.
- Documentation work may begin after T1, but final validation waits for T7.

## Risks and Mitigations

| Risk | Mitigation |
| --- | --- |
| Existing transport limits truncate instructions. | Use `ToolTextContent`, measure serialized output before state commit, and reject oversize definitions. |
| Skill files change after approval. | Retain validated bytes or compare a safely reread SHA-256 before activation. |
| Parser migration breaks local skills. | Accepted breaking change; use clear validation errors and documentation updates. |
| Scope expands into resources or scripts. | Require a re-confirmed specification for any `@skill` or script-execution work. |
| Compaction loses instructions. | Persist ordered active state and fail closed on malformed/missing/overflowing state. |

## Completion Definition

This plan is complete only when T1-T8 and C1-C3 are checked, the accepted
specification remains accurate, and the full offline quality gate passes.
