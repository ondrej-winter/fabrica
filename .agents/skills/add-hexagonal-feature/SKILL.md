---
name: add-hexagonal-feature
description: Implement a new vertical feature slice or use case in a Python hexagonal project, including domain modeling, ports, application service, adapters when needed, and tests.
metadata:
  version: "1.1.0"
  dependencies:
    tools: []
    skills:
      - name: python-add-port
        purpose: Define a required inbound or outbound application port.
        required: false
      - name: python-add-adapter
        purpose: Implement a required inbound or outbound adapter.
        required: false
---

# Add a Hexagonal Vertical Feature Slice

Use this skill to implement a new feature, use case, or business capability as a
vertical slice in a Python hexagonal project.

This skill focuses on a complete slice through domain, application, ports,
adapters when needed, and tests. When the change requires detailed port or
adapter work, use the specialized skill for that procedure instead of duplicating
it here.

## Prerequisites

- The project already has the standard hexagonal vertical-slice `src/` layout.
- The feature is clear enough that you understand its inputs, outputs, and core
  business rules.
- The relevant inbound port already exists, or creating it is part of the same
  change through `python-add-port`.

## Steps

### 1. Name the slice and use case

Choose a clear verb-noun name for the use case, for example `PlaceOrder`,
`RegisterUser`, or `SendNotification`. Use that name consistently for the
related files and classes.

Choose a `snake_case` slice name for the business capability, for example
`orders`, `user_registration`, or `notifications`. Use this as the package under
`src/<app_name>/features/<feature_name>/`.

### 2. Model the domain if needed

Create or update files under
`src/<app_name>/features/<feature_name>/domain/`:

- **Entity** — an object with identity that changes over time.
- **Value object** — an immutable descriptor (e.g. `EmailAddress`, `Money`).
- **Domain event** — something that happened (e.g. `OrderPlaced`).

Rules:

- Domain objects must be pure Python with no framework imports or I/O.
- Use `@dataclass(frozen=True)` for value objects.
- Raise domain-specific exceptions, not HTTP or database errors.

```python
# src/<app_name>/features/<feature_name>/domain/<entity>.py
from dataclasses import dataclass

@dataclass
class <Entity>:
    id: str
```

### 3. Define or confirm the required ports

Identify the application boundaries the feature needs:

- an inbound port when an external caller invokes a new use case
- one or more outbound ports when the application needs infrastructure
  dependencies such as repositories, publishers, or gateways

If a required port does not exist yet, use `python-add-port` for the detailed
procedure. In this skill, keep the focus on deciding which boundaries the
feature needs. Inbound adapters should depend on inbound port contracts;
application services should satisfy those contracts and depend on outbound port
contracts for infrastructure.

If the use case needs command, query, or result objects, create or update them
under `src/<app_name>/features/<feature_name>/application/dtos/`.

### 4. Implement the application service

Create the use case implementation under
`src/<app_name>/features/<feature_name>/application/use_cases/`:

```python
class <UseCaseName>:
    def __init__(self, repository: <EntityRepositoryPort>) -> None:
        self._repository = repository

    def execute(self, command: <Command>) -> <Result>:
        ...
```

Rules:

- The application service depends only on domain objects and port interfaces.
- If an inbound port exists for the use case, the application service must satisfy
  that contract.
- Keep command, query, and result DTOs under the owning slice's
  `application/dtos/` and use them at the application boundary when dedicated
  boundary types help clarify the use case.
- It must not import from `adapters/`.
- It must not perform I/O directly, including `open()`, HTTP calls, or database
  access.
- If the feature needs a new adapter implementation for an existing or new
  port, use `python-add-adapter` for that procedure.

### 5. Write unit tests

Create application-service tests under
`tests/unit/features/<feature_name>/application/`. If the change adds or changes
domain invariants, add or update domain tests under
`tests/unit/features/<feature_name>/domain/` as well.

```python
class FakeRepository:
    def __init__(self) -> None:
        self.saved: list[object] = []

    def save(self, entity: object) -> None:
        self.saved.append(entity)

def test_<use_case_name>_happy_path() -> None:
    repo = FakeRepository()
    use_case = <UseCaseName>(repository=repo)
    use_case.execute(<Command>(...))
    assert len(repo.saved) == 1
```

TDD is encouraged when it fits the change. Writing tests before the
implementation is fine and often preferable.

- Prefer a hand-written fake for outbound ports. Use `MagicMock` only when a
  narrow interaction assertion is clearer than asserting on fake state.
- Cover the happy path and at least one failure or edge case.

### 6. Validate the feature slice

Run the target project's narrowest relevant test command for the changed domain
and application modules. Then run any available architecture checks, type checks,
linting, and broader test suite required by the project.

Before handoff, confirm:

- the feature's happy path and important failure or edge cases pass
- dependency-direction or architecture checks pass when the project provides them
- the application service has no direct adapter or infrastructure dependencies
- any skipped validation is reported with the reason

## Dependency direction reminder

Follow the target project's architecture guardrails when they are available. This
diagram is a quick dependency-direction reference only.

```
adapters/inbound   →  application  →  domain
adapters/outbound  →  (implements application/ports)
```

Never let an arrow point in the opposite direction.

Keep this diagram inside the owning feature slice. Cross-slice calls must go
through explicit inbound ports, published application APIs, or events rather than
private modules.
