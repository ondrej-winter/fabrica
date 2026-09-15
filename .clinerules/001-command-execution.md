# Cline command execution

These rules govern how Cline executes commands. Repository-wide safety policy,
including Git authorization and remote-execution restrictions, lives in `AGENTS.md`
at the repository root.

- Do not stream multiline scripts into a shell or interpreter. Write non-trivial
  helper scripts to a workspace-local trace or scratch file, then execute that
  file with an explicit command.
- Prefer direct non-interactive commands. Do not open editors, pagers, watchers,
  or prompts unless the user requests an interactive workflow.
- Disable Git paging, for example with `git --no-pager`, and use non-interactive
  Git options when available.
