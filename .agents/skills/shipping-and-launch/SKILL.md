---
name: shipping-and-launch
description: Prepares production launches. Use when preparing to deploy to production. Use when you need a pre-launch checklist, when setting up monitoring, when planning a staged rollout, or when you need a rollback strategy.
metadata:
  version: "1.3.0"
  dependencies:
    tools: []
    skills:
      - name: add-observability
        purpose: Ensure launch, rollout, and rollback plans include meaningful operational signals.
        required: false
      - name: performance-optimization
        purpose: Address launch risks involving latency, throughput, resource usage, or scalability.
        required: false
      - name: debugging-and-error-recovery
        purpose: Prepare recovery steps for known failure modes, incidents, or rollback scenarios.
        required: false
---

# Shipping and Launch

## Overview

Ship with confidence. The goal is not just to deploy, but to deploy safely, with
monitoring in place, a recovery plan ready, and a clear understanding of what
success looks like. Make each launch observable and incremental when the system
allows it. Define a rollback, disablement, roll-forward, or compensation path for
changes that cannot be directly reversed.

## When to Use

- Deploying a feature to production for the first time
- Releasing a significant change to users
- Migrating data or infrastructure
- Opening a beta or early access program
- Any deployment that carries risk (all of them)

Use `add-observability` when launch readiness requires new logs, metrics, traces,
dashboards, alerts, or troubleshooting notes. Use `performance-optimization` when
launch readiness depends on diagnosing and fixing a performance bottleneck. Use
`debugging-and-error-recovery` when a launch, rollout, or rollback exposes an
active failure that needs root-cause repair.

## Steps

1. Identify the release scope, production risk, owners, target users, and planned
   launch window.
2. Complete the pre-launch checklist sections that apply to the release.
3. Use the supporting reference checklists for deeper security, performance, or
   accessibility verification when those risks apply.
4. Define the rollout sequence, monitoring thresholds, recovery triggers, and
   recovery path
   before changing production state.
5. Deploy incrementally, verify post-launch signals, and hold or execute the
   recovery plan when thresholds are missed.
6. Record launch evidence, accepted residual risks, cleanup owners, and any
   follow-up work after the release.

## The Pre-Launch Checklist

### Code Quality

- [ ] Required tests pass, including unit, integration, contract, workflow, or end-to-end checks where relevant
- [ ] Build, package, migration, or deployment artifact generation succeeds with no unexpected warnings
- [ ] Static analysis, linting, schema checks, or type checks pass where used
- [ ] Code reviewed and approved
- [ ] No TODO comments, temporary flags, or debug-only paths that should be resolved before launch
- [ ] No ad hoc debugging output, sensitive logging, or noisy diagnostics left in production paths
- [ ] Error handling covers expected failure modes

### Security

- [ ] No secrets in code or version control
- [ ] Dependency, image, package, or artifact checks show no unacceptable release-blocking vulnerabilities
- [ ] Input validation covers user-facing, partner-facing, batch, and integration entry points
- [ ] Authentication and authorization checks are in place where identity or permissions are involved
- [ ] Transport, browser, API, and platform security controls are configured where relevant
- [ ] Abuse controls, rate limits, quotas, or backpressure are configured for sensitive operations
- [ ] Cross-origin, network, and integration access is restricted to intended consumers

### Performance

- [ ] User-facing responsiveness, request latency, or job processing time meets launch targets
- [ ] Critical paths avoid repeated, unbounded, or unexpectedly expensive work
- [ ] Payloads, assets, artifacts, and transferred data stay within release budgets
- [ ] Data access paths, indexes, partitions, or storage patterns are ready for expected production volume
- [ ] Caching, batching, pagination, or queueing behavior is configured where relevant
- [ ] Resource use and saturation limits are understood for expected traffic or data volume

### Accessibility

- [ ] Keyboard or non-pointer navigation works for interactive surfaces where applicable
- [ ] Assistive technologies can convey content, structure, and state for user interfaces
- [ ] Text, icons, and meaningful visual states meet contrast and non-color communication expectations
- [ ] Focus management works for dialogs, dynamic content, and workflow transitions
- [ ] Errors and recovery instructions are descriptive and connected to the affected action or input
- [ ] Automated or manual accessibility checks have no unresolved launch-blocking findings

### Infrastructure

- [ ] Production configuration, environment variables, and secrets are set through the approved mechanism
- [ ] Data migrations, schema changes, or infrastructure changes are applied or ready to apply safely
- [ ] Routing, networking, certificate, and access configuration are ready where relevant
- [ ] Static assets, packages, images, or deployment artifacts are published and cache behavior is understood
- [ ] Logging, metrics, tracing, and error reporting are configured
- [ ] Health, readiness, smoke, or equivalent verification checks exist and respond

### Documentation

- [ ] README updated with any new setup requirements
- [ ] User, operator, API, integration, or runbook documentation is current where relevant
- [ ] ADRs or decision records written for durable architectural or operational decisions
- [ ] Changelog updated
- [ ] User-facing documentation updated (if applicable)

## Feature Flag Strategy

When the change can be controlled safely at runtime, ship behind a feature flag
or equivalent release control to decouple deployment from release:

```text
if release_control_enabled("new_capability", actor_or_context):
    use_new_behavior()
else:
    use_existing_behavior()
```

### Feature Flag Lifecycle

1. Deploy with flag off: code is in production but inactive.
2. Enable for team or beta users: internal testing happens in the production environment.
3. Gradually roll out: increase exposure through risk-appropriate stages.
4. Monitor at each stage: watch error rates, performance, and user feedback.
5. Clean up: remove the flag and dead code path after full rollout.

### Feature Flag Rules

- Every feature flag has an owner and an expiration date
- Clean up flags within the agreed post-rollout cleanup window
- Do not nest feature flags because doing so creates exponential combinations
- Test both flag states (on and off) in CI

## Staged Rollout

### Example Rollout Sequence

Tailor cohort sizes and observation windows to traffic volume, release risk,
time-to-detection, and how quickly recovery can complete. Do not advance merely
because an example time window elapsed; advance when the defined evidence is
sufficient.

1. Deploy to staging.
   - Run the full test suite in the staging environment.
   - Manually smoke test critical flows.
2. Deploy to production with the feature flag off.
   - Verify deployment succeeded with a health check.
   - Check error monitoring for new errors.
3. Enable for the team with the flag on for internal users.
   - Have the team use the feature in production.
   - Observe for a risk-appropriate period.
4. Start a canary rollout with the flag on for 5% of users.
   - Monitor error rates, latency, and user behavior.
   - Compare canary metrics against baseline metrics.
   - Observe long enough to collect representative evidence.
   - Advance only if all thresholds pass.
5. Gradually increase from 25% to 50% to 100%.
   - Repeat the same monitoring at each step.
   - Keep the ability to roll back to the previous percentage at any point.
6. Complete the full rollout with the flag on for all users.
   - Continue monitoring through the agreed stabilization period.
   - Clean up the feature flag after the stabilization period succeeds.

### Example Rollout Decision Thresholds

Replace these example values with release-specific thresholds, then use them to
decide whether to advance, hold, or execute the recovery plan at each stage:

| Metric                      | Advance (green)        | Hold and investigate (yellow) | Roll back (red)     |
| --------------------------- | ---------------------- | ----------------------------- | ------------------- |
| Error rate                  | Within 10% of baseline | 10-100% above baseline        | >2x baseline        |
| P95 latency                 | Within 20% of baseline | 20-50% above baseline         | >50% above baseline |
| New failure modes           | No new severe types    | Low-volume non-severe types   | Severe or growing   |
| Product or business metrics | Neutral or positive    | Decline <5% or unclear signal | Decline >5%         |

### When to Roll Back

Roll back immediately if:

- Error rate increases by more than 2x baseline
- P95 latency increases by more than 50%
- User-reported issues spike
- Data integrity issues detected
- Security vulnerability discovered

## Monitoring and Observability

### What to Monitor

Application metrics:

- Error rate (total and by endpoint)
- Response time (p50, p95, p99)
- Request volume
- Active users
- Key business metrics (conversion, engagement)

Infrastructure metrics:

- CPU and memory utilization
- Database connection pool usage
- Disk space
- Network latency
- Queue depth (if applicable)

Client metrics:

- Frontend responsiveness or page load time, for browser-facing products
- Client-side, device-side, or edge errors
- API, integration, or synchronization failures from the consumer perspective
- Accessibility, usability, or workflow completion signals where relevant

### Error Reporting

When an error reaches a release boundary:

1. Record the exception type, operation, correlation ID, release version, and safe context.
2. Exclude secrets, credentials, raw personal data, and sensitive internals.
3. Return or display a safe recovery message to the user or caller.
4. Emit a metric or alert signal when the failure affects launch thresholds.
5. Preserve enough detail for operators to diagnose the issue from logs or traces.

### Post-Launch Verification

During the initial post-launch observation window:

1. Check the system's health, readiness, smoke, or equivalent operational signal.
2. Check the error monitoring dashboard for new error types.
3. Check the latency dashboard for regressions.
4. Test the critical user flow manually.
5. Verify logs are flowing and readable.
6. Confirm the recovery mechanism works, using a dry run if possible.

## Recovery Strategy

Every deployment needs a recovery plan before it happens. Use rollback or
disablement when safe; otherwise define roll-forward or compensation steps:

```markdown
## Recovery Plan for [Feature/Release]

### Trigger Conditions

- Error rate > 2x baseline
- P95 latency > [X]ms
- User reports of [specific issue]

### Rollback Steps

1. Disable feature flag (if applicable)
   OR
1. Deploy or restore the previous known-good version: `<rollback_command>`
1. Verify rollback: health check, error monitoring
1. Communicate: notify team of rollback

### Alternative Recovery Steps

- If rollback is unsafe or impossible, disable exposure, roll forward, or execute
  the tested compensation procedure: `<recovery_command_or_runbook>`

### Data and State Considerations

- Migration, schema change, configuration change, or state transition [X] has a tested rollback or compensation plan
- Data written by the release is [preserved / migrated back / cleaned up / reconciled]

### Recovery Time Targets

- Feature flag: < 1 minute
- Redeploy previous version: < 5 minutes
- Database rollback: < 15 minutes
```

## See Also

- For security pre-launch checks, see `references/security-checklist.md`
- For performance pre-launch checklist, see `references/performance-checklist.md`
- For accessibility verification before launch, see `references/accessibility-checklist.md`

## Common Rationalizations

| Rationalization                                   | Reality                                                                                       |
| ------------------------------------------------- | --------------------------------------------------------------------------------------------- |
| "It works in staging, it will work in production" | Production has different data, traffic patterns, and edge cases. Monitor after deploy.        |
| "We do not need feature flags for this"           | Every feature benefits from a kill switch. Even "simple" changes can break things.            |
| "Monitoring is overhead"                          | Not having monitoring means you discover problems from user complaints instead of dashboards. |
| "We will add monitoring later"                    | Add it before launch. You cannot debug what you cannot see.                                   |
| "Rolling back is admitting failure"               | Rolling back is responsible engineering. Shipping a broken feature is the failure.            |

## Red Flags

- Deploying without a rollback plan
- No monitoring or error reporting in production
- Big-bang releases (everything at once, no staging)
- Feature flags with no expiration or owner
- No one monitoring the deploy during the initial observation window
- Production environment configuration done by memory, not code
- "It is Friday afternoon, let us ship it"

## Verification

Before deploying:

- [ ] Applicable pre-launch checklist sections completed
- [ ] Feature flag configured (if applicable)
- [ ] Recovery plan documented
- [ ] Monitoring views and alerts set up
- [ ] Team notified of deployment

After deploying:

- [ ] Health, readiness, smoke, or equivalent operational check passes
- [ ] Error rate is normal
- [ ] Latency is normal
- [ ] Critical user flow works
- [ ] Logs are flowing
- [ ] Recovery mechanism tested or verified ready
