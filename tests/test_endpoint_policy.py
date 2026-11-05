"""Gate 1: the endpoint cannot leave loopback, and the refusal precedes the socket.

The contract (``docs/pm/agentic-mvp-contract-2026-11-03.md``, section 2) permits
exactly one destination for model inference: an HTTP endpoint on loopback. The
source accepted any URL, so these tests exist to make "no request *can* route
off loopback" a checkable claim rather than a stated one.

**Why every rejection test forbids sockets.** ``http://evil.example/v1`` is
unreachable from this machine anyway, so a test that only asserts "an error
happened" is green with no validator at all -- it is testing the network. The
autouse fixture below makes any socket an immediate failure, so a rejection can
only be green if it happened before a connection was attempted. Delete the
validator and these tests go red for the right reason.
"""

from __future__ import annotations

import socket
from pathlib import Path
from typing import Any, NoReturn

import httpx
import pytest
from openai import APIConnectionError
from pydantic import ValidationError

from agent import (
    DEFAULT_BASE_URL,
    ENDPOINT_DESCRIPTION,
    AgentConfig,
    AgentError,
    EndpointPolicyError,
    LoopbackOnlyTransport,
    ReActAgent,
    build_local_http_client,
    build_openai_client,
    validate_loopback_url,
)
from config import ConfigError, Settings, resolve
from tests.fakes import FakeOpenAI

#: A port nothing on this machine listens on, distinctive enough that a test can
#: assert it does not appear in an error message.
UNUSED_PORT = 65500

ACCEPTED = [
    DEFAULT_BASE_URL,
    "http://localhost:11434/v1",
    "http://127.0.0.1:11434/v1",
    "http://[::1]:11434/v1",
    "http://localhost:1/v1",
    "http://localhost/v1",
    "http://localhost:11434/",
    # 127.0.0.0/8 is loopback in its entirety, not just .1.
    "http://127.0.0.2:11434/v1",
    # urlsplit lower-cases the host, so case is not a way in or out.
    "http://LOCALHOST:11434/v1",
]

REJECTED = [
    ("http://evil.example/v1", "a foreign host"),
    ("http://127.0.0.1.example.com/v1", "a host that only begins with the digits"),
    ("http://localhost.attacker.test/v1", "a host that only begins with localhost"),
    ("http://localhost./v1", "the trailing-dot form of localhost"),
    ("http://0.0.0.0:11434/v1", "the unspecified IPv4 address"),
    ("http://[::]:11434/v1", "the unspecified IPv6 address"),
    ("http://[::ffff:127.0.0.1]:11434/v1", "IPv4-mapped loopback"),
    ("http://ollama:11434/v1", "a bare hostname"),
    ("http://2130706433/v1", "loopback as a 32-bit integer"),
    ("http://0x7f000001/v1", "loopback in hexadecimal"),
    ("http://127.1:11434/v1", "the short form of loopback"),
    ("file:///etc/passwd", "a file URL"),
    ("ftp://localhost/v1", "a non-HTTP scheme"),
    ("https://localhost:11434/v1", "TLS on loopback, refused deliberately"),
    ("http://user:pw@localhost:11434/v1", "user information"),
    ("http://localhost:11434@evil.example/v1", "loopback hidden in the user information"),
    ("http://localhost:11434/v1?stream=1", "a query"),
    ("http://localhost:11434/v1#fragment", "a fragment"),
    ("http://localhost:notaport/v1", "a port that is not a number"),
    ("http://[::1/v1", "a malformed IPv6 host"),
    ("http:///v1", "no host at all"),
    ("not a url at all", "not a URL"),
    ("", "the empty string"),
]

REJECTED_URLS = [url for url, _ in REJECTED]
REJECTED_IDS = [why for _, why in REJECTED]


@pytest.fixture(autouse=True)
def _forbid_every_socket(monkeypatch: pytest.MonkeyPatch) -> None:
    """Any connection attempt in this module is a failure, not a result.

    This is what makes a rejection test a test of the validator: if the refusal
    arrived at connection time, the shim raises first and the test fails with a
    message saying so.
    """

    def refuse(*_args: Any, **_kwargs: Any) -> NoReturn:
        raise AssertionError("a socket was opened: the refusal came too late")

    monkeypatch.setattr(socket.socket, "connect", refuse)
    monkeypatch.setattr(socket.socket, "connect_ex", refuse)
    monkeypatch.setattr(socket, "create_connection", refuse)
    monkeypatch.setattr(httpx.HTTPTransport, "handle_request", refuse)


# --------------------------------------------------------------------------- #
# what the policy accepts
# --------------------------------------------------------------------------- #


@pytest.mark.parametrize("url", ACCEPTED)
def test_every_accepted_form_constructs(url: str) -> None:
    assert AgentConfig(base_url=url).base_url == url
    assert Settings(base_url=url).base_url == url
    assert validate_loopback_url(url) == url


def test_the_shipped_default_is_accepted_by_its_own_validator() -> None:
    """A policy that refused the default would be discovered by every user."""
    assert AgentConfig().base_url == DEFAULT_BASE_URL


# --------------------------------------------------------------------------- #
# what it refuses, before a socket exists
# --------------------------------------------------------------------------- #


@pytest.mark.parametrize("url", REJECTED_URLS, ids=REJECTED_IDS)
def test_every_rejected_form_raises_at_configuration_time(url: str) -> None:
    with pytest.raises(ValidationError):
        AgentConfig(base_url=url)


@pytest.mark.parametrize("url", REJECTED_URLS, ids=REJECTED_IDS)
def test_the_settings_layer_refuses_the_same_forms(url: str) -> None:
    """``Settings`` is where the CLI, the environment and the TOML land."""
    with pytest.raises(ValidationError):
        Settings(base_url=url)


@pytest.mark.parametrize("url", REJECTED_URLS, ids=REJECTED_IDS)
def test_the_validator_is_the_one_refusing(url: str) -> None:
    with pytest.raises(EndpointPolicyError):
        validate_loopback_url(url)


def test_a_rejected_endpoint_from_the_environment_names_the_layer() -> None:
    """The user-facing path reports which layer supplied the bad value."""
    with pytest.raises(ConfigError) as caught:
        resolve(env={"OMNIAGENT_BASE_URL": "http://evil.example/v1"}, use_env_file=False)

    assert "base_url (environment)" in str(caught.value)


def test_a_rejected_endpoint_in_a_config_file_is_refused_at_load(tmp_path: Path) -> None:
    config_file = tmp_path / "omniagent.toml"
    config_file.write_text('[defaults]\nbase_url = "http://evil.example/v1"\n', encoding="utf-8")

    with pytest.raises(ConfigError):
        resolve(config_path=config_file, env={}, use_env_file=False)


def test_the_refusal_does_not_echo_user_information() -> None:
    """A credential in the URL must not be copied into the error text.

    Only the validator's own message is asserted on. Pydantic's envelope
    repeats the input value, which is why ``config.resolve`` -- the path a user
    reaches -- rebuilds the message from ``msg`` alone.
    """
    with pytest.raises(ValidationError) as caught:
        AgentConfig(base_url="http://user:hunter2@localhost:11434/v1")

    message = caught.value.errors()[0]["msg"]
    assert "hunter2" not in message


def test_building_an_agent_with_a_rejected_endpoint_never_reaches_a_client() -> None:
    """The config object cannot hold an invalid endpoint until something uses it."""
    with pytest.raises(ValidationError):
        ReActAgent(config=AgentConfig(base_url="http://evil.example/v1"))


# --------------------------------------------------------------------------- #
# the client cannot be routed elsewhere
# --------------------------------------------------------------------------- #


def test_proxy_environment_variables_cannot_carry_the_request(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """With all three variables set, the transport that would carry a request to
    the endpoint is still the policy transport, not a proxy mount.

    The routing assertions and the flag assertion catch different mistakes, and
    both were checked by mutation. Dropping the explicit transport is what
    actually lets httpx mount the environment's proxies
    (``allow_env_proxies = trust_env and transport is None``), and that is what
    the routing assertions below go red on. Flipping ``trust_env`` back to true
    changes no routing while a transport is passed, so the flag assertion is
    what catches that one.
    """
    for variable in ("HTTP_PROXY", "HTTPS_PROXY", "ALL_PROXY"):
        monkeypatch.setenv(variable, "http://proxy.invalid:8080")

    client = build_local_http_client(timeout=1.0)

    assert client.trust_env is False
    assert client._mounts == {}
    chosen = client._transport_for_url(httpx.URL("http://127.0.0.1:11434/v1/models"))
    assert isinstance(chosen, LoopbackOnlyTransport)
    assert chosen is client._transport


def test_the_transport_refuses_a_foreign_host_before_the_socket() -> None:
    """The per-request chokepoint, which is what a redirect hop also passes."""
    transport = LoopbackOnlyTransport(httpx.HTTPTransport())
    request = httpx.Request("GET", "http://evil.example/v1/models")

    with pytest.raises(EndpointPolicyError):
        transport.handle_request(request)


def test_a_cross_host_redirect_is_not_followed() -> None:
    seen: list[httpx.URL] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request.url)
        return httpx.Response(307, headers={"Location": "http://evil.example/v1/models"})

    client = build_local_http_client(timeout=1.0, transport=httpx.MockTransport(handler))
    response = client.get("http://127.0.0.1:11434/v1/models")

    assert response.status_code == 307
    assert [url.host for url in seen] == ["127.0.0.1"]


def test_the_sdk_client_does_not_follow_a_cross_host_redirect() -> None:
    """The same proof through the client the agent actually builds.

    The SDK sets ``follow_redirects=True`` on its own default client
    (``openai/_base_client.py``), so this asserts that passing our own client
    keeps the setting -- measured, not assumed.
    """
    seen: list[httpx.URL] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request.url)
        return httpx.Response(307, headers={"Location": "http://evil.example/v1/models"})

    client = build_openai_client(AgentConfig(), transport=httpx.MockTransport(handler))

    with pytest.raises(Exception, match="307"):
        client.models.list()

    # One hop, to the configured host. Two entries would mean the redirect was
    # followed; an entry for evil.example would mean it was followed off host.
    assert [url.host for url in seen] == ["localhost"]


def test_the_agent_wires_the_policy_transport_into_its_own_client() -> None:
    """A factory nothing calls would pass every test above and protect nothing."""
    agent = ReActAgent(config=AgentConfig(verbose=False), printer=lambda _: None)

    assert isinstance(agent.client._client._transport, LoopbackOnlyTransport)


# --------------------------------------------------------------------------- #
# the endpoint is not printed
# --------------------------------------------------------------------------- #


def _agent_pointed_at(port: int, fake: FakeOpenAI) -> ReActAgent:
    config = AgentConfig(
        base_url=f"http://127.0.0.1:{port}/v1",
        verbose=False,
        retry_backoff=0.0,
        max_retries=0,
    )
    return ReActAgent(config=config, client=fake.as_client(), printer=lambda _: None)


def test_the_connection_check_reports_a_classification_not_the_url() -> None:
    fake = FakeOpenAI(models_error=APIConnectionError(request=None))  # type: ignore[arg-type]
    agent = _agent_pointed_at(UNUSED_PORT, fake)

    with pytest.raises(AgentError) as caught:
        agent.check_connection()

    message = str(caught.value)
    assert ENDPOINT_DESCRIPTION in message
    for leak in ("127.0.0.1", str(UNUSED_PORT), "/v1"):
        assert leak not in message


def test_a_lost_connection_reports_a_classification_not_the_url() -> None:
    fake = FakeOpenAI(completion_error=APIConnectionError(request=None))  # type: ignore[arg-type]
    agent = _agent_pointed_at(UNUSED_PORT, fake)

    with pytest.raises(AgentError) as caught:
        agent.run("What is 2 + 2?")

    message = str(caught.value)
    assert ENDPOINT_DESCRIPTION in message
    for leak in ("127.0.0.1", str(UNUSED_PORT), "/v1"):
        assert leak not in message
