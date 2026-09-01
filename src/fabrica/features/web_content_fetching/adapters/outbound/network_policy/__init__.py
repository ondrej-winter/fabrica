"""Outbound DNS and public-destination policy adapters."""

from fabrica.features.web_content_fetching.adapters.outbound.network_policy.destination_policy import (
    ValidatedPublicDestination,
    validate_public_destination,
)
from fabrica.features.web_content_fetching.adapters.outbound.network_policy.dns_resolver import AsyncioPublicDnsResolver
from fabrica.features.web_content_fetching.adapters.outbound.network_policy.url_policy import (
    ValidatedWebUrl,
    validate_web_url,
)

__all__ = [
    "AsyncioPublicDnsResolver",
    "ValidatedPublicDestination",
    "ValidatedWebUrl",
    "validate_public_destination",
    "validate_web_url",
]
