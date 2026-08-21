"""Exceptions raised by HTTPX retry execution."""

import httpx

from fabrica.adapters.outbound.httpx_client.contracts import RetryDiagnostics


class HttpxRetryError(Exception):
    """HTTPX request failure with bounded retry diagnostics."""

    def __init__(self, error: httpx.HTTPError, diagnostics: RetryDiagnostics) -> None:
        super().__init__(str(error))
        self.error_type = type(error).__name__
        self.diagnostics = diagnostics
