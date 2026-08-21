"""HTTPX retry client lifecycle wrapper."""

from __future__ import annotations

from typing import TYPE_CHECKING

import httpx

from fabrica.adapters.outbound.httpx_client.executor import SyncHttpxRetryExecutor

if TYPE_CHECKING:
    from collections.abc import Callable

    from fabrica.adapters.outbound.httpx_client.contracts import HttpxRetryRequest, HttpxRetryResult


class SyncHttpxRetryClient:
    """Create HTTPX clients, execute retry requests, and own client lifecycle."""

    def __init__(
        self,
        *,
        client_factory: Callable[[], httpx.Client] | None = None,
        executor: SyncHttpxRetryExecutor | None = None,
    ) -> None:
        self._client_factory = client_factory if client_factory is not None else httpx.Client
        self._executor = executor if executor is not None else SyncHttpxRetryExecutor()

    def request(self, request: HttpxRetryRequest) -> HttpxRetryResult:
        """Execute one retry request using a short-lived HTTPX client."""
        with self._client_factory() as client:
            return self._executor.request(client=client, request=request)
