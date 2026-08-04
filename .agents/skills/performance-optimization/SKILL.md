---
name: performance-optimization
description: Optimizes software performance using measurement-driven diagnosis, targeted fixes, and regression guards. Use when performance requirements exist, users or monitoring report slow behavior, a regression is suspected, or profiling reveals bottlenecks that need fixing.
metadata:
  version: "1.2.0"
  dependencies:
    tools: []
    skills:
      - name: add-observability
        purpose: Add measurement, profiling, metrics, tracing, or logs needed to diagnose and verify performance changes.
        required: false
      - name: debugging-and-error-recovery
        purpose: Reproduce and root-cause performance regressions that present as failures or broken behavior.
        required: false
      - name: shipping-and-launch
        purpose: Plan safe rollout, monitoring, and rollback for performance-sensitive changes.
        required: false
---

# Performance Optimization

## Overview

Measure before optimizing. Performance work without measurement is guessing, and
guessing leads to premature optimization that adds complexity without improving
what matters. Establish a baseline, identify the actual bottleneck, apply the
smallest targeted fix, measure again, and add a guard so the issue does not
return.

Use concrete technology guidance only after identifying the system type and the
metric that matters. A web page, batch job, API, database query, command-line
tool, and embedded service can all be "slow" for different reasons.

## When to use this skill

Use this skill when:

- performance requirements exist in a specification, service objective, contract,
  or acceptance criterion
- users, operators, tests, or monitoring report slow behavior
- a change may have introduced a performance regression
- a feature handles larger data volumes, higher concurrency, bigger payloads, or
  more expensive work than existing paths
- profiling, tracing, logs, or resource metrics identify a bottleneck that needs a
  fix

Do not use this skill when:

- there is no evidence of a performance problem and no explicit performance goal
- the proposed change is a speculative micro-optimization
- the optimization would make correctness, security, or maintainability worse
  without a documented trade-off

Use `add-observability` when the missing piece is logs, metrics, traces, or
profiling signals rather than a confirmed performance fix. Use
`debugging-and-error-recovery` first when slow behavior is part of an active
failure that still needs reproduction and root-cause diagnosis. Use
`shipping-and-launch` when performance checks are launch readiness, rollout, or
rollback gates.

## Steps

```text
1. MEASURE: Capture a baseline with realistic conditions.
2. IDENTIFY: Find the actual bottleneck, not an assumed one.
3. FIX: Address the specific bottleneck with the smallest useful change.
4. VERIFY: Re-measure the same scenario and compare with the baseline.
5. GUARD: Add monitoring, tests, budgets, or review checks to prevent regression.
```

### Step 1: Measure

Start with the user-visible symptom and the metric that would prove improvement.
Useful metric categories include:

- latency: response time, startup time, render time, queue wait time, or end-to-end
  task duration
- throughput: requests, jobs, messages, records, or operations per time unit
- resource use: CPU, memory, I/O, network transfer, storage, power, or cost
- scalability: behavior as data volume, concurrency, payload size, or dependency
  latency grows
- reliability under load: timeouts, retries, error rate, saturation, or backpressure

Use complementary measurement sources when possible:

- production telemetry or real-user data to validate impact in real conditions
- synthetic benchmarks or repeatable tests to isolate causes
- profiles, traces, logs, query plans, and resource metrics to locate bottlenecks
- representative fixtures, datasets, network conditions, and concurrency levels

For noisy metrics, run enough repetitions to distinguish the change from normal
variation. Report a suitable summary such as a percentile, range, confidence
interval, or other distribution measure, and include the sample count instead of
relying on one unusually fast or slow run.

Record the baseline in a format that can be compared after the fix:

```text
PERFORMANCE BASELINE
Scenario: <operation_or_user_flow>
Metric: <metric_name>
Current: <value_and_unit>
Target: <value_and_unit>
Conditions: <data_volume, concurrency, environment, network, or workload notes>
Evidence: <profile, trace, log, test run, dashboard, or benchmark reference>
```

### Where to start measuring

Use the symptom to decide what to measure first:

```text
What is slow?

- Startup or initial load
  - Large artifacts, expensive initialization, dependency loading, or cold caches?
  - Slow external dependencies, configuration reads, or migrations?
- Interactive or request-response path
  - Blocking work on the critical path?
  - Repeated computation, repeated I/O, or avoidable serialization?
  - Dependency latency, network waterfalls, or contention?
- Data access
  - Missing indexes, full scans, N+1 access patterns, oversized payloads, or
    unbounded reads?
- Batch or background work
  - Inefficient loops, lack of batching, excessive retries, or poor parallelism?
- Resource saturation
  - CPU-bound work, memory growth, garbage collection pressure, I/O wait, lock
    contention, or connection pool exhaustion?
```

### Step 2: Identify the bottleneck

Common bottleneck categories:

| Symptom                       | Likely cause                                                                     | Investigation                                 |
| ----------------------------- | -------------------------------------------------------------------------------- | --------------------------------------------- |
| High latency on one operation | Hot-path computation, dependency call, or storage access                         | Trace the operation and profile the slow span |
| Latency grows with data size  | Unbounded reads, inefficient algorithm, missing index, or large payload          | Test with representative data volumes         |
| High resource use             | Repeated work, memory retention, large allocations, or inefficient serialization | Inspect profiles and resource metrics         |
| Intermittent slowness         | Contention, retries, saturation, cold starts, or external dependency variance    | Compare traces across fast and slow cases     |
| Poor perceived responsiveness | Blocking user-visible work or delaying first useful output                       | Measure the user-visible milestone directly   |

### Step 3: Fix common anti-patterns

Prefer removing unnecessary work before adding caches or complex infrastructure.
The examples below are technology-neutral patterns; adapt them to the project
language, framework, and runtime.

#### Repeated dependent reads

Avoid one dependency or storage call per item when the data can be fetched in a
single bounded operation.

```text
Avoid:
1. Fetch records.
2. For each record, fetch related data with another call.

Prefer:
1. Fetch records and required related data in one query, join, batch request, or
   preloaded lookup.
2. Preserve limits so the result size remains bounded.
```

#### Unbounded data processing

Do not load or process all records when the user or operation needs only a subset.

```python
# Avoid: unbounded work for every call.
records = repository.list_all_records()

# Prefer: explicit limit and cursor or page boundary.
records = repository.list_records(limit=50, cursor=next_cursor)
```

#### Repeated expensive computation

Compute expensive values once per required scope and reuse them only while the
inputs remain valid.

```python
# Avoid: repeated computation in a hot loop.
for item in items:
    score = calculate_expensive_score(config, item)
    publish(score)

# Prefer: precompute shared inputs or move invariant work outside the loop.
prepared_config = prepare_scoring_config(config)
for item in items:
    score = calculate_score(prepared_config, item)
    publish(score)
```

#### Missing bounds on caches or queues

Caches and queues should have clear bounds, invalidation, and fallback behavior.

```text
Avoid:
- unlimited cache growth
- stale data with no invalidation path
- queues with no backpressure or dead-letter handling

Prefer:
- maximum size or time-to-live
- explicit invalidation conditions
- metrics for hit rate, evictions, depth, age, and failures
```

#### Oversized artifacts or payloads

Send, store, or load only what the operation needs.

```text
Check for:
- unused fields in responses or messages
- large media, documents, archives, or generated artifacts
- unnecessary dependency bundles or plugin loading
- repeated serialization of the same data

Prefer:
- field selection or projections
- pagination, streaming, compression, or chunking
- lazy loading for expensive optional features
```

### Step 4: Verify the fix

Re-run the same scenario under comparable conditions. Do not claim improvement
from a different workload, smaller dataset, warmer cache, or more powerful
environment unless that difference is intentional and documented.

Repeat measurements when results vary, compare the same summary statistic, and
report the sample count and spread needed to support the conclusion. Account for
warm-up, cache state, background load, and rate limiting when they affect the
scenario.

```text
PERFORMANCE RESULT
Scenario: <operation_or_user_flow>
Before: <value_and_unit>
After: <value_and_unit>
Target: <value_and_unit>
Change: <summary_of_fix>
Trade-offs: <complexity, cost, resource, correctness, or maintainability notes>
Evidence: <profile, trace, log, test run, dashboard, or benchmark reference>
```

If the metric did not improve enough, keep the measurement and repeat the
workflow. Failed optimizations are useful evidence when they rule out a suspected
cause.

### Step 5: Guard against regression

Choose guards that fit the project and risk:

- performance budgets for latency, throughput, artifact size, memory, payload size,
  or resource cost
- regression tests or benchmarks for critical paths
- production monitors and alerts for user-visible metrics
- review checklist items for hot paths, data access, payloads, and caching
- documentation of expected data volume, concurrency, and trade-offs

Use placeholders for project-specific commands:

```sh
<benchmark_command>
<load_test_command>
<profile_command>
<quality_gate_command>
```

## Web-specific examples

When optimizing browser-based user experiences, web metrics may be the right
target. Treat them as domain-specific examples, not universal performance goals.

Common Core Web Vitals thresholds:

| Metric                         | Good    | Needs improvement | Poor    |
| ------------------------------ | ------- | ----------------- | ------- |
| LCP, Largest Contentful Paint  | ≤ 2.5s  | ≤ 4.0s            | > 4.0s  |
| INP, Interaction to Next Paint | ≤ 200ms | ≤ 500ms           | > 500ms |
| CLS, Cumulative Layout Shift   | ≤ 0.1   | ≤ 0.25            | > 0.25  |

Web-specific investigation examples:

- first load: network waterfall, server response time, render-blocking resources,
  asset size, font loading, and image dimensions
- interaction delay: main-thread work, expensive rendering, long tasks, event
  handlers, and unnecessary UI updates
- navigation or data loading: request waterfalls, cache behavior, streaming, and
  user-visible loading states

## Performance budgets

Set budgets for the metrics that matter to the system. Examples:

```text
API or service latency: <p95_latency_budget>
Batch job duration: <duration_budget>
Startup time: <startup_budget>
Memory use: <memory_budget>
Artifact or payload size: <size_budget>
Throughput: <throughput_budget>
User-visible milestone: <user_visible_budget>
```

Budgets should be enforced by the project's normal test, monitoring, review, or
release process. Avoid assuming a particular CI provider, package manager, or
benchmarking tool.

## See also

For a concise planning and verification checklist, see
`references/performance-checklist.md`.

## Common rationalizations

| Rationalization                                  | Reality                                                                                                              |
| ------------------------------------------------ | -------------------------------------------------------------------------------------------------------------------- |
| "We will optimize later."                        | Performance debt compounds when hot paths and data models harden around slow assumptions.                            |
| "It is fast on my machine."                      | Local conditions rarely match real users, production data, or operational load.                                      |
| "This optimization is obvious."                  | If you did not measure, you do not know whether it improves the target metric.                                       |
| "Users will not notice this delay."              | Users notice delays in the context of their task; measure the user-visible milestone.                                |
| "The framework or platform handles performance." | Tools help, but they cannot remove unbounded work, inefficient access patterns, or oversized payloads by themselves. |

## Red flags

- optimization without profiling data, baseline metrics, or explicit performance
  requirements
- changes that improve one metric while silently harming correctness, security, or
  maintainability
- unbounded reads, writes, queues, caches, retries, or payloads
- repeated dependency calls or storage access inside loops
- benchmarks that use unrealistic data, concurrency, environment, or cache state
- performance budgets that exist but are not checked by tests, monitoring, review,
  or release gates

## Verification

After any performance-related change:

- [ ] Before and after measurements exist with specific numbers and units.
- [ ] Noisy measurements include enough repetitions and report variability.
- [ ] The measured scenario matches the user-visible symptom or requirement.
- [ ] The specific bottleneck was identified and addressed.
- [ ] The result was compared against the baseline and target.
- [ ] Trade-offs and remaining risks were documented.
- [ ] Regression guards were added or the reason for skipping them was recorded.
- [ ] Existing correctness checks still pass.
