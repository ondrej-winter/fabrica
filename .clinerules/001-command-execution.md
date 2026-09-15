# Cline command execution

These rules govern how Cline executes commands. Repository-wide safety policy,
including Git authorization and remote-execution restrictions, lives in `AGENTS.md`
at the repository root.

- Treat `run_commands` as non-interactive. Never launch an editor, pager, watcher,
  prompt, or other process that waits for terminal input through it, even when the
  user requests an interactive workflow. Explain the limitation or use a supported
  host interaction mechanism instead.
- Prefer direct, readable one-line commands. Do not stream multiline scripts into
  a shell or interpreter, including through heredocs or piped standard input.
- In Act mode, when a non-trivial helper script is necessary, create it with a
  file-writing tool under the ignored `.tmp/cline/` directory. Use a descriptive
  filename and execute it with an explicit command containing its absolute path.
- In Plan mode, do not create helper files. Use a straightforward read-only
  command when possible; otherwise describe and defer the command until Act mode.
- Disable Git paging, for example with `git --no-pager`, and use non-interactive
  Git options when available.
