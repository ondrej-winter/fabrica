"""Tests for public-destination address validation."""

import asyncio
from dataclasses import dataclass, field

import pytest

from fabrica.features.web_content_fetching.adapters.outbound.network_policy import (
    ValidatedPublicDestination,
    ValidatedWebUrl,
    validate_public_destination,
    validate_web_url,
)
from fabrica.features.web_content_fetching.application.dtos import FetchError, FetchErrorCode, FetchWebContentLimits
from fabrica.features.web_content_fetching.application.ports import FetchWebContentContext


@dataclass
class FakeResolver:
    answers: tuple[str, ...] = ()
    error: OSError | None = None
    hostnames: list[str] = field(default_factory=list)

    async def resolve(self, hostname: str, context: FetchWebContentContext) -> tuple[str, ...]:
        _ = context
        self.hostnames.append(hostname)
        if self.error is not None:
            raise self.error
        return self.answers


class NeverCancelled:
    """Cancellation signal for deterministic policy tests."""

    @property
    def is_cancelled(self) -> bool:
        return False


@pytest.mark.parametrize(
    "address",
    [
        "0.0.0.0",  # noqa: S104 -- intentionally exercises unspecified-address rejection.
        "127.0.0.1",
        "10.0.0.1",
        "169.254.1.1",
        "100.64.0.1",
        "192.0.2.1",
        "198.18.0.1",
        "224.0.0.1",
        "::1",
        "fc00::1",
        "fe80::1",
        "ff00::1",
        "::ffff:127.0.0.1",
    ],
)
def test_validate_public_destination_rejects_non_public_answers(address: str) -> None:
    resolver = FakeResolver(answers=(address,))

    result = asyncio.run(
        validate_public_destination(_url("https://public.example"), resolver=resolver, context=_context())
    )

    assert isinstance(result, FetchError)
    assert result.code is FetchErrorCode.DESTINATION_NOT_ALLOWED
    assert result.metadata == {"address_count": 1}


def test_validate_public_destination_rejects_mixed_public_and_private_answers() -> None:
    resolver = FakeResolver(answers=("8.8.8.8", "10.0.0.1"))

    result = asyncio.run(
        validate_public_destination(_url("https://public.example"), resolver=resolver, context=_context())
    )

    assert isinstance(result, FetchError)
    assert result.code is FetchErrorCode.DESTINATION_NOT_ALLOWED


def test_validate_public_destination_rejects_localhost_when_it_resolves_to_loopback() -> None:
    resolver = FakeResolver(answers=("127.0.0.1",))

    result = asyncio.run(validate_public_destination(_url("https://localhost"), resolver=resolver, context=_context()))

    assert isinstance(result, FetchError)
    assert result.code is FetchErrorCode.DESTINATION_NOT_ALLOWED
    assert resolver.hostnames == ["localhost"]


def test_validate_public_destination_returns_all_public_answers_and_revalidates_each_request() -> None:
    resolver = FakeResolver(answers=("8.8.8.8", "2001:4860:4860::8888"))
    context = _context()

    first = asyncio.run(
        validate_public_destination(_url("https://public.example/one"), resolver=resolver, context=context)
    )
    second = asyncio.run(
        validate_public_destination(_url("https://public.example/two"), resolver=resolver, context=context)
    )

    assert first == ValidatedPublicDestination(_url("https://public.example/one"), ("8.8.8.8", "2001:4860:4860::8888"))
    assert second == ValidatedPublicDestination(_url("https://public.example/two"), ("8.8.8.8", "2001:4860:4860::8888"))
    assert resolver.hostnames == ["public.example", "public.example"]


def test_validate_public_destination_handles_dns_errors_and_empty_answers_without_leaking_details() -> None:
    error_result = asyncio.run(
        validate_public_destination(
            _url("https://failure.example"),
            resolver=FakeResolver(error=OSError("internal resolver address 10.0.0.5")),
            context=_context(),
        )
    )
    empty_result = asyncio.run(
        validate_public_destination(_url("https://empty.example"), resolver=FakeResolver(), context=_context())
    )

    assert isinstance(error_result, FetchError)
    assert isinstance(empty_result, FetchError)
    assert error_result.code is FetchErrorCode.DNS_FAILED
    assert "10.0.0.5" not in error_result.message
    assert empty_result.code is FetchErrorCode.DNS_FAILED


def test_validate_public_destination_checks_ip_literals_without_dns() -> None:
    resolver = FakeResolver(answers=("8.8.8.8",))

    result = asyncio.run(validate_public_destination(_url("https://127.0.0.1"), resolver=resolver, context=_context()))

    assert isinstance(result, FetchError)
    assert result.code is FetchErrorCode.DESTINATION_NOT_ALLOWED
    assert resolver.hostnames == []


def _url(url: str) -> ValidatedWebUrl:
    result = validate_web_url(url)
    assert isinstance(result, ValidatedWebUrl)
    return result


def _context() -> FetchWebContentContext:
    return FetchWebContentContext(
        public_web_enabled=True,
        cancellation=NeverCancelled(),
        deadline_at=None,
        limits=FetchWebContentLimits(),
    )
