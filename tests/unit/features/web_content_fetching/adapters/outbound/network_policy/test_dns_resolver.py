"""Tests for the injectable asyncio DNS resolver adapter."""

import asyncio
from typing import cast

from fabrica.features.web_content_fetching.adapters.outbound.network_policy import AsyncioPublicDnsResolver
from fabrica.features.web_content_fetching.adapters.outbound.network_policy.dns_resolver import AddressInfo
from fabrica.features.web_content_fetching.application.dtos import FetchWebContentLimits
from fabrica.features.web_content_fetching.application.ports import FetchWebContentContext


class NeverCancelled:
    """Cancellation signal for deterministic resolver tests."""

    @property
    def is_cancelled(self) -> bool:
        return False


def test_asyncio_dns_resolver_deduplicates_ipv4_and_ipv6_answers() -> None:
    calls: list[tuple[object, ...]] = []

    async def getaddrinfo(*args: object, **kwargs: object) -> list[AddressInfo]:
        calls.append((*args, kwargs))
        return [
            cast("AddressInfo", (0, 0, 0, "", ("8.8.8.8", 0))),
            cast("AddressInfo", (0, 0, 0, "", ("2001:4860:4860::8888", 0, 0, 0))),
            cast("AddressInfo", (0, 0, 0, "", ("8.8.8.8", 0))),
        ]

    addresses = asyncio.run(AsyncioPublicDnsResolver(getaddrinfo=getaddrinfo).resolve("public.example", _context()))

    assert addresses == ("8.8.8.8", "2001:4860:4860::8888")
    assert calls[0][0:2] == ("public.example", None)


def _context() -> FetchWebContentContext:
    return FetchWebContentContext(
        public_web_enabled=True,
        cancellation=NeverCancelled(),
        deadline_at=None,
        limits=FetchWebContentLimits(),
    )
