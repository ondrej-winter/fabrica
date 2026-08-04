# Security Review Checklist

Use this checklist when reviewing changes that touch authentication, authorization, input handling, data storage, networking, secrets, dependencies, or deployment configuration.

## Checks

- Confirm user-controlled input is validated, encoded, or rejected at the right boundary.
- Confirm authorization checks happen server-side and are scoped to the requested resource.
- Confirm secrets, tokens, keys, and credentials are not logged, committed, returned, or exposed to clients.
- Confirm sensitive data is encrypted or protected according to its risk and retention needs.
- Confirm dependency, image, or runtime changes do not introduce known vulnerable versions.
- Confirm errors do not reveal stack traces, credentials, internal URLs, or sensitive identifiers.
- Confirm security-sensitive behavior has tests or a documented manual verification path.

## Review prompts

- What new trust boundary does this change introduce?
- What could an unauthenticated or low-privilege user do with this path?
- What happens when input is malformed, oversized, repeated, or intentionally hostile?
- What evidence proves the mitigation works?
