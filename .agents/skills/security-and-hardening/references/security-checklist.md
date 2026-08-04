# Security Hardening Checklist

Use this checklist when implementing or reviewing security-sensitive changes.

## Boundaries

- Identify trusted and untrusted inputs.
- Validate input at the boundary closest to where it enters the system.
- Encode output for the target context.
- Keep data separate from query, command, path, template, and markup syntax.
- Fail closed when authorization, validation, or policy checks are uncertain.

## Access control

- Authenticate identities before using user-specific data.
- Authorize every protected operation against the actor, action, resource, and tenant or ownership boundary.
- Avoid relying on client-side checks for security decisions.
- Test denial paths as well as allowed paths.

## Secrets and sensitive data

- Keep secrets out of source control, logs, analytics, and client bundles.
- Use least-privilege credentials and scoped tokens.
- Protect sensitive data in storage and transit.
- Define retention, redaction, and deletion behavior for sensitive data.

## Files and generated content

- Restrict allowed file types, sizes, paths, and encodings.
- Generate server-side filenames or object keys instead of trusting client names.
- Protect archives and generated files from traversal, unsafe previews, and excessive resource use.

## Dependencies and operations

- Check new dependencies, images, and runtime versions for known risks.
- Use secure defaults for headers, cookies, CORS, and transport.
- Ensure security events are observable without exposing sensitive details.
- Document any accepted risk with an owner, mitigation, and review date.
