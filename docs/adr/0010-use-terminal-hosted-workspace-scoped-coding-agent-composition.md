# 0010. Use Terminal-Hosted Workspace-Scoped Coding-Agent Composition

Date: 2026-09-08
Status: Accepted

## Context

Fabrica has accepted and largely implemented provider-neutral agent runtime,
workspace read/search/command primitives, journaled patch mutation, and
in-memory user interaction. These capabilities are currently exposed as
independent bootstrap composition APIs, while the public `fabrica run` command
performs a one-shot runtime prompt without workspace coding tools.

Leaving the coding workflow solely to custom hosts prevents developers from using
Fabrica as a complete local coding agent. Conversely, exposing all existing tools
through a generic CLI without workspace scope, explicit approval, and terminal
interaction would turn safe primitives into ambient authority.

## Decision

Fabrica will ship a first-class `fabrica agent` command as an interactive,
terminal-hosted coding-agent session bound to one explicitly supplied workspace
root. The command will compose the existing tool-aware runtime with read, search,
policy-governed command execution, terminal-backed `ask_question`, and
capability-gated `apply_patch`.

The terminal host will request an explicit digest-bound approval for every patch
plan. It will not treat `ask_question`, a selected workspace, or an earlier
approval as blanket authorization. Commits, pushes, public web access, and Agent
Skill script execution remain absent from the default coding-session tool set.

## Consequences

- Fabrica gains a coherent developer-facing coding workflow without changing the
  ownership of its existing runtime and tool contracts.
- The product CLI needs a workspace argument, a tool-aware Codex composition, and
  terminal adapters for structured questions and patch approvals.
- Patch mutation remains fail-closed: a failed capability/recovery gate leaves a
  usable read-only session rather than weakening mutation guarantees.
- Command execution must receive an explicit terminal-host policy; the session
  cannot use an unrestricted shell as its safety model.
- The default tool set stays narrow. New default capabilities require an accepted
  policy decision and tests rather than being added incidentally.
- Offline end-to-end tests must cover session composition, approval denial, and
  mutation-gate failure; live Codex validation remains opt-in.

## Alternatives considered

| Option | Reason rejected |
| --- | --- |
| Keep coding-agent composition custom-host-only | It leaves the project without a usable local coding-agent product workflow and repeats host integration work for every developer. |
| Extend `fabrica run` implicitly with workspace tools | It would change a direct prompt command into a stateful mutating workflow without a clear public contract or safety boundary. |
| Expose all tools and rely on one session-wide approval | Workspace selection and a single approval do not safely authorize later commands, changed patches, Git mutation, scripts, or network access. |
| Build a VS Code or web host first | A terminal host provides the smallest inspectable interactive surface while retaining future host-adapter options. |
