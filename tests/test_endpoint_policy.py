"""Tests for the loopback-only model endpoint policy."""

from __future__ import annotations

import socket
from typing import Any, NoReturn

import httpx
import pytest
from openai import OpenAI
from pydantic import ValidationError

from agent import (
    DEFAULT_BASE_URL,
    AgentConfig,
    EndpointPolicyError,
    LoopbackOnlyTransport,
    build_openai_client,
    validate_loopback_url,
    validate_openai_client_endpoint,
)
from config import ConfigError, Settings, resolve


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


# --------------------------------------------------------------------------- #
# the endpoint corpus (contract section 2, as amended 2026-11-22)
# --------------------------------------------------------------------------- #
#
# Contract section 2 permits loopback IP literals only; ``localhost`` is refused.
# The corpus is brief 14's frozen set, with the five ``localhost`` spellings that
# an earlier tree accepted moved to the rejected side.
#
# Every rejection below is asserted three ways at once: it raises, it raises
# *before* any socket (the autouse shim below fails the test otherwise), and the
# message names the branch that fired. The third is what keeps one branch from
# hiding behind another: several corpus forms are refused by two branches, so a
# test that only asserted "refused" would stay green with either deleted.

#: A port nothing on this machine listens on.
UNUSED_PORT = 65500

_PREFIX = "base_url must name the local loopback endpoint:"

#: Fragments of the validator's own messages, one per branch.
CANNOT_PARSE = "it cannot be parsed"
SCHEME = "the scheme must be 'http'"
USER_INFO = "user information is not allowed"
QUERY_OR_FRAGMENT = "query and fragment are not allowed"
NO_HOST = "it names no host"
NOT_AN_IP_LITERAL = "the host must be a loopback IP literal"
UNSPECIFIED = "an unspecified bind address is not an approved destination"
IPV4_MAPPED = "IPv4-mapped IPv6 addresses are not approved loopback destinations"
NOT_LOOPBACK = "the host is not a loopback address"
BAD_PORT = "the port must be valid"

#: 3 accepted forms, plus the tree's own default (tested on its own below).
ACCEPTED_CORPUS = [
    pytest.param("http://127.0.0.1:11434/v1", id="loopback IPv4"),
    pytest.param("http://[::1]:11434/v1", id="loopback IPv6"),
    # 127.0.0.0/8 is loopback in its entirety, not just .1.
    pytest.param("http://127.0.0.2:11434/v1", id="the rest of 127.0.0.0/8"),
]

#: 28 rejected forms: (url, why, the branch that must refuse it).
REJECTED_CORPUS = [
    ("http://evil.example/v1", "a foreign host", NOT_AN_IP_LITERAL),
    (
        "http://127.0.0.1.example.com/v1",
        "a host that only begins with the digits",
        NOT_AN_IP_LITERAL,
    ),
    (
        "http://localhost.attacker.test/v1",
        "a host that only begins with localhost",
        NOT_AN_IP_LITERAL,
    ),
    ("http://localhost./v1", "the trailing-dot form of localhost", NOT_AN_IP_LITERAL),
    ("http://0.0.0.0:11434/v1", "the unspecified IPv4 address", UNSPECIFIED),
    ("http://[::]:11434/v1", "the unspecified IPv6 address", UNSPECIFIED),
    ("http://[::ffff:127.0.0.1]:11434/v1", "IPv4-mapped loopback", IPV4_MAPPED),
    ("http://ollama:11434/v1", "a bare hostname", NOT_AN_IP_LITERAL),
    ("http://2130706433/v1", "loopback as a 32-bit integer", NOT_AN_IP_LITERAL),
    ("http://0x7f000001/v1", "loopback in hexadecimal", NOT_AN_IP_LITERAL),
    ("http://127.1:11434/v1", "the short form of loopback", NOT_AN_IP_LITERAL),
    ("file:///etc/passwd", "a file URL", SCHEME),
    ("ftp://localhost/v1", "a non-HTTP scheme", SCHEME),
    ("https://localhost:11434/v1", "TLS on loopback, refused deliberately", SCHEME),
    ("http://user:pw@localhost:11434/v1", "user information", USER_INFO),
    (
        "http://localhost:11434@evil.example/v1",
        "loopback hidden in the user information",
        USER_INFO,
    ),
    ("http://localhost:11434/v1?stream=1", "a query", QUERY_OR_FRAGMENT),
    ("http://localhost:11434/v1#fragment", "a fragment", QUERY_OR_FRAGMENT),
    ("http://localhost:notaport/v1", "a port that is not a number", CANNOT_PARSE),
    ("http://[::1/v1", "a malformed IPv6 host", CANNOT_PARSE),
    ("http:///v1", "no host at all", NO_HOST),
    ("not a url at all", "not a URL", SCHEME),
    ("", "the empty string", SCHEME),
    # The five spellings of localhost that an earlier tree accepted. Contract
    # section 2 now refuses them, as hostnames - the name is resolved by the
    # system, not by this code, so it is not a loopback IP literal.
    ("http://localhost:11434/v1", "a hostname, including localhost", NOT_AN_IP_LITERAL),
    ("http://localhost:1/v1", "a hostname, including localhost (port 1)", NOT_AN_IP_LITERAL),
    ("http://localhost/v1", "a hostname, including localhost (no port)", NOT_AN_IP_LITERAL),
    ("http://localhost:11434/", "a hostname, including localhost (no path)", NOT_AN_IP_LITERAL),
    (
        "http://LOCALHOST:11434/v1",
        "a hostname, including localhost (upper case)",
        NOT_AN_IP_LITERAL,
    ),
]

REJECTED_PARAMS = [pytest.param(url, fragment, id=why) for url, why, fragment in REJECTED_CORPUS]

#: Forms the frozen corpus does not contain, so a branch only these can reach
#: is not left unpinned: a non-loopback IP literal and port zero.
BEYOND_THE_CORPUS = [
    pytest.param("http://192.168.1.10:11434/v1", NOT_LOOPBACK, id="a private IPv4 literal"),
    pytest.param("http://8.8.8.8/v1", NOT_LOOPBACK, id="a public IPv4 literal"),
    pytest.param("http://[2001:db8::1]:11434/v1", NOT_LOOPBACK, id="a non-loopback IPv6 literal"),
    pytest.param("http://127.0.0.1:0/v1", BAD_PORT, id="port zero"),
]


@pytest.fixture(autouse=True)
def _forbid_every_socket(monkeypatch: pytest.MonkeyPatch) -> None:
    """Any connection attempt in this module is a failure, not a result.

    ``http://evil.example/v1`` is unreachable from this machine anyway, so a test
    that only asserts "an error happened" is green with no validator at all - it
    is testing the network. With every socket forbidden, a rejection can only be
    green if it happened before a connection was attempted.
    """

    def refuse(*_args: Any, **_kwargs: Any) -> NoReturn:
        raise AssertionError("a socket was opened: the refusal came too late")

    monkeypatch.setattr(socket.socket, "connect", refuse)
    monkeypatch.setattr(socket.socket, "connect_ex", refuse)
    monkeypatch.setattr(socket, "create_connection", refuse)
    monkeypatch.setattr(httpx.HTTPTransport, "handle_request", refuse)


def test_the_corpus_has_the_amended_shape() -> None:
    assert len(ACCEPTED_CORPUS) + len(REJECTED_CORPUS) == 31
    assert len(REJECTED_CORPUS) == 28
    urls = [url for url, _, _ in REJECTED_CORPUS]
    assert len(set(urls)) == len(urls)
    assert not {p.values[0] for p in ACCEPTED_CORPUS} & set(urls)


@pytest.mark.parametrize("url", ACCEPTED_CORPUS)
def test_every_accepted_form_constructs(url: str) -> None:
    assert validate_loopback_url(url) == url
    assert AgentConfig(base_url=url).base_url == url
    assert Settings(base_url=url).base_url == url


def test_the_shipped_default_is_accepted_by_its_own_validator() -> None:
    """A policy that refused the default would be discovered by every user."""
    assert DEFAULT_BASE_URL == "http://127.0.0.1:11434/v1"
    assert validate_loopback_url(DEFAULT_BASE_URL) == DEFAULT_BASE_URL
    assert AgentConfig().base_url == DEFAULT_BASE_URL
    assert Settings().base_url == DEFAULT_BASE_URL


@pytest.mark.parametrize(("url", "branch"), REJECTED_PARAMS)
def test_the_validator_refuses_every_rejected_form_for_its_own_reason(
    url: str, branch: str
) -> None:
    with pytest.raises(EndpointPolicyError) as caught:
        validate_loopback_url(url)

    assert str(caught.value) == f"{_PREFIX} {branch}"


@pytest.mark.parametrize(("url", "branch"), REJECTED_PARAMS)
def test_agent_config_refuses_every_rejected_form_for_its_own_reason(
    url: str, branch: str
) -> None:
    with pytest.raises(ValidationError) as caught:
        AgentConfig(base_url=url)

    assert f"{_PREFIX} {branch}" in str(caught.value)


@pytest.mark.parametrize(("url", "branch"), REJECTED_PARAMS)
def test_settings_refuses_every_rejected_form_for_its_own_reason(
    url: str, branch: str
) -> None:
    with pytest.raises(ValidationError) as caught:
        Settings(base_url=url)

    assert f"{_PREFIX} {branch}" in str(caught.value)


@pytest.mark.parametrize(("url", "branch"), REJECTED_PARAMS)
def test_config_resolution_refuses_every_rejected_form(url: str, branch: str) -> None:
    with pytest.raises(ConfigError, match="base_url") as caught:
        resolve({"base_url": url}, env={}, use_env_file=False)

    assert branch in str(caught.value)


@pytest.mark.parametrize(("url", "branch"), BEYOND_THE_CORPUS)
def test_forms_beyond_the_corpus_are_refused_for_their_own_reason(
    url: str, branch: str
) -> None:
    with pytest.raises(EndpointPolicyError) as caught:
        validate_loopback_url(url)

    assert str(caught.value) == f"{_PREFIX} {branch}"
    with pytest.raises(ValidationError):
        AgentConfig(base_url=url)
    with pytest.raises(ValidationError):
        Settings(base_url=url)


def test_a_rejected_form_never_reaches_a_client() -> None:
    """The refusal is at configuration, not at build or request time."""
    with pytest.raises(ValidationError):
        build_openai_client(AgentConfig(base_url="http://localhost:11434/v1"))


def test_the_refusal_message_does_not_echo_the_unused_port() -> None:
    url = f"http://localhost:{UNUSED_PORT}/v1"

    with pytest.raises(EndpointPolicyError) as caught:
        validate_loopback_url(url)

    assert str(UNUSED_PORT) not in str(caught.value)
    assert "localhost" not in str(caught.value)
