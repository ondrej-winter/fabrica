# Pre-Launch Performance Checklist

Use this checklist before releasing changes that affect page load, request latency, background work, data volume, integrations, or resource usage.

## Required checks

- Confirm key user flows meet expected latency or responsiveness targets.
- Confirm database queries, external calls, and background jobs scale with expected production volume.
- Confirm payloads, assets, and bundles are not unexpectedly large.
- Confirm caching, batching, pagination, or rate limits behave correctly when relevant.
- Confirm observability is in place for latency, errors, saturation, and throughput.
- Confirm rollback can be performed if performance degrades.

## Release evidence

- Record baseline and post-change measurements when available.
- Note any load, smoke, or manual verification performed.
- Document known limits and monitoring thresholds.
