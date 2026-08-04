# Logging conventions

Use these rules to keep logging consistent, searchable, and easy to filter across modules.

This file covers logging implementation details. Broader code quality expectations live in `002-core-standards.md`. Secret source handling and configuration boundaries live in `008-configuration-and-secrets.md`.

## Default logger pattern

- **Must** define a module-level logger in any module that emits logs:
  - `LOGGER = logging.getLogger(__name__)`
- **Must** use the module-level `LOGGER` inside functions and class methods.
- **Must not** create per-instance loggers like `self._logger` by default.

## Message construction and levels

- **Must** use lazy log formatting (`LOGGER.info("user_id=%s", user_id)`) instead of eager f-strings in log calls.
- **Should** keep messages stable and searchable. Put highly variable details in structured context when possible.
- **Should** choose log levels based on operational usefulness: `debug` for diagnostics, `info` for state transitions, `warning` for recoverable anomalies, and `error` for user-visible or operator-visible failures.
- **Should** prefer concise, event-oriented messages with structured fields over dumping raw payloads into the message body.

## Context and structure

- **Should** include structured context via `extra={...}` for operational logs.
- **Should** use stable field names for recurring concepts (`request_id`, `job_id`, `component`, `adapter`, etc.).
- **Should** include `component` or equivalent context when class attribution is useful.
- **Should** propagate request, correlation, or job IDs when available.
- **Must not** put secrets or very high-cardinality raw values into structured fields by default.
- **Must** redact or avoid authentication headers, cookies, tokens, secrets, raw request/response bodies, file contents, and personal data unless there is an explicit approved need.
- **Should** prefer allowlisted metadata (IDs, counts, sizes, status codes, durations) over raw content.
- **Must** keep logger names hierarchical by using `__name__` to support selective filtering.

## Volume management

- **Should** sample, aggregate, or rate-limit repeated noisy logs in retry loops, polling loops, and hot paths.
- **Should** log outcomes at meaningful boundaries rather than every low-level step when high-volume logging would hide signal.

## Exception logging

- **Should** log an exception once at the boundary that can handle, translate, or report it.
- **Must** avoid duplicate full-stack logging at multiple layers for the same failure.
- **Should** use `LOGGER.exception(...)` when the stack trace is useful at that boundary. Otherwise, log contextual information and re-raise or translate with `from err`.

## Permitted deviations

- **May** use instance-specific loggers only when behavior requires runtime logger names or explicit logger injection.
- **Must** document the reason in a short inline comment when deviating from the default pattern.

## Central configuration

- **Must** configure logging through the central logging configuration utilities.
- **Must not** duplicate global logging setup in feature modules.
