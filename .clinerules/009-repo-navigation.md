# Repository navigation guidelines for hexagonal vertical-slice Python projects

Use these guidelines to organize and navigate code in Python projects that combine hexagonal architecture with vertical slices.

## Standard directory structure

### Source layout pattern

Prefer a `src/<package_name>/` layout for libraries and reusable services. Smaller applications may use `<package_name>/` at the project root if packaging and test imports stay clear.

In monorepos, apply this mental model to each package or service, and keep entry points, tests, and docs discoverable near each package root.

```
src/<package_name>/
├── features/                         # Business capabilities as vertical slices
│   └── <feature_name>/
│       ├── domain/                  # Slice-owned entities, value objects, events, errors
│       ├── application/             # Slice-owned use cases and orchestration
│       │   ├── use_cases/           # Application use cases
│       │   ├── ports/               # Inbound/outbound ports owned by the slice
│       │   └── dtos/                # Command/query/result DTOs and boundary types
│       └── adapters/                # Slice-owned external system interfaces
│           ├── inbound/             # Driving adapters (CLI, HTTP, GraphQL)
│           └── outbound/            # Driven adapters (DB, APIs, messaging)
├── shared_kernel/                    # Optional pure domain concepts shared by slices
└── bootstrap/                        # Optional composition root and wiring helpers
```

If a legacy project already uses top-level `domain/`, `application/`, and `adapters/`, keep changes incremental. New capabilities should move toward the feature-slice structure unless the project documents a different slice root.

### Test layout pattern

```
tests/
├── unit/                   # Fast, isolated unit tests
│   └── features/
│       └── <feature_name>/
│           ├── domain/            # Slice domain tests
│           ├── application/       # Slice use case tests
│           └── adapters/
│               ├── inbound/       # Driving adapter unit tests
│               └── outbound/      # Driven adapter unit tests
├── integration/           # Integration tests with I/O
│   └── features/
│       └── <feature_name>/
│           └── adapters/
│               ├── inbound/       # Driving adapter integration tests
│               └── outbound/      # Driven adapter integration tests
└── e2e/                   # Optional end-to-end scenarios
```

Test directories should mirror the source structure where practical. `e2e/` may be organized by user flow instead of strict source mirroring.

## Documentation and configuration

- `README.md`: project onboarding, setup, and usage
- `docs/`: architecture decision records (ADRs) and design docs
- `examples/`: runnable code examples and integration snippets when useful
- `pyproject.toml`: primary package, build, dependency, and tool configuration
- `uv.lock`: locked dependency state when the project uses `uv`

## Search workflow

Prefer cross-platform tools such as IDE search, `rg`, and `rg --files` for
local exploration.

For reusable command recipes and the step-by-step process for generating a
project-specific navigation guide, use `workflows/update-repo-navigation.md`.

## Navigation principles

- **Slice discovery**: start in `features/<feature_name>/` to understand one business capability end to end
- **Layer isolation**: code in a slice's `domain/` should not import from that slice's `application/` or `adapters/`
- **Port discovery**: look in the owning slice's `application/ports/` to understand system boundaries
- **DTO discovery**: look in the owning slice's `application/dtos/` for command, query, and result types that define the application boundary
- **Entry points**: find wiring and configuration in entry point files (`__main__.py`, `cli.py`, or framework-specific bootstrap modules)
- **Packaging clues**: start with `pyproject.toml` and `uv.lock` to identify package roots, toolchain, and supported Python versions
- **Test mirroring**: navigate tests using the same path as the source module under test
