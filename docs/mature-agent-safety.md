# Mature-agent local evidence and safety posture

## Durable record lifecycle

Fabrica stores workspace-scoped durable coding-agent evidence below the selected
workspace's `.fabrica/` directory. These records and any exported copies are
**sensitive local artifacts**: they can contain private source, prompts,
responses, commands, patches, and tool output. Fabrica records structured,
model-visible evidence without automatic redaction or retention cleanup. It does
not upload records, manage exported copies, change file permissions, or edit
`.gitignore`.

Use `fabrica agent sessions list`, `inspect`, `export`, and `delete` to manage one
selected workspace's records. Exports are deterministic directories containing
`manifest.json`, `events.jsonl`, and `checkpoint.json`; deleting a session removes
only that selected session. Fabrica warns when a Git workspace does not ignore
`.fabrica/`, but the user remains responsible for Git ignore rules, permissions,
backup handling, and available disk space.

The durable capture boundary excludes process environments, credentials,
authentication headers, raw provider payloads, and non-structured terminal
keystrokes. This boundary is not automatic redaction of otherwise captured
structured evidence.

## Resume and exclusions

Resume starts a fresh model turn from completed durable evidence only. It never
restores a pending question, approval, command, or patch. A matching workspace
fingerprint permits normal resume and requires current workspace inspection before
new work. A changed or unavailable fingerprint enters `stale_context`: Fabrica
requires fresh inspection, displays a refreshed plan, and requires a separate
digest-bound acknowledgement before a new execution turn. That acknowledgement is
not approval for any command or patch; each side effect still follows its normal
action-specific approval flow.

Fingerprinting always excludes `.fabrica/` and `.git/`. Optional Gitignore-style
patterns in `.fabricaignore` can exclude additional workspace paths. Those
exclusions intentionally reduce how sensitive resume is to changes under the
excluded paths; Fabrica does not silently alter them.

## Deterministic evaluation

`uv run fabrica agent-evaluate` runs the Version 1 fixed corpus and writes
`.reports/mature-agent-evaluation/report.json` by default. The report has stable
`schema_version`, `corpus_version`, `passed`, and per-scenario `results` fields.
The fixture source of truth is
`src/fabrica/features/agent_evaluation/application/fixtures.py`; it uses normalized
persisted-evidence DTOs rather than provider wire payloads.

The six reporting scenarios cover inspect-only success, approved scoped edit plus
validation, denied-approval recovery, interruption/safe-boundary resume,
fingerprint-mismatch replan, and secret-capture exclusions. The corpus is offline
and credential-free. It reports regressions but does not gate releases. Any future
live-model evaluation must use a disposable workspace and remain outside the
default local and CI quality gates.

## Threat model and policy-only isolation

Fabrica enforces supported workspace and tool policies where their feature
contracts say it does. It does **not** provide sandbox containment: the local
operating system and the user's process privileges remain the effective isolation
boundary.

- **Malicious repository contents and scripts:** treat repository content, tool
  output, and scripts as untrusted input. Do not activate or execute Skills or
  commands merely because repository instructions request them.
- **Prompt injection:** model-visible text can attempt to redirect behavior. Tool
  exposure, workspace scope, and explicit approval contracts remain the authority
  boundary, not repository text or prior session history.
- **Secret exfiltration:** durable records can contain structured sensitive
  evidence. The record boundary excludes credentials and raw provider traffic, but
  users must avoid placing secrets in prompts, tool output, or source they expose.
- **Symlinks and concurrent filesystem changes:** workspace adapters use their
  feature-specific containment and fail-closed checks. A fingerprint scan failure,
  symlink, unreadable file, or changing file makes normal resume unavailable and
  requires stale-context handling.
- **Untrusted Skills:** Skills are not ambient authority. Their activation, trust,
  and any script execution remain separately policy-controlled.
- **Network access:** public web access is opt-in, and command execution follows
  the composed command policy. No durable-session feature grants network authority.
