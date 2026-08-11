# Plan: CLI Architecture Remediation

This plan records the follow-up work from the CLI architecture audit performed
with the hexagonal vertical-slices review checklist. It is an implementation
plan, not a record of completed changes.

## Goal

Keep the Fabrica CLI clearly aligned with hexagonal architecture and vertical
feature slices while preserving current user-visible CLI behavior.

Target dependency direction:

```text
entry point / product CLI shell
  -> feature-owned inbound CLI adapter
  -> application inbound port or use case
  -> outbound ports
  -> outbound adapters wired only by bootstrap/composition
```

## Deliverables

- Smaller, capability-focused bootstrap composition modules.
- Product CLI model-evidence types imported from the shared kernel rather than a
  feature-slice re-export.
- Clearer separation between parsed CLI use-case input and CLI composition
  options.
- Sync-to-async compatibility wrappers removed or relocated out of application
  use-case modules.
- Explicit ownership decision for interactive commit confirmation.
- Focused regression tests around CLI parsing, runners, confirmation behavior,
  and bootstrap wiring.
- Local quality-gate evidence before handoff.

## Constraints

- Keep `argparse`, terminal streams, prompts, and process exit-code mapping in
  inbound CLI adapters.
- Keep concrete adapter construction in bootstrap/composition.
- Keep application ports expressed in application or shared-kernel DTOs, never CLI
  parser models or framework/process types.
- Do not introduce compatibility shims solely for old import paths; this project
  is still in raw development and prioritizes clarity.

## Phase 1: Establish a behavior baseline

Run focused tests before refactoring so behavior changes are intentional.

Suggested checks:

```bash
uv run pytest tests/unit/adapters/inbound/cli tests/unit/test_bootstrap_api.py
uv run pytest tests/integration/adapters/inbound/cli
uv run pytest tests/integration/features/agent_runtime tests/integration/features/developer_workflow
```

Success criteria:

- Current pass/fail status is known.
- Any pre-existing failure is documented before structural changes begin.

## Phase 2: Fix shared-kernel model-evidence ownership

Update `src/fabrica/bootstrap/cli.py` so product CLI evidence protocols use the
actual shared-kernel owner:

```python
from fabrica.shared_kernel.model_usage import ModelCostEvidence, ModelUsageEvidence
```

Avoid importing these types through
`fabrica.features.agent_runtime.application.dtos` in feature-neutral CLI code.

Success criteria:

- Product CLI evidence contracts point directly to `shared_kernel`.
- No behavior changes.
- Focused CLI/bootstrap tests still pass.

## Phase 3: Split bootstrap composition by capability

Replace the current catch-all `src/fabrica/bootstrap/composition.py` with a
package of focused modules:

```text
src/fabrica/bootstrap/composition/
  __init__.py
  codex_runtime.py
  developer_workflow.py
  skill_context.py
  skill_scripts.py
  tool_loop.py
```

Suggested ownership:

- `skill_context.py`: skill markdown/resource context loaders and command
  augmentation options.
- `skill_scripts.py`: script policy/evaluation/execution composition and the
  deny-by-default approval lookup.
- `tool_loop.py`: registered tool-loop and model-driven selected-skill runtime
  composition.
- `codex_runtime.py`: Codex-backed and PydanticAI-shaped local runtime factories.
- `developer_workflow.py`: commit-message workflow composition, staged git tool
  composition, and pre-commit tool composition.

Keep `composition/__init__.py` as the curated composition API used by
`src/fabrica/bootstrap/__init__.py` and existing bootstrap contribution modules.

Success criteria:

- No 900-line bootstrap god module remains.
- Concrete adapters are still wired only from bootstrap/composition.
- Feature application modules do not import bootstrap.
- Tests importing bootstrap composition APIs are updated intentionally.

## Phase 4: Separate CLI command input from composition options

Feature CLI command models currently contain both application input and
composition-only flags such as model names, reasoning effort, skill roots, and
script approval metadata. Make this ownership explicit.

### Developer workflow

Target files:

- `src/fabrica/features/developer_workflow/adapters/inbound/cli/command_models.py`
- `src/fabrica/features/developer_workflow/adapters/inbound/cli/registration.py`
- `src/fabrica/features/developer_workflow/adapters/inbound/cli/runner.py`
- `src/fabrica/bootstrap/cli_contributions/developer_workflow.py`

Proposed shape:

```python
@dataclass(frozen=True, slots=True)
class CliCommitMessageCommand:
    skill_id: str


@dataclass(frozen=True, slots=True)
class CliCommitCommand:
    skill_id: str


@dataclass(frozen=True, slots=True)
class CliDeveloperWorkflowCompositionOptions:
    model: str | None
    reasoning_effort: str | None
    skill_roots: tuple[Path, ...]
```

### Agent runtime

Target files:

- `src/fabrica/features/agent_runtime/adapters/inbound/cli/command_models.py`
- `src/fabrica/features/agent_runtime/adapters/inbound/cli/registration.py`
- `src/fabrica/bootstrap/cli_contributions/agent_runtime.py`

Proposed supporting DTOs:

```python
@dataclass(frozen=True, slots=True)
class CliSkillRootOptions:
    skill_roots: tuple[Path, ...]


@dataclass(frozen=True, slots=True)
class CliScriptApprovalOptions:
    script_type: SkillScriptType
    suffix: str
    byte_size: int
    content_digest: str
```

Success criteria:

- Feature CLI runners map only use-case input into application DTOs.
- Bootstrap contribution factories consume explicit composition options.
- Application DTOs remain free of CLI and composition concerns.
- Existing CLI flags remain behaviorally equivalent.

## Phase 5: Clarify commit confirmation ownership

Use the current design unless a second inbound adapter needs shared confirmation
policy: terminal confirmation is CLI UX, and the application commit workflow
expects external approval before `commit(...)` is called.

Actions:

- Keep prompt/readline behavior in
  `src/fabrica/features/developer_workflow/adapters/inbound/cli/runner.py`.
- Document in the relevant port/use-case docstrings that
  `ConfirmedCommitWorkflowRunner.commit(...)` requires external approval.
- Add or update tests for:
  - empty or `n` response does not call `commit(...)`;
  - `y` and `yes` call `commit(...)`;
  - `KeyboardInterrupt` maps to `DeveloperWorkflowStatus.SAFETY_DENIED`.

Success criteria:

- CLI-specific terminal interaction stays out of application code.
- Approval expectations are explicit and tested.

## Phase 6: Remove or relocate sync-to-async compatibility wrappers

Inspect usages of these classes in
`src/fabrica/features/developer_workflow/application/use_cases/commit_workflow.py`:

- `SyncGitStagedChangesLoaderAdapter`
- `SyncStagedFileCommitMessageAnalyzerAdapter`
- `SyncCommitMessageSynthesizerAdapter`

If unused, delete them. If still needed, move them to an adapter-owned module such
as:

```text
src/fabrica/features/developer_workflow/adapters/outbound/async_compat.py
```

Success criteria:

- Application use-case modules contain orchestration and application contracts,
  not concrete compatibility adapters.
- Moved wrappers depend inward on application DTOs and ports.
- Imports and tests are updated.

## Phase 7: Optional argparse type cleanup

The product CLI contribution contract currently uses the private argparse type
`argparse._SubParsersAction`. This is low priority but can be replaced with a
small behavior protocol if typing friction grows.

Success criteria:

- No private argparse type suppression is needed.
- Feature command registration remains simple.

## Phase 8: Final validation

Run focused tests first, then the full local quality gate:

```bash
uv run ruff format .
uv run ruff check .
uv run ty check .
uv run pytest
```

Success criteria:

- Formatting, linting, type checking, and tests pass.
- No domain/application code imports `argparse`, terminal streams, bootstrap, or
  concrete infrastructure.
- Concrete dependency selection remains in bootstrap/composition.
- Handoff notes list changed files, architectural decisions, and validation
  evidence.
