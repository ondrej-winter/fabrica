---
name: hexagonal-vertical-slices
description: Design, review, or refactor systems that use hexagonal architecture organized by vertical feature slices, keeping business logic isolated from frameworks and infrastructure.
metadata:
  version: "1.0.0"
  dependencies:
    tools: []
    skills:
      - name: api-and-interface-design
        purpose: Use when a port, public API, event contract, or other durable boundary needs detailed contract design.
        required: false
---

# Hexagonal Vertical Slices

Use this skill when designing, reviewing, or refactoring a codebase that should
combine hexagonal architecture with vertical feature slices.

This skill is technology-agnostic. Follow the target project's local language,
framework, naming, package, and testing conventions when they are more specific
than the examples here.

## When to use this skill

Use this skill when you need to:

- place new behavior into the correct architectural layer
- design a feature slice around a business capability or use case
- decide whether code belongs in domain, application, ports, adapters, shared
  kernel, infrastructure, or composition root
- review dependency direction between slices and layers
- refactor framework, I/O, persistence, or transport concerns out of business
  logic
- evaluate whether cross-slice collaboration is explicit and safe

Do not use this skill as a substitute for a project-specific implementation
workflow. If a language-specific feature, port, adapter, or test skill exists,
use this skill for architecture decisions and the specific skill for mechanics.

## Core model

Hexagonal architecture protects business behavior from external details.
Vertical slices keep ownership aligned with business capabilities.

The two ideas work together:

- A slice owns one business capability or closely related use-case family.
- Each slice keeps hexagonal responsibilities separate inside its boundary.
- Dependencies point inward toward domain and application behavior.
- External systems connect through adapters that implement or call explicit
  ports.

Generic shape:

```text
<slice_root>/<feature_name>/
  domain/
  application/
    ports/
    use_cases/
    dtos/
  adapters/
    inbound/
    outbound/
```

Small slices may omit empty directories until they are needed. Do not move code
into the wrong layer just to avoid a directory.

## Vocabulary

- Domain: business entities, value objects, domain services, domain events,
  invariants, and domain errors. Domain code is independent of frameworks and
  I/O.
- Application: use-case orchestration, command/query handling, authorization
  checks, transaction boundaries, and coordination of domain behavior.
- Ports: application-owned contracts. Inbound ports describe use-case entry
  points. Outbound ports describe dependencies the application needs from the
  outside world.
- Adapters: edge implementations that translate between external systems and
  application ports. Examples include HTTP, CLI, UI, database, messaging,
  filesystem, SDK, or external service integrations.
- Composition root: startup or bootstrap code that wires concrete adapters into
  application use cases.
- Feature slice: a package, module, directory, namespace, or component boundary
  that owns a business capability end to end.
- Shared kernel: a deliberately small set of pure domain concepts genuinely
  reused by multiple slices.

## Dependency rules

Allowed dependencies:

- Domain to domain concepts in the same slice.
- Application to its own domain model and application-owned ports.
- Adapters to the application ports and boundary types they call or implement.
- Composition root to application and adapter implementations for wiring.
- Cross-slice collaboration through explicit inbound ports, published
  application APIs, domain events, or other documented contracts.
- Shared kernel to shared-kernel concepts only.

Forbidden dependencies:

- Domain depending on application, adapters, frameworks, infrastructure, or I/O.
- Application depending on adapters, concrete infrastructure, transport schemas,
  persistence models, or framework request/response objects.
- Adapters calling other adapters directly when an application port should own
  the boundary.
- Inbound adapters orchestrating domain workflows directly instead of calling an
  application use case or inbound port.
- One slice importing another slice's private domain, application service,
  repository, DTO, adapter, or helper modules.
- Shared kernel importing from feature slices, application layers, adapters, or
  infrastructure.

Quick direction reference:

```text
inbound adapter  ->  application  ->  domain
application      ->  outbound port
outbound adapter ->  outbound port
composition root ->  application + adapters
```

Never let the core depend on the edge.

## Steps

### 1. Identify the business capability

Name the slice by business language, not by transport, database, framework, or
technical mechanism.

Prefer names like:

- billing
- user_registration
- report_generation
- access_control

Avoid names like:

- rest_handlers
- database_models
- cloud_functions
- utilities

If the change spans several capabilities, split the work into multiple slices or
define an explicit collaboration boundary before implementing.

### 2. Classify each responsibility

For every meaningful object, function, type, module, or file, ask what it owns:

- Business invariant or concept: domain.
- Use-case orchestration or transaction boundary: application.
- Contract needed by callers or dependencies: port.
- Translation to or from external technology: adapter.
- Startup wiring: composition root.
- Pure concept reused by multiple slices: shared kernel.

When classification is unclear, prefer the innermost layer that can own the
behavior without importing external details.

### 3. Define ports at application boundaries

Use ports when the application must interact across a boundary.

Inbound ports are useful when external callers need a stable use-case contract.
Outbound ports are useful when the application needs persistence, messaging,
filesystem access, clocks, external APIs, notifications, or other side effects.

Port guidance:

- Keep contracts small and explicit.
- Define ports in the owning application's boundary.
- Use domain or application boundary types in signatures.
- Keep transport schemas, ORM models, SDK objects, framework requests, and
  framework responses out of port signatures.
- Use the `api-and-interface-design` skill when the boundary is durable or has
  multiple consumers.

### 4. Keep adapters at the edge

Adapters translate between external details and application contracts.

Inbound adapters should:

- receive external input
- validate and translate it into application boundary types
- call an inbound port or application use case
- translate the result back to the caller's format

Outbound adapters should:

- implement outbound ports
- contain SDK, database, filesystem, network, messaging, serialization, and
  retry details
- translate external data into domain or application boundary types

Adapters may contain technical error handling and mapping logic. They should not
own business workflows or invariants.

### 5. Place composition and configuration outside the core

Keep dependency injection, service construction, environment lookups, secret
loading, framework startup, and process lifecycle code in composition-root,
bootstrap, or adapter-owned infrastructure modules.

Do not let containers, service locators, framework globals, environment access,
or persistence sessions leak into domain entities or application use cases.

### 6. Review cross-slice collaboration

When one slice needs another, choose an explicit integration style:

- call a published inbound port or application API
- publish and handle events through application-owned ports
- extract a genuinely shared pure domain concept into a shared kernel
- coordinate externally in a composition layer when the flow is orchestration,
  not domain behavior

Do not import another slice's private internals for convenience.

### 7. Verify the architecture

Use project-appropriate validation. Useful checks include:

- unit tests for domain and application behavior without real infrastructure
- adapter tests at I/O boundaries
- contract tests for ports, APIs, events, or schemas
- import-boundary checks when available
- code review against dependency direction and slice ownership
- documentation or ADR updates for intentional deviations

## Review checklist

- New business behavior is owned by a feature slice.
- Domain code is pure and independent of frameworks, I/O, persistence, transport,
  and SDK objects.
- Application code orchestrates use cases through domain objects and ports.
- Ports are owned by the application boundary and use domain/application types.
- Adapters translate external details and do not orchestrate business workflows.
- Composition root owns wiring and concrete dependency selection.
- Cross-slice calls use explicit published boundaries, events, or shared-kernel
  concepts.
- Shared kernel remains small, pure, and domain-focused.
- Tests verify core behavior without requiring real external systems.
- Any deviation from the architecture is documented with the reason and risk.

## Red flags

- Domain imports a web framework, UI framework, ORM, SDK, filesystem, network, or
  environment API.
- Application code creates concrete database clients, HTTP clients, queues, UI
  objects, or framework responses.
- Adapter code contains business decisions that belong in domain or application.
- A global services, utilities, common, or helpers package mixes unrelated slice
  behavior.
- One slice imports another slice's private modules.
- Ports expose transport schemas, persistence models, or framework types.
- The shared kernel grows because it is convenient rather than genuinely shared.
- Dependency wiring is scattered through domain or application code.
- Tests for business rules require real infrastructure to run.
