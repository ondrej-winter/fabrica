# Performance Optimization Checklist

Use this checklist to plan and verify performance work.

## Baseline

- Identify the user-visible symptom or business impact.
- Capture a baseline metric before changing code.
- Define the target metric and acceptable trade-offs.
- Use realistic data volume, network conditions, and concurrency.
- Repeat noisy measurements and record the sample count and variability.

## Investigation

- Separate client, server, database, network, and infrastructure causes.
- Find the bottleneck with measurement rather than assumption.
- Check logs, traces, profiles, query plans, and resource metrics as applicable.
- Identify whether latency, throughput, memory, CPU, I/O, or payload size is
  limiting the system.

## Optimization

- Remove unnecessary work before adding caches or complexity.
- Prefer bounded, observable caches with clear invalidation.
- Batch, paginate, stream, or defer work when it improves user-visible performance.
- Keep correctness, security, and maintainability constraints explicit.

## Verification

- Re-measure the same scenario after the change.
- Compare the same summary statistic against the baseline and target.
- Keep workload, environment, warm-up, and cache conditions comparable.
- Check for regressions in edge cases and resource usage.
- Document the evidence and remaining risks.

## Regression guards

- Add a benchmark, performance budget, monitor, alert, or review check that fits
  the risk.
- Record the reason if a durable guard is not practical for the change.
