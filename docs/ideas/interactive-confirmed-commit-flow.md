# Interactive Confirmed Commit Flow

## Problem Statement

How might we let a developer turn the generated `fabrica commit-message`
recommendation into an actual git commit only after explicit interactive
approval, without weakening the current staged-only evidence flow or committing
accidentally?

## Recommended Direction

Add a separate `fabrica commit` command that reuses the existing evidence-first
commit-message generation workflow, displays the generated recommendation, and
then asks the developer to confirm before mutating git state.

This keeps the existing `fabrica commit-message` command as a safe, read-only
preview workflow while making the mutating flow obvious from the command name.
On confirmation, the new command runs `git commit` with the generated message.
On rejection, EOF, or any answer other than an explicit yes, it exits without
creating a commit or changing staged files.

## Key Assumptions to Validate

- [ ] The generated `CommitMessageRecommendation.commit_message` is directly
      suitable for `git commit`.
      Test with unit and integration coverage that the exact generated message is
      passed to the git commit port, including any body text.
- [ ] Developers will understand that `fabrica commit` mutates repository state
      while `fabrica commit-message` remains read-only.
      Test through CLI help text and README examples that make the distinction
      explicit.
- [ ] Rejection should leave the repository untouched.
      Test with a temporary git repository that answering no creates no commit and
      preserves the staged changes.
- [ ] The first version does not need editing or regeneration.
      Validate through manual use; if users often reject messages that are close
      but not quite right, consider adding edit or regenerate flows later.

## MVP Scope

The minimum useful version is a new interactive `fabrica commit` command.

In scope:

- Reuse existing staged-only, evidence-first commit-message generation.
- Display the generated summary, rationale, and final commit message before any
  mutation.
- Prompt with a conservative default such as `Commit with this message? [y/N]`.
- Treat only explicit `y` or `yes` as approval.
- Run `git commit` with the generated message after approval.
- Exit without changes on rejection, empty input, EOF, or interrupted input.
- Keep git subprocess execution in a developer-workflow outbound adapter.
- Cover approve, reject, no staged changes, and git failure behavior with tests.
- Update README usage documentation because the new command mutates repository
  state.

Out of scope for the MVP:

- Editing the generated message before committing.
- Regenerating a new message after rejection.
- Staging unstaged files or modifying the index.
- Auto-pushing after commit.
- Bypassing or customizing git hooks.
- JSON output or non-interactive automation modes.

## Not Doing and Why

- Extending `fabrica commit-message` to commit by default — this would blur the
  current command's read-only safety contract.
- Adding an edit-before-commit prompt — useful later, but it introduces multiline
  input and editor behavior before the core confirmation flow is proven.
- Adding regenerate-on-reject — this increases model cost, latency, and retry
  semantics before there is evidence that rejection usually means "try again."
- Auto-staging changes — the workflow should remain scoped to the developer's
  explicit staged intent.
- Auto-push — committing and publishing are separate risk boundaries.

## Open Questions

- Should the command be named exactly `fabrica commit`, or should it use a more
  explicit verb such as `fabrica commit-confirmed` during the experimental phase?
- Should cancellation return exit code `0` as a neutral no-op or a distinct
  non-zero code for scripts?
- How should multiline commit bodies be passed to git: repeated `-m` arguments, a
  temporary commit-message file, or stdin to `git commit --file -`?
- Should the confirmation prompt show only the final commit message, or the full
  summary/rationale/message block?
- Should the implementation eventually support an explicit non-interactive flag,
  or should automation continue using `fabrica commit-message` plus manual git
  commands?
