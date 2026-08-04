# Command execution safety

Use these rules to keep command execution safe, explicit, traceable, and non-interactive in any workspace.

This rule is intentionally atomic. It applies to shell commands, interpreter invocations, version-control commands, remote installers, generated scripts, and other process execution regardless of programming language or project architecture.

## Hard constraints

- **Must not** stream multiline scripts directly into a shell or interpreter.
- **Must not** run inline interpreter heredocs such as `python - <<'PY' ... PY`, `uv run python - <<'PY' ... PY`, or similar multiline stdin-fed execution patterns.
- **Must not** use equivalent shell patterns such as `cat <<'SH' | bash`, `printf '...' | sh`, or other non-one-liner script streaming into the terminal.
- **May** run a direct one-liner command when it is simple, explicit, and does not depend on streamed multiline content.
- **Must** write script content to a file and execute that file when the command is not a straightforward one-liner.
- **Must** create generated helper scripts in a workspace-local trace directory using a descriptive directory name, timestamped filename, and appropriate file extension.
- **Must** prefer direct, non-interactive CLI commands where possible before creating any script.
- **Must not** pipe remote scripts directly into a shell or interpreter, for example `curl ... | sh`. Download, inspect, and execute only when explicitly required.
- **Must** run version-control commands in non-interactive mode whenever possible and avoid waiting for user input.
- **Must** disable paging when command output could invoke a pager, for example `git --no-pager <command>`.
- **Must not** run commands that open interactive editors or prompts unless explicitly requested by the user.
- **Must** treat file paths, branch names, search text, and other interpolated values as untrusted input; quote or sanitize them appropriately and avoid `eval`-style shell construction.
- **Should** use dry-run, preview, or listing variants before destructive commands when feasible.
- **Should** keep generated helper scripts available for traceability unless there is a clear reason to remove them.

## Required file-based execution pattern

Preferred approach:

1. Decide whether the command is a true one-liner. If not, write it to a file.
2. Create a helper script under a workspace-local trace directory using a path like `<execution-log-dir>/<descriptive-name>/timestamp-<suffix>.<ext>`.
3. Use an extension that matches the interpreter or shell, such as `.py`, `.sh`, or `.js`.
4. Execute the file with an explicit command such as `<interpreter> <absolute-path-to-script>`.
5. Capture output and exit code as needed.

Example paths:

- `<execution-log-dir>/inspect-project/timestamp-20260415T082853.py`
- `<execution-log-dir>/shell-check/timestamp-20260415T082853.sh`

If the host workspace defines a command log or scratch directory, use that location. Otherwise, choose a workspace-local path that is easy to identify and exclude from committed source if appropriate.

## Disallowed streamed execution patterns

Forbidden approach:

- `python - <<'PY'`
- `uv run python - <<'PY'`
- `cat <<'SH' | bash`
- `printf '%s\n' '...' | python`
- Any multiline script passed directly via stdin to a shell or interpreter.

## Allowed direct execution pattern

Allowed when the command is a real one-liner:

- `python -c "print('ok')"`
- `uv run python -c "from pathlib import Path; print(Path.cwd())"`
- `jq '.items | length' file.json`

Do not stretch the idea of a one-liner to avoid creating a file. If readability or safety is starting to suffer, write the script to a file and run that file.

## Version-control non-interactive pattern

Preferred approach:

- `git --no-pager diff --stat`
- `git --no-pager log --oneline -n 20`
- `git commit --no-edit` only when this behavior is explicitly appropriate

Avoid when not explicitly requested:

- Commands that trigger pagers, prompts, or interactive editors.

## Destructive and remote command safety

- Prefer commands scoped to explicit files, directories, refs, or resources instead of broad globs or repository-wide destructive operations.
- Call out commands that mutate state, such as `rm`, `mv`, recursive permission changes, hard resets, schema migrations, or deploys, before running them and double-check the target.
- Prefer explicit timeouts, non-interactive flags, and machine-readable output modes when the tool supports them.

## Enforcement

- Treat this rule as a hard constraint in reviews and operational practice.
- Any deviation must be explicitly requested and documented in handoff or PR notes.
