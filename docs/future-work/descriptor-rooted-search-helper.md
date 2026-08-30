# Future Work: Descriptor-Rooted Search Helper

## Status

Not accepted for implementation. This note records a possible future replacement
for best-effort native ripgrep execution on supported platforms; it is not a
current product guarantee or roadmap commitment.

## Goal

Restore lifecycle-long workspace containment for `search_codebase` on Linux
`x86_64` and macOS Apple Silicon without requiring users to install Bubblewrap,
Docker, Apple Container, or another external runtime.

## Candidate design

Ship Fabrica-owned, signed and checksum-verified native helpers for the supported
platforms. Each helper would open the configured workspace root once and
recursively traverse only through inherited directory file descriptors. It would refuse symlink
following, open children relative to their verified parent directory descriptor,
and read only regular files reached through that descriptor-rooted tree.

The helper should expose a small Fabrica-owned, versioned JSON-event protocol to
the Python adapter rather than emulate the public ripgrep command-line interface.
It would need to preserve the search contract's line-oriented regex behavior,
glob and ignore semantics, deterministic ordering, binary/file-size handling,
limits, cancellation, and bounded output.

## Why it is deferred

The helper is a security-sensitive native component, not a packaging shortcut. It
requires a dedicated design, artifact build/signing/release pipeline, descriptor
traversal and race-regression test matrix, and a decision about how to preserve
ripgrep-compatible regex and ignore semantics. Until those requirements are met,
ADR 0008 intentionally defines direct native ripgrep as best-effort pre-launch
containment only on both supported platforms.

## Acceptance bar for reconsideration

- Demonstrate that post-validation directory and symlink replacements cannot make
  the helper read outside the opened workspace root.
- Preserve the canonical `search_codebase` request/result contract and stable
  error taxonomy without host binary discovery or a fallback regex engine.
- Provide Linux `x86_64` and Apple Silicon builds, artifact integrity verification, and
platform-appropriate signing/release controls for Fabrica distribution.
- Add deterministic unit, integration, and distribution conformance coverage for
  descriptor traversal, ignore/glob behavior, cancellation, output limits, and
  malformed/unavailable artifacts.
- Record the finalized design in a new ADR before replacing the direct native
  backend.
