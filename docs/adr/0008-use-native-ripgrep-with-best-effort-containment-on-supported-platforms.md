# 0008. Use Native Ripgrep With Best-Effort Containment on Supported Platforms

Date: 2026-08-30
Status: Accepted

Supersedes [0007](./0007-use-native-macos-ripgrep-with-explicit-best-effort-containment.md).

## Context

`search_codebase` must work as an ordinary local developer tool on each supported
platform. ADR 0007 retained Bubblewrap lifecycle-long workspace containment on
Linux `x86_64` while moving macOS Apple Silicon to direct execution of Fabrica's
verified native `ripgrep` package data.

Bubblewrap adds a host-runtime dependency and requires namespace capabilities
that are unavailable or inconvenient in common local and containerized Linux
environments. Requiring it makes Linux materially harder to operate than macOS
without changing the trust model for a developer-controlled workspace enough to
justify the friction.

The project must still preserve pinned Rust-regex semantics, avoid host `rg`
discovery and shell execution, validate literal workspace-relative scopes, and
state filesystem-safety limitations accurately.

## Decision

Fabrica will execute its checksum-verified, pinned package-data `ripgrep`
payload directly on both supported platforms: Linux `x86_64` and macOS Apple
Silicon.

- Before execution, Fabrica validates the requested literal workspace-relative
  scope and rejects absolute paths, traversal, missing targets, special files,
  and resolved symlink escapes.
- The verified executable receives fixed argv with `--no-config` and
  `--no-follow`, plus only the validated canonical scope.
- Both supported platforms provide **best-effort pre-launch containment**. Neither
  guarantees resistance to malicious concurrent pathname or symlink replacement
  after validation and during recursive traversal.
- Bubblewrap is not a Fabrica installation or runtime requirement.
- Unsupported platforms and missing, malformed, unexecutable, or checksum-invalid
  Fabrica payloads fail closed with `SEARCH_BACKEND_UNAVAILABLE`.

## Consequences

- Linux and macOS now have the same package-only runtime model and the same
  explicitly limited containment guarantee.
- Linux distribution conformance can run in a standard Linux `x86_64`
  environment without Bubblewrap or privileged namespace support.
- `search_codebase` remains suitable for developer-controlled workspaces, not a
  hostile multi-tenant filesystem or a threat model requiring concurrent-mutation
  resistance.
- The descriptor-rooted helper investigation now applies to both supported
  platforms as the future path to stronger containment.

## Alternatives considered

| Option | Reason rejected or deferred |
| --- | --- |
| Retain Linux Bubblewrap | It introduces a runtime dependency and namespace-capability requirement inconsistent with the package-only macOS path. |
| Require Docker for Linux search | Docker is an external runtime with comparable operational friction and does not strengthen ordinary host execution. |
| Descriptor-rooted Fabrica helper | Potentially restores stronger containment, but requires a dedicated security-reviewed native design and artifact pipeline. |
| Discover or use host-installed ripgrep | Makes semantics, versioning, and trust vary by host. |
