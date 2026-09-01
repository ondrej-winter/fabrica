"""Composition helpers for explicitly enabled public-web retrieval."""

from collections.abc import Callable, Mapping
from dataclasses import dataclass

import httpx

from fabrica.features.agent_runtime.application.ports import AsyncRegisteredTool
from fabrica.features.web_content_fetching.adapters.inbound.registered_tool import (
    create_fetch_web_content_registered_tool,
)
from fabrica.features.web_content_fetching.adapters.outbound.content_processing import WebContentProcessingAdapter
from fabrica.features.web_content_fetching.adapters.outbound.httpx_fetcher import HttpxWebContentAttemptFetcher
from fabrica.features.web_content_fetching.application.dtos import FetchWebContentLimits
from fabrica.features.web_content_fetching.application.ports import PublicDnsResolver
from fabrica.features.web_content_fetching.application.use_cases import FetchWebContent


@dataclass(frozen=True, slots=True)
class FetchWebContentToolOptions:
    """Explicit host policy and dependencies for public-web retrieval."""

    public_web_enabled: bool
    headers: Mapping[str, str]
    resolver: PublicDnsResolver
    client_factory: Callable[[], httpx.AsyncClient]
    limits: FetchWebContentLimits

    def __post_init__(self) -> None:
        if not isinstance(self.public_web_enabled, bool):
            msg = "public_web_enabled must be a boolean"
            raise TypeError(msg)
        if any(not isinstance(key, str) or not isinstance(value, str) for key, value in self.headers.items()):
            msg = "headers must map strings to strings"
            raise TypeError(msg)


def create_fetch_web_content_registered_tool_adapter(
    *,
    options: FetchWebContentToolOptions,
) -> AsyncRegisteredTool:
    """Create a public-web tool without DNS, HTTP, or model activity at construction."""
    attempt_fetcher = HttpxWebContentAttemptFetcher(
        resolver=options.resolver,
        client_factory=options.client_factory,
        headers=options.headers,
    )
    use_case = FetchWebContent(attempt_fetcher=attempt_fetcher, processor=WebContentProcessingAdapter())
    return create_fetch_web_content_registered_tool(
        use_case,
        public_web_enabled=options.public_web_enabled,
        limits=options.limits,
    )


__all__ = ["FetchWebContentToolOptions", "create_fetch_web_content_registered_tool_adapter"]
