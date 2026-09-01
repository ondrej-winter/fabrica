"""Asyncio-backed DNS resolution for public web fetch validation."""

import asyncio
import socket
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import cast

from fabrica.features.web_content_fetching.application.ports import FetchWebContentContext

type SocketAddress = tuple[str, int] | tuple[str, int, int, int]
type AddressInfo = tuple[int, int, int, str, SocketAddress]
type Getaddrinfo = Callable[..., Awaitable[list[AddressInfo]]]


@dataclass(frozen=True, slots=True)
class AsyncioPublicDnsResolver:
    """Resolve hostnames through an injectable asyncio getaddrinfo boundary."""

    getaddrinfo: Getaddrinfo | None = None

    async def resolve(self, hostname: str, context: FetchWebContentContext) -> tuple[str, ...]:
        """Return deduplicated IPv4 and IPv6 answers for one hostname."""
        _ = context
        getaddrinfo = self.getaddrinfo or asyncio.get_running_loop().getaddrinfo
        answers = await getaddrinfo(hostname, None, family=socket.AF_UNSPEC, type=socket.SOCK_STREAM)
        return tuple(dict.fromkeys(cast("str", answer[4][0]) for answer in answers))


__all__ = ["AsyncioPublicDnsResolver", "Getaddrinfo"]
