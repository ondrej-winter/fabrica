# Cline command execution

These rules govern how Cline executes commands. Repository-wide safety policy
remains in `../AGENTS.md`.

- Do not stream multiline scripts into a shell or interpreter. Write non-trivial
  helper scripts to a workspace-local trace or scratch file, then execute that
  file with an explicit command.
- Do not pipe remote downloads directly into a shell or interpreter. Download,
  inspect, and execute them only when explicitly required.
- Prefer direct non-interactive commands. Do not open editors, pagers, watchers,
  or prompts unless the user requests an interactive workflow.
- Disable Git paging, for example with `git --no-pager`, and use non-interactive
  Git options when available.
- Do not run commands that modify Git's index, refs, or history, including
  `git add`, `git restore --staged`, `git commit`, and `git reset`, unless the
  user explicitly requests that exact operation. Leave changes unstaged for the
  user to inspect and stage.
