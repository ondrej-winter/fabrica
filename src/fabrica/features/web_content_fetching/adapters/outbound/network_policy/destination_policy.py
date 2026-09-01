"""DNS and IP-address policy for public web fetch destinations."""

import ipaddress
from dataclasses import dataclass

from fabrica.features.web_content_fetching.adapters.outbound.network_policy.url_policy import ValidatedWebUrl
from fabrica.features.web_content_fetching.application.dtos import FetchError, FetchErrorCode
from fabrica.features.web_content_fetching.application.ports import FetchWebContentContext, PublicDnsResolver


@dataclass(frozen=True, slots=True)
class ValidatedPublicDestination:
    """A URL whose complete current address set is globally routable."""

    url: ValidatedWebUrl
    addresses: tuple[str, ...]


async def validate_public_destination(
    url: ValidatedWebUrl,
    *,
    resolver: PublicDnsResolver,
    context: FetchWebContentContext,
) -> ValidatedPublicDestination | FetchError:
    """Resolve one URL hostname and reject any non-global address in its answer set."""
    addresses = await _resolve_addresses(url, resolver=resolver, context=context)
    if isinstance(addresses, FetchError):
        return addresses
    if any(not _is_globally_routable(address) for address in addresses):
        return FetchError(
            code=FetchErrorCode.DESTINATION_NOT_ALLOWED,
            message="Destination is not publicly routable",
            metadata={"address_count": len(addresses)},
        )
    return ValidatedPublicDestination(url=url, addresses=addresses)


async def _resolve_addresses(
    url: ValidatedWebUrl,
    *,
    resolver: PublicDnsResolver,
    context: FetchWebContentContext,
) -> tuple[str, ...] | FetchError:
    """Resolve a hostname or preserve an already-parsed IP literal."""
    try:
        literal = ipaddress.ip_address(url.hostname)
    except ValueError:
        try:
            addresses = await resolver.resolve(url.hostname, context)
        except OSError:
            return FetchError(code=FetchErrorCode.DNS_FAILED, message="DNS resolution failed")
        if not addresses:
            return FetchError(code=FetchErrorCode.DNS_FAILED, message="DNS resolution returned no addresses")
        return tuple(addresses)
    return (str(literal),)


def _is_globally_routable(address: str) -> bool:
    """Return whether one DNS answer is a globally routable IP address."""
    try:
        candidate = ipaddress.ip_address(address)
    except ValueError:
        return False
    return candidate.is_global and not any(
        (
            candidate.is_loopback,
            candidate.is_private,
            candidate.is_link_local,
            candidate.is_multicast,
            candidate.is_unspecified,
            candidate.is_reserved,
        )
    )


__all__ = ["ValidatedPublicDestination", "validate_public_destination"]
