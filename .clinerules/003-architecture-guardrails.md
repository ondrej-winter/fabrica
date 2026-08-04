# Hexagonal architecture with vertical slices doctrine (hard constraints)

Use this doctrine as the default architecture standard for the codebase. Organize business capabilities as vertical slices while preserving hexagonal dependency direction inside each slice. Any deviation must be explicitly documented.

## Core principles (non-negotiable)

- **Dependency direction**: All dependencies point **inward** toward the domain and application core.
- **Vertical slice ownership**: Business capabilities are grouped by feature or use case first, then by hexagonal layer inside that slice.
- **Business logic isolation**: Domain models are pure and independent of frameworks, I/O, and infrastructure.
- **Explicit boundaries**: Interaction between layers happens only through ports (interfaces/protocols).
- **Replaceable adapters**: I/O details are swappable without changing the core.

## Vocabulary

- **Domain**: Entities, value objects, domain services, and domain errors. No I/O concerns.
- **Application**: Orchestrates use cases. Defines **ports** (inbound/outbound) and coordinates domain behavior.
- **Ports**: Application-owned contracts that isolate the core from infrastructure. Inbound ports describe use case entry points; outbound ports describe dependencies such as persistence, messaging, and external APIs.
- **Adapters**: Implementation of ports at the system edge (CLI, HTTP, DB, external APIs, message queues, etc.).
- **Infrastructure**: Frameworks, SDKs, DB drivers, HTTP clients, serializers, etc. Lives only in adapters.
- **Feature slice**: A package that owns one business capability or closely related use-case family, including its local domain, application, ports, DTOs, adapters, and tests.
- **Shared kernel**: A small optional package for pure domain concepts genuinely reused by multiple slices. It must not become a dumping ground for convenience utilities.

## Dependency rules (allowed/forbidden)

Allowed:

- Domain → Domain (same layer)
- Within a feature slice: Application → its slice domain and shared-kernel domain types
- Within a feature slice: Adapters → its slice application ports + approved domain/application boundary types exposed by those ports
- Cross-slice collaboration only through another slice's explicit inbound port, published application API, or events handled through application-owned ports
- Shared kernel → Shared kernel only

Forbidden:

- Domain → Application, Adapters, Infrastructure
- Application → Adapters, Infrastructure
- Adapter → Adapter (unless through application ports)
- Driving adapters → Domain orchestration directly (bypassing application ports)
- One slice importing another slice's private domain, application service, DTO, repository, or adapter modules directly
- Shared kernel importing from feature slices, application layers, adapters, frameworks, or infrastructure

## Layer responsibilities

### Domain

- Pure business rules and invariants.
- No side effects, no I/O, no framework imports.
- Exposes domain errors and value objects.
- Value objects should be immutable, or treated as immutable by convention, when mutation would weaken invariants.

### Application (Use Cases)

- Orchestrates flows, validates inputs (structural validation), invokes domain logic.
- Keeps business invariants in the domain; application-level validation should focus on command shape, authorization, orchestration, and transaction boundaries.
- Defines ports and DTOs that are **inward-facing** and stable.
- Handles cross-cutting concerns such as transactions or unit-of-work abstractions.

### Ports

- **Inbound ports**: Contracts that driving adapters call and application services satisfy.
- **Outbound ports**: Contracts that application services call and outbound adapters implement.
- Ports are defined in the owning slice's application layer only, unless they describe an intentionally shared application boundary.
- Prefer small, explicit port contracts expressed via `Protocol` or ABCs.
- Port signatures must use domain/application types rather than transport schemas, ORM models, or framework request/response objects.
- Keep command, query, and result DTOs under the owning slice's `application/dtos/` when the application boundary needs dedicated request/response objects.

### Adapters

- Connect external systems to application-owned ports.
- Inbound adapters live with the slice whose inbound port they call and usually translate external data into application DTOs or other domain/application types explicitly accepted by the port.
- Outbound adapters live with the slice whose outbound port they implement, unless the adapter is intentionally shared infrastructure wired through multiple slice ports.
- Translate external data structures ↔ DTOs/domain objects.
- Handle I/O, serialization, transport, and retry logic.
- Do not orchestrate domain behavior directly inside adapters.

## Vertical slice organization

- **Must** package new business capabilities under a feature or use-case slice before adding global layer packages.
- **Must** keep each slice internally hexagonal: `domain/`, `application/`, and `adapters/` remain separate responsibilities inside the slice.
- **Must** keep slice internals private by default. Other slices may depend only on explicitly published inbound ports, application APIs, domain events, or shared-kernel types.
- **Should** name slices by business capability, such as `billing`, `report_generation`, or `user_registration`, rather than by transport or database technology.
- **Should** keep the first implementation of a capability in one slice even when it touches inbound adapters, application, domain, outbound ports, adapters, and tests.
- **Must not** create broad top-level `services`, `utils`, or `common` packages that bypass slice ownership.
- **Must** document intentionally shared application contracts or shared infrastructure adapters when more than one slice depends on them.

## Composition root and framework isolation

- **Must** keep dependency wiring, service construction, and framework bootstrapping in entry points or dedicated bootstrap/composition-root modules.
- **Must** keep framework request/response objects, ORM models, serializer models, and transport schemas inside adapters.
- **Must** keep environment/config lookups, secret loading, and framework settings access in adapters or bootstrap modules rather than scattering them through the core.
- Detailed settings DTO, environment-backed adapter, config validation, and secret-safety rules live in `008-configuration-and-secrets.md`.
- **Should** keep transport and event-loop concerns at I/O boundaries; use async in the core only when business semantics truly require asynchronous contracts.
- **Must not** let dependency-injection containers or service locators leak into domain entities or application use cases.

## Transactions and side effects

- **Must** coordinate transactions, unit-of-work boundaries, and side-effect ordering in the application layer or adapter-owned infrastructure boundaries.
- **Must not** hide persistence commits, network retries, or message publication inside domain entities.
- Domain events may be modeled in the core, but publication and delivery belong behind outbound ports/adapters.

## Module/package structure guidance

- `features/<feature_name>/domain/`: entities, value objects, domain services, domain events, domain errors owned by the slice.
- `features/<feature_name>/application/`: use cases + ports + DTOs under the owning slice.
- `features/<feature_name>/adapters/`: inbound (CLI/HTTP/GraphQL) and outbound (persistence, external APIs, messaging, etc.) adapters owned by the slice.
- `shared_kernel/` (optional): pure domain concepts shared across slices.
- `infrastructure/` or `bootstrap/` (optional): composition-root or adapter-only utilities that do not contain business behavior.
- Detailed file splitting, package export, and `__init__.py` mechanics are governed by `006-module-structure.md`.

## Naming conventions (layer-aware)

- `.../ports/` for interfaces/protocols.
- `.../adapters/inbound/` and `.../adapters/outbound/` for adapter implementations.
- DTOs named for their intent and kept under the owning slice's `application/dtos/`: `CreateOrderCommand`, `UserProfileDTO`, `PaymentResultDTO`.

## No-go examples (explicitly banned)

- Importing an HTTP client in `domain/` or `application/`.
- ORM models inside domain entities.
- Adapters calling each other directly instead of via application ports.
- Inbound adapters importing domain services and running business workflows directly.
- A feature slice importing another slice's repository implementation or domain service directly.
- A top-level `common/` package accumulating mixed domain, application, and adapter code.
- "Helper" utilities in `domain/` that perform I/O.

## Adapter directory structure

Adapters at the same conceptual level **must** be organized uniformly to keep navigation predictable and scalable.

- **Must** keep adapter structure consistent within the same conceptual category.
- **Must** avoid mixing one-off standalone adapters with subdirectory-based adapters without a documented reason.
- **Must** keep adapter naming and packaging aligned with the package-structure rules in `006-module-structure.md`.
- For directory, file naming, and export conventions, follow `006-module-structure.md`.
