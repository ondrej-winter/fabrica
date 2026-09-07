"""Offline integration tests for explicit fetch-web-content tool composition."""

import asyncio
import json
from collections.abc import Mapping
from dataclasses import dataclass

import httpx
import pytest

from fabrica.bootstrap import FetchWebContentToolOptions, create_fetch_web_content_registered_tool_adapter
from fabrica.features.agent_runtime.application.dtos import (
    RegisteredToolOutcome,
    ToolArgumentValue,
    ToolExecutionContext,
    ToolTextContent,
    canonical_tool_arguments_digest,
)
from fabrica.features.agent_runtime.application.ports.registered_tool import AsyncRegisteredToolHandler
from fabrica.features.web_content_fetching.application.dtos import FetchWebContentLimits


def test_fetch_web_content_factory_is_inert_and_disabled_access_performs_no_dns_or_http_work() -> None:
    resolver = _FailingResolver()
    client_factory = _FailingClientFactory()
    arguments = {"requests": ({"url": "https://example.com/page"},)}
    tool = create_fetch_web_content_registered_tool_adapter(
        options=FetchWebContentToolOptions(
            public_web_enabled=False,
            headers={"User-Agent": "fabrica-test"},
            resolver=resolver,
            client_factory=client_factory,
            limits=FetchWebContentLimits(),
        )
    )

    assert resolver.calls == 0
    assert client_factory.calls == 0

    outcome = asyncio.run(_invoke(tool.handler, arguments, _context(arguments)))

    assert resolver.calls == 0
    assert client_factory.calls == 0
    text = "".join(part.text for part in outcome.content if isinstance(part, ToolTextContent))
    payload = json.loads(text)
    assert payload["results"] == [
        {
            "error": {"code": "PUBLIC_WEB_DISABLED", "message": "", "metadata": {}},
            "final_url": None,
            "redirects": [],
            "requested_url": "https://example.com/page",
            "status": None,
            "success": False,
            "trust": "untrusted_web_content",
        }
    ]


@pytest.mark.parametrize(
    ("public_web_enabled", "headers", "expected_message"),
    [
        ("false", {"User-Agent": "fabrica-test"}, "public_web_enabled must be a boolean"),
        (False, {"User-Agent": 1}, "headers must map strings to strings"),
    ],
)
def test_fetch_web_content_options_reject_invalid_host_configuration(
    public_web_enabled: object,
    headers: Mapping[str, object],
    expected_message: str,
) -> None:
    with pytest.raises(TypeError, match=expected_message):
        FetchWebContentToolOptions(
            public_web_enabled=public_web_enabled,  # ty: ignore[invalid-argument-type]
            headers=headers,  # ty: ignore[invalid-argument-type]
            resolver=_FailingResolver(),
            client_factory=_FailingClientFactory(),
            limits=FetchWebContentLimits(),
        )


@dataclass(slots=True)
class _FailingResolver:
    calls: int = 0

    async def resolve(self, hostname: str, context: object) -> tuple[str, ...]:
        _ = (hostname, context)
        self.calls += 1
        msg = "disabled access must not resolve DNS"
        raise AssertionError(msg)


@dataclass(slots=True)
class _FailingClientFactory:
    calls: int = 0

    def __call__(self) -> httpx.AsyncClient:
        self.calls += 1
        msg = "disabled access must not construct an HTTP client"
        raise AssertionError(msg)


@dataclass(frozen=True, slots=True)
class _NeverCancelled:
    @property
    def is_cancelled(self) -> bool:
        return False

    async def wait_until_cancelled(self) -> None:
        await asyncio.Event().wait()


async def _invoke(
    handler: AsyncRegisteredToolHandler,
    arguments: Mapping[str, ToolArgumentValue],
    context: ToolExecutionContext,
) -> RegisteredToolOutcome:
    return await handler(arguments, context)


def _context(arguments: Mapping[str, ToolArgumentValue]) -> ToolExecutionContext:
    return ToolExecutionContext(
        call_id="call-1",
        argument_digest=canonical_tool_arguments_digest(arguments),
        cancellation=_NeverCancelled(),
    )
