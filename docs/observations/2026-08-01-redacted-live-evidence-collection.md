# Redacted live evidence collection: 2026-08-01

This note is the next manual evidence slice for the subscription-backed Python
agent runtime viability gate. It records only explicitly requested, redacted live
validation results.

Do not paste raw credentials, auth headers, cookies, backend payloads, account
identifiers, private absolute paths, raw script contents, screenshots with
personal data, or billing/account details into this note.

## Collection status

`repeated_transport_runtime_cli_success`

## Scope

- Validation category targets: transport, runtime, optional CLI, and reactive
  usage/quota observations.
- Required session coverage before any `go` or `conditional_go` recommendation:
  at least two successful live runs across separate local sessions.
- Current decision label can move to `conditional_go` after these repeated
  redacted live observations are reviewed with caveats preserved.

## Manual prerequisites

- Confirm this live collection is intentional.
- Authenticate locally when needed with `codex login`.
- Use safe session labels such as `session-1` and `session-2`.
- Record only normalized statuses, safe status/header field names, bounded error
  summaries, and high-level request/response shape notes.

## Observation rows

Add one row per explicit live validation command. Keep observed facts separate
from interpretation.

| Session | Category | Command path | Normalized status | Successful | Reactive usage/quota signal | Safe notes |
| --- | --- | --- | --- | --- | --- | --- |
| `session-1` | transport | `make test-live-codex` | success | yes | not_observed | Explicit live transport probe passed and verified bounded expected output `pong`; no raw backend payloads, credentials, account identifiers, or private paths were recorded. |
| `session-1` | runtime | `make test-live-runtime` | success | yes | not_observed | Explicit live Codex-backed runtime test passed and verified bounded expected output `pong`; no raw backend payloads, credentials, account identifiers, or private paths were recorded. |
| `session-1` | cli | `make run-live-cli PROMPT="Reply with the single word: pong"` | success | yes | not_observed | Explicit live CLI run returned bounded expected output `pong`; no raw backend payloads, credentials, account identifiers, or private paths were recorded. |
| `session-2` | transport | `make test-live-codex` | success | yes | not_observed | Explicit separate-session live transport probe passed and verified bounded expected output `pong`; no raw backend payloads, credentials, account identifiers, or private paths were recorded. |
| `session-2` | runtime | `make test-live-runtime` | success | yes | not_observed | Explicit separate-session live Codex-backed runtime test passed and verified bounded expected output `pong`; no raw backend payloads, credentials, account identifiers, or private paths were recorded. |
| `session-2` | cli | `make run-live-cli PROMPT="Reply with the single word: pong"` | success | yes | not_observed | Explicit separate-session live CLI run returned bounded expected output `pong`; no raw backend payloads, credentials, account identifiers, or private paths were recorded. |

## Safe failure categories

Use these categories if a live run fails:

- `auth_failure`
- `rate_limit_or_quota`
- `backend_shape_mismatch`
- `transport_error`
- `other`

Include only bounded, redacted summaries. Do not include raw backend JSON,
headers, cookies, tokens, credential file content, account IDs, private paths, or
screenshots with personal data.

## Interpretation

Observed facts:

- This note has been prepared for manual collection.
- Explicitly requested `session-1` live transport, runtime, and CLI validation
  runs succeeded with bounded expected output `pong`.
- Explicitly requested `session-2` live transport, runtime, and CLI validation
  runs succeeded with bounded expected output `pong`.
- No reactive usage/quota live failure or safe quota signal was observed in these
  successful runs.

Interpretation:

- The viability gate now has repeated successful live validation across two
  separately labeled local sessions.
- The evidence supports `conditional_go` rather than `go` because billing
  attribution remains ambiguous and public Responses API comparison remains
  source-limited.

Recommended decision label: `conditional_go`

Follow-up needed:

- Keep future live validation opt-in and redacted.
- Revisit `2026-08-01-codex-runtime-viability-decision.md` if a blocking
  normalized failure appears or stronger billing/source evidence becomes
  available.
