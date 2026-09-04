"""Asynchronous HTTPX retry client lifecycle wrapper."""

from __future__ import annotations

from typing import TYPE_CHECKING

import httpx

from fabrica.adapters.outbound.httpx_client.async_executor import AsyncHttpxRetryExecutor

if TYPE_CHECKING:
    from collections.abc import Callable

    from fabrica.adapters.outbound.httpx_client.contracts import (
        AsyncHttpBodyConsumer,
        HttpxRetryRequest,
        HttpxRetryResult,
    )


class AsyncHttpxRetryClient:
    """Create async HTTPX clients, execute retry requests, and own client lifecycle."""

    def __init__(
        self,
        *,
        client_factory: Callable[[], httpx.AsyncClient] | None = None,
        executor: AsyncHttpxRetryExecutor | None = None,
    ) -> None:
        self._client_factory = client_factory if client_factory is not None else httpx.AsyncClient
        self._executor = executor if executor is not None else AsyncHttpxRetryExecutor()

    async def request(self, request: HttpxRetryRequest) -> HttpxRetryResult:
        """Execute one retry request using a short-lived async HTTPX client."""
        async with self._client_factory() as client:
            return await self._executor.request(client=client, request=request)

    async def stream(self, request: HttpxRetryRequest, body_consumer: AsyncHttpBodyConsumer) -> HttpxRetryResult:
        """Execute a retry request and pass its unbuffered body to one consumer.

        The shared client owns the HTTPX response and client lifecycles. It makes
        a retry decision before consuming the response body and never retries
        after consumption starts.
        """
        async with self._client_factory() as client:
            return await self._executor.stream(client=client, request=request, body_consumer=body_consumer)
