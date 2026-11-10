"""Tests for the loopback-only model endpoint policy."""

from __future__ import annotations

import httpx
import pytest
from openai import OpenAI
from pydantic import ValidationError

from agent import (
    AgentConfig,
    EndpointPolicyError,
    LoopbackOnlyTransport,
    build_openai_client,
    validate_openai_client_endpoint,
)
from config import Settings


@pytest.mark.parametrize(
    "url",
    [
        "https://attacker.example/v1",
        "http://attacker.example/v1",
        "http://user:password@127.0.0.1/v1",
        "http://127.0.0.1/v1?token=secret",
        "http://127.0.0.1/v1#fragment",
        "http://localhost:11434/v1",
        "http://0.0.0.0:11434/v1",
        "http://127.0.0.1:bad/v1",
    ],
)
def test_agent_config_rejects_nonlocal_or_sensitive_endpoints(url: str) -> None:
    with pytest.raises(ValidationError):
        AgentConfig(base_url=url)


def test_settings_rejects_hostname_endpoint_during_config_resolution() -> None:
    with pytest.raises(ValidationError):
        Settings(base_url="http://localhost:11434/v1")


@pytest.mark.parametrize(
    "url",
    [
        "http://127.0.0.2:11434/v1",
        "http://127.0.0.1:11434/v1",
        "http://[::1]:11434/v1",
    ],
)
def test_loopback_endpoints_are_accepted(url: str) -> None:
    assert AgentConfig(base_url=url).base_url == url


def test_built_client_disables_proxy_and_redirect_paths(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("HTTP_PROXY", "http://proxy.attacker.invalid:8080")
    monkeypatch.setenv("HTTPS_PROXY", "http://proxy.attacker.invalid:8080")
    monkeypatch.setenv("ALL_PROXY", "http://proxy.attacker.invalid:8080")
    client = build_openai_client(AgentConfig())
    try:
        assert validate_openai_client_endpoint(client) == "loopback"
        http_client = client._client
        assert http_client.trust_env is False
        assert http_client.follow_redirects is False
        assert http_client._mounts == {}
        assert type(http_client._transport) is LoopbackOnlyTransport
        assert type(http_client._transport._inner) is httpx.HTTPTransport
    finally:
        client.close()


def test_guarded_transport_refuses_redirect_destination_before_socket() -> None:
    class CountingTransport(httpx.BaseTransport):
        def __init__(self) -> None:
            self.requests = 0

        def handle_request(self, request: httpx.Request) -> httpx.Response:
            self.requests += 1
            return httpx.Response(200, request=request)

        def close(self) -> None:
            pass

    inner = CountingTransport()
    guarded = LoopbackOnlyTransport(inner)

    with pytest.raises(EndpointPolicyError):
        guarded.handle_request(httpx.Request("GET", "https://attacker.example/redirect"))

    assert inner.requests == 0


def test_unguarded_openai_transport_is_rejected_even_for_loopback_url() -> None:
    client = OpenAI(base_url="http://127.0.0.1:11434/v1", api_key="local")
    try:
        with pytest.raises(EndpointPolicyError):
            validate_openai_client_endpoint(client)
    finally:
        client.close()


def test_proxy_transport_wrapped_by_guard_is_rejected() -> None:
    proxy_transport = httpx.HTTPTransport(proxy="http://127.0.0.1:9999")
    http_client = httpx.Client(
        trust_env=False,
        follow_redirects=False,
        transport=LoopbackOnlyTransport(proxy_transport),
    )
    client = OpenAI(
        base_url="http://127.0.0.1:11434/v1",
        api_key="local",
        http_client=http_client,
    )
    try:
        with pytest.raises(EndpointPolicyError):
            validate_openai_client_endpoint(client)
    finally:
        client.close()


def test_unix_domain_socket_transport_wrapped_by_guard_is_rejected() -> None:
    uds_transport = httpx.HTTPTransport(uds="omniagent-test.sock")
    http_client = httpx.Client(
        trust_env=False,
        follow_redirects=False,
        transport=LoopbackOnlyTransport(uds_transport),
    )
    client = OpenAI(
        base_url="http://127.0.0.1:11434/v1",
        api_key="local",
        http_client=http_client,
    )
    try:
        with pytest.raises(EndpointPolicyError):
            validate_openai_client_endpoint(client)
    finally:
        client.close()


def test_custom_network_backend_is_rejected() -> None:
    client = build_openai_client(AgentConfig())
    try:
        transport = client._client._transport
        assert type(transport) is LoopbackOnlyTransport
        pool = vars(transport._inner)["_pool"]
        pool._network_backend = object()

        with pytest.raises(EndpointPolicyError):
            validate_openai_client_endpoint(client)
    finally:
        client.close()


def test_guard_rejects_socket_pool_mutation_before_inner_request() -> None:
    inner = httpx.HTTPTransport()
    guard = LoopbackOnlyTransport(inner)
    pool = inner._pool
    pool._uds = "mutated-socket-path"

    with pytest.raises(EndpointPolicyError):
        guard.handle_request(httpx.Request("GET", "http://127.0.0.1:11434/v1"))


def test_client_without_verifiable_endpoint_is_rejected() -> None:
    with pytest.raises(EndpointPolicyError):
        validate_openai_client_endpoint(object())
