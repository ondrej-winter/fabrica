# Performance and observability

Use these rules to keep performance expectations explicit, regressions visible, and runtime behavior traceable.
Use the `add-observability` skill when you need a practical workflow for
profiling, measurement, metrics, tracing, or operational documentation.

## Performance budgets and baselines

- **Should** define latency/throughput/error-budget expectations for user-facing or operationally critical workflows.
- **Should** make budgets measurable (for example p95/p99 latency, throughput, failure rate, memory, or backlog limits) rather than using vague "fast enough" language.
- **Must** benchmark representative workloads before claiming a performance improvement on a hot path.
- **Must not** make performance claims from toy inputs or unrepresentative datasets when production behavior is the real concern.
- **Should** avoid introducing heavy dependencies without evidence from profiling or measurement.

## Profiling expectations

- **Should** profile when changing hot paths (external API calls, parsing, persistence).
- **Must** capture before/after numbers when optimizing.
- **Should** note the dataset/environment when numbers drive a decision.
- **Should** measure memory/allocation behavior as well as latency when the workflow is data-heavy or long-lived.
- **Should** prefer targeted micro-benchmarks for isolated code and end-to-end timings for workflow claims.

## Logging, tracing, and metrics

- **Should** instrument critical workflows with at least duration, success/failure, and volume counters when the project's observability stack supports it.
- **Should** add metrics for long-running steps (parsing, external API calls, rendering, persistence).
- **Should** use tracing spans around external I/O (external APIs, filesystem, databases, message queues).
- **Must** keep metric labels/tags low-cardinality; avoid user IDs, raw queries, full file paths, or other highly variable values as labels.
- **Should** propagate request, correlation, or job IDs across adapter boundaries when available.
- **Should** sample or rate-limit especially noisy diagnostic logs/events in tight loops, retries, or high-volume code paths.
- **Must** apply the same sensitive-data rules to metrics and traces that apply to logs.
- **Should** align logging field names and metric dimensions with `013-logging-conventions.md`.

## Operational notes

- **Should** add troubleshooting notes when new failure modes are introduced.
- **Should** document dashboards, alerts, or runbook hooks for new critical paths when they exist.
- **Should** document alert thresholds or operational ownership when a new critical workflow meaningfully changes on-call expectations.
- **Must** document new observability hooks in the README or an ADR.
