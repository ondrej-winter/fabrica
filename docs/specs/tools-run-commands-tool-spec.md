# Spec: Run Commands Tool

## Status

- State: Accepted and implemented.
- Accepted by: Product interview
- Accepted on: August 30, 2026
- Revision: Aligned with the implemented `workspace_command_execution` feature
  on September 2, 2026, preserving the confirmed execution, timeout, output,
  context, and safety decisions recorded on August 31, 2026.
- Supersedes: Not applicable.

This document is the canonical source of truth for the `run_commands` tool
contract. Any material change to its objective, requirements, constraints,
boundaries, or success criteria requires this specification to be updated and
re-confirmed.

## Objective

Define the model-facing and host-facing specification for a `run_commands`
process-execution tool.

The tool is for autonomous coding agents that need one preferred primitive for
non-interactive command execution in a configured workspace. It must support
tests, linters, formatters, compilers, build systems, Git inspection, project
tooling, scripts, genuinely necessary shell pipelines, and concurrent execution
of independent commands.

The governing principle is:

```text
Use direct process execution as the normal primitive; treat shell interpretation
as an explicitly requested capability.
```

## Current Context

- Project: `fabrica`, a Python 3.14 local agent runtime experiment using a
  `src/` layout and hexagonal architecture organized by vertical slices.
- Runtime direction is owned by `docs/specs/agent-runtime-spec.md`.
- Filesystem reading is owned by `docs/specs/tools-read-files-tool-spec.md`.
- Textual source discovery is owned by `docs/specs/tools-search-codebase-tool-spec.md`.
- Filesystem mutation is owned by `docs/specs/tools-apply-patch-tool-spec.md`.
- This spec defines the implemented `run_commands` tool contract. The capability
  is owned by `src/fabrica/features/workspace_command_execution/`, with its
  registered-tool adapter and bootstrap composition preserving this contract.
- `run_commands` is the verification and project-tooling counterpart to the
  read/search/edit tools. It should not replace them for ordinary reading,
  searching, or editing work.
- The public contract is closed enough that implementation changes can be
  evaluated against focused acceptance tests rather than rediscovering core
  semantics.

The intended agent loop is:

```text
search_codebase
      ↓
read_files
      ↓
apply_patch
      ↓
run_commands
      ↓
tests / type checks / lint / build
```

## Assumptions

- The primary caller is a model-driven coding agent operating inside a configured
  workspace root.
- Canonical model-facing working directories are workspace-relative, not absolute.
- The host can provide a canonical workspace root, a platform shell description,
  cancellation signals, timeout configuration, permission policy, sandbox policy,
  environment filtering, and progress-event delivery.
- Version 1 is designed for commands expected to terminate, such as tests, builds,
  linters, Git commands, package-manager operations, and one-shot scripts.
- Version 1 does not expose detached/background process lifecycle management in
  the public schema.
- Documentation-only changes should be reviewed for clarity and consistency;
  implementation changes will require tests and the project quality gate.

## Scope

### In Scope

- The non-interactive workspace command-execution tool contract.

### Out of Scope

The detailed exclusions already recorded below remain authoritative.

## Desired Behavior

`run_commands` must allow a model to:

- run ordinary programs through direct argv execution;
- run shell syntax explicitly when shell semantics are required;
- execute one or more commands in a single call;
- choose explicit sequential or parallel execution for the batch;
- provide per-command workspace-relative working directories;
- provide per-command environment overrides;
- provide per-command timeouts;
- receive structured per-command results in input order;
- receive non-zero exit output without the tool treating ordinary failures as
  infrastructure exceptions;
- receive partial output on timeout and cancellation;
- preserve bounded, UTF-8-safe head and tail output;
- stream transient progress while a command is running when the host supports it;
- cancel commands and terminate complete process trees.

`run_commands` should not be the preferred mechanism for:

```text
reading files       → read_files
searching source    → search_codebase
editing files       → apply_patch
fetching web pages  → fetch_web_content
```

Primary design goals:

1. Direct execution as the safe, portable default.
2. Explicit shell interpretation.
3. Parallel execution by default, with explicit sequential execution for dependencies.
4. Per-command workspace-relative `cwd`.
5. Filtered environment inheritance.
6. Non-interactive deterministic execution.
7. Process-tree timeout and cancellation semantics.
8. Structured ordered output with bounded context consumption.
9. Host-managed default-deny safety policy and sandbox boundaries outside the executor.
10. No automatic retries.

## Tool interface

Tool name:

```text
run_commands
```

Keep this name. It communicates that batching is part of the primitive.

Canonical model-facing JSON schema:

```json
{
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "type": "object",
  "properties": {
    "execution": {
      "type": "string",
      "enum": ["parallel", "sequential"],
      "default": "parallel"
    },
    "commands": {
      "type": "array",
      "minItems": 1,
      "maxItems": 8,
      "items": {
        "type": "object",
        "oneOf": [
          {
            "required": ["argv"],
            "not": { "required": ["shell"] }
          },
          {
            "required": ["shell"],
            "not": { "required": ["argv"] }
          }
        ],
        "properties": {
          "argv": {
            "type": "array",
            "minItems": 1,
            "maxItems": 256,
            "items": {
              "type": "string",
              "maxLength": 12000
            }
          },
          "shell": {
            "type": "string",
            "minLength": 1,
            "maxLength": 12000
          },
          "cwd": {
            "type": "string",
            "minLength": 1
          },
          "env": {
            "type": "object",
            "additionalProperties": { "type": "string" }
          },
          "timeout_ms": {
            "type": "integer",
            "minimum": 1,
            "maximum": 300000
          }
        },
        "additionalProperties": false
      }
    }
  },
  "required": ["commands"],
  "additionalProperties": false
}
```

Defaults:

```text
cwd        = "."
env        = {}
timeout_ms = 30000
execution  = parallel
stdin      = closed
retryable  = false
maxRetries = 0
```

Recommended host maximums:

```text
MAX_COMMANDS_PER_CALL      = 8
MAX_COMMAND_INPUT_CHARS    = 12,000
DEFAULT_COMMAND_TIMEOUT    = 30 seconds
MAX_COMMAND_TIMEOUT        = 5 minutes
MAX_COMMAND_OUTPUT_CHARS    = 48,000
MAX_SERIALIZED_RESULT_CHARS = 96,000
```

The public schema must make direct argv and shell execution first-class and
mutually exclusive. It must not rely on hidden conventions such as “presence of an
`args` key means direct execution”.

Schema validation alone is not the complete input contract. The host must also
normalize and validate every command before any process starts:

- absent `execution` must normalize to `parallel`; every downstream policy,
  scheduler, and result component receives the resulting effective execution
  policy explicitly;
- each command must contain exactly one of `argv` or `shell`;
- the command input length must not exceed `MAX_COMMAND_INPUT_CHARS = 12,000`;
- for `shell`, command input length is the shell string length;
- for `argv`, command input length is the sum of argument string lengths plus one
  separator character between adjacent arguments;
- `timeout_ms` must not exceed the configured host maximum;
- `cwd` must resolve inside the workspace;
- `env` keys must be non-empty strings without NUL or `=` characters;
- `env` values must be strings without NUL characters.

The JSON Schema may enforce a conservative subset of these constraints, but the
canonical runtime validation must enforce all of them consistently across
providers and schema-dialect adapters.

## Canonical examples

Run one test:

```json
{
  "execution": "sequential",
  "commands": [
    {
      "argv": [
        "uv",
        "run",
        "pytest",
        "tests/test_users.py::test_create_user",
        "-q"
      ]
    }
  ]
}
```

Run independent quality gates:

```json
{
  "execution": "parallel",
  "commands": [
    { "argv": ["uv", "run", "ruff", "check", "."] },
    { "argv": ["uv", "run", "ty", "check", "src", "tests"] },
    { "argv": ["uv", "run", "pytest", "-q"], "timeout_ms": 120000 }
  ]
}
```

Run from a subdirectory:

```json
{
  "execution": "sequential",
  "commands": [
    {
      "argv": ["npm", "test", "--", "--runInBand"],
      "cwd": "frontend",
      "timeout_ms": 120000
    }
  ]
}
```

Use an actual shell pipeline:

```json
{
  "execution": "sequential",
  "commands": [
    { "shell": "git diff --name-only | grep -E '\\.(py|toml)$'" }
  ]
}
```

## Model-facing description

Recommended concise description:

```text
Run non-interactive commands in the project workspace.

Prefer argv execution for ordinary programs because it bypasses shell parsing.
Use shell execution only when shell features such as pipes, redirection,
globbing, command substitution, heredocs, or compound commands are required.

Commands run in parallel by default. Set execution to sequential only when a
command depends on an earlier command completing first.

Commands start in the workspace root unless cwd is provided. cwd must remain
inside the workspace.

Output is bounded with the beginning and end preserved. Commands have timeouts,
and cancellation terminates their process tree.

Use read_files to read files, search_codebase to locate source, and apply_patch
to edit files instead of reproducing those operations with shell commands.

The configured shell for shell-mode commands is: <dynamic shell description>.
```

The dynamic shell description should come from the host and should tell the model
which syntax applies, such as POSIX-compatible shell, zsh, bash, PowerShell,
`cmd.exe`, WSL/bash, or another configured shell.

## Direct execution

Direct execution uses `argv`:

```json
{ "argv": ["git", "status", "--short"] }
```

Simple commands should normally use `argv` rather than `shell`:

```json
{ "argv": ["uv", "run", "pytest", "tests/test_api.py", "-q"] }
```

Direct execution avoids shell quoting, shell expansion, command substitution,
globbing surprises, platform syntax differences, accidental command composition,
and injection through arguments.

Arguments must be passed to the child process exactly as arguments, including
arguments containing spaces, empty arguments, Unicode arguments, and arguments
containing shell metacharacters. Shell metacharacters in `argv` must not be
shell-expanded.

## Shell execution

Shell execution uses `shell`:

```json
{ "shell": "git status --short | head -20" }
```

Use shell mode when actual shell semantics are required: pipes, redirection,
`&&` or `||`, environment expansion, globbing, command substitution, heredocs, or
compound scripts.

Do not force a complicated shell parser into the agent merely to avoid shell mode
entirely.

The model must not select an arbitrary shell executable through metadata such as:

```json
{ "shell_executable": "/bin/zsh" }
```

The shell is configured by the host. The tool description should dynamically tell
the model which shell syntax applies.

## Heredocs and multiline scripts

A multiline shell script or heredoc must be represented as one shell command:

```json
{ "shell": "python <<'PY'\nprint('hello')\nPY" }
```

The canonical protocol must not allow malformed split heredocs across separate
`commands[]` entries. A compatibility adapter may repair common legacy model
mistakes, but repair behavior must not become part of the domain contract.

## Execution policy

Array semantics default to `parallel`. A request may set `execution` to
`sequential` only when command order is required.

Before either execution policy starts processes, the tool must build a normalized
execution plan for the entire request:

```text
validate request shape
      ↓
normalize defaults
      ↓
resolve workspace-relative cwd values
      ↓
build filtered per-command environments
      ↓
evaluate permissions and sandbox policy
      ↓
execute planned commands
```

Invalid input, invalid `cwd`, denied permission, or sandbox denial discovered
during planning must prevent process launch for the affected command. When the
host can evaluate the entire request up front, it should do so before launching
any command, especially for parallel batches and potentially mutating commands.
If a host needs user approval for one or more commands, approval belongs between
planning and execution; the process supervisor must never prompt.

Use `parallel` for independent commands:

```text
A ─┐
B ─┼─ concurrent
C ─┘
```

Examples include independent checks such as `pytest`, `ruff`, and a type checker
when they do not depend on each other's side effects.

Parallel commands are independent. If one command fails, the failure must not
cancel siblings. All results must be returned in input order.

Use `sequential` when execution order matters:

```text
A → B → C
```

Sequential execution controls start order only. An unsuccessful command does not
stop later commands: non-zero exits, timeouts, rejections, and spawn failures all
produce a per-command result and the sequence proceeds to its next eligible
command. This preserves complete diagnostic coverage for the submitted batch.

Commands may be `skipped` only when the host prevents their start for a
batch-wide reason, such as agent cancellation or a batch wall-clock timeout.
Stable skipped reasons are:

- `BATCH_CANCELLED`;
- `BATCH_TIMED_OUT`.

If the agent genuinely wants shell-level short-circuit semantics, it can use a
single shell command such as `command1 && command2`.

## Working directory

Default:

```text
cwd = workspace root
```

`cwd` is workspace-relative:

```json
{ "argv": ["pytest", "-q"], "cwd": "backend" }
```

Resolve `cwd` through the same canonical `WorkspacePathResolver` used by
`read_files`, `search_codebase`, and `apply_patch`.

Reject `../outside`, absolute external cwd values, Windows absolute paths such as
`C:\\outside`, paths that resolve outside the workspace, and symlink escapes.

Resolution model:

```text
resolved_cwd = workspace_root / requested_cwd
canonical_cwd = filesystem_resolve(resolved_cwd)
```

The implementation must verify that the final canonical path remains inside the
configured workspace root before spawning the command.

Restricting `cwd` is an ergonomic boundary, not a security boundary. A child
process can still access anything permitted to the child OS process, and shell
mode can execute `cd /`. Actual security must live in the execution sandbox and
host permission policy.

## Environment

Do not blindly pass all host environment variables to child processes.

Recommended architecture:

```text
HostEnvironment
      ↓
EnvironmentFilter
      ↓
ProjectEnvironment
      ↓
command-specific env overrides
```

Reasonable default inherited variables include:

```text
PATH
HOME / USERPROFILE
TMP / TEMP
LANG
LC_*
TERM
SYSTEMROOT on Windows
```

Additional variables should be supplied explicitly by host policy. Version 1
must not expose full-environment inheritance to callers; the host filters the
inherited environment and must exclude secrets and credentials by default.

Command-specific environment entries apply only to that command:

```json
{
  "argv": ["pytest", "-q"],
  "env": {
    "CI": "1",
    "PYTHONUNBUFFERED": "1"
  }
}
```

They must not mutate the parent process environment.

## Non-interactive execution

Commands must be non-interactive.

Good examples:

```text
git --no-pager diff
apt-get -y
npm --yes
pytest -q
```

Avoid:

```text
vim
nano
less
top
interactive REPL
password prompt
confirmation prompt
```

For Version 1, `stdin = closed`. The child should immediately observe EOF. This
prevents commands from silently hanging while waiting for input.

Spawn using ordinary pipes, not a PTY:

```text
stdin  → closed
stdout → pipe
stderr → pipe
```

A future extension may add explicit `stdin` text, but it must not add interactive
terminal semantics to this tool. A PTY is a different abstraction.

## Timeout and cancellation

Recommended default:

```text
DEFAULT_COMMAND_TIMEOUT = 30 seconds
```

Allow command-specific override:

```json
{ "argv": ["uv", "run", "pytest"], "timeout_ms": 120000 }
```

Recommended host maximum:

```text
MAX_COMMAND_TIMEOUT = 5 minutes
```

unless explicitly configured otherwise.

Do not reproduce layered, competing timeout implementations. Tool-orchestration
timeout, executor timeout, and subprocess timeout must resolve to one effective
command deadline owned by the process supervisor.

A host may additionally define a batch-level wall-clock timeout. If present, it
must be explicit host policy and must not expire unexpectedly before valid
per-command deadlines. Running commands terminated by a batch timeout return
`timed_out` with `error.code = "BATCH_TIMEOUT"`; queued sequential commands that
never started return `skipped` with `reason = "BATCH_TIMED_OUT"`.

Timeout result example:

```json
{
  "status": "timed_out",
  "success": false,
  "exit_code": null,
  "stdout": "...partial command output...",
  "stderr": "",
  "duration_ms": 30018
}
```

Cancellation result example:

```json
{
  "status": "cancelled",
  "success": false,
  "exit_code": null,
  "stdout": "...partial output...",
  "stderr": ""
}
```

Timeout and cancellation must always preserve output produced before termination.
Queued sequential commands that have not started when cancellation occurs should
return `skipped` with an appropriate cancellation reason.

Agent cancellation must propagate to every running command in a parallel batch and
to the currently running command in a sequential batch. Running commands return
`cancelled`; queued sequential commands return `skipped` with
`reason = "BATCH_CANCELLED"`.

## Process-tree termination

Cancellation and timeout must terminate the complete process tree, not merely the
immediate shell or parent process.

Example tree:

```text
shell
 └── npm
      └── node
           └── test worker
```

Preferred strategy:

```text
cancel / timeout
      ↓
SIGTERM / graceful tree termination
      ↓
grace period (~1–2 s)
      ↓
SIGKILL / force termination
```

On Windows, prefer Job Object termination when the runtime supports it. Fallback
to `taskkill /T /F` when necessary. On POSIX, start the process in its own process
group and terminate the process group.

## Exit semantics and spawn errors

Exit code `0`:

```json
{
  "status": "exited",
  "success": true,
  "exit_code": 0
}
```

Non-zero exit code:

```json
{
  "status": "exited",
  "success": false,
  "exit_code": 1
}
```

Non-zero exit is a command result, not an infrastructure exception. Preserve its
output.

A genuine execution failure is different. For example, `argv: ["does-not-exist"]`
returns:

```json
{
  "status": "spawn_failed",
  "success": false,
  "exit_code": null,
  "error": { "code": "EXECUTABLE_NOT_FOUND" }
}
```

Distinguish “process launched and returned 127” from “runtime could not spawn the
process” where possible.

If a launched process terminates because of a signal, keep `status = "exited"`,
`success = false`, and `exit_code = null`, and include signal metadata:

```json
{
  "status": "exited",
  "success": false,
  "exit_code": null,
  "signal": "SIGTERM"
}
```

Do not introduce a separate signal status unless a future public contract changes
the stable status set.

Stable command statuses:

```text
exited
timed_out
cancelled
spawn_failed
skipped
```

`success` is derived:

```text
exited + exit_code 0 → true
everything else      → false
```

## Output collection

Keep output bounded while preserving the most useful regions:

```text
first half of output
+
rolling last half
```

Use UTF-8-safe stream decoding so multibyte characters split across stream chunks
are not corrupted.

Recommended per-command retained output:

```text
MAX_COMMAND_OUTPUT_CHARS = 48,000
```

This is one combined retained-character budget for `stdout` and `stderr` for a
single command, not a separate 48,000-character allowance for each stream. When
both streams contain output, allocate the available budget deterministically
between them, such as proportionally to their retained lengths.

Head plus tail is preferable because command output often has this shape:

```text
head:
    invocation / test collection / build configuration

middle:
    repetitive progress

tail:
    compiler error / traceback / failed assertion / summary
```

Truncation marker example:

```text
<first section>

[... output truncated: 184203 characters total ...]

<last section>
```

Return truncation metadata as well:

```json
{
  "output_truncated": true,
  "total_output_chars": 184203,
  "retained_output_chars": 48000
}
```

The model should never need to infer truncation.

Each truncated stream must include at most one truncation marker. Markers count
toward `retained_output_chars`; `total_output_chars` records decoded characters
observed before any per-command or aggregate limiting.

## stdout and stderr ordering

Do not concatenate all stdout before all stderr because that loses temporal
ordering between streams.

Internally preserve stream-aware events:

```text
stdout chunk
stdout chunk
stderr chunk
stdout chunk
stderr chunk
```

Coalesce adjacent chunks where useful.

The model-visible final result must return separate `stdout` and `stderr`
fields. The host may retain ordered stream events separately for richer rendering.

Do not return a `combined_output` field in the model-visible final result because
it duplicates provider tokens. Apply the command's combined fixed output cap
across the separate `stdout` and `stderr` fields. Apply explicit truncation
metadata to the command result, and preserve a marker in each truncated stream.

## Progress streaming

Running commands should optionally emit transient progress events:

```json
{
  "command_index": 0,
  "execution_id": "...",
  "stream": "stdout",
  "chunk": "collecting tests...\n"
}
```

Progress events are a UI/runtime concern, not part of the final result. Batch
events at roughly `PROGRESS_FLUSH_INTERVAL ≈ 50 ms` rather than emitting one
update per raw stream chunk.

## Serialized result limiting

Recommended complete serialized model-visible result limit:

```text
MAX_SERIALIZED_RESULT_CHARS = 96,000
```

The 96,000-character limit applies to the complete serialized JSON result,
including JSON structure, result metadata, command previews, error values,
escaping overhead, truncation markers, and retained `stdout` and `stderr` text.
It is not a 96,000-character payload allowance in addition to serialized-result
overhead.

Before allocating retained output, reserve enough serialized capacity for every
command result object and its required status, exit, duration, error, and
truncation metadata. If output would exceed the remaining serialized-result
budget, further truncate individual streams using head-and-tail semantics. Never
drop an entire command result merely because another command was verbose.

Serialized-result limiting should be fair and deterministic:

1. Preserve every command result object and all status, duration, exit, signal,
   error, and truncation metadata.
2. Reserve a small output allowance for every command that produced output.
3. Allocate the remaining serialized capacity to output in input order or another
   documented stable policy, accounting for JSON escaping and truncation markers.
4. When reducing an individual command's retained output, use the same head and
   tail strategy and update `output_truncated`, `retained_output_chars`, and
   `batch_output_truncated`.

The limiter must never remove a failed command's diagnostic output merely because
a successful sibling produced more output.

## Registered-tool result transport

The command slice owns the fair 96,000-character complete serialized-result
budget, separate `stdout` and `stderr` payloads, and all result truncation
metadata. It must serialize and limit the final model-visible JSON before the
agent runtime transports it without applying its generic `result_text` bound.

The final serialized result must be at most 96,000 characters and use at most two
provider-neutral `ToolTextContent` parts. Each part is independently capped at
48,000 characters; the two parts together carry the complete bounded structured
result. Split only at UTF-8-safe text boundaries. The runtime must not duplicate
the full structured payload in `result_text`; a short non-duplicative summary is
permitted only when a provider requires one.

The generic runtime must preserve all content parts and must not convert a valid
multipart command result into `LIMIT_EXCEEDED` solely because the legacy
`result_text` limit is smaller than the command tool's serialized-result budget.

## Result contract

Top-level result:

```json
{
  "execution": "parallel",
  "results": [
    {
      "index": 0,
      "command_preview": "uv run pytest tests/...",
      "status": "exited",
      "success": true,
      "exit_code": 0,
      "duration_ms": 4218,
      "stdout": "128 passed in 3.72s\n",
      "stderr": "",
      "output_truncated": false,
      "total_output_chars": 21,
      "retained_output_chars": 21,
      "stdout_chars": 21,
      "stderr_chars": 0
    },
    {
      "index": 1,
      "command_preview": "uv run ruff check .",
      "status": "exited",
      "success": false,
      "exit_code": 1,
      "duration_ms": 811,
      "stdout": "",
      "stderr": "src/foo.py:28: F401 ...",
      "output_truncated": false,
      "total_output_chars": 24,
      "retained_output_chars": 24,
      "stdout_chars": 0,
      "stderr_chars": 24
    }
  ],
  "batch_output_truncated": false
}
```

Do not repeat the entire command in every result. The command already exists in
the tool-call input. Include only a small `command_preview`, capped at about 200
characters.

Every command result must include these common fields:

- `index`;
- `command_preview`;
- `status`;
- `success`;
- `exit_code`;
- `duration_ms`;
- `stdout`;
- `stderr`;
- `output_truncated`;
- `total_output_chars`;
- `retained_output_chars`.

Status-specific fields:

| Status | Required fields | Notes |
| --- | --- | --- |
| `exited` | `exit_code`; optional `signal` | `success = true` only when `exit_code = 0`; signal exits use `exit_code = null`. |
| `timed_out` | `exit_code = null`, `error.code` | Use `COMMAND_TIMEOUT` or `BATCH_TIMEOUT`; preserve partial output. |
| `cancelled` | `exit_code = null`, `error.code = "COMMAND_CANCELLED"` | Preserve partial output after process-tree termination. |
| `spawn_failed` | `exit_code = null`, `error.code` | Use `EXECUTABLE_NOT_FOUND`, `PERMISSION_DENIED`, `SANDBOX_DENIED`, or `SPAWN_FAILED` as appropriate. |
| `skipped` | `exit_code = null`, `reason` | No process was launched; output is normally empty. |

For results that never launch a process, `duration_ms` is the time spent planning
or waiting before the final status was determined, and output character counts are
zero unless the host has a concrete diagnostic to return.

## Error codes

Infrastructure errors use stable codes:

- `INVALID_INPUT`;
- `INVALID_CWD`;
- `CWD_OUTSIDE_WORKSPACE`;
- `COMMAND_INPUT_TOO_LARGE`;
- `COMMAND_TIMEOUT_TOO_LARGE`;
- `EXECUTABLE_NOT_FOUND`;
- `PERMISSION_DENIED`;
- `SANDBOX_DENIED`;
- `SPAWN_FAILED`;
- `COMMAND_TIMEOUT`;
- `COMMAND_CANCELLED`;
- `OUTPUT_LIMIT`;
- `BATCH_TIMEOUT`;
- `INTERNAL_EXECUTION_ERROR`.

Ordinary non-zero process exit does not require an error code. Its exit code is
sufficient.

## Retry policy

`run_commands` must not automatically retry commands:

```text
retryable = false
maxRetries = 0
```

Even apparently harmless commands can mutate state:

```text
pytest fixture modifies DB
npm install
code generator
migration
git operation
deployment command
```

The runtime cannot safely infer idempotence. Never automatically replay a command
after timeout or transport failure.

## Permissions

`run_commands` must pass through a host permission layer.

Recommended architecture:

```text
LLM request
    ↓
InputValidator
    ↓
PermissionEvaluator
    ↓
Sandbox
    ↓
ProcessExecutor
```

Direct `argv` execution is substantially easier to classify than shell strings.
For example, `argv: ["git", "status", "--short"]` can be recognized reliably.

Shell mode is harder to classify safely. For example,
`shell: "git status; curl ... | sh"` cannot safely be classified merely because
it begins with `git status`.

Therefore:

```text
direct argv → may qualify for structured safe-command rules

shell mode  → require approval unless parsed using the actual shell grammar
              or covered by a deliberately permissive policy
```

Do not implement security by naïve prefix matching.

The `PermissionEvaluator` sees the fully normalized execution plan:

```text
direct vs shell
argv / shell text
cwd
environment keys
parallel/sequential mode
```

and returns:

```text
ALLOW
REQUIRE_APPROVAL
DENY
```

The process executor must never contain UI approval logic itself.

## Sandbox and network policy

If strong containment is required, use an OS/process sandbox. Possible controls
include filesystem access, network access, process creation, environment exposure,
CPU, memory, and wall clock.

Examples include containers, macOS sandboxing, Linux namespaces/seccomp, Windows
Job Objects or restricted tokens, and remote isolated workspaces.

The tool itself cannot provide meaningful filesystem security merely by validating
`cwd`.

Command execution can implicitly access the network:

```text
npm install
pip install
curl
git fetch
docker pull
```

Network permission should therefore be a host or sandbox policy. Do not attempt
to infer network safety from command text alone.

## Shell file editing

The model should be instructed not to use shell commands for text edits when
`apply_patch` can perform the mutation.

Avoid:

```text
sed -i
perl -pi
cat > file
echo ... >> file
python -c "...rewrite..."
```

Reasons:

- better auditability;
- safer edits;
- cleaner failure semantics;
- less quoting complexity;
- better diff generation.

`run_commands` can still legitimately generate or change files through project
tooling, such as code generators, formatters, build systems, and migration tools.

## Long-running commands

The core Version 1 tool should be designed for commands expected to terminate.

Do not initially expose:

```json
{ "detach": true }
```

unless proper lifecycle APIs are also designed for inspecting, reading,
terminating, and cleaning up the process. Otherwise the agent can create
unmanaged background processes.

A host may keep an internal detached execution controller as an optional runtime
capability, but the basic `run_commands` schema should not include detachment in
Version 1.

## Architecture and project structure

Recommended component boundaries:

```text
RunCommandsTool
      ↓
InputValidator
      ↓
CommandPlanner
      ↓
PermissionEvaluator
      ↓
EnvironmentBuilder
      ↓
ProcessSupervisor
      ├── DirectExecutor
      └── ShellExecutor
      ↓
OutputCollector
      ↓
ResultLimiter
      ↓
CommandResult[]
```

`ProcessSupervisor` owns spawn, PID/process group, timeout, cancellation, tree
termination, stream draining, exit detection, duration, and resource cleanup. Do
not distribute these concerns between the tool wrapper and executor.

`OutputCollector` owns UTF-8 decoding, stream ordering, progress batching,
character counting, head preservation, rolling tail, and truncation metadata. It
must operate with bounded memory.

Implementation ownership:

- Spec: `docs/specs/tools-run-commands-tool-spec.md`.
- Runtime tool contracts and DTOs: the `workspace_command_execution` application
  boundary, composed with `agent_runtime` registered-tool contracts by its inbound
  adapter.
- Process execution, POSIX process-tree handling, workspace resolution,
  environment filtering, and platform shell invocation: outbound adapters under
  `src/fabrica/features/workspace_command_execution/adapters/outbound/`.
- Permission policy integration: application-owned policy ports plus host-owned
  UI or approval adapters supplied through bootstrap composition.
- Bootstrap composition: `src/fabrica/bootstrap/composition/workspace_command_execution.py`.
  The built-in supervisor supports macOS and Linux POSIX process groups; other
  platforms must provide a platform-specific `CommandSupervisor` explicitly.
- Unit tests: mirrored under `tests/unit/features/workspace_command_execution/`
  for validation, planning, environment filtering, result limiting, output
  collection, permission decisions, workspace containment, and POSIX supervision.
- Integration tests: under `tests/integration/features/workspace_command_execution/`
  for explicit runtime composition and real subprocess behavior.

Implementation must preserve hexagonal boundaries: domain and application code
must not directly depend on OS-specific process APIs, shell syntax, UI approval
widgets, or provider-specific tool-call schemas.

## Relationship to neighboring tools

### `read_files`

Use `read_files` when the model needs known file contents. Reading ordinary source
through `cat`, `sed -n`, `head`, `tail`, `type`, or `Get-Content` should be
discouraged.

`run_commands` remains appropriate for generated output, Git state, build and
test output, specialized extraction, and very large logs requiring command-line
tools.

### `search_codebase`

Use `search_codebase` for ordinary source discovery. Discourage shell commands
such as `grep -R`, `rg`, `findstr`, and `Select-String` when the intent is normal
workspace source search.

Shell search commands remain appropriate for genuinely shell-specific behavior or
for generated command output that is not workspace source.

### `apply_patch`

Use `apply_patch` for workspace file edits. Do not use shell redirection,
`sed -i`, `perl -pi`, or ad hoc rewrite scripts when a contextual patch can
represent the mutation.

## Differences from current Cline behavior

Keep these Cline-compatible concepts:

- `run_commands` name;
- multiple commands per call;
- direct subprocess capability;
- shell execution capability;
- platform-aware shell prompting;
- non-interactive requirement;
- command cancellation;
- process-tree termination;
- 30-second default timeout;
- 48,000-character output budget;
- head and tail output preservation;
- UTF-8-safe streaming;
- progress streaming;
- preserve output for non-zero exits;
- no automatic retries;
- permission gating outside executor.

Change these behaviors for this implementation:

- shell strings are not the only advertised format;
- no hidden `args`-key convention for direct execution;
- command-array concurrency is not implicit;
- do not inherit all `process.env` by default;
- do not concatenate all stdout before all stderr;
- do not lose partial output on timeout or cancellation;
- no competing timeout layers;
- no unbounded parallel command array;
- no unlimited serialized batch result;
- do not require shell syntax for simple `cwd` or `env` use cases.

Add these requirements beyond current Cline behavior:

- explicit `argv` mode;
- explicit `shell` mode;
- optional `execution` with an explicit normalized `parallel`/`sequential`
  execution policy;
- per-command workspace-relative `cwd`;
- per-command environment;
- structured status;
- structured exit code;
- structured duration;
- partial timeout/cancellation output;
- filtered environment provider;
- serialized-result budget;
- explicit permission evaluator;
- explicit sandbox boundary;
- graceful-to-forced process-tree termination.

## Testing Strategy

The implemented tool's acceptance coverage includes the following scenarios;
new or changed behavior must preserve or extend this coverage.

### Direct execution

- Simple executable.
- Arguments containing spaces.
- Empty argument.
- Unicode argument.
- Argument containing shell metacharacters.
- Verify metacharacters are not shell-expanded.

### Shell execution

- Pipeline.
- Redirection.
- `&&`.
- Quoted paths.
- Environment expansion.
- Multiline script.
- Heredoc.

### Working directory

- Workspace root.
- Nested cwd.
- Missing cwd.
- `../` escape.
- Absolute cwd.
- Symlink escape.

### Execution policy

- Omitted `execution` normalizes to `parallel`.
- Parallel commands overlap.
- Sequential commands do not overlap.
- Parallel failure does not cancel siblings.
- Sequential failure does not prevent subsequent commands from running.
- Result order matches input order.

### Exit behavior

- Exit 0.
- Exit 1.
- Exit 127.
- Process terminated by signal.
- Executable missing.
- Spawn failure.

### Timeout

- Long process times out.
- Partial output retained.
- Child processes killed.
- Grandchild processes killed.
- No process remains after timeout.

### Cancellation

- Running command cancelled.
- Tree terminated.
- Partial output retained.
- Queued commands are skipped only after batch cancellation.

### Output

- stdout.
- stderr.
- Interleaving.
- Empty output.
- More than 48,000 characters of output.
- Head preserved.
- Tail preserved.
- Truncation marker.
- UTF-8 sequence split across chunks.
- Very long single output chunk.
- A near-96,000-character complete serialized result reaches the model in at
  most two 48,000-character `ToolTextContent` parts without generic runtime
  truncation or an incorrect `LIMIT_EXCEEDED` result.
- Escape-heavy output and maximum required metadata are accounted for before
  retaining streams, producing valid JSON within the 96,000-character limit.

### Environment

- Required `PATH` inherited.
- Command-specific env override.
- Parent environment unchanged.
- Filtered secret absent.
- Host-authorized secret present when configured.

### Security

- Permission evaluator called.
- Shell command cannot bypass approval policy.
- Sandbox denial returned correctly.
- cwd validation is not treated as sandboxing.

## Commands and Validation

| Check | Command or procedure | Applicability |
| --- | --- | --- |
| Format | `uv run ruff format --check .` | Required for implementation changes |
| Lint | `uv run ruff check .` | Required for implementation changes |
| Type check | `uv run ty check src tests` | Required for implementation changes |
| Tests | `uv run pytest` | Required for implementation changes |
| Documentation | Review this specification and its internal references for accuracy and consistency. | Required |
| Migration or compatibility | Not applicable unless this specification explicitly introduces a migration. | Not applicable by default |
| Manual acceptance | Confirm the recorded acceptance remains accurate when this contract changes materially. | Required for material contract changes |

Documentation-only changes should be reviewed for clarity and consistency.

Implementation changes should use the project quality gate:

- Format: `uv run ruff format .`
- Lint: `uv run ruff check .`
- Type check: `uv run ty check src tests`
- Test: `uv run pytest`

The implementation is covered by focused validator, planner, permission,
environment, output collector, result limiter, process supervisor, and
model-callable runtime adapter tests.

## Execution Boundaries

- Always prefer direct `argv` execution for ordinary programs.
- Always require explicit `shell` mode for shell interpretation.
- Always require explicit `execution` policy for multi-command requests.
- Always keep commands non-interactive with closed stdin in Version 1.
- Always resolve `cwd` relative to the configured workspace and reject canonical
  escapes.
- Always treat cwd validation as distinct from sandboxing.
- Always filter host environment variables by default.
- Always preserve partial output for non-zero exits, timeouts, and cancellation.
- Always terminate complete process trees on timeout and cancellation.
- Always keep permission approval and sandbox policy outside the process executor.
- Ask before exposing detached process management in the public schema.
- Ask before enabling full host environment inheritance by default.
- Ask before allowing model-controlled shell executable selection.
- Ask before adding interactive stdin or PTY semantics.
- Never infer safe shell commands through naïve prefix matching.
- Never automatically retry commands.
- Never use `run_commands` as the preferred mechanism for ordinary file reading,
  source search, or file editing.
- Never drop an entire command result because another command exhausted the output
  budget.

## Success Criteria

- The spec defines `run_commands` as the preferred non-interactive process
  execution primitive for coding-agent verification and project-tooling workflows.
- The public tool interface exposes direct `argv` mode and explicit `shell` mode,
  with exactly one required per command.
- The public tool interface requires explicit `parallel` or `sequential` execution
  policy.
- The command model includes per-command workspace-relative `cwd`, per-command
  environment overrides, and per-command timeout overrides.
- The runtime model includes closed stdin, no default PTY, no public detach mode in
  Version 1, process-tree cancellation, one authoritative deadline, and
  graceful-to-forced termination.
- The environment model filters host variables by default and keeps command
  overrides local to the child process.
- The permission and sandbox model makes approval, safe-command classification,
  network policy, and OS containment explicit host responsibilities.
- The output model preserves ordered stdout/stderr events, UTF-8-safe head and
  tail output, partial timeout/cancellation output, truncation metadata, a fair
  aggregate batch output cap, and failed-command diagnostics.
- The result contract includes stable statuses, success semantics, exit codes,
  signal metadata, durations, command previews, skipped reasons, spawn errors,
  and infrastructure error codes.
- The architecture separates validation, planning, permissions, environment
  building, process supervision, output collection, result limiting, and host UI
  progress concerns.
- Future acceptance tests are explicit enough to drive implementation.

## Deferred future questions

The following items are explicitly non-blocking and must not weaken the accepted
Version 1 contract.

### FQ-01: Preferred strong-containment mechanisms

- **Status:** Non-blocking.
- **Owner:** Engineering and security review.
- **Decision needed:** Select preferred sandbox mechanisms for local macOS, Linux,
  and Windows execution if strong containment becomes required.
- **Impact:** Does not alter the baseline process-execution interface or its
  default-deny preflight policy.

### FQ-02: Retained stream-event format

- **Status:** Non-blocking.
- **Owner:** Engineering.
- **Decision needed:** Define the host-private ordered stream-event envelope used
  for richer stdout/stderr rendering outside the model-visible final result.
- **Impact:** Must not change the separate-stream result contract, output caps,
  truncation metadata, or cancellation semantics.

### FQ-03: Future detached-process lifecycle APIs

- **Status:** Non-blocking.
- **Owner:** Product and engineering.
- **Decision needed:** Decide whether a future tool family exposes detached command
  inspection and termination or keeps long-running process management outside
  `run_commands`.
- **Impact:** Version 1 remains unchanged: no public detached/background process
  lifecycle management is exposed.

## Open Questions

| Question | Impact | Blocking? | Owner | Resolution |
| --- | --- | --- | --- | --- |
| No additional unresolved question is recorded by this migration. | None known. | No | Maintainer | Not applicable |

## Acceptance and Planning Gate

The recorded acceptance in the Status section permits derived planning. A plan remains subordinate to this specification and must not redefine its requirements or success criteria.

## Conventions and Constraints

Follow the project architecture, typing, logging, secret-safety, and validation conventions recorded in `.clinerules/`.

## Project Structure

- Specification: This file under `docs/specs/`.
- Source and test ownership: The detailed architecture section in this specification remains authoritative.
- Documentation ownership: `docs/specs/` and the relevant documentation indexes.
