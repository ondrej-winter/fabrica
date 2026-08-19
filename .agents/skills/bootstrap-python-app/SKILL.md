---
name: bootstrap-python-app
description: Initialize a new Python project with a hexagonal vertical-slice architecture layout, core tooling, quality checks, and GitHub Actions CI/CD when starting a Python application from scratch.
metadata:
  version: "1.3.0"
  dependencies:
    tools:
      - name: uv
        purpose: Initialize the project, manage dependencies, and run development tools.
        required: true
      - name: ruff
        purpose: Format Python code, lint code, and organize imports through the project environment.
        required: true
      - name: ty
        purpose: Type-check the generated source and test tree through the project environment.
        required: true
      - name: pytest
        purpose: Run the generated test suite through the project environment.
        required: true
      - name: import-linter
        purpose: Enforce hexagonal vertical-slice dependency boundaries through the project environment.
        required: true
      - name: python-semantic-release
        purpose: Create automated patch releases in CI/CD after the quality gate passes.
        required: true
      - name: pre-commit
        purpose: Install optional local hooks that run the same project quality checks before commits.
        required: false
      - name: GitHub Actions
        purpose: Run reproducible CI quality checks, build artifacts, create semantic patch releases, and publish to PyPI.
        required: true
      - name: PyPI trusted publishing
        purpose: Publish release artifacts from GitHub Actions without committing PyPI tokens.
        required: true
    skills:
      - name: add-hexagonal-feature
        purpose: Add the first real vertical feature slice after the project scaffold exists.
        required: false
      - name: ci-cd-and-automation
        purpose: Review CI/CD trigger, permission, artifact, release, and publishing safety.
        required: false
      - name: run-local-quality-gate
        purpose: Run the full configured quality gate before handoff.
        required: false
      - name: update-project-docs
        purpose: Update project-facing documentation when bootstrap behavior, usage, or configuration changes.
        required: false
---

# Bootstrap a Python Hexagonal Vertical-Slice Application

Use this skill to initialize a new Python project with a hexagonal
(ports-and-adapters) architecture organized by vertical feature slices, local
quality gates, and GitHub Actions CI/CD that mirrors the generated local checks.
The scaffold is intentionally strict by default: Ruff selects all rules with a
small documented ignore set, `ty` checks both `src` and `tests`, import-linter
guards architectural boundaries, pytest runs with coverage, and CI creates
semantic patch releases only after the quality job passes.

## Prerequisites

- `uv` is installed. Use the installation method appropriate for the host
  environment.
- `<app_name>` — the project and package name.
- `<python_version>` — for example `3.13`.
- `<python_version_nodot>` — the Ruff target version suffix, for example `313`.
- `<repository_url>` — the public repository URL, for example
  `https://github.com/<owner>/<repo>`.
- `<default_branch>` — the release branch. Use `master` when mirroring this
  scaffold's default CI/CD behavior.
- `<coverage_fail_under>` — the minimum total coverage percentage. Use `93` when
  mirroring this scaffold's strict default; lower it only with an explicit
  bootstrap-stage decision.

Use a valid Python package identifier for `<app_name>` because the template uses
it as both the distribution name and import package. If the published package
name should contain hyphens, add a separate distribution-name decision before
rendering the templates.

## Steps

### 1. Initialize the project with uv

```bash
uv init <app_name> --python <python_version>
cd <app_name>
printf '%s\n' '<python_version>' > .python-version
```

Run the remaining steps from the project root.

### 2. Create the hexagonal vertical-slice `src/` layout

```
src/
└── <app_name>/
    ├── __init__.py
    ├── adapters/        # Product-level driving adapters, kept feature-agnostic
    │   ├── __init__.py
    │   └── inbound/
    │       ├── __init__.py
    │       └── cli/
    │           ├── __init__.py
    │           ├── __main__.py
    │           ├── options.py
    │           ├── parser.py
    │           └── runner.py
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

Do not create broad top-level `services`, `utils`, or `common` packages for mixed
business behavior. Start with the smallest slice structure that keeps domain,
application, and adapter responsibilities clear.

The product-level CLI shell under `src/<app_name>/adapters/inbound/cli/` should
stay feature-agnostic. Put command registration, dependency wiring, and concrete
use-case composition in `bootstrap/` or thin composition modules rather than in
generic parsing and runner modules.

Provide a minimal console entry point so packaging and CI can smoke-test the
installed command:

```python
# src/<app_name>/adapters/inbound/cli/__main__.py
from __future__ import annotations

import argparse


def main() -> int:
    """Run the application CLI."""
    parser = argparse.ArgumentParser(prog="<app_name>")
    parser.add_argument("--version", action="store_true", help="Show version information and exit.")
    parser.parse_args()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
```

### 3. Configure pyproject.toml

Create or update `pyproject.toml` from `assets/pyproject.toml.template`.
Replace `<app_name>`, `<python_version>`, `<python_version_nodot>`,
`<repository_url>`, and `<coverage_fail_under>`. Keep the values `uv init`
already set for `name`, `version`, and `requires-python` unless the user asked
for something else.

The template uses Hatchling packaging, a `src/<app_name>` package, a `dev`
dependency group, Ruff formatting/linting, `ty` type checking, import-linter
architecture contracts, pytest with parallel execution and coverage, semantic
patch-release versioning, and a console script named `<app_name>`. Keep runtime
dependencies in `[project].dependencies` and development-only tools in
`[dependency-groups].dev`.

Use the generated tool policy as the default quality bar:

- Ruff uses `select = ["ALL"]` with only formatter-conflict, docstring-style,
  lightweight package/module, copyright, TODO, and FIXME ignores.
- Do not globally ignore annotation rules. Public interfaces and boundary types
  should stay explicitly typed; test fixtures get narrow per-file exceptions.
- Exclude copied Agent Skills under `.agents` from Ruff and `ty` so skill
  markdown/assets are not treated as application code.
- `ty` checks `src` and `tests`; the CI and pre-commit commands should use the
  same scope.
- Pytest runs from `tests`, uses `pytest-xdist` with `-n=auto`, reports missing
  coverage, and enforces branch coverage through `[tool.coverage.*]`.
- Import-linter contracts should stay generic in the scaffold and be expanded
  only when the new project introduces concrete cross-slice dependencies.

### 4. Install development dependencies

```bash
uv sync --group dev
```

If the project later adds multiple dependency groups, use `uv sync --all-groups`
to install them together.

### 5. Set up pre-commit

```bash
uv run pre-commit install
```

Create `.pre-commit-config.yaml` from
`assets/pre-commit-config.yaml.template`. Replace `<python_version>` with the
selected Python version, for example `3.13`, so the generated value is
`python3.13`.

The template uses local hooks so pre-commit runs the same `uv run ...` commands
as the project quality gate, including import-linter architecture validation.

### 6. Add local automation and ignore rules

Create `Makefile` from `assets/Makefile.template`. The generated targets mirror
the local and CI quality gate:

- `make format` -> `uv run ruff format .`
- `make lint` -> `uv run ruff check . --fix`
- `make type` -> `uv run ty check src tests`
- `make import-lint` -> `uv run lint-imports`
- `make test` -> `uv run pytest`
- `make quality` -> lint, format, type, import-lint, and test
- `make pre-commit` -> all configured pre-commit hooks
- dependency inspection targets for tree, outdated, and vulnerability review

Create `.gitignore` from `assets/gitignore.template`. Keep generated caches,
virtual environments, build outputs, coverage files, import-linter caches, and
temporary audit files out of version control.

### 7. Add GitHub Actions CI/CD

Create `.github/workflows/ci-cd.yaml` from `assets/ci-cd.yaml.template`.
Replace `<app_name>`, `<python_version>`, and `<default_branch>`.

The workflow mirrors the local quality gate and release behavior:

- runs on every push, pull request, and manual dispatch
- installs dependencies with `uv sync --frozen --all-groups`
- checks Ruff formatting, Ruff linting, `ty`, import-linter, and pytest
- builds distribution packages with `uv build`
- smoke-tests the local console package with `uvx --from . <app_name> --help`
- uploads `dist/` as a CI artifact
- creates a semantic patch release on non-bot pushes to `<default_branch>` after
  quality succeeds
- updates `pyproject.toml` and `uv.lock`, commits `chore(release): v{version}`,
  creates a `v{version}` tag, and builds distribution artifacts through
  `python-semantic-release`
- publishes to PyPI through trusted publishing using the GitHub environment named
  `pypi`

Before relying on the release job, configure the repository and PyPI project:

- the GitHub default branch matches `<default_branch>`
- the GitHub `pypi` environment exists and has any required approvals
- the PyPI project trusts the GitHub repository, workflow file, environment
  `pypi`, and branch
- release commits from `github-actions[bot]` are allowed to push to the release
  branch but do not recursively trigger another release
- branch protection allows the release job to push version/tag updates, or the
  project intentionally uses a separate approved release mechanism
- automatic PyPI publication is disabled or deferred until trusted publishing is
  configured; do not use long-lived PyPI tokens in repository secrets by default

### 8. Verify the setup

```bash
uv run ruff format .
uv run ruff check .
uv run ty check src tests
uv run lint-imports
uv run pytest
uv build
uvx --from . <app_name> --help
```

All commands must exit with code 0. If a check fails, fix the root cause and
rerun the narrow failing command before repeating the full gate. For a final
local pre-commit parity check, run:

```bash
uv run pre-commit run --all-files
```

### 9. Write a minimal README

Write a `README.md` that includes:

- What the application does.
- How to install dependencies (`uv sync --group dev`).
- How to run quality checks (`uv run ruff format .`, `uv run ruff check .`, `uv run ty check src tests`, `uv run lint-imports`, `uv run pytest`).
- How to use `make quality`, `make pre-commit`, and the dependency inspection
  targets when the generated Makefile is included.
- How CI/CD runs in GitHub Actions and how patch releases are published from
  `<default_branch>` to PyPI.
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
as `import-linter`, and keep those contracts aligned with `pyproject.toml`,
pre-commit, and CI.

## CI/CD conventions

- The GitHub Actions quality job must be reproducible locally with the same
  `uv run ...`, `uv build`, and `uvx --from .` commands.
- Release automation must run only after the quality job passes.
- Semantic patch releases use `python-semantic-release` with `--patch` for every
  non-bot push to the release branch. Do not rely on Conventional Commit parsing
  for version level unless the project intentionally changes the release policy.
- The release build command should refresh the lockfile before building so the
  release commit contains both `pyproject.toml` and `uv.lock` updates.
- The release job publishes to PyPI with OIDC trusted publishing, not committed
  tokens or long-lived API keys.
- Keep CI permissions least-privilege: read-only contents for quality, write
  contents and `id-token: write` only for the release job.
- Treat a failed release as a deployment failure: inspect logs, fix the root
  cause, and rerun through the workflow rather than publishing artifacts by hand.

## Handoff checklist

- The project uses a `src/<app_name>/` package layout and mirrored `tests/` tree.
- Tooling is installed through `uv sync --group dev`.
- Ruff formatting, Ruff linting, `ty`, import-linter, pytest, build, and console
  smoke checks pass through `uv run`, `uv build`, or `uvx --from .`.
- `.pre-commit-config.yaml`, `Makefile`, `.gitignore`, `.python-version`, and
  `uv.lock` are present and aligned with the generated `pyproject.toml`.
- README setup, quality gate, CI/CD, release, and architecture notes match the
  generated project.
- PyPI trusted publishing and the GitHub `pypi` environment are configured before
  depending on automatic patch releases.
- Any omitted directories were intentionally deferred until the first real
  capability needs them.
