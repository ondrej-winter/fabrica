---
name: bootstrap-python-app
description: Initialize a new Python project with a hexagonal vertical-slice architecture layout, core tooling, and quality checks when starting a Python application from scratch.
metadata:
  version: "1.0.1"
  dependencies:
    tools:
      - name: uv
        purpose: Initialize the project, manage dependencies, and run development tools.
        required: true
    skills: []
---

# Bootstrap a Python Hexagonal Vertical-Slice Application

Use this skill to initialize a new Python project with a hexagonal
(ports-and-adapters) architecture organized by vertical feature slices.

## Prerequisites

- `uv` is installed. Use the installation method appropriate for the host
  environment.
- `<app_name>` — the project and package name.
- `<python_version>` — for example `3.13`.

## Steps

### 1. Initialize the project with uv

```bash
uv init <app_name> --python <python_version>
cd <app_name>
```

Run the remaining steps from the project root.

### 2. Create the hexagonal vertical-slice `src/` layout

```
src/
└── <app_name>/
    ├── __init__.py
    ├── features/        # Business capabilities as vertical slices
    │   ├── __init__.py
    │   └── <feature_name>/
    │       ├── __init__.py
    │       ├── domain/          # Slice-owned entities, value objects, events
    │       │   └── __init__.py
    │       ├── application/     # Slice-owned use cases, ports, DTOs
    │       │   ├── __init__.py
    │       │   ├── use_cases/
    │       │   │   └── __init__.py
    │       │   ├── ports/
    │       │   │   └── __init__.py
    │       │   └── dtos/
    │       │       └── __init__.py
    │       └── adapters/        # Slice-owned inbound and outbound adapters
    │           ├── __init__.py
    │           ├── inbound/
    │           │   └── __init__.py
    │           └── outbound/
    │               └── __init__.py
    ├── shared_kernel/   # Optional pure domain concepts shared by slices
    │   └── __init__.py
    └── bootstrap/       # Optional composition-root helpers
        └── __init__.py
tests/
├── __init__.py
├── unit/
│   ├── __init__.py
│   └── features/
│       ├── __init__.py
│       └── <feature_name>/
│           └── __init__.py
└── integration/
    ├── __init__.py
    └── features/
        ├── __init__.py
        └── <feature_name>/
            └── __init__.py
```

Create the listed directories that are useful for the initial capability. Use a
real business slice name instead of `<feature_name>`, or omit the example slice
until the first feature is known. Add `__init__.py` files when the project uses
regular packages or intentionally exposes package-level APIs; namespace packages
are acceptable only when chosen deliberately.

### 3. Configure pyproject.toml

Create or update `pyproject.toml` from `assets/pyproject.template.toml`.
Replace `<app_name>`, `<python_version>`, and `<python_version_nodot>`. Keep the
values `uv init` already set for `name`, `version`, and `requires-python` unless
the user asked for something else.

### 4. Install development dependencies

```bash
uv sync --group dev
```

If the project later adds multiple dependency groups, use `uv sync --all-groups`
to install them together.

### 5. Set up pre-commit

```bash
uv add --group dev pre-commit
uv run pre-commit install
```

Create `.pre-commit-config.yaml` from
`assets/pre-commit-config.template.yaml`. Replace `<python_version>` with the
selected Python version, for example `3.13`, so the generated value is
`python3.13`.

### 6. Verify the setup

```bash
uv run ruff check .
uv run mypy .
uv run pytest
```

All three commands must exit with code 0.

### 7. Write a minimal README

Write a `README.md` that includes:

- What the application does.
- How to install dependencies (`uv sync --group dev`).
- How to run quality checks (`uv run ruff format .`, `uv run ruff check .`, `uv run mypy .`, `uv run pytest`).
- A high-level architecture overview (features / domain / application / adapters).

## Hexagonal vertical-slice architecture conventions

| Area                | Directory                                                   | Rule                                                                                                                |
| ------------------- | ----------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------- |
| Feature slice       | `src/<app_name>/features/<feature_name>/`                   | Owns one business capability end to end.                                                                            |
| Domain              | `src/<app_name>/features/<feature_name>/domain/`            | No imports from `application` or `adapters`. Pure Python only.                                                      |
| Application         | `src/<app_name>/features/<feature_name>/application/`       | Depends only on slice domain, shared kernel, and ports. Keeps use cases, ports, and boundary DTOs inside the slice. |
| Adapters (inbound)  | `src/<app_name>/features/<feature_name>/adapters/inbound/`  | Calls inbound ports and maps external data to application boundary types.                                           |
| Adapters (outbound) | `src/<app_name>/features/<feature_name>/adapters/outbound/` | Implements outbound ports and keeps infrastructure types inside adapters.                                           |
| Shared kernel       | `src/<app_name>/shared_kernel/`                             | Optional pure domain concepts shared by multiple slices.                                                            |
| Bootstrap           | `src/<app_name>/bootstrap/`                                 | Optional composition-root helpers and dependency wiring.                                                            |

If appropriate for the project, enforce these rules with an import linter such
as `import-linter`, or document them in a root-level `ARCHITECTURE.md`.
