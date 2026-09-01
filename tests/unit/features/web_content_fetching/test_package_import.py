"""Tests the web-content feature-slice package skeleton."""

import importlib
import socket

import httpx


class NetworkUseError(AssertionError):
    """Raised when a package import attempts network or HTTP client setup."""


def test_package_skeleton_imports_without_network_or_http_client_setup(monkeypatch) -> None:
    """Keep FWC-01 package imports free from runtime side effects."""

    def fail_protocol_client(*args: object, **kwargs: object) -> None:
        _ = (args, kwargs)
        msg = "unexpected network or HTTPX client setup"
        raise NetworkUseError(msg)

    monkeypatch.setattr(socket, "getaddrinfo", fail_protocol_client)
    monkeypatch.setattr(httpx, "AsyncClient", fail_protocol_client)

    for module_name in (
        "fabrica.features.web_content_fetching",
        "fabrica.features.web_content_fetching.application",
        "fabrica.features.web_content_fetching.application.dtos",
        "fabrica.features.web_content_fetching.application.ports",
        "fabrica.features.web_content_fetching.application.use_cases",
        "fabrica.features.web_content_fetching.adapters",
        "fabrica.features.web_content_fetching.adapters.inbound",
        "fabrica.features.web_content_fetching.adapters.inbound.registered_tool",
        "fabrica.features.web_content_fetching.adapters.outbound",
        "fabrica.features.web_content_fetching.adapters.outbound.content_processing",
        "fabrica.features.web_content_fetching.adapters.outbound.httpx_fetcher",
        "fabrica.features.web_content_fetching.adapters.outbound.network_policy",
    ):
        importlib.import_module(module_name)
