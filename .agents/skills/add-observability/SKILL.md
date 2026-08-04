---
name: add-observability
description: Add logs, metrics, traces, profiling, or operational notes when a workflow needs better runtime visibility or measurable evidence without unsupported performance claims.
metadata:
  version: "1.1.4"
  dependencies:
    tools: []
    skills:
      - name: debugging-and-error-recovery
        purpose: Reproduce, localize, and fix active failures before adding observability around them.
        required: false
      - name: performance-optimization
        purpose: Diagnose and optimize known or suspected performance bottlenecks after measurement signals exist.
        required: false
      - name: shipping-and-launch
        purpose: Include observability in rollout, monitoring, and rollback-readiness planning.
        required: false
      - name: update-project-docs
        purpose: Document operational signals, dashboards, alerts, or troubleshooting notes affected by observability changes.
        required: false
---

# Add Observability

Use this skill when a workflow needs better runtime visibility, measurable
performance evidence, or operator-facing troubleshooting support.

## When to use this skill

Use this skill when you need to:

- profile an important path before or after a change
- add metrics or tracing around meaningful workflow boundaries
- improve logging context for operator-visible paths
- document dashboards, alerts, failures, or troubleshooting notes
- support investigation of latency, throughput, reliability, or resource usage

Do not use this skill to justify toy benchmarks, noisy logs, speculative
performance claims, or instrumentation that exposes sensitive data.

Use `performance-optimization` when the goal is to diagnose and fix a known or
suspected bottleneck. Use this skill when the goal is to add or improve the
signals that make runtime behavior observable. Use
`debugging-and-error-recovery` when an active failure needs reproduction,
localization, and root-cause repair. Use `shipping-and-launch` when observability
is part of a release checklist, rollout, or rollback plan.

## Steps

### 1. Define the workflow and signal

Identify the specific path, such as:

- a user-facing request or command
- an external service call chain
- persistence, parsing, rendering, or processing work
- a high-volume or latency-sensitive workflow
- a background job, queue, or scheduled task

State what you want to observe, for example latency, throughput, failure rate,
retry behavior, queue depth, memory growth, saturation, or error categories.

### 2. Measure before making claims

Before claiming an optimization or reliability improvement, capture a baseline
using representative inputs and environment notes.

Record:

- workload or dataset shape
- relevant environment assumptions
- before numbers
- what changed
- after numbers when applicable
- limitations of the measurement

If the outcome is better visibility rather than better performance, say that
plainly.

### 3. Instrument meaningful boundaries

Prefer instrumentation at boundaries where an operator or maintainer can act on
the signal, such as:

- workflow start and completion
- external I/O calls
- long-running processing steps
- retry loops and failure boundaries
- queue enqueue, dequeue, and completion points

Avoid scattering instrumentation across low-value internal helpers.

### 4. Add safe logs, metrics, or traces

Inspect existing observability conventions before adding new instrumentation.
Prefer established loggers, metric clients, tracing APIs, naming patterns, and
documentation locations. Do not introduce a new observability dependency or
vendor-specific tool unless the project already uses it or the user explicitly
asks for it.

Choose signals that fit the project conventions.

- Add logs for state transitions, decisions, and operator-visible failures.
- Add metrics for duration, volume, success, failure, and saturation where
  supported.
- Add traces or spans around external I/O and cross-service boundaries where
  supported.
- Use profiles for representative investigations of CPU, memory, allocation, or
  contention costs rather than as permanent request-level instrumentation.
- Propagate request, correlation, job, or tenant identifiers when available and
  safe.

Prefer the smallest set of signals that answers the stated question. Avoid
recording the same event redundantly unless each signal supports a distinct
operational use.

Do not log or emit secrets, credentials, personal data, or highly variable labels
that would create high cardinality.

### 5. Keep operational semantics clear

Use stable names and fields. Document what a signal means, when it increments or
records, and what action a maintainer should take when it changes.

When alerting or dashboards are affected, document thresholds, ownership, and
known limitations if those details are available.

### 6. Update documentation when needed

When the change matters operationally, update project-facing docs with:

- troubleshooting notes
- dashboard or alert references
- new failure modes
- rollout, migration, or on-call implications
- measurement caveats

Use `update-project-docs` for durable documentation updates.

### 7. Validate the signal

Exercise representative success and failure paths when practical. Confirm the
expected logs, metrics, traces, or profile outputs are emitted, and check that
signals are not missing, duplicated, or emitted at an unexpected volume. Check
that labels and fields are stable, low-cardinality, and free of sensitive data.

## Output checklist

- workflow and observed signal are explicit
- baseline and environment are captured when claims depend on numbers
- instrumentation is placed at meaningful boundaries
- logs, metrics, and traces use safe low-cardinality context
- operational documentation is updated when needed
- emitted signals were validated when practical
