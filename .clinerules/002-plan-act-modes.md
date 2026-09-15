# Cline Plan and Act modes

The mode selected for the user's newest message governs the current turn. A mode
switch overrides the mode used for earlier messages.

## Plan mode

- Limit work to read-only inspection, analysis, clarification, and planning.
- Do not create, modify, move, or delete files, and do not run commands that
  change repository, workspace, dependency, build, report, cache, or Git state.
- End a plan that requires mutation by asking the user to toggle to Act mode.
  Cline cannot switch modes on the user's behalf.

## Act mode

- Before editing, re-check Git status and re-read the affected files if they may
  have changed since planning.
- Apply the approved work while continuing to follow `AGENTS.md`, the selected
  task procedures, and all command-safety constraints.
