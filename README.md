# Fabrica

Fabrica is a Python application scaffold for local agent runtime experiments, starting from the idea of a subscription-backed Codex transport while keeping volatile integrations isolated behind hexagonal boundaries.

## Development setup

Install dependencies with `uv`:

```bash
uv sync --group dev
```

## Quality checks

Run the local quality gate before handing off changes:

```bash
uv run ruff format .
uv run ruff check .
uv run ty check src tests
uv run lint-imports
uv run pytest
```

The default test suite is deterministic and offline. It does not read real Codex
credentials and does not call the live Codex backend. Each default `uv run pytest` run
also writes a self-contained results report to `.reports/pytest/report.html` and a
coverage HTML report to `.reports/coverage/index.html`. These local artifacts are
ignored by Git.

## Interactive `ask_question` tool composition

Hosts can opt in to the live `ask_question` tool with
`create_interactive_tool_loop_runtime()`. The factory requires a host-owned
`InteractionTransport` that publishes structured questions. It does not provide
a terminal, web, VS Code, or remote-client transport itself.

```python
import asyncio

from fabrica.bootstrap import create_interactive_tool_loop_runtime
from fabrica.features.agent_runtime.application.dtos import LocalAgentRunCommand
from fabrica.features.user_interaction.application.dtos import AnswerSubmission, InteractionPublication


class HostTransport:
    async def publish(self, publication: InteractionPublication) -> None:
        print(publication.question.question)
        print(publication.question.options)


runtime = create_interactive_tool_loop_runtime(model=model, transport=HostTransport())
run = runtime.start_run()
task = asyncio.create_task(run.run(LocalAgentRunCommand(prompt="Choose a database")))

# The host obtains the published question ID from its transport and submits the
# user's non-empty free-text answer through the same run object.
await run.submit_answer(AnswerSubmission(question_id, "PostgreSQL", selected_option=0))
result = await task
```

Each `start_run()` creates an opaque owner that authorizes its host answer and
cancellation methods. `ask_question` accepts one focused question with 2–5
unique suggestions, blocks the tool loop until an answer or cancellation, and
returns a structured `answered` or `cancelled` result to the next model turn.
Suggested options do not constrain a user's non-empty free-text answer.

The ordinary `create_tool_loop_runtime()` factory remains headless and does not
expose `ask_question`. Hosts must not fabricate an answer or select option zero
when interaction is unavailable. Use this tool only for material missing user
information—not tool permission, destructive-action approval, or plan-execution
approval. See [`docs/specs/tools-ask-question-tool-spec.md`](docs/specs/tools-ask-question-tool-spec.md)
for the accepted Version 1 contract and its intentional limits: no durable
recovery, expiry, multi-select, attachments, or concrete UI transport.

## Production workspace-editing composition

Hosts can compose the model-facing `apply_patch` tool for a workspace through
`create_production_workspace_editing_composition()`. The factory performs
actual-workspace capability verification and durable startup recovery before it
exposes mutation. Production mutation requires a host approval callback; every
patch is planned and approved before visible filesystem effects begin.

```python
from pathlib import Path

from fabrica.bootstrap import (
    ProductionWorkspaceEditingOptions,
    create_production_workspace_editing_composition,
)
from fabrica.features.workspace_editing.adapters.outbound.authorization import PatchApprovalDecision


async def approve_patch(plan):
    return PatchApprovalDecision(approved=True, plan_digest=plan.plan_digest)


composition = await create_production_workspace_editing_composition(
    Path("/path/to/workspace"),
    options=ProductionWorkspaceEditingOptions(approval_callback=approve_patch),
    read_only_tools=(),
)
```

Capability evidence is specific to the actual workspace; platform or filesystem
names alone never enable mutation. Apple Silicon macOS is the primary v1 release
target. Linux support is capability-gated and may remain unavailable for an
unsupported filesystem/backend combination. In either case, the factory preserves
the supplied read-only tools and omits `apply_patch` when mutation cannot safely
start. Inspect `composition.mutation_gate.error` for structured
`UNSUPPORTED_FILESYSTEM_GUARANTEE` evidence after a failed capability proof, or
`RECOVERY_REQUIRED` evidence when an interrupted mutation journal needs operator
resolution. See [`docs/specs/tools-apply-patch-tool-spec.md`](docs/specs/tools-apply-patch-tool-spec.md)
for the accepted patch, recovery, and safety contract.

## Public web-content tool composition

Hosts can explicitly add the read-only `fetch_web_content` tool to a tool-loop
runtime. The factory requires host-owned enablement, request-header, DNS, HTTP
client, and limit policy; construction does not resolve DNS or construct an HTTP
client. Set `public_web_enabled=False` to return ordered `PUBLIC_WEB_DISABLED`
results without network activity.

```python
import httpx

from fabrica.bootstrap import (
    FetchWebContentToolOptions,
    create_fetch_web_content_registered_tool_adapter,
    create_tool_loop_runtime,
)
from fabrica.features.agent_runtime.application.dtos import ToolLoopLimits
from fabrica.features.web_content_fetching.adapters.outbound.network_policy import AsyncioPublicDnsResolver
from fabrica.features.web_content_fetching.application.dtos import FetchWebContentLimits

fetch_web_content_tool = create_fetch_web_content_registered_tool_adapter(
    options=FetchWebContentToolOptions(
        public_web_enabled=True,
        headers={"User-Agent": "FabricaAgent/1.0", "Accept": "text/html,application/json,text/plain"},
        resolver=AsyncioPublicDnsResolver(),
        client_factory=lambda: httpx.AsyncClient(follow_redirects=False),
        limits=FetchWebContentLimits(),
    )
)
runtime = create_tool_loop_runtime(
    model=model,
    tools=(fetch_web_content_tool,),
    limits=ToolLoopLimits(),
)
```

The model-facing schema accepts only `{"requests": [{"url": "...", "max_chars": ...}]}`:
one to eight known **public HTTPS** URLs and optional bounded output lengths. It
does not accept methods, headers, cookies, authentication, bodies, proxies, TLS
options, browser automation, or web search. Each returned item is marked
`trust: "untrusted_web_content"`; treat fetched text as reference material, not
agent instructions.

The tool validates the URL, resolves and checks every destination address, and
revalidates every manual redirect before retrieving bounded textual content. It
does not provide connection-level DNS address pinning or complete DNS-rebinding
protection, and it does not support binary documents or JavaScript-rendered
pages. See [`docs/specs/tools-fetch-web-content-tool-spec.md`](docs/specs/tools-fetch-web-content-tool-spec.md)
for the accepted contract, limits, and deferred hardening.

## Workspace file-reading tool composition

Hosts can explicitly add the read-only `read_files` tool to a tool-loop runtime.
The factory requires the workspace root plus host-owned authorization and model
image-capability policy; construction does not inspect the workspace, start
helper processes, or contact a model provider.

```python
from pathlib import Path

from fabrica.bootstrap import create_read_files_registered_tool_adapter, create_tool_loop_runtime
from fabrica.features.agent_runtime.application.dtos import ToolLoopLimits

read_files_tool = create_read_files_registered_tool_adapter(
    Path("/path/to/workspace"),
    external_read_authorized=True,
    image_input_supported=False,
)
runtime = create_tool_loop_runtime(
    model=model,
    tools=(read_files_tool,),
    limits=ToolLoopLimits(),
)
```

The registered tool accepts the canonical `{ "files": [...] }` request shape
with workspace-relative paths and optional inclusive one-based `start_line` and
`end_line` bounds. It preserves batch request order, returns structured
per-file outcomes, and supports UTF-8/UTF-8-BOM text plus verified PNG, JPEG,
GIF, and WebP images when `image_input_supported=True`. Reads are bounded,
read-only, restricted to the configured workspace, and can be truncated or
paged; consult [`docs/specs/tools-read-files-tool-spec.md`](docs/specs/tools-read-files-tool-spec.md)
for the complete accepted contract and limits.

## Workspace code-search tool composition

Hosts can explicitly add the read-only `search_codebase` tool to a tool-loop
runtime. Construction requires only the workspace root; it does not inspect the
workspace or start a subprocess until the model invokes the tool.

```python
from pathlib import Path

from fabrica.bootstrap import (
    create_read_files_registered_tool_adapter,
    create_search_codebase_registered_tool_adapter,
    create_tool_loop_runtime,
)
from fabrica.features.agent_runtime.application.dtos import ToolLoopLimits

workspace_root = Path("/path/to/workspace")
search_codebase_tool = create_search_codebase_registered_tool_adapter(workspace_root)
read_files_tool = create_read_files_registered_tool_adapter(
    workspace_root,
    external_read_authorized=True,
    image_input_supported=False,
)
runtime = create_tool_loop_runtime(
    model=model,
    tools=(search_codebase_tool, read_files_tool),
    limits=ToolLoopLimits(),
)
```

## Workspace command-execution tool composition

Hosts can explicitly add the `run_commands` tool to a tool-loop runtime. The
factory requires host-owned environment, permission, approval, and sandbox policy
dependencies; it does not supply permissive defaults. On macOS and Linux it uses
the built-in POSIX process-group supervisor. Other platforms must provide a
platform-specific `CommandSupervisor` explicitly.

```python
from pathlib import Path

from fabrica.bootstrap import (
    RunCommandsToolOptions,
    create_run_commands_registered_tool_adapter,
    create_tool_loop_runtime,
)
from fabrica.features.agent_runtime.application.dtos import ToolLoopLimits

run_commands_tool = create_run_commands_registered_tool_adapter(
    Path("/path/to/workspace"),
    options=RunCommandsToolOptions(
        shell_executable="/bin/sh",
        environment_builder=host_environment_builder,
        permission_evaluator=host_permission_evaluator,
        approval_resolver=host_approval_resolver,
        sandbox_preflight=host_sandbox_preflight,
    ),
)
runtime = create_tool_loop_runtime(
    model=model,
    tools=(run_commands_tool,),
    limits=ToolLoopLimits(),
)
```

The tool prefers direct `argv` invocation. It permits `shell` only through the
single host-configured shell executable, and both modes use the same workspace,
environment, permission, approval, sandbox, deadline, cancellation, and output
bounds. Construction is inert: workspace resolution, policy evaluation, and
process execution begin only if the model invokes the tool.

Use `search_codebase` first to locate matching workspace-relative files and
one-based line locations, then pass only the relevant paths and line ranges to
`read_files` for bounded source context. Search never discovers a host `rg`
installation. Linux `x86_64` and macOS Apple Silicon use checksum-verified Fabrica
package-data native `rg` executables with no container runtime or OCI-image setup.
Direct native search on both platforms uses best-effort pre-launch workspace
containment: it rejects ordinary path and symlink escapes but does not defend
against malicious concurrent filesystem mutation during traversal. It is read-only, supports bounded batches of textual
regular-expression queries, and returns ordered structured results with matching
and surrounding lines.
See [`docs/specs/tools-search-codebase-tool-spec.md`](docs/specs/tools-search-codebase-tool-spec.md)
for its complete accepted contract, limits, and supported platforms.

### Search distribution conformance

Before releasing workspace search changes, run the package-data distribution
conformance target on **both** supported platforms: Linux `x86_64` and macOS
Apple Silicon. It builds a wheel and source distribution, installs each into an
isolated environment, verifies the selected packaged `rg` executable against its
checksum metadata and executable permission, and runs a representative search.

```bash
make test-search-distribution
```

This host is verified only for its own platform. Both supported-platform checks
cover the documented best-effort pre-launch containment and must not be
represented as race-proof containment.

You can also run the default tests through `make`:

```bash
make test
```

Pre-commit hooks can be installed with:

```bash
uv run pre-commit install
```

## Dependency inspection

Use the focused dependency inspection targets when reviewing dependency health:

```bash
make deps-tree      # show the full resolved dependency tree from uv.lock
make deps-outdated  # check top-level dependencies for newer available versions
make deps-audit     # audit locked dependencies for known vulnerabilities
```

`deps-tree` is a local lockfile inspection. `deps-outdated` and `deps-audit` may
query remote package or vulnerability indexes.

## Live Codex transport validation

Live Codex backend validation is opt-in because it reads local Codex credentials
and sends one request to the live backend.

The transport exposes only one final normalized completion result. It does not
surface incremental stream events or partial output: success requires the
recognized terminal completion event and non-empty final text; malformed,
truncated, cancelled, or terminal-error streams return a non-success result
without partial text.

Keep live validation output redacted: do not copy credentials, auth headers,
cookies, backend payloads, account identifiers, private paths, or personal data
into logs, issue notes, or documentation.

Prerequisite: authenticate the Codex CLI first:

```bash
codex login
```

Then run the live probe:

```bash
make test-live-codex
```

The target runs:

```bash
FABRICA_RUN_LIVE_CODEX_TESTS=1 uv run pytest -m live_codex tests/integration/features/codex_transport/test_live_codex_backend.py
```

By default, the live test reads credentials from `~/.codex/auth.json` only after
the explicit live-test gate is enabled. To use a different auth file for manual
validation, pass a test-only override:

```bash
FABRICA_CODEX_AUTH_FILE=/path/to/auth.json make test-live-codex
```

The credential adapter is read-only: it does not copy, persist, print, or log raw
credential values. Failure output uses normalized, redacted diagnostics.

## Local CLI entrypoint

The project exposes a minimal local CLI for explicit runtime experiments:

```bash
uv run fabrica --help
uv run fabrica run --prompt "Reply with the single word: pong"
uv run fabrica --print-usage --print-prices run --prompt "Reply with the single word: pong"
```

The `run` command uses the direct Codex-backed runtime composition. It may read
local Codex credentials and call the live backend only when explicitly invoked;
authenticate the Codex CLI first with `codex login`. Help and import paths are
offline and do not read credentials, read skill roots, call backends, prompt for
approval, or execute scripts.

Selected Agent Skills markdown and non-script resources can be added explicitly:

```bash
uv run fabrica run \
  --prompt "Use the selected context." \
  --skill python-testing \
  --resource python-testing:references/example.md \
  --skill-root .agents/skills
```

### Commit workflows for staged changes

The first productized selected-skill workflows propose Conventional Commit text
from the currently staged git changes. Use `commit-message` when you want a
read-only preview that you can copy, edit, or run through your own git command:

```bash
uv run fabrica commit-message
```

By default, the workflow loads the `conventional-commits` Agent Skill. You can
override the selected skill, skill root, Codex model, and reasoning effort:

```bash
uv run fabrica commit-message \
  --skill conventional-commits \
  --model gpt-5.3-codex-spark \
  --reasoning-effort low \
  --skill-root .agents/skills
```

Use `commit` when you want Fabrica to generate the same recommendation, show it
once, prompt for approval, and create the git commit only after explicit
confirmation:

```bash
uv run fabrica commit
```

Before generating that recommendation, `commit` runs the configured pre-commit
quality gate against the staged workflow when `.pre-commit-config.yaml` exists.
Repositories without pre-commit configuration are valid: Fabrica skips that gate
and continues to recommendation generation. If configured pre-commit fails,
cannot run, times out, has invalid configuration, or modifies files, Fabrica
stops before model invocation, skips the prompt, and creates no commit. Formatter
rewrites are treated as modified files: review and stage the resulting changes,
then rerun `fabrica commit`. After Fabrica displays a recommendation, it checks
that the staged index is unchanged both before display and immediately after
approval; tracked but unstaged worktree edits alone do not block approval. This
is a best-effort check rather than atomic compare-and-commit protection, so the
index can still change after the final check and before Git starts the commit.

For the default `conventional-commits` skill and `.agents/skills` root, the same
interactive workflow is available through `make`:

```bash
make commit
```

`commit` accepts the same selected skill, skill root, Codex model, and reasoning
effort options as `commit-message`:

```bash
uv run fabrica commit \
  --skill conventional-commits \
  --model gpt-5.3-codex-spark \
  --reasoning-effort low \
  --skill-root .agents/skills
```

Fabrica-wide reporting and diagnostic flags must be passed before the
subcommand. They apply to commands that produce model runtime evidence:

```bash
uv run fabrica --print-usage --print-prices --verbose-diagnostics commit-message \
  --skill conventional-commits \
  --skill-root .agents/skills
```

For the interactive commit workflow, place the same global reporting flags before
the `commit` subcommand:

```bash
uv run fabrica --print-usage --print-prices --verbose-diagnostics commit \
  --skill conventional-commits \
  --skill-root .agents/skills
```

The Codex-backed commit-message workflow defaults to `gpt-5.3-codex-spark` with
`low` reasoning effort because the task is a bounded staged-change analysis and
Conventional Commit formatting workflow. Use `--model` and `--reasoning-effort`
when a specific run needs a different Codex model or deeper reasoning.

Both workflows read staged changes only. They list staged files, load each staged
file diff individually, analyze each file into structured evidence, and then run
one final synthesis call. They do not auto-stage files, inspect unstaged changes,
fall back to unstaged changes, auto-push, bypass hooks, open an editor,
regenerate on rejection, or produce JSON output.

`commit-message` remains read-only: it does **not** run `git commit`, write a
commit-message file, or mutate staged or unstaged repository state.

`commit` is mutating only after approval. It prints the `Summary:`,
`Rationale:`, and `Commit message:` block once, then asks:

```text
Commit with this message? [y/N]
```

Only trimmed, case-insensitive `y` or `yes` creates a commit. `n`, `no`, empty
input, EOF, and unrecognized answers cancel the command as a successful no-op:
no commit is created and staged changes remain staged. Interrupted input such as
Ctrl-C exits non-zero without committing. When approval succeeds, Fabrica passes
the exact generated message to git through a temporary commit-message file and
prints `Committed as <short-sha>.` when git reports the new short hash.

The recommendation workflow is evidence-first and multi-call in v1: it may make
one model call per staged file plus one final synthesis call. The final
synthesizer receives compact structured evidence and selected Agent Skill
context, not the full raw staged diff by default. The selected skill is applied
after evidence collection to group changes by intent and propose a Conventional
Commit centered on the dominant change intent.

Default terminal output stays concise and copy-oriented rather than exposing a
verbose per-file evidence report. It preserves these labels:

```text
Summary:
Rationale:
Commit message:
```

Fabrica fails closed when staged changes are absent, more than 25 staged files
are present, serialized structured evidence exceeds 50,000 characters, git is
unavailable, the current directory is not a git repository, git times out, a
per-file diff or analysis fails, final synthesis fails, or selected skill loading
fails. Raw diffs are not printed in diagnostics; raw staged file diffs are scoped
to their per-file analysis calls.

Script policy can be inspected without execution:

```bash
uv run fabrica script-policy \
  --skill-id python-testing \
  --script-id scripts/check.py \
  --skill-root .agents/skills
```

When policy approves the selected script, the command prints the exact approval
metadata needed for a later execution request:

```text
status: approved
approve-script-type: python
approve-suffix: .py
approve-byte-size: 128
approve-content-digest: sha256:abc123
```

Selected scripts can also be executed through the CLI only when the caller
supplies explicit, non-interactive approval metadata bound to the inspected
script:

```bash
uv run fabrica script-execute \
  --skill-id python-testing \
  --script-id scripts/check.py \
  --skill-root .agents/skills \
  --approve-script-type python \
  --approve-suffix .py \
  --approve-byte-size 128 \
  --approve-content-digest sha256:abc123
```

The approval fields must exactly match the selected script metadata loaded at
execution time: skill ID, relative script ID, script type, suffix, byte size, and
content digest. Missing or mismatched metadata fails closed as `policy_denied`
and the subprocess adapter is not called.

CLI script execution remains experimental, selected-only, approval-gated, and
non-interactive. It is **not production sandboxing** or safe execution of
untrusted code. The existing subprocess constraints still apply: `.py` and `.sh`
only, explicit interpreter argument lists with `shell=False`, no inherited
environment by default, execution-specific temporary working directory by
default, and bounded stdout/stderr capture.

For an explicit manual live CLI check, run:

```bash
make run-live-cli PROMPT="Reply with the single word: pong"
```

Default tests remain offline. They do not read real Codex credentials, call live
backends, read real user skill directories, prompt for approval, or execute real
user scripts.

## Local Codex-backed runtime experiment

The `agent_runtime` slice exposes an experimental Python API for one local agent
run backed by the existing `codex_transport` application boundary. Runtime
orchestration lives in `agent_runtime`; Codex credential loading, backend request
details, response mapping, and usage evidence remain isolated in
`codex_transport` adapters and application DTOs.

Create the composed runtime from the composition root:

```python
import asyncio

from fabrica.bootstrap import create_codex_runtime
from fabrica.features.agent_runtime.application.dtos import LocalAgentRunCommand

runtime = create_codex_runtime()
result = asyncio.run(runtime.run(LocalAgentRunCommand(prompt="Reply with the single word: pong")))

if result.succeeded:
    print(result.output_text)
else:
    print(result.status)
```

This API is intentionally narrow and experimental. It proves a local Python
runtime path over the subscription-backed Codex transport without introducing
streaming runtime responses, tool calls, or model-driven Agent Skills execution.

Default runtime tests are offline and use synthetic credentials or mocked HTTP
behavior. To run the live Codex-backed runtime smoke test, authenticate the Codex
CLI first:

```bash
codex login
```

Then run:

```bash
make test-live-runtime
```

The target runs:

```bash
FABRICA_RUN_LIVE_CODEX_TESTS=1 uv run pytest -m live_codex tests/integration/features/agent_runtime/test_live_local_agent_runtime.py
```

Like the live transport probe, the live runtime test reads `~/.codex/auth.json`
only after `FABRICA_RUN_LIVE_CODEX_TESTS=1` is set. To use a different auth
file for manual validation, pass the same test-only override:

```bash
FABRICA_CODEX_AUTH_FILE=/path/to/auth.json make test-live-runtime
```

Credential handling remains read-only: raw tokens, auth headers, cookies,
credential files, account identifiers, and backend payloads are not copied,
persisted, printed, or logged by the runtime path. Runtime failures return
normalized statuses and bounded, redacted observations.

Still-deferred runtime work remains explicit: streaming support, OAuth refresh or
credential mutation, production sandboxing, and UI entry points. Tool loops,
PydanticAI-shaped composition proofs, and model-driven selected Agent Skills
composition are documented below as explicit, bounded Python API paths rather
than ambient runtime powers.

## Offline PydanticAI runtime compatibility proof

The `agent_runtime` slice also includes an offline PydanticAI compatibility
proof behind the same application-owned runtime boundary. The composition helper
requires an explicit completion dependency, so construction does not read Codex
credentials, call a backend, load skill roots, or execute scripts.

```python
import asyncio
from dataclasses import dataclass

from fabrica.bootstrap import create_pydantic_ai_runtime
from fabrica.features.agent_runtime.adapters.outbound.pydantic_ai_model import (
    PydanticAICompletionRequest,
)
from fabrica.features.agent_runtime.application.dtos import LocalAgentRunCommand


@dataclass
class SyntheticCompletion:
    async def complete(self, request: PydanticAICompletionRequest) -> str:
        return f"received: {request.prompt}"


runtime = create_pydantic_ai_runtime(completion=SyntheticCompletion())
result = asyncio.run(runtime.run(LocalAgentRunCommand(prompt="Reply with pong")))
```

This proof uses `pydantic-ai-slim` and an adapter-local custom PydanticAI model
to verify compatibility with PydanticAI orchestration without exposing
PydanticAI concrete types in `agent_runtime/application/`. It is not a live Codex
backend integration and does not provide production billing guarantees, streaming
responses, tool calls, structured outputs, Agent Skills execution, automatic
skill discovery, or sandboxing.

For a Codex-backed PydanticAI composition experiment, use the dedicated helper:

```python
import asyncio

from fabrica.bootstrap import create_codex_pydantic_ai_runtime
from fabrica.features.agent_runtime.application.dtos import LocalAgentRunCommand

runtime = create_codex_pydantic_ai_runtime()
result = asyncio.run(runtime.run(LocalAgentRunCommand(prompt="Reply with pong")))
```

This helper still uses the existing `codex_transport` completion boundary for
credential loading, HTTP request construction, response mapping, and redacted
failure observations. It performs no credential reads or network calls during
construction; those side effects happen only when the returned runtime is run.
Default tests cover this path with synthetic credentials and mocked HTTP.

## Agent Skills context loading and activation

The `agent_runtime` slice can also load explicitly selected local Agent Skills
markdown and text resources as bounded context for one runtime command. This is
a host-selected context path: it reads selected `SKILL.md` text and explicitly
selected non-script resource text, then converts those inputs into
`LocalAgentContextBlock` values without executing scripts, auto-discovering
resources, scanning global skill directories, or calling Codex.

Use the composition helper to augment a runtime command before passing it to a
runtime:

```python
from pathlib import Path

from fabrica.bootstrap import (
    SkillContextAugmentationOptions,
    create_skill_context_augmented_local_agent_command,
)
from fabrica.features.agent_runtime.application.dtos import (
    LocalAgentRunCommand,
    SelectedSkill,
    SelectedSkillResource,
)

command = LocalAgentRunCommand(prompt="Use the selected skill and resource context.")
augmented = create_skill_context_augmented_local_agent_command(
    command,
    SkillContextAugmentationOptions(
        skill_selections=(SelectedSkill(skill_id="python-testing"),),
        resource_selections=(SelectedSkillResource(skill_id="python-testing", resource_id="references/example.md"),),
        skill_roots=(Path(".agents/skills"),),
    ),
)
```

When no root override is supplied, the default skill root is the working
repository's `.agents/skills` directory. The file adapters read only explicitly
selected `<skill_id>/SKILL.md` files and explicitly selected resource files under
configured roots. `SKILL.md` files must contain UTF-8 (without a BOM), YAML frontmatter with
lowercase-kebab-case `name`, non-empty `description`, and optional JSON-like mapping `metadata` fields, a directory name
matching `name`, and non-empty markdown instructions. Resource loading is also UTF-8 text-only and
allowlisted to `.md`, `.txt`, `.json`, `.yaml`, `.yml`, and `.toml` files;
`SKILL.md`, script-like files, binary files, directories, absolute paths, and
path traversal are rejected.

Default bounds are intentionally conservative for one local runtime command:

- at most 8 selected skills
- at most 8,000 characters per skill
- at most 16,000 total skill-context characters
- at most 120 characters per safe skill label or identifier
- at most 8 selected skill resources
- at most 8,000 characters per resource
- at most 16,000 total skill-resource-context characters
- at most 160 characters per safe resource label or identifier

Callers may supply `SkillContextBounds` and `SkillResourceContextBounds`
overrides, but those bounds must still fit the runtime context block limits.

Diagnostics are privacy-first by default: failures expose safe selected skill
identifiers and normalized categories rather than private absolute paths or file
contents. Verbose path diagnostics require explicit opt-in at composition time.

### Model-facing `skills` activation

The accepted Version 1 `skills` tool is a separate, model-callable activation
primitive. A host first builds an immutable registry snapshot from configured
global and workspace skill roots, then composes one registered `skills` tool with
that snapshot, a run-scoped `ActiveSkillSet`, and a host-owned trust evaluator.
The tool exposes exactly `{ "skill": string, "args"?: string | null }`.

Its catalog advertises deterministic concise descriptions within the existing
tool-description limit. A successful activation resolves a configured skill,
checks the host allowlist and trust binding, safely rereads the canonical
`SKILL.md`, verifies its exact `sha256:` revision against the snapshot, and
returns the complete instructions as bounded structured tool text. The optional
`args` value remains data in the activation result; it is not interpreted as
instructions. Repeating the same skill revision is idempotent. Ordered active
skills are retained with compacted run state and are rehydrated before ordinary
retrieved context; malformed state or insufficient context capacity fails closed
before the next model turn.

The `skills` tool loads procedural instructions only. Version 1 does not grant
permissions, register tools dynamically, execute scripts automatically, expose
`@skill/...` resource paths or skill roots through workspace tools, scan arbitrary
directories, support plugin or managed providers, install or edit skills, or
expand command, filesystem, network, or sandbox capabilities. Selected resources
and separately policy-gated selected-script workflows remain host-controlled
paths; they are not model-callable consequences of activation. Default tests use
synthetic local skill files only and do not read real user skill directories,
read Codex credentials, call live backends, or execute scripts.

## Selected Agent Skills script policy evaluation

The `agent_runtime` slice also includes a policy foundation for explicitly
selected Agent Skills scripts. This is policy evaluation only: it inspects safe
metadata for one selected script, checks that metadata against a non-interactive
approval decision and declarative sandbox policy, and returns a normalized
policy result. It does not execute scripts, spawn subprocesses, invoke shells,
prompt for approval, grant network access, or enforce an OS/container sandbox.

Use the composition helper to construct a policy evaluator:

```python
from pathlib import Path

from fabrica.bootstrap import (
    SkillScriptPolicyEvaluationOptions,
    create_skill_script_policy_evaluator,
)
from fabrica.features.agent_runtime.application.dtos import (
    SelectedSkillScript,
    SkillScriptPolicyEvaluationCommand,
)

evaluator = create_skill_script_policy_evaluator(
    SkillScriptPolicyEvaluationOptions(skill_roots=(Path(".agents/skills"),)),
)
result = evaluator.evaluate(
    SkillScriptPolicyEvaluationCommand(
        selection=SelectedSkillScript(
            skill_id="python-testing",
            script_id="scripts/check.py",
        ),
    ),
)
```

When no root override is supplied, the default skill root is the working
repository's `.agents/skills` directory. Metadata inspection is selected-only and
read-only: the file adapter checks only the requested `<skill_id>/<script_id>`
under configured roots, supports `.py` and `.sh` suffixes, computes bounded
metadata such as script type, byte size, and content digest, and rejects absolute
paths, path traversal, directories, missing files, unsupported suffixes,
oversized scripts, and ambiguous root matches.

Approval is modeled as a non-interactive lookup dependency. The default
composition uses a deny-by-default approval lookup, so callers must explicitly
supply an approval dependency for a script to be approved. Approval decisions are
bound to the selected script metadata, including skill ID, relative script ID,
script suffix/type, byte size, and content digest, so a decision cannot be reused
after a script changes.

The sandbox policy is declarative and preparatory. Defaults deny network access,
writable filesystem paths, and environment-variable access, with conservative
timeout and output-capture bounds. These DTOs describe intended constraints for a
future execution path; they are not production sandbox enforcement.

Diagnostics are privacy-first by default: policy results and adapter failures use
safe selected IDs and normalized categories rather than private absolute paths,
script contents, environment values, raw command lines, or secrets. Verbose path
diagnostics require explicit opt-in at composition time.

Default tests use synthetic script files only. They do not read real user skill
directories, read Codex credentials, call live backends, prompt for approval, run
subprocesses, or execute scripts. No persistent environment variable surface is
introduced for this policy foundation, so `.env.example` does not need script
policy entries.

## Experimental selected Agent Skills script execution

The `agent_runtime` slice now includes an experimental, opt-in execution path for
explicitly selected Agent Skills scripts. This is narrower than full Agent Skills
support: callers select one script, provide a non-interactive approval lookup,
and execute through the policy-gated application boundary. The runtime does not
auto-discover scripts, does not let Codex or PydanticAI call scripts directly,
does not prompt for approval, and does not implement model-driven tool loops.

Use the composition helper to construct a policy-gated executor:

```python
from pathlib import Path

from fabrica.bootstrap import (
    SkillScriptExecutionOptions,
    create_skill_script_executor,
)
from fabrica.features.agent_runtime.application.dtos import (
    SelectedSkillScript,
    SkillScriptExecutionCommand,
)

executor = create_skill_script_executor(
    SkillScriptExecutionOptions(
        skill_roots=(Path(".agents/skills"),),
        approval_lookup=my_non_interactive_approval_lookup,
    ),
)
result = executor.execute(
    SkillScriptExecutionCommand(
        selection=SelectedSkillScript(
            skill_id="python-testing",
            script_id="scripts/check.py",
        ),
    ),
)
```

Execution always evaluates policy first. The selected script executes only when
metadata inspection succeeds and the approval lookup returns an approved decision
bound to the current script metadata: skill ID, relative script ID, suffix/type,
byte size, and content digest. The subprocess adapter then loads a private
snapshot of the selected script bytes and executes that snapshot only if its
binding still matches the approved metadata, so a later path replacement cannot
change the executed bytes. The default composition remains deny-by-default, so
callers must supply approval state explicitly for execution to proceed.

The local subprocess adapter enforces conservative process-level constraints for
the spike:

- supports selected `.py` and `.sh` scripts only
- invokes interpreters with explicit argument lists and `shell=False`
- runs Python scripts with the configured Python interpreter, defaulting to the
  current interpreter
- runs shell scripts through an explicit POSIX shell interpreter such as
  `/bin/sh`, never through shell expansion fallback
- executes a private temporary snapshot of the bytes whose digest matches the
  approved binding, rather than reopening the selected script path as the
  interpreter target
- does not inherit the caller's environment by default
- uses an execution-specific temporary working directory by default
- may use an explicitly supplied working directory for tests or controlled local
  callers
- bounds timeout, stdout, and stderr according to the application sandbox-policy
  DTO
- returns normalized statuses for success, policy denial, non-zero exit, timeout,
  unsupported interpreter/script type, and adapter errors

These constraints are **not production sandboxing** and are not safe execution of
untrusted code. They do not guarantee OS/container isolation, blocked network
access, or filesystem-write confinement beyond the selected working-directory
intent. Treat bundled skill scripts as local code that must be reviewed and
explicitly approved before use.

Default tests remain offline and synthetic. They use temporary scripts under
`tmp_path`; they do not read real user skill directories, run real user scripts,
read Codex credentials, call live backends, or require subscription access. No
persistent environment variable surface is introduced for this execution spike,
so `.env.example` does not need script-execution entries.

## Offline registered tool-loop proof

The `agent_runtime` slice now includes an offline foundation for bounded model →
tool → model loops. The application-owned `RunToolLoop` use case coordinates a
tool-aware model port and a tool-execution port using backend-neutral DTOs. The
first concrete proof is intentionally local and explicit: callers register
in-process Python callables directly through composition, and the model can only
request those registered tool names.

Use the composition helper with an injected tool-aware model and explicit tools:

```python
from collections.abc import Mapping
from dataclasses import dataclass, field

from fabrica.bootstrap import create_tool_loop_runtime
from fabrica.features.agent_runtime.adapters.outbound.registered_tool import RegisteredTool
from fabrica.features.agent_runtime.application.dtos import (
    LocalAgentRunCommand,
    SafeRuntimeMetadataValue,
    ToolAwareModelResponse,
    ToolCallRequest,
    ToolCallResult,
    ToolDefinition,
    ToolLoopLimits,
)


@dataclass
class SyntheticToolAwareModel:
    calls: list[tuple[LocalAgentRunCommand, tuple[ToolDefinition, ...], tuple[ToolCallResult, ...]]] = field(
        default_factory=list,
    )

    def run_turn(
        self,
        command: LocalAgentRunCommand,
        available_tools: tuple[ToolDefinition, ...],
        tool_results: tuple[ToolCallResult, ...] = (),
    ) -> ToolAwareModelResponse:
        if not tool_results:
            return ToolAwareModelResponse(
                tool_calls=(ToolCallRequest(call_id="call-1", tool_name="lookup_note", arguments={"note_id": "abc"}),),
            )
        return ToolAwareModelResponse(output_text=f"final: {tool_results[0].result_text}")


def lookup_note(arguments: Mapping[str, SafeRuntimeMetadataValue]) -> str:
    note_id = arguments.get("note_id")
    if not isinstance(note_id, str):
        raise ValueError("note_id must be a string")
    return f"note:{note_id}"


runtime = create_tool_loop_runtime(
    model=SyntheticToolAwareModel(),
    tools=(
        RegisteredTool(
            definition=ToolDefinition(name="lookup_note", description="Lookup a synthetic note"),
            handler=lookup_note,
        ),
    ),
    limits=ToolLoopLimits(max_tool_iterations=2, max_tool_result_chars=100),
)
result = runtime.run(LocalAgentRunCommand(prompt="Use the lookup tool"))
```

Default loop limits are conservative: at most 4 tool iterations and at most 4,000
characters returned from a tool result to the model. Callers may provide
`ToolLoopLimits`, but result text remains bounded by the runtime context limits.
Unknown tools, invalid arguments, timeouts, tool failures, adapter errors, and
iteration-limit stops are normalized into application statuses and safe
observations.

This is **not** broad autonomous tool execution. The registered-tool adapter does
not scan for tools, dynamically import callables from strings, read skill roots,
execute Agent Skills scripts, spawn subprocesses, invoke shells, read Codex
credentials, call live backends, or integrate PydanticAI/Codex private tool-call
schemas. Agent Skills scripts remain available only through the explicit
selected, approval-gated CLI/API paths documented above; they are not
model-callable tools in this cut.

Default tests for the tool loop use fake models and synthetic in-process tools
only. They remain offline and subscription-credential independent.

The PydanticAI-shaped tool-aware adapter can also be composed into the same
registered-tool loop for offline integration proofs:

```python
from fabrica.bootstrap import create_pydantic_ai_tool_loop_runtime
from fabrica.features.agent_runtime.adapters.outbound.registered_tool import RegisteredTool
from fabrica.features.agent_runtime.application.dtos import LocalAgentRunCommand, ToolDefinition

runtime = create_pydantic_ai_tool_loop_runtime(
    turn_runner=my_synthetic_pydantic_ai_turn_runner,
    tools=(
        RegisteredTool(
            definition=ToolDefinition(name="lookup_note", description="Lookup a synthetic note"),
            handler=lookup_note,
        ),
    ),
)
result = runtime.run(LocalAgentRunCommand(prompt="Use the lookup tool"))
```

This helper still requires an injected turn runner and explicit registered tools.
It does not read Codex credentials, call live backends, read skill roots, execute
Agent Skills scripts, prompt for approval, discover tools, dynamically import
callables, or claim production sandboxing. Default coverage uses synthetic
PydanticAI-shaped `ToolCallPart`, `ToolReturnPart`, and `TextPart` messages only;
live Codex/PydanticAI tool-call validation remains a separate opt-in follow-up.

### Optional staged git registered tools

Developer workflows can explicitly compose three read-only, staged-only git tools
into the registered tool loop:

- `git_staged_files` lists staged file paths and staged statuses.
- `git_staged_diff` returns the bounded full staged diff.
- `git_staged_file_diff` returns the bounded staged diff for one validated staged
  file path.

These tools are never exposed globally or by default. Callers opt in by creating
them at the composition root and passing them to a tool-loop runtime:

```python
from pathlib import Path

from fabrica.bootstrap import (
    StagedGitToolOptions,
    create_tool_loop_runtime,
    create_staged_git_registered_tools,
)

tools = create_staged_git_registered_tools(
    StagedGitToolOptions(working_directory=Path.cwd()),
)
runtime = create_tool_loop_runtime(
    model=my_tool_aware_model,
    tools=tools,
)
```

Construction only wires dependencies; git is inspected lazily when a model calls
one of the supplied tools. The model cannot choose the repository working
directory, arbitrary git flags, arbitrary pathspecs, or mutating operations. The
tools do not inspect unstaged changes and do not run `git add`, `git commit`,
`git reset`, checkout, branch switching, stash, push, or pull.

These optional tools are separate from the deterministic `commit-message`
workflow. `commit-message` deterministically loads staged file metadata and
per-file staged diffs before model invocation and does not depend on model tool
calls. No environment-variable or settings surface is introduced for staged git
tool composition.

### Optional read-only git context registered tools

Developer workflows can also explicitly compose broader read-only git context
tools for model-driven worktree, commit-history, and ref/range inspection. These
tools are exposed only through Python composition in
`fabrica.bootstrap.composition`, not through a human-facing `fabrica git ...` CLI
surface. The helper remains internal in v1 and is intentionally not exported from
the curated `fabrica.bootstrap` package API.

The registered tools are atomic and grouped by stable intent:

- worktree tools: `git_status_summary`, `git_unstaged_files`,
  `git_unstaged_diff`, and `git_unstaged_file_diff`
- commit-history tools: `git_commit_log`, `git_commit_details`,
  `git_commit_changed_files`, `git_commit_diff`, and `git_commit_file_diff`
- ref/range tools: `git_ref_changed_files`, `git_ref_diff`,
  `git_ref_file_diff`, `git_branch_ahead_behind`, and `git_merge_base`

Construction wires adapters only; git state is inspected lazily when one of the
registered tool handlers is invoked by an explicitly composed tool-loop runtime.
The model cannot choose the repository working directory, arbitrary git commands,
arbitrary git flags, or pathspecs. The subprocess adapter uses fixed read-only
git argument lists, disables paging, bounds diff/log output, validates refs,
commit-ish values, and file paths before inspection, and does not fetch or mutate
repository state.

These broader read-only context tools are separate from the staged git tools and
from the deterministic `commit-message` workflow. `commit-message` remains
staged-only: it does not inspect unstaged changes, commit history, or ref/range
context, and it does not depend on model-callable git context tools.

## Model-driven selected Agent Skills composition

Model-driven selected Agent Skills are currently available only through the
Python API and composition-root helpers. This cut combines explicitly selected
`SKILL.md` context, explicitly selected non-script resources, and explicitly
supplied skill-associated `RegisteredTool` values through the bounded tool loop.
It does not add CLI support for model-driven skill tools.

The boundaries stay intentionally separate:

- selected `SKILL.md` files and selected resources become bounded runtime
  context only
- skill-associated registered tools are supplied by the caller through Python
  composition and may become model-callable tool definitions
- script policy evaluation inspects selected script metadata without execution
- script execution remains an explicit, approval-gated CLI/API path
- Agent Skills scripts are not registered as model-callable tools

Any future CLI surface for model-driven selected skills must avoid automatic
skill or tool discovery, dynamic import strings, implicit script registration,
and model-callable script execution. Default tests for this path remain offline
and use synthetic skill files, synthetic PydanticAI-shaped turns, and synthetic
in-process tools only.

## Codex usage evidence probe

The `codex_transport` slice also includes a Python API for probing usage and
quota evidence through the same credential and HTTP adapter boundaries. The
usage probe is offline-tested with synthetic payloads by default and keeps the
current best-known usage endpoint shape inside the outbound HTTP adapter.

The usage result exposes only bounded, application-safe evidence such as safe
usage/quota fields and `x-codex-*` rate-limit headers. It intentionally excludes
tokens, cookies, raw auth headers, account identifiers, and raw nested backend
payloads from application results and observations.

## Architecture

The project uses a `src/` layout and hexagonal architecture organized by vertical
feature slices:

- `src/fabrica/features/agent_runtime/` owns local runtime orchestration, runtime
  DTOs, selected Agent Skills context/policy/execution boundaries, and bounded
  tool-loop contracts.
- `src/fabrica/features/codex_transport/` owns Codex credential loading, backend
  transport, usage probing, response mapping, and provider-specific usage/cost
  evidence mapping behind application-owned ports and outbound adapters.
- `src/fabrica/features/developer_workflow/` owns staged-change commit-message
  generation, confirmed commit creation, and explicit read-only git registered
  tools for developer workflows.
- `src/fabrica/features/query_execution/` owns bounded async query fan-out
  execution.
- `src/fabrica/features/workspace_editing/` owns the canonical `apply_patch`
  model-facing mutation tool, including parsing, hunk matching, immutable
  planning, authorization, POSIX filesystem adapters, journaling, rollback, and
  startup recovery boundaries. Production POSIX mutation is enabled only after
  positive, actual-workspace capability evidence and clean recovery; unsupported
  or recovery-blocked workspaces remain fail-closed without exposing
  `apply_patch`.
- `src/fabrica/shared_kernel/` contains pure concepts genuinely shared by slices,
  such as provider-neutral model usage and pricing evidence DTOs.
- `src/fabrica/bootstrap/` contains composition-root code, dependency wiring, and
  startup helpers.
- `tests/unit/` and `tests/integration/` mirror source ownership for fast unit
  checks and explicit I/O-facing integration checks.

The product CLI keeps the same boundaries. Generic shell modules under
`src/fabrica/adapters/inbound/cli/` own feature-neutral parser construction,
global option parsing, execution-only invocation dispatch, and shared CLI
contracts only; they do not import feature slices. Feature slices own their
subcommand registration values, adapter-local parsed command models, CLI runners,
and output mapping under
`features/<feature>/adapters/inbound/cli/`. Bootstrap-owned handler factories in
`src/fabrica/bootstrap/cli/features/` attach per-command handlers and lazily
assemble those feature CLI adapters with default concrete dependencies only when
the selected command runs.

Feature-owned CLI registrations contribute commands through the shared
keyword-only `Command` contract. A registration configures only its subcommand
parser, decodes the feature-owned part of the resulting `argparse.Namespace` into
an adapter-local immutable command value, and handles expected user input failures
with `UsageError`; unexpected decoder failures remain programmer errors. Repeated
values should be converted to immutable containers such as tuples or frozensets
before leaving the decoder. Feature parser configuration must not mutate
shell-owned destinations through either argument actions or
`ArgumentParser.set_defaults()`.

After the single argparse parse, the shell explicitly splits the namespace before
feature decoding:

```text
argparse.Namespace
├── shell state   → selected command name + immutable GlobalOptions
└── feature state → immutable decoded command + composition options
```

Global flags therefore remain shell-owned, are passed to runners through
`CommandContext.global_options`, and must be supplied before the subcommand.
The root CLI also provides `fabrica --version`, which prints the installed
`fabrica` distribution version to stdout and exits successfully without selecting
a subcommand.

```python
from argparse import ArgumentParser, Namespace

from fabrica.adapters.inbound.cli import Command, CommandContext, CommandRegistry, UsageError


def register_example_commands(commands: CommandRegistry) -> None:
    commands.register(
        Command(
            name="example",
            summary="run one example workflow",
            configure=_configure_parser,
            decode=_decode_command,
            run=_handle_command,
        ),
    )


def _configure_parser(parser: ArgumentParser) -> None:
    parser.add_argument("--name", required=True)


def _decode_command(namespace: Namespace) -> str:
    if not namespace.name.strip():
        raise UsageError("name must not be blank")
    return namespace.name


def _handle_command(name: str, context: CommandContext) -> int:
    context.stdout.write(f"hello {name}\n")
    return 0
```
