---
name: security-and-hardening
description: Hardens software against vulnerabilities. Use when handling untrusted input, authentication, authorization, sensitive data, dependencies, or external integrations.
metadata:
  version: "1.1.5"
  dependencies:
    tools: []
    skills: []
---

# Security and Hardening

Use this skill when implementing or reviewing security-sensitive behavior. Treat
external input as untrusted, secrets as protected assets, and authorization as a
required check on every protected operation.

Security is not a final phase. It is a constraint on design, implementation,
testing, deployment, and maintenance wherever a system touches users, data,
credentials, networks, files, subprocesses, or third-party services.

## Steps

1. Identify trust boundaries, protected assets, actors, and sensitive data touched
   by the change.
2. Apply the relevant boundary, identity, data, dependency, and configuration
   controls before or while implementing the change.
3. Add or update tests for rejected input, denied access, expired credentials,
   abuse controls, and sensitive-data redaction where relevant.
4. Run the applicable dependency, secret, static-analysis, lint, test, and build
   checks before handoff.
5. Document any accepted risk with an owner, mitigation, and review date.

## When to use

- Accepting input from users, clients, files, queues, webhooks, jobs, or external systems
- Implementing authentication, authorization, sessions, tokens, or roles
- Storing, processing, logging, transmitting, importing, or exporting sensitive data
- Adding integrations, callbacks, plugins, extensions, or dependency changes
- Handling uploads, generated content, templates, commands, or dynamic evaluation
- Preparing a change for release where dependency or configuration risk matters

## Security boundaries

### Always do

- Validate and normalize untrusted input at the boundary where it enters the system.
- Use parameterized query APIs and argument-vector subprocess APIs instead of
  constructing queries or commands with string concatenation.
- Encode or escape output for the target context before rendering or serialization.
- Authenticate identities before using identity-specific data.
- Authorize every protected operation against the specific resource and action.
- Protect secrets with environment, secret-manager, or platform mechanisms instead of source code.
- Hash passwords with a memory-hard or slow password hashing algorithm such as Argon2, scrypt, or bcrypt.
- Use encrypted transport for external communication.
- Apply secure defaults for headers, cookies, tokens, file permissions, and storage.
- Check dependencies, container images, runtimes, and generated artifacts for known vulnerabilities before release.

### Ask first

Get explicit human approval before expanding scope or risk through changes such as:

- adding or changing authentication flows
- changing authorization logic, roles, policies, or tenant boundaries
- storing new categories of sensitive, regulated, payment, or personal data
- adding new external service integrations or callbacks
- changing cross-origin, network, firewall, or trust-boundary configuration
- adding file upload, archive extraction, template rendering, plugin, or subprocess features
- changing rate limits, throttling, quotas, abuse controls, or account lockout behavior
- granting elevated permissions to users, services, credentials, jobs, or infrastructure

### Never do

- Never commit secrets, credentials, private keys, tokens, or production configuration to version control.
- Never log passwords, tokens, session identifiers, private keys, full payment data, or unnecessary personal data.
- Never trust client-side validation, UI state, hidden fields, or caller claims as a security boundary.
- Never disable security controls for convenience without an explicit approved exception.
- Never execute, import, render, or evaluate untrusted content without a documented sandbox or validation strategy.
- Never expose stack traces, internal identifiers, debug pages, or sensitive error details to untrusted users.
- Never rely on obscurity, undocumented endpoints, or internal-only assumptions as the primary defense.

## Common risk areas

### Injection

Injection happens when untrusted data is interpreted as code, query syntax,
commands, templates, paths, filters, or markup. Prefer APIs that keep data and
instructions separate.

Example using parameterized SQL in Python:

```python
# Avoid building queries by concatenating untrusted input.
cursor.execute("SELECT * FROM users WHERE id = ?", (user_id,))
```

Apply the same principle to document databases, search queries, shell commands,
template engines, spreadsheet formulas, file paths, and generated configuration.

### Authentication and session management

Protect identity proof and session state deliberately:

- use established authentication libraries or platform mechanisms where possible
- hash passwords with Argon2, scrypt, bcrypt, or another approved password hashing scheme
- store session secrets and signing keys outside source code
- rotate credentials when exposed or when policy requires it
- expire password reset, invitation, and one-time tokens
- bind session protections to the runtime context, such as secure cookie settings for browser clients
- add rate limiting, lockout, or abuse detection to credential endpoints and sensitive flows

### Access control

Authorization must be checked for each protected operation and resource. A user
being authenticated is not enough.

Example access-control shape:

```python
def update_document(actor, document_id, changes):
    document = documents.get(document_id)
    if not policies.can_update(actor, document):
        raise PermissionDenied("not authorized to update this document")
    return documents.update(document_id, changes)
```

Test both allowed and denied paths. Include cross-tenant, ownership, role,
disabled-account, expired-token, and missing-permission cases where relevant.

### Output encoding and content handling

Encode output for the destination context. HTML, JSON, URLs, command arguments,
logs, CSV, XML, and templates have different escaping rules.

Avoid rendering untrusted markup or scriptable content. If rich content is
required, sanitize with an allowlist-based sanitizer appropriate for the output
format and document why rendering is necessary.

### Input validation

Validate at trust boundaries before data reaches core business logic. Validation
should define expected shape, type, size, range, encoding, and allowed values.

Example Python dataclass validation shape:

```python
from dataclasses import dataclass


@dataclass(frozen=True)
class CreateTask:
    title: str
    priority: str

    def validate(self) -> None:
        if not 1 <= len(self.title.strip()) <= 200:
            raise ValueError("title must be 1 to 200 characters")
        if self.priority not in {"low", "medium", "high"}:
            raise ValueError("priority is invalid")
```

Use the validation mechanism idiomatic to the target stack. Keep validation close
to the boundary and convert untrusted input into typed or structured internal
data before deeper processing.

### Files and generated content

For uploads, imports, exports, archives, reports, or generated files:

- restrict allowed file types, sizes, paths, and encodings
- inspect content rather than trusting extensions or declared media types
- store files outside executable paths where possible
- generate server-side filenames or object keys instead of trusting client names
- scan files when policy, risk, or platform requirements call for it
- protect against archive traversal, decompression bombs, metadata leakage, and unsafe previews

### Secrets and sensitive data

Keep secrets and sensitive data minimized, scoped, and observable without leaking
their values.

- Store real secrets in environment-specific secret stores or deployment configuration.
- Commit only templates with placeholder values when examples are needed.
- Redact sensitive values in logs, traces, metrics, error reports, and screenshots.
- Use least-privilege credentials and rotate them after exposure.
- Define retention, deletion, export, and redaction behavior for personal or regulated data.

Before committing, inspect staged changes using the repository's normal Git
workflow and any configured secret-scanning tools.

### Dependencies and supply chain

Treat dependencies, runtimes, images, lockfiles, generated code, and plugins as
part of the attack surface.

When an audit tool reports a vulnerability, triage it with these questions:

- Is the vulnerable component reachable in production or only present in development tooling?
- Is the vulnerable code path used by this system?
- Is a patched version or safe replacement available?
- Does the vulnerability matter in this deployment context?
- Is there a compensating control, and is it documented with a review date?

Fix critical or high reachable vulnerabilities before release unless an approved
exception documents the reason, owner, mitigation, and review date.

### Configuration and operations

Security controls often depend on runtime configuration. Review:

- transport encryption and certificate behavior
- security headers and cookie attributes for browser-facing systems
- cross-origin, network, firewall, and allowlist configuration
- rate limits, quotas, throttling, retries, and abuse controls
- error handling, debug mode, tracing, and observability settings
- backup, restore, retention, and key-management behavior
- production versus local defaults

Fail closed when policy, authorization, validation, or configuration cannot be
loaded safely.

## Review checklist

Use this quick checklist before handoff:

### Boundaries

- [ ] Trusted and untrusted inputs are identified.
- [ ] Input is validated and normalized at system boundaries.
- [ ] Output is encoded for the target context.
- [ ] Unsafe parsing, rendering, command, template, or evaluation paths are avoided or controlled.

### Identity and access

- [ ] Authentication uses established mechanisms and protects credential flows.
- [ ] Authorization checks the actor, action, resource, and tenant or ownership boundary.
- [ ] Denied paths are tested as well as allowed paths.
- [ ] Sensitive flows have rate limits or abuse controls where relevant.

### Data and secrets

- [ ] Secrets are not present in source code, logs, generated files, or version history.
- [ ] Sensitive fields are minimized, encrypted or protected when needed, and excluded from unsafe outputs.
- [ ] Retention, deletion, redaction, and export behavior are understood for sensitive data.

### Dependencies and configuration

- [ ] New dependencies, images, runtimes, and plugins were checked for known risks.
- [ ] Secure defaults are active in the target environment.
- [ ] Error responses and observability do not expose sensitive internals.
- [ ] Any accepted risk has an owner, reason, mitigation, and review date.

For a focused companion checklist, see `references/security-checklist.md`.

## Red flags

- User-controlled input reaches queries, commands, templates, file paths, or
  rendered output without validation and encoding.
- Authorization checks rely only on UI controls, client-provided roles, or authentication status.
- Secrets, tokens, private keys, or sensitive personal data appear in source code, logs, traces, errors, or screenshots.
- Debug mode, permissive cross-origin settings, wildcard network access, or
  detailed error pages are enabled in production.
- Dependency vulnerabilities are ignored without reachability analysis or documented risk acceptance.
- File uploads, archive extraction, dynamic imports, plugins, or generated code execute with excessive privileges.
- Tests cover success paths but not rejected, unauthorized, malformed, expired, or cross-boundary cases.

## Verification

After implementing security-relevant code:

- Run the project's configured dependency, secret, static-analysis, lint, test,
  and build checks that apply to the change.
- Add or update tests for validation failures, authorization denials, abuse controls, and sensitive-data redaction.
- Manually inspect configuration and staged changes for secrets or insecure defaults.
- Document any deferred vulnerability or accepted risk with an owner and review date.
- Confirm final handoff notes include which security checks passed, failed, or were skipped.
