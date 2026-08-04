# Configuration and secrets management

Use these rules to keep runtime configuration explicit, testable, and separated from the domain and application core.

## Ownership and boundaries

- **Must** keep environment variable reads, secret loading, framework settings access, and config file parsing out of domain entities and application use cases.
- **Must** perform runtime configuration loading in adapters, entry points, bootstrap modules, or composition-root modules.
- **Must** pass validated configuration into application services as explicit constructor arguments, settings DTOs, or port implementations rather than reading global process state inside use cases.
- **Should** keep configuration shape owned by the layer that consumes it: application-owned settings DTOs for core behavior, adapter-owned settings for infrastructure concerns.
- **Should** prefer immutable settings objects once startup validation has completed.

## Settings DTOs and ports

- **Must** define settings DTOs with explicit fields and types when configuration crosses an application boundary.
- **Must not** expose environment variable names, framework settings objects, or secret-manager SDK types through application ports.
- **Should** name settings DTOs by intent, such as `EmailSettings`, `StorageSettings`, or `RetryPolicySettings`, rather than by source.
- **Should** keep secret values as narrowly scoped as possible and avoid passing them through unrelated DTOs or log context.

## Environment-backed adapters

- **Must** keep parsing, defaulting, normalization, and validation for environment-backed settings inside the adapter or bootstrap path that owns the environment source.
- **Must** fail fast at startup or adapter construction time when required configuration is missing or invalid.
- **Should** produce clear validation errors that identify the missing or invalid setting without printing secret values.
- **Should** centralize source-specific mechanics such as environment variable names, config file keys, and secret-manager paths in one adapter-owned module per integration.

## Configuration documentation

- **Must** maintain a canonical settings reference under `docs/` when a project has an explicit runtime settings model.
- **Must** document every settings model option in that reference, including environment variable name, field name, type or format, required/default behavior, safe example value, secret/redaction status, and runtime usage.
- **Must** keep the main project documentation, usually root `README.md`, linked to the canonical settings reference.
- **Must** maintain a root `.env.example` that lists all supported environment variables with safe example values.
- **Must** keep the settings reference, `.env.example`, settings model, and settings tests synchronized when configuration changes.
- **Must not** include real secrets, tokens, private keys, production credentials, or private endpoints in `.env.example` or documentation examples.

## Secret safety

- **Must not** commit real secrets, tokens, passwords, private keys, or production credentials.
- **Must not** log, trace, metric-label, print, or include raw secret values in exception messages.
- **Must** redact secrets before including configuration-derived values in diagnostics.
- **Should** use placeholders in examples, tests, and documentation.
- **Should** document required configuration keys and secret sources without exposing real values.

## Validation and testability

- **Must** validate required configuration before starting long-running workers, serving traffic, or running scheduled jobs.
- **Must** cover configuration parsing and validation with focused tests when defaults, coercion, or secret-source behavior is non-trivial.
- **Should** test application use cases with explicit settings DTOs or fake ports rather than mutating process environment globally.
- **Should** isolate process-environment mutation in tests with fixtures or monkeypatching that restores state after each test.

## Relationship to neighboring rules

- Use `003-architecture-guardrails.md` for dependency direction, composition-root placement, and ports/adapters boundaries.
- Use `013-logging-conventions.md` for logger structure, safe context fields, and redaction expectations.
- Use `011-tooling-and-ci.md` for dependency and CI policy around libraries used to parse or validate settings.
