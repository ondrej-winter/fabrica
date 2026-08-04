# Pre-Launch Security Checklist

Use this checklist before shipping changes that affect users, data, infrastructure, authentication, authorization, or external integrations.

## Required checks

- Confirm authentication and authorization paths were tested for allowed and denied users.
- Confirm secrets are not exposed in source, logs, build output, client bundles, or configuration examples.
- Confirm user input handling covers malformed, oversized, repeated, and hostile inputs.
- Confirm error responses do not expose sensitive internals.
- Confirm dependencies, containers, and runtime images are acceptable for release.
- Confirm rollback does not weaken security or expose stale sensitive data.

## Release evidence

- List tests or manual checks performed.
- Record any accepted residual risk.
- Note the owner for post-launch security monitoring.
