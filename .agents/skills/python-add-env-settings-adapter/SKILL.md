---
name: python-add-env-settings-adapter
description: Add an environment-backed runtime settings adapter to a Python hexagonal vertical-slice app or library, using a configuration slice, application-owned settings DTOs, pydantic-settings adapter validation, and focused tests.
metadata:
  version: "1.0.1"
  dependencies:
    tools:
      - name: python
        purpose: Implement and validate the Python settings adapter and templates.
        required: true
      - name: pydantic-settings
        purpose: Parse and validate environment-backed runtime settings.
        required: true
      - name: pytest
        purpose: Run the supplied settings DTO and adapter test patterns.
        required: true
      - name: uv
        purpose: Run project-managed Python quality commands when available.
        required: false
      - name: ruff
        purpose: Lint the resulting Python implementation when available.
        required: false
      - name: mypy
        purpose: Type-check the resulting Python implementation when available.
        required: false
    skills:
      - name: python-add-adapter
        purpose: Add an adapter when the configuration boundary already exists.
        required: false
      - name: run-python-quality-gate
        purpose: Run the full Python validation pass when available.
        required: false
      - name: update-project-docs
        purpose: Update user-facing and operator-facing configuration documentation.
        required: false
      - name: write-adr
        purpose: Record a durable configuration architecture decision.
        required: false
---

# Add an Environment Settings Adapter

Use this skill when a Python hexagonal application or library needs runtime
configuration loaded from environment variables or a `.env` file.

This skill follows a concrete env settings adapter pattern:

- the owning configuration slice's application layer owns the runtime settings
  DTO and configuration exception,
- the owning configuration slice's inbound adapter owns `pydantic-settings`,
  environment aliases, parsing, and validation,
- the adapter entry point stays thin and maps validated adapter settings to the
  application DTO,
- tests isolate the process environment and `.env` lookup.

Use `assets/` templates as starting points, then adapt fields, aliases,
defaults, validation rules, and package paths to the target project.

## Prerequisites

- The project follows a Python hexagonal vertical-slice layout with
  `src/<app_name>/features/` or a documented equivalent.
- Runtime configuration requirements are known well enough to identify required
  values, defaults, and validation rules.
- The project either already uses `pydantic-settings` or the user has approved
  adding it as a dependency.

## Target structure

```text
src/<app_name>/
└── features/
    └── runtime_configuration/
        ├── application/
        │   ├── dtos/
        │   │   ├── __init__.py
        │   │   └── app_settings.py
        │   └── exceptions.py
        └── adapters/
            └── inbound/
                └── env_settings_adapter/
                    ├── __init__.py
                    ├── adapter.py
                    └── settings.py

tests/unit/
└── features/
    └── runtime_configuration/
        ├── application/dtos/test_app_settings.py
        └── adapters/inbound/env_settings_adapter/test_env_settings.py

docs/
└── configuration.md

README.md
.env.example
```

Use `runtime_configuration` as the default slice name unless the project already
has a documented configuration slice. Adjust paths to match the repository's
existing test layout. Keep the same responsibilities and dependency direction.

## Steps

### 1. Define application-owned settings

Create or update
`src/<app_name>/features/runtime_configuration/application/dtos/app_settings.py`
from `assets/app_settings.template.py`.

The DTO should:

- represent runtime settings consumed by application services,
- use application-friendly types such as `Path`, `str`, `int`, `float`, `bool`,
  `Enum`, or `Literal`,
- keep application defaults in one canonical place,
- stay independent of `pydantic`, environment variables, and framework types.

If the project exposes DTOs from the configuration slice's
`application/dtos/__init__.py`, export `AppSettings` there following the local
pattern.

### 2. Add or reuse a configuration exception

If the project does not already have an application-level configuration error,
add one to
`src/<app_name>/features/runtime_configuration/application/exceptions.py` using
`assets/exceptions.template.py` as a guide.

The adapter should translate `pydantic` validation failures into this exception
so callers do not depend on adapter library exception types.

### 3. Create the inbound adapter package

Create
`src/<app_name>/features/runtime_configuration/adapters/inbound/env_settings_adapter/`
with:

- `__init__.py` from `assets/env_settings_adapter_init.template.py`,
- `adapter.py` from `assets/env_settings_adapter_adapter.template.py`,
- `settings.py` from `assets/env_settings_adapter_settings.template.py`.

Replace the example `example_app` package, `example app` display name,
`EXAMPLE_APP` environment prefix, aliases, defaults, and field names with
project-specific values.

### 4. Keep environment parsing in `settings.py`

`settings.py` is the external configuration boundary. It should own:

- environment variable alias constants,
- stable error-message constants,
- `.env` loading settings,
- string trimming and blank rejection,
- path normalization,
- feature-group validation when optional features require bundled settings,
- translation of `ValidationError` to the application `ConfigurationError`.

Use `SettingsConfigDict` with these defaults unless the project needs stricter
behavior:

```python
SettingsConfigDict(
    env_file=".env",
    env_file_encoding="utf-8",
    case_sensitive=False,
    populate_by_name=True,
    extra="ignore",
)
```

Keep `pydantic` and `pydantic-settings` imports inside the adapter package.

### 5. Keep `adapter.py` thin

`adapter.py` should only convert validated `EnvSettings` into `AppSettings`.

Use `settings.model_dump()` when the adapter model contains all defaults that
should be passed through. Use `settings.model_dump(exclude_none=True)` when
optional adapter fields are `None` so application DTO defaults should apply.

Do not duplicate validation or add business logic in `adapter.py`.

### 6. Wire the adapter at the composition root

Update the CLI bootstrap, HTTP startup, worker startup, or other composition root
to:

1. instantiate `EnvSettingsAdapter`,
2. call `load()` once at startup,
3. pass the resulting `AppSettings` into logging setup, service factories, and
   adapters that need runtime configuration.

Keep environment access centralized. Do not scatter `os.getenv()` calls across
the codebase once this adapter exists.

### 7. Test DTO defaults and adapter behavior

Create or update tests from:

- `assets/test_app_settings.template.py`,
- `assets/test_env_settings.template.py`.

Adapter tests should use `monkeypatch` for environment variables and an autouse
fixture that changes into `tmp_path` so developer-local `.env` files cannot
affect test results.

Cover at least:

- missing required settings raise `ConfigurationError`,
- blank text and blank path settings raise `ConfigurationError`,
- explicit values are trimmed and passed through,
- unset optional values use intended defaults,
- path-like values become `Path`,
- unrelated environment variables are ignored.

### 8. Document every settings option

When adding or changing the settings model, create or update a canonical settings
reference under `docs/`, such as `docs/configuration.md`, using
`assets/configuration.template.md` as a starting point.

The settings reference should list every option exposed by `EnvSettings` and
include:

- environment variable name,
- application DTO field name when different,
- expected type or format,
- required/default behavior,
- safe example value,
- whether the value is secret and must be redacted,
- where the setting is used at runtime.

Keep this file synchronized with `settings.py`, `AppSettings`, and tests.

### 9. Maintain `.env.example`

Create or update the root `.env.example` from `assets/env.example.template`.

The example file should list all supported environment variables, including
optional variables with defaults. Use safe placeholders for secret values and do
not include real credentials, tokens, private keys, or production URLs.

### 10. Reference configuration docs from the main README

Add or update a short configuration section in the main project documentation,
usually root `README.md`, using
`assets/readme_configuration_section.template.md` as a guide.

The README section should point readers to the canonical settings reference and
the `.env.example` file rather than duplicating the full settings table.

If runtime configuration changes the user-facing surface, also update any
operator documentation with required environment variables, defaults, `.env`
support, and the `pydantic-settings` dependency.

Use `write-adr` if the configuration approach is a durable architectural
decision.

### 11. Validate locally

Run focused tests first, then the repository quality gate.

Preferred order:

1. settings DTO and env adapter tests,
2. `uv run ruff check .`,
3. `uv run mypy .`,
4. `uv run pytest`.

When available, use `run-python-quality-gate` for the full Python validation
pass.

## Design checklist

- Application code depends on `AppSettings`, not `BaseSettings`.
- The adapter owns environment aliases, parsing, validation, and `.env` support.
- Runtime defaults are intentional and defined in either the DTO or adapter model
  consistently.
- Validation errors are translated into an application exception.
- The composition root loads configuration once and passes the DTO inward.
- Tests isolate both environment variables and `.env` file lookup.
- `docs/configuration.md`, `.env.example`, README links, and settings tests stay
  synchronized with every `EnvSettings` field.

## Related skills

- Use `python-add-adapter` when the configuration boundary already exists and
  only an adapter implementation is needed.
- Use `update-project-docs` when runtime configuration changes require README or
  operator-facing documentation updates.
- Use `write-adr` when the configuration approach or boundary is a durable
  architectural decision.
