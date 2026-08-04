---
name: python-add-adapter
description: Add an inbound or outbound adapter to the owning vertical slice in a Python hexagonal project while keeping business logic in the application layer.
metadata:
  version: "1.0.1"
  dependencies:
    tools: []
    skills:
      - name: python-add-port
        purpose: Define the application boundary before implementing an adapter when the required port does not exist.
        required: false
      - name: python-add-env-settings-adapter
        purpose: Follow the dedicated workflow for an environment-backed settings adapter.
        required: false
      - name: add-hexagonal-feature
        purpose: Implement a complete feature slice when the change extends beyond adapter work.
        required: false
      - name: run-python-quality-gate
        purpose: Run the full project-configured Python validation pass before handoff.
        required: false
---

# Add an Adapter

Add an inbound or outbound adapter to the owning vertical slice in a Python
hexagonal project while keeping business logic in the application layer.

This skill owns adapter implementation. If the required application boundary
does not exist yet, define the port first with `python-add-port`.

## When to use this skill

Use this skill when you need to:

- add an inbound adapter that receives external input and calls an existing
  application port
- add an outbound adapter that implements an existing application port and talks
  to infrastructure
- wire a concrete adapter into dependency injection, routing, bootstrap, or the
  composition root without moving business logic out of the application layer

## Prerequisites

- The relevant port interface exists in
  `src/<app_name>/features/<feature_name>/application/ports/` or a documented
  shared application port location.
- The adapter technology has been chosen and any required library is installed,
  for example with `uv add <library>`.

If the port does not exist yet, use `python-add-port` before implementing the
adapter.

## Steps

Choose the inbound or outbound adapter path below based on the direction of the
boundary being implemented.

## Inbound adapter

An inbound adapter receives external input, maps it into application boundary
types, and calls the application through an inbound port.

### 1. Create the module

```text
src/<app_name>/features/<feature_name>/adapters/inbound/<adapter_name>/
    __init__.py
    adapter.py
```

Keep `__init__.py` lightweight. Re-export the public symbol only when you want a
stable package-level API, and declare `__all__` when it adds clarity:

```python
from .adapter import router

__all__ = ["router"]
```

### 2. Implement

- Accept external input and map it to an application command or query DTO.
- Call the application through its inbound port contract.
- Map the result or exception back to the external format.
- Map domain or application exceptions to adapter-level error responses when
  they are part of the caller-visible boundary.
- Import domain types directly only when the port contract or exception mapping
  requires them; otherwise prefer application DTOs.
- Do not call domain services, repositories, or outbound adapters directly from
  the adapter.
- Keep all business logic in the application service.
- Update routing, framework registration, or other entry-point wiring so the
  adapter is reachable in the running system.

### 3. Test

Place transport-level tests under
`tests/integration/features/<feature_name>/adapters/inbound/<adapter_name>/`.
Test through the framework test client or transport boundary, injecting a fake
or stubbed inbound port implementation to keep tests focused on adapter behavior.

Add unit tests under
`tests/unit/features/<feature_name>/adapters/inbound/<adapter_name>/` only when the
adapter contains meaningful mapping or serialization helpers that warrant direct,
framework-free verification.

## Outbound adapter

An outbound adapter implements a port interface and talks to external infrastructure.

### 1. Create the module

```text
src/<app_name>/features/<feature_name>/adapters/outbound/<adapter_name>/
    __init__.py
    adapter.py
```

Keep `__init__.py` lightweight. Re-export the public symbol only when you want a
stable package-level API, and declare `__all__` when it adds clarity:

```python
from .adapter import <AdapterName>

__all__ = ["<AdapterName>"]
```

### 2. Implement

- Implement all port interface methods.
- Map infrastructure types to the domain or application types required by the
  port. Do not expose infrastructure types beyond the adapter boundary.
- Translate infrastructure exceptions into the domain or application exceptions
  expected by the port contract.
- Keep framework clients, ORM models, serializers, and transport-specific
  configuration inside the adapter package.
- Update dependency injection, bootstrap, or composition-root wiring when the
  new adapter becomes part of the runtime path.

### 3. Test

Write unit tests under
`tests/unit/features/<feature_name>/adapters/outbound/<adapter_name>/` using fakes,
stubs, or mocks around the infrastructure boundary. Follow with integration
tests under
`tests/integration/features/<feature_name>/adapters/outbound/<adapter_name>/` when
adapter behavior depends on actual driver, network, or persistence integration.

## Validation

Run the narrowest tests that cover the adapter first, then the repository's
normal quality gate when available.

Useful checks often include:

- adapter unit or integration tests for the changed adapter path
- `uv run ruff check .`
- `uv run mypy .`
- `uv run pytest`

When available, use `run-python-quality-gate` for the full Python validation pass
before handoff.

## Related skills

- Use `python-add-port` when the required application boundary does not exist
  yet.
- Use `python-add-env-settings-adapter` for the dedicated environment settings
  adapter workflow.
- Use `add-hexagonal-feature` when the change is a complete feature slice that
  spans domain, application, adapters, and tests.
