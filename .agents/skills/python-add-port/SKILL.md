---
name: python-add-port
description: Add a technology-agnostic inbound or outbound application port interface to the owning vertical slice in a Python hexagonal project for a new use case or dependency.
metadata:
  version: "1.0.1"
  dependencies:
    tools: []
    skills:
      - name: add-hexagonal-feature
        purpose: Coordinate complete end-to-end feature work that includes a port.
        required: false
      - name: python-add-adapter
        purpose: Implement an adapter for the port when the change requires one.
        required: false
---

# Add a Port

Use this skill to add a port interface to the owning vertical slice in a Python
hexagonal project.

A port defines an application-layer boundary. It describes either how the
outside world uses the application or what the application needs from external
systems. A port is not an adapter and must remain technology-agnostic.

This skill owns the detailed procedure for defining new application ports.
Keep feature orchestration and adapter implementation in related skills.

## When to use this skill

Use this skill when you need to:

- expose a new use case through an inbound port
- define a new dependency the application needs through an outbound port
- extract an application-facing interface so adapters depend on an application
  contract rather than concrete implementation details

## Prerequisites

- The project follows a hexagonal vertical-slice structure under
  `src/<app_name>/features/<feature_name>/` or a documented equivalent.
- You understand the use case or dependency the port represents.
- Any command, query, or result DTOs used by the port already exist or are part
  of the same change.

## Port types

### Inbound port

An inbound port defines how the outside world invokes an application use case.
Inbound adapters depend on this contract, and application services satisfy it.

Examples:

- `CreateOrderPort`
- `RegisterUserPort`
- `GenerateReportPort`

### Outbound port

An outbound port defines a dependency the application needs from external
infrastructure. It is declared by the application and implemented by an outbound
adapter.

Examples:

- `OrderRepositoryPort`
- `EmailSenderPort`
- `PaymentGatewayPort`

## Steps

### 1. Choose the file and name

Create the interface under:

```
src/<app_name>/features/<feature_name>/application/ports/
```

Use a shared application port location only when the port is intentionally shared
across slices and that public boundary is documented.

Use a focused file name that matches the responsibility, for example:

- `<use_case_name>_port.py`
- `<dependency_name>_port.py`

Name both the file and the class by business capability or dependency, not by
technology.

Good: `CreateInvoicePort`, `CustomerRepositoryPort`

Avoid: `FastAPIPort`, `PostgresPort`, `S3AdapterPort`

### 2. Define the interface

Use `Protocol` by default for lightweight structural typing. Use `ABC` only
when you need shared abstract behavior or stricter inheritance semantics.

Example:

```python
from typing import Protocol

from <app_name>.features.<feature_name>.application.dtos.create_invoice import (
    CreateInvoiceCommand,
    CreateInvoiceResult,
)


class CreateInvoicePort(Protocol):
    def execute(self, command: CreateInvoiceCommand) -> CreateInvoiceResult:
        ...
```

For outbound ports, follow the same pattern using domain objects or application
DTOs in the signature.

Store related command, query, and result DTOs under:

```
src/<app_name>/features/<feature_name>/application/dtos/
```

### 3. Keep the port clean

- Keep ports in the application layer.
- Do not import from `adapters/` or infrastructure libraries.
- Do not embed framework request or response types in port method signatures.
- Prefer domain objects and application DTOs from the owning slice's
  `application/dtos/` in method signatures.
- Keep each port narrowly focused on one use case or one dependency role.
- Name methods by business intent, not transport or storage mechanics.

For inbound ports, a single `execute(...)` method is often enough.

For outbound ports, define only the operations the application needs. Do not
mirror a full ORM, SDK, or driver API.

### 4. Wire dependencies in the right direction

The arrows below show call flow, not import dependency direction. Keep import
dependencies pointed inward toward the application boundary.

```text
inbound adapters -> inbound ports -> application service
application service -> outbound ports -> outbound adapters
```

In practice:

- inbound adapters depend on inbound port contracts
- application services satisfy inbound port contracts
- application services depend on outbound port contracts
- outbound adapters implement outbound port contracts

Never let a port import an adapter or mention a specific framework.

### 5. Test appropriately

Ports are interfaces, so they usually need little or no direct testing.

Test surrounding behavior instead:

- unit test that the application service honors the inbound port contract
- unit test that application services call outbound ports as expected
- test adapter implementations separately in adapter-focused tests

If the project uses runtime-checkable protocols or shared contract fixtures, add
small targeted tests only when they provide clear value.

### 6. Review related changes

When adding a new port, check whether the same change needs:

- a new application service satisfying the inbound port
- a new outbound adapter implementing the outbound port contract
- new command, query, or result DTOs under the owning slice's `application/dtos/`
- dependency injection or composition-root wiring updates

If a required adapter does not exist yet, use `python-add-adapter` for that
follow-up work instead of embedding adapter logic into the port.

If the overall change is a complete end-to-end use case spanning domain,
application service, and tests, use `add-hexagonal-feature` as the primary
feature workflow and use this skill only for the port-definition part.
