"""Tests for public web-content fetching application port ownership."""

import inspect
from datetime import UTC, datetime
from typing import cast

import pytest

from fabrica.features.web_content_fetching.application import ports
from fabrica.features.web_content_fetching.application.dtos import FetchWebContentLimits
from fabrica.features.web_content_fetching.application.ports import FetchWebContentContext


class NeverCancelled:
    """Test cancellation signal that never requests cancellation."""

    @property
    def is_cancelled(self) -> bool:
        return False


def test_web_content_fetching_ports_are_application_owned_without_transport_types() -> None:
    exported_names = set(ports.__all__)

    assert {
        "FetchCancellationSignal",
        "FetchWebContentContext",
        "FetchWebContentPort",
        "PublicDnsResolver",
        "WebContentAttemptFetcher",
    } <= exported_names
    for name in exported_names:
        exported = getattr(ports, name)
        assert inspect.isclass(exported)
        assert "fabrica.features.web_content_fetching.application.ports" in exported.__module__

    source = inspect.getsource(ports)
    assert ".adapters" not in source
    assert "httpx" not in source
    assert "open(" not in source


def test_fetch_context_requires_boolean_access_policy_and_aware_deadline() -> None:
    with pytest.raises(TypeError, match="boolean"):
        FetchWebContentContext(
            public_web_enabled=cast("bool", 1),
            cancellation=NeverCancelled(),
            deadline_at=None,
            limits=FetchWebContentLimits(),
        )
    with pytest.raises(ValueError, match="timezone-aware"):
        FetchWebContentContext(
            public_web_enabled=True,
            cancellation=NeverCancelled(),
            deadline_at=datetime.fromtimestamp(0, tz=UTC).replace(tzinfo=None),
            limits=FetchWebContentLimits(),
        )
