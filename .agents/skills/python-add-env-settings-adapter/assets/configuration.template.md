# Configuration

This document is the canonical reference for runtime configuration options.
Keep it synchronized with `EnvSettings`, `AppSettings`, `.env.example`, and
settings tests.

## Environment variables

| Variable                      | Field             | Required | Default                        | Example                        | Secret | Description                            |
| ----------------------------- | ----------------- | -------- | ------------------------------ | ------------------------------ | ------ | -------------------------------------- |
| `EXAMPLE_APP_REQUIRED_SECRET` | `required_secret` | Yes      | None                           | `change-me-local-secret`       | Yes    | Shared secret used by the application. |
| `EXAMPLE_APP_SERVICE_URL`     | `service_url`     | No       | `https://service.example.test` | `https://service.example.test` | No     | Base URL for the external service.     |
| `EXAMPLE_APP_OUTPUT_PATH`     | `output_path`     | No       | `.local-data/output.sqlite3`   | `.local-data/output.sqlite3`   | No     | Local path for runtime output data.    |

## Notes

- `.env` files are supported for local development.
- Values are loaded once at startup through the environment settings adapter.
- Secret values must not be committed, logged, printed, or included in error
  messages.
- Use `.env.example` as the starting point for local configuration.
