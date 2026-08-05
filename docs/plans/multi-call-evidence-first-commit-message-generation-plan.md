# Implementation Plan: Multi-Call Evidence-First Commit Message Generation

## Overview

Replace the current one-shot `commit-message` preparation flow with a multi-call
developer-workflow orchestration:

```text
list staged files
  -> load one staged file diff at a time
  -> analyze each file in its own model call/session
  -> collect structured per-file evidence
  -> run one final synthesis call with the selected commit-message skill
  -> return a concise Conventional Commit recommendation
```

This plan supersedes the completed prompt-level plan. Completed temporary plans
are deleted from `docs/plans/`, so this file is the active implementation plan for
future evidence-first architecture work.

## Goal

Deliver an evidence-first commit-message workflow whose architecture enforces
per-file analysis before final Conventional Commit synthesis, rather than asking
one model call to reason over the entire staged diff.

## Deliverables

- Developer-workflow application DTOs for per-file evidence, evidence bundles,
  analysis commands/results, synthesis commands/results, and final workflow
  results.
- Developer-workflow application ports for:
  - per-file commit-message evidence analysis;
  - final commit-message synthesis.
- A developer-workflow orchestration use case that:
  - lists staged files;
  - loads each file's staged diff;
  - analyzes each file independently;
  - aggregates evidence deterministically;
  - synthesizes the final recommendation.
- Agent-runtime-backed outbound adapters for the new developer-workflow ports.
- Composition-root and CLI wiring that routes `fabrica commit-message` through
  the new workflow.
- Unit and integration tests proving ordering, boundaries, failure behavior, and
  output contract.
- README command documentation updates for the user-visible multi-call,
  evidence-first behavior.

## Success criteria

- The workflow uses `GitStagedChangesLoader.list_files()` before loading per-file
  diffs.
- The workflow calls `load_file_diff(path)` once for each staged file selected for
  analysis.
- The workflow invokes the per-file analyzer once per staged file and never asks
  that analyzer for a final commit message.
- The workflow invokes final synthesis only after all required per-file evidence
  has been collected.
- The final synthesizer receives structured evidence and selected skill context,
  not the full raw staged diff by default.
- No staged files, per-file diff load failures, per-file analysis failures, and
  synthesis failures are normalized into clear existing result/error patterns.
- The command remains read-only, staged-only, deterministic in default tests, and
  does not run `git commit` or write commit-message files.
- Focused tests and the full local quality gate pass before handoff.

## Constraints

- Do not mutate repository state.
- Do not fall back to unstaged changes.
- Do not expose raw staged diffs in diagnostics.
- Do not add parallel analysis in the first implementation unless explicitly
  approved after sequential behavior is working.
- Do not synthesize from partial evidence in the first implementation.
- Do not add JSON output, interactive evidence review, automatic commits, or
  commit-message file writing in this implementation.
- Preserve the existing terminal output labels `Summary:`, `Rationale:`, and
  `Commit message:` for v1 unless a later plan explicitly changes the CLI
  contract.
- Use strict structured model output for per-file evidence in v1, parsed and
  validated inside the outbound adapter before returning application DTOs.
- Bound v1 staged input to at most 25 staged files and bound serialized evidence
  passed to final synthesis to at most 50,000 characters. Exceeding either bound
  fails before the next model invocation with safe diagnostics.
- Keep developer-workflow language and orchestration inside the
  `developer_workflow` feature slice.
- Keep agent-runtime details behind ports/adapters where practical.

## Architecture decisions

### Developer-workflow owns the commit-message workflow

The multi-call behavior is no longer just an agent-runtime command-preparation
concern. The `developer_workflow` feature should own DTOs and ports expressed in
commit-message terms: staged file evidence, evidence bundles, analysis, and
synthesis.

### Agent runtime is an implementation detail

Adapters may use `LocalAgentRunCommand`, selected skill context loading, and the
existing runtime internally, but the core developer-workflow use case should not
be typed directly around one concrete agent-runtime use case.

### Sequential analysis first

Analyze staged files sequentially for the first implementation. This keeps
failure behavior, ordering, tests, and observability straightforward. Parallelism
can be added later behind the same ports after correctness is established.

### Fail on missing required evidence

If a staged file cannot be diffed or analyzed, stop before final synthesis. This
avoids producing overconfident commit messages from incomplete evidence.

### Developer-workflow owns result and failure language

The application use case should return developer-workflow-owned result DTOs or
raise developer-workflow-owned application errors. Composition and CLI adapters
may translate those results into agent-runtime `LocalAgentRunResult` values, but
the developer-workflow core should not expose agent-runtime status or observation
DTOs as its own contract.

### Preserve CLI output labels for v1

The final synthesizer should keep the existing terminal-friendly labels
`Summary:`, `Rationale:`, and `Commit message:` for the first multi-call
implementation. Evidence collection changes the architecture and prompt inputs;
it should not introduce a separate visible output-format migration unless that is
planned explicitly.

## Proposed project structure

```text
src/fabrica/features/developer_workflow/application/
├── dtos/
│   ├── commit_message.py
│   └── git_staged_changes.py
├── ports/
│   ├── commit_message.py
│   └── git_staged_changes.py
└── use_cases/
    └── generate_commit_message.py

src/fabrica/features/developer_workflow/adapters/outbound/
└── commit_message_agent_runtime/
    ├── adapter.py
    ├── prompts.py
    └── mappers.py
```

`generate_commit_message.py` is the required application orchestration use case.
Add separate analyzer or synthesizer use-case modules only if they own meaningful
application behavior beyond delegating to outbound ports. Exact file names may
change during implementation if a smaller cohesive module is clearer.

## Phase 1: Application DTOs and ports

### Task 1: Add commit-message DTOs

**Description:** Add typed application DTOs for staged file analysis and final
synthesis.

**Likely DTOs:**

- `AnalyzeStagedFileForCommitMessageCommand`
- `StagedFileCommitEvidence`
- `CommitMessageEvidenceBundle`
- `SynthesizeCommitMessageCommand`
- `CommitMessageRecommendation`
- `GenerateCommitMessageResult`

**Acceptance criteria:**

- [ ] DTOs are immutable where practical.
- [ ] DTOs use application/domain terms, not transport schemas.
- [ ] DTOs reuse existing staged-git DTO concepts such as `GitStagedFile`,
      `GitStagedFileList`, `GitStagedFileStatus`, and `GitStagedDiff` where
      practical instead of duplicating staged path/status models.
- [ ] Evidence contains staged path, status, summary, category, and optional impact
      fields.
- [ ] Evidence captures `public_contract_impact`, `validation_relevance`,
      `migration_concern`, and `breaking_risk` as explicit structured fields.
- [ ] Final workflow results and failures are represented with
      developer-workflow-owned DTOs or errors, not agent-runtime result DTOs.
- [ ] DTO validation rejects empty required text and empty evidence bundles.
- [ ] DTO validation rejects evidence bundles above the v1 serialized evidence
      bound of 50,000 characters.

**Verify:**

```bash
uv run pytest tests/unit/features/developer_workflow/application/test_commit_message_dtos.py
```

### Task 2: Add analyzer and synthesizer ports

**Description:** Define developer-workflow-owned ports for per-file evidence
analysis and final synthesis.

**Acceptance criteria:**

- [ ] Ports are narrow `Protocol`s in the developer-workflow application layer.
- [ ] Port signatures use developer-workflow DTOs.
- [ ] Ports do not expose agent-runtime DTOs, HTTP schemas, or framework types.

**Verify:**

```bash
uv run ty check src/fabrica/features/developer_workflow/application
```

## Phase 2: Orchestration use case

### Task 3: Add `GenerateCommitMessage` use case

**Description:** Implement the application orchestration that lists staged files,
loads each file diff, runs per-file analysis, and calls final synthesis.

**Acceptance criteria:**

- [ ] Calls `list_files()` before per-file diff loading.
- [ ] Calls `load_file_diff(path)` for each staged file.
- [ ] Calls analyzer once per staged file.
- [ ] Preserves staged file order in the evidence bundle.
- [ ] Calls synthesizer once after all evidence is collected.
- [ ] Fails before per-file analysis when more than 25 staged files are present.
- [ ] Fails before final synthesis when serialized evidence exceeds 50,000
      characters.
- [ ] Stops before synthesis if staged discovery, diff loading, or analysis fails.

**Verify:**

```bash
uv run pytest tests/unit/features/developer_workflow/application/test_generate_commit_message.py
```

### Task 4: Normalize failure behavior

**Description:** Decide and implement application-level error/result behavior for
staged-git failures, analysis failures, and synthesis failures.

**Acceptance criteria:**

- [ ] No staged files fail before model invocation.
- [ ] Too many staged files fail before per-file model invocation.
- [ ] Per-file diff load failure reports which staged file failed without exposing
      raw diff content.
- [ ] Per-file analyzer failure stops final synthesis.
- [ ] Invalid or unparsable structured per-file analyzer output stops final
      synthesis and reports a safe application failure.
- [ ] Oversized serialized evidence stops final synthesis.
- [ ] Final synthesis failure maps into developer-workflow-owned failure/result
      language before composition maps it to the existing CLI/result pattern.

**Verify:**

```bash
uv run pytest tests/unit/features/developer_workflow/application/test_generate_commit_message.py
```

## Phase 3: Agent-runtime-backed adapters

### Task 5: Add per-file analyzer adapter

**Description:** Implement an outbound adapter that maps one staged file diff into
an agent-runtime call and maps the response into `StagedFileCommitEvidence`.

**Acceptance criteria:**

- [ ] The per-file prompt asks for factual file evidence only.
- [ ] The per-file prompt explicitly forbids final commit-message synthesis.
- [ ] The per-file prompt requests strict structured output with required fields:
      `summary`, `category`, `public_contract_impact`, `validation_relevance`,
      `migration_concern`, and `breaking_risk`.
- [ ] The adapter owns parsing and validation of structured model output.
- [ ] Missing, empty, invalid, or unparsable required fields become safe analyzer
      failures before final synthesis.
- [ ] Raw file diff is scoped to the per-file call.
- [ ] Adapter output is normalized into application DTOs.

**Verify:**

```bash
uv run pytest tests/unit/features/developer_workflow/adapters/outbound/test_commit_message_agent_runtime.py
```

### Task 6: Add final synthesizer adapter

**Description:** Implement an outbound adapter that maps the evidence bundle plus
selected skill context into one final agent-runtime call.

**Acceptance criteria:**

- [ ] Final prompt receives structured evidence, not the full raw staged diff by
      default.
- [ ] Final prompt applies the selected commit-message skill after evidence
      grouping.
- [ ] Final prompt preserves the `Summary:`, `Rationale:`, and `Commit message:`
      output labels.
- [ ] Final output remains terminal-friendly and copy-oriented.

**Verify:**

```bash
uv run pytest tests/unit/features/developer_workflow/adapters/outbound/test_commit_message_agent_runtime.py
```

## Phase 4: Composition and CLI migration

### Task 7: Wire the new workflow in the composition root

**Description:** Update `src/fabrica/bootstrap/local_agent_runtime.py` so the
commit-message workflow uses the new developer-workflow orchestration.

**Acceptance criteria:**

- [ ] Existing CLI command options still work unless explicitly changed.
- [ ] Default skill remains `conventional-commits`.
- [ ] Model and reasoning-effort overrides still reach model-backed adapters.
- [ ] Git access remains read-only and staged-only.

**Verify:**

```bash
uv run pytest tests/integration/features/developer_workflow/test_commit_message_composition.py
```

### Task 8: Remove or replace one-shot preparation path

**Description:** Because the project is still in raw development, remove stale
one-shot code instead of preserving compatibility shims if the new workflow fully
replaces it.

**Acceptance criteria:**

- [ ] `PrepareCommitMessageRun` is deleted or clearly no longer used.
- [ ] Tests no longer assert one full staged diff context block as the core
      architecture.
- [ ] Exports remain clear and focused on the new workflow.

**Verify:**

```bash
rg "PrepareCommitMessageRun|prepare_commit_message_run"
uv run pytest tests/unit/features/developer_workflow tests/integration/features/developer_workflow
```

## Phase 5: Documentation and quality gate

### Task 9: Update user-facing docs

**Description:** Update README text for the command's visible multi-call behavior,
failure bounds, and preserved output contract.

**Acceptance criteria:**

- [ ] README describes the staged-only, read-only, evidence-first behavior.
- [ ] README notes that v1 may make one per-file model call plus one final
      synthesis call and may fail closed when staged file or evidence bounds are
      exceeded.
- [ ] README does not promise verbose per-file evidence output by default.

### Task 10: Run quality gate

**Acceptance criteria:**

- [ ] Formatting passes.
- [ ] Lint passes.
- [ ] Type checking passes.
- [ ] Tests pass.

**Verify:**

```bash
uv run ruff format .
uv run ruff check .
uv run ty check src tests
uv run pytest
```

## Risks and mitigations

| Risk | Impact | Mitigation |
| --- | --- | --- |
| More model calls increase latency | Medium | Start sequential for correctness; add measurement before optimizing or parallelizing. |
| Model returns unstructured per-file evidence | Medium | Prefer structured output contract or adapter-owned parser with strict validation. |
| Evidence bundle becomes too large | Medium | Keep per-file evidence compact; enforce the v1 limits of 25 staged files and 50,000 serialized evidence characters before later model invocations. |
| Partial analysis failure blocks useful output | Medium | Fail closed for v1; revisit partial synthesis as an explicit future feature. |
| Developer-workflow depends too directly on agent-runtime internals | High | Define developer-workflow-owned ports and keep agent-runtime mappings in adapters/composition. |

## Open questions

- Should strict structured per-file evidence use literal JSON, XML-style tags, or
  another parser-friendly format for the first adapter implementation?
- Should manual smoke verification use a fake runtime, live Codex, or both?

## Implementation readiness checklist

- [x] Target spec updated to require multi-call evidence-first orchestration.
- [x] Existing prompt-level plan identified as superseded for future architecture
      work.
- [x] Open questions resolved or accepted as implementation assumptions for
      structured evidence, v1 bounds, result ownership, and output labels.
- [x] Plan reviewed before coding.
