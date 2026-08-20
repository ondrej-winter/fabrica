# Spec: Run Commands Tool

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

## Current context

- Project: `fabrica`, a Python 3.13 local agent runtime experiment using a
  `src/` layout and hexagonal architecture organized by vertical slices.
- Runtime direction is owned by `docs/specs/agent-runtime.md`.
- Filesystem reading is owned by `docs/specs/read-files-tool.md`.
- Textual source discovery is owned by `docs/specs/search-codebase-tool.md`.
- Filesystem mutation is owned by `docs/specs/apply-patch-tool.md`.
- This spec defines the desired `run_commands` tool contract only. It does not
  implement the tool.
- `run_commands` is the verification and project-tooling counterpart to the
  read/search/edit tools. It should not replace them for ordinary reading,
  searching, or editing work.
- The public contract must be closed enough that future implementation work can
  start from focused acceptance tests rather than rediscovering core semantics.

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

## Desired behavior

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
3. Explicit sequential or parallel execution policy.
4. Per-command workspace-relative `cwd`.
5. Filtered environment inheritance.
6. Non-interactive deterministic execution.
7. Process-tree timeout and cancellation semantics.
8. Structured ordered output with bounded context consumption.
9. Permission and sandbox boundaries outside the executor.
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
      "enum": ["parallel", "sequential"]
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
  "required": ["execution", "commands"],
  "additionalProperties": false
}
```

Defaults:

```text
cwd        = "."
env        = {}
timeout_ms = 30000
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
MAX_COMMAND_OUTPUT_CHARS   = 48,000
MAX_BATCH_OUTPUT_CHARS     = 96,000
```

The public schema must make direct argv and shell execution first-class and
mutually exclusive. It must not rely on hidden conventions such as “presence of an
`args` key means direct execution”.

Schema validation alone is not the complete input contract. The host must also
normalize and validate every command before any process starts:

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

Specify whether multiple commands are sequential or parallel. Use parallel only
for independent commands.

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

Array semantics must not be implicit. The request must specify `parallel` or
`sequential` execution.

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

Default sequential failure behavior:

```text
stop_on_error = true  # fixed Version 1 behavior; not a model-controlled field
```

For sequential execution, any unsuccessful command stops the sequence. This
includes non-zero exit, timeout, cancellation, spawn failure, permission denial,
sandbox denial, and invalid per-command planning results. If command A fails,
commands B and C are skipped. Skipped commands return:

```json
{
  "status": "skipped",
  "success": false,
  "exit_code": null,
  "reason": "PREVIOUS_COMMAND_FAILED"
}
```

Stable skipped reasons are:

- `PREVIOUS_COMMAND_FAILED`;
- `PREVIOUS_COMMAND_TIMED_OUT`;
- `PREVIOUS_COMMAND_CANCELLED`;
- `PREVIOUS_COMMAND_SPAWN_FAILED`;
- `PREVIOUS_COMMAND_DENIED`;
- `BATCH_CANCELLED`;
- `BATCH_TIMED_OUT`.

If the agent genuinely wants shell-level transactional sequencing, it can use a
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

Additional variables should be supplied explicitly by host policy. For trusted
developer-local operation, the host may enable `inherit_full_environment = true`,
but this must be a conscious runtime policy.

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
  "output": "...partial command output...",
  "duration_ms": 30018
}
```

Cancellation result example:

```json
{
  "status": "cancelled",
  "success": false,
  "exit_code": null,
  "output": "...partial output..."
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

The retained output for a command must include at most one truncation marker. The
marker counts toward `retained_output_chars`; `total_output_chars` records decoded
characters observed before any per-command or aggregate limiting.

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

A compact final result may return one ordered output field:

```text
starting tests...
[stderr] warning: ...
test_a PASSED
test_b FAILED
```

with metadata:

```json
{
  "stdout_chars": 8104,
  "stderr_chars": 213,
  "total_output_chars": 8317
}
```

Do not return `stdout`, `stderr`, and `combined_output` simultaneously in the
model-visible final result because that duplicates provider tokens. The host UI
may retain richer structured stream events separately.

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

## Aggregate output limiting

Recommended aggregate limit:

```text
MAX_BATCH_OUTPUT_CHARS = 96,000
```

Always preserve command status, exit code, duration, error code, and truncation
metadata before allocating context budget to output.

If aggregate output exceeds the tool budget, further truncate individual outputs
using head-and-tail semantics. Never drop an entire command result merely because
another command was verbose.

Aggregate limiting should be fair and deterministic:

1. Preserve every command result object and all status, duration, exit, signal,
   error, and truncation metadata.
2. Reserve a small output allowance for every command that produced output.
3. Allocate remaining output budget in input order or another documented stable
   policy.
4. When reducing an individual command's retained output, use the same head and
   tail strategy and update `output_truncated`, `retained_output_chars`, and
   `batch_output_truncated`.

The limiter must never remove a failed command's diagnostic output merely because
a successful sibling produced more output.

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
      "output": "128 passed in 3.72s\n",
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
      "output": "src/foo.py:28: F401 ...",
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
- `output`;
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

Likely future implementation ownership:

- Spec: `docs/specs/run-commands-tool.md`.
- Runtime tool contracts and DTOs: under
  `src/fabrica/features/agent_runtime/application/` if exposed as a model-callable
  runtime tool.
- Process execution, OS-specific process-tree handling, sandbox integration, and
  platform shell invocation: adapter or infrastructure code, not domain or
  application core.
- Permission policy integration: application-owned policy port plus adapter-owned
  UI or host approval mechanism.
- Unit tests: mirrored under `tests/unit/` for validation, planning, environment
  filtering, result limiting, output collection, and permission decisions.
- Integration tests: under `tests/integration/` for real subprocess behavior,
  process-tree termination, shell behavior, environment filtering, cwd
  containment, cancellation, and timeout checks.

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
- no unlimited aggregate batch output;
- do not require shell syntax for simple `cwd` or `env` use cases.

Add these requirements beyond current Cline behavior:

- explicit `argv` mode;
- explicit `shell` mode;
- explicit parallel/sequential execution;
- per-command workspace-relative `cwd`;
- per-command environment;
- structured status;
- structured exit code;
- structured duration;
- partial timeout/cancellation output;
- filtered environment provider;
- aggregate output budget;
- explicit permission evaluator;
- explicit sandbox boundary;
- graceful-to-forced process-tree termination.

## Testing strategy

Required future acceptance tests include the following scenarios.

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

- Parallel commands overlap.
- Sequential commands do not overlap.
- Parallel failure does not cancel siblings.
- Sequential failure skips subsequent commands.
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
- Queued sequential commands skipped.

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

## Commands and validation

Documentation-only changes should be reviewed for clarity and consistency.

Implementation changes should use the project quality gate:

- Format: `uv run ruff format .`
- Lint: `uv run ruff check .`
- Type check: `uv run ty check src tests`
- Test: `uv run pytest`

Future implementation should start with focused validator, planner, permission,
environment, output collector, result limiter, and process supervisor tests before
adding a model-callable runtime adapter.

## Boundaries

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

## Success criteria

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

## Open questions

- What exact host policy should decide when direct `argv` commands can be
  auto-approved?
- Should shell mode always require approval in Version 1, or can a host opt into a
  real shell-grammar-based classifier?
- Which environment variables should Fabrica's default `EnvironmentFilter` allow
  beyond the minimal cross-platform set?
- Should `inherit_full_environment` exist only in developer-local profiles, and
  how should the UI disclose it?
- What sandbox mechanism should be preferred for local macOS, Linux, and Windows
  execution if strong containment becomes required?
- What exact structured event format should the host retain for richer stdout and
  stderr stream rendering outside the compact final model-visible result?
- Should future lifecycle APIs expose detached command inspection and termination,
  or should long-running process management remain outside this tool family?
