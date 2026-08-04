---
name: api-and-interface-design
description: Design stable APIs, module contracts, schemas, component boundaries, command interfaces, or other public integration surfaces that are predictable, documented, and hard to misuse.
metadata:
  version: "1.1.4"
  dependencies:
    tools: []
    skills:
      - name: deprecation-and-migration
        purpose: Plan breaking interface changes, consumer migration, and removal.
        required: false
---

# API and Interface Design

Use this skill when designing or changing a surface that another caller,
component, service, team, user, or automated process depends on. The goal is to
make the interface explicit, stable, observable enough to verify, and difficult
to misuse.

This applies to HTTP APIs, message contracts, library interfaces, module
boundaries, plugin hooks, command-line interfaces, component inputs, schemas,
configuration surfaces, and any other boundary where one part of a system talks
to another.

## When to use this skill

Use this skill when you need to:

- design a new public or cross-boundary interface
- change an existing interface without surprising consumers
- define input, output, error, or event contracts
- choose compatibility, versioning, pagination, or naming conventions
- review whether an interface is predictable and hard to misuse

Do not use this skill to standardize internal helper shapes that have no durable
consumer or observable boundary.

## Principles

### Hyrum's Law

With a sufficient number of users of an API, all observable behaviors of your
system will be depended on by somebody, regardless of what you promise in the
contract.

Treat observable behavior as a commitment. This includes response shape, error
codes, message text, ordering, timing, default values, side effects, and
undocumented quirks.

Design implications:

- expose only behavior you are willing to support
- avoid leaking implementation details through names, errors, timing, or data
  shape
- plan deprecation before consumers depend on the old behavior
- remember that tests cannot prove a change is safe for undocumented consumer
  dependencies

### One-version rule

Avoid forcing consumers to choose between multiple active versions of the same
interface or dependency. Multiple versions increase maintenance cost and create
compatibility problems when different consumers need different versions at the
same time.

Prefer extending one stable interface over forking it. If multiple versions are
unavoidable, document the support window, migration path, and removal criteria.

## Steps

### 1. Identify the boundary and consumers

State what boundary is being designed and who or what consumes it.

Capture:

- consumer types, such as users, services, modules, plugins, clients, scripts, or
  operators
- whether the interface is public, internal but cross-team, or private to one
  implementation
- expected stability and compatibility requirements
- inputs, outputs, side effects, errors, and ordering guarantees
- operational constraints such as latency, rate limits, retries, or idempotency

The more durable or widely consumed the interface is, the more explicit the
contract should be.

### 2. Define the contract before implementation

Describe the interface before building the implementation. Use the contract
format that fits the project, such as an OpenAPI document, schema file,
protocol definition, type definition, command help text, ADR, README section, or
test fixture.

At minimum, define:

- operation names and responsibilities
- required and optional inputs
- output shape and generated fields
- default values and side effects
- error shape and retry semantics
- compatibility expectations
- examples for common and edge cases

For example, a neutral resource contract might state:

```md
Operation: create item
Input: required name, optional description
Output: item identifier, name, description, creation timestamp
Errors: validation failed, duplicate name, unauthorized
Compatibility: future optional fields may be added to output
```

### 3. Choose consistent error semantics

Pick one error strategy for the boundary and apply it consistently.

Define:

- how callers detect success or failure
- whether errors are returned, raised, emitted, logged, or encoded as status
  values
- machine-readable error identifiers
- human-readable messages
- which details are safe to expose
- whether an operation can be retried

For request-response APIs, this might be a status code plus a structured error
body. For libraries, it might be typed exceptions or result values. For command
interfaces, it might be exit codes plus structured output.

Do not mix patterns at the same boundary without a documented reason. If some
operations return empty values, some raise errors, and others return structured
errors, consumers cannot reliably predict behavior.

### 4. Validate at trust boundaries

Validate external or less-trusted data where it enters the system. After
validation, keep internal code focused on domain behavior instead of repeatedly
revalidating the same already-trusted data.

Validate data from:

- user input
- network requests
- files and configuration
- environment variables
- message queues or events
- third-party service responses
- generated or model-produced content

Treat third-party responses as untrusted. Validate their shape and content before
using them in logic, rendering, persistence, or security decisions.

Avoid scattering duplicate validation between internal functions that share the
same trusted contract.

### 5. Prefer additive compatible changes

Extend interfaces without breaking existing consumers.

Usually compatible:

- adding optional input fields
- adding output fields consumers can ignore
- adding new operations without changing existing ones
- adding new enum or status values only when consumers are expected to handle
  unknown values
- relaxing overly strict validation when it does not create ambiguity

Usually breaking:

- removing fields, operations, status values, or error codes
- changing field meaning, type, units, default values, or ordering
- making optional fields required
- narrowing accepted input values
- changing idempotency, side effects, or authorization semantics

When a breaking change is unavoidable, use a deprecation and migration workflow
to plan communication, migration, compatibility support, and removal timing. If
the `deprecation-and-migration` skill is available, use it for that follow-up
planning.

### 6. Make naming predictable

Use names that match the existing interface style and domain language. Prefer
one convention per boundary over mixing styles.

Check names for:

- resource or concept names that reflect the domain rather than implementation
  details
- operation names that describe intent without duplicating transport mechanics
- field names that use consistent casing, tense, and units
- boolean names that read clearly as true or false
- status values that are stable, documented, and safe for unknown-value handling
- identifiers that are hard to confuse across entity types

Do not import a naming convention from another language, framework, or transport
unless it is already the project convention or required by consumers.

### 7. Design collections and partial updates explicitly

For list or search operations, define:

- pagination or streaming behavior
- filtering and sorting options
- default limits and maximum limits
- result ordering stability
- empty result behavior
- consistency expectations when data changes during iteration

For partial updates, define:

- how omitted fields differ from explicit empty or null values
- whether updates are idempotent
- how conflicts are detected
- whether generated fields can be changed by consumers

### 8. Separate caller input from system output

Do not require callers to provide fields that the system owns, such as generated
identifiers, creation timestamps, computed values, or audit fields.

Keep separate shapes for:

- creation input
- update input
- persisted or returned output
- internal representation when it differs from the public contract

This separation keeps callers from depending on implementation details and makes
future changes easier.

### 9. Verify the interface from the consumer perspective

Validate the design and implementation with consumer-facing checks.

Useful verification includes:

- contract tests or schema validation
- examples that can be executed or copied safely
- compatibility tests for old and new consumers
- negative tests for validation and error behavior
- documentation review against actual behavior
- migration tests when changing an existing interface

Verification should prove the contract is understandable and stable from the
consumer's point of view, not only that the provider implementation works.

## Red flags

- observable behavior is undocumented but likely to be consumed
- operations at the same boundary use inconsistent error shapes
- input validation is missing at external boundaries
- third-party responses are trusted without validation or sanitization
- fields expose storage, framework, or implementation details unnecessarily
- collection operations have no pagination, streaming, or limit strategy
- partial updates do not define omitted, empty, and null value behavior
- compatibility impact is unclear for changed fields or status values
- examples require a specific framework even though the skill is meant to be
  reusable

## Output checklist

- boundary and consumers are explicit
- contract is documented before or alongside implementation
- input, output, error, and side-effect semantics are consistent
- validation happens at trust boundaries
- changes are additive or have a migration plan
- naming follows the local interface convention
- collection and partial-update behavior is defined when relevant
- consumer-facing tests, examples, or documentation verify the contract
