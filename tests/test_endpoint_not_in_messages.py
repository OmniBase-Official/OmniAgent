"""The configured endpoint URL must not reach a message or a log record.

Contract section 2: "Do not log the full endpoint URL." The URL used to reach
users by three paths on this line, and there are six places that held it:

====  ============================  =========================================
site  where                         what carried it
====  ============================  =========================================
U1    ``check_connection``          the AgentError text ("Cannot reach ...")
U2    ``check_connection``          the ``agent.connection.unreachable`` event
U3    ``check_connection``          the ``agent.connection.error`` event
U4    ``check_connection``          the ``agent.connection.ok`` event
U5    the request retry path        the AgentError text ("Lost the connection")
U6    the request retry path        the ``agent.llm.unreachable`` event
====  ============================  =========================================

The structured-log sites (U2, U3, U4, U6) are subtle: ``observability.event``
keeps only a closed schema, so the URL never reached a *written* record even
when a call site passed it. That sanitiser is one guard; a call site that passes
``base_url=`` is a second thing that must not happen, and only a test that
watches the arguments (``spy_on_events``) can see it. The distinctive port
``65500`` is the needle: it appears nowhere else in the repository.

A test that asserted only "the log record has no URL" would stay green with the
call-site argument restored, because the sanitiser would still drop it - so the
message, the event arguments and the written records are asserted separately.

Static: the client is a fake, and ``no_sockets`` fails the test if anything
tries to open a connection or resolve a name.
"""

from __future__ import annotations

import logging
import socket
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import httpx
import pytest
from openai import APIConnectionError, APIStatusError

import observability as obs
from agent import AgentConfig, AgentError, ReActAgent
from tests.fakes import FakeOpenAI
from tests.log_capture import configure_memory_sink, read_lines, reset_capture

PORT = "65500"
URL = f"http://127.0.0.1:{PORT}/v1"


@pytest.fixture(autouse=True)
def no_sockets(monkeypatch: pytest.MonkeyPatch) -> Iterator[list[str]]:
    """Fail loudly if anything opens a connection or resolves a name."""
    attempts: list[str] = []

    def refuse(name: str) -> Any:
        def inner(*args: object, **kwargs: object) -> Any:
            attempts.append(name)
            raise AssertionError(f"a test tried to use the network: socket {name}")

        return inner

    monkeypatch.setattr(socket.socket, "connect", refuse("connect"))
    monkeypatch.setattr(socket.socket, "connect_ex", refuse("connect_ex"))
    monkeypatch.setattr(socket, "create_connection", refuse("create_connection"))
    monkeypatch.setattr(socket, "getaddrinfo", refuse("getaddrinfo"))
    yield attempts
    assert attempts == [], f"network was touched: {attempts}"


@pytest.fixture(autouse=True)
def _clean_logging() -> Iterator[None]:
    reset_capture()
    yield
    reset_capture()


def connection_error() -> APIConnectionError:
    request = httpx.Request("POST", f"{URL}/chat/completions")
    return APIConnectionError(message="Connection error.", request=request)


def status_error() -> APIStatusError:
    request = httpx.Request("GET", f"{URL}/models")
    response = httpx.Response(500, request=request)
    return APIStatusError("server said no", response=response, body=None)


def build(fake: FakeOpenAI) -> ReActAgent:
    config = AgentConfig(verbose=False, base_url=URL, max_retries=0, retry_backoff=0.0)
    return ReActAgent(config=config, client=fake.as_client(), printer=lambda _: None)


def spy_on_events(monkeypatch: pytest.MonkeyPatch) -> list[tuple[str, dict[str, Any]]]:
    """Record every ``obs.event`` call exactly as the call site made it."""
    seen: list[tuple[str, dict[str, Any]]] = []
    real = obs.event

    def spy(name: str, *args: Any, **fields: Any) -> None:
        seen.append((name, dict(fields)))
        real(name, *args, **fields)

    monkeypatch.setattr(obs, "event", spy)
    return seen


def leaks(text: str) -> bool:
    return PORT in text or URL in text


def event_arguments(
    seen: list[tuple[str, dict[str, Any]]], name: str
) -> list[dict[str, Any]]:
    return [fields for event_name, fields in seen if event_name == name]


def assert_no_url_in_arguments(fields: dict[str, Any]) -> None:
    assert "base_url" not in fields, "a call site passed base_url to the log"
    assert not any(leaks(str(value)) for value in fields.values()), fields


def connect_check_unreachable() -> AgentError:
    agent = build(FakeOpenAI(models_error=connection_error()))
    with pytest.raises(AgentError) as caught:
        agent.check_connection()
    return caught.value


def run_unreachable() -> AgentError:
    agent = build(FakeOpenAI(completion_error=connection_error()))
    with pytest.raises(AgentError) as caught:
        agent.run("hello")
    return caught.value


# --------------------------------------------------------------------------- #
# the messages (U1, U5)
# --------------------------------------------------------------------------- #


def test_u1_the_unreachable_server_message_names_the_classification_not_the_url() -> None:
    error = connect_check_unreachable()

    assert not leaks(str(error))
    assert "endpoint: loopback" in str(error)
    assert not leaks(str(error.__cause__))


def test_u5_the_lost_connection_message_names_the_classification_not_the_url() -> None:
    error = run_unreachable()

    assert not leaks(str(error))
    assert "endpoint: loopback" in str(error)
    assert not leaks(str(error.__cause__))


# --------------------------------------------------------------------------- #
# what the call sites hand to the logger (U2, U3, U4, U6)
# --------------------------------------------------------------------------- #


def test_u2_the_unreachable_event_is_not_given_the_url(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    seen = spy_on_events(monkeypatch)
    connect_check_unreachable()

    emitted = event_arguments(seen, "agent.connection.unreachable")
    assert len(emitted) == 1
    assert_no_url_in_arguments(emitted[0])


def test_u3_the_connection_error_event_is_not_given_the_url(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    seen = spy_on_events(monkeypatch)
    agent = build(FakeOpenAI(models_error=status_error()))
    with pytest.raises(AgentError):
        agent.check_connection()

    emitted = event_arguments(seen, "agent.connection.error")
    assert len(emitted) == 1
    assert_no_url_in_arguments(emitted[0])


def test_u4_the_connection_ok_event_is_not_given_the_url(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    seen = spy_on_events(monkeypatch)
    agent = build(FakeOpenAI(models=["qwen2.5:7b"]))

    assert agent.check_connection() == ["qwen2.5:7b"]

    emitted = event_arguments(seen, "agent.connection.ok")
    assert len(emitted) == 1
    assert_no_url_in_arguments(emitted[0])


def test_u6_the_llm_unreachable_event_is_not_given_the_url(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    seen = spy_on_events(monkeypatch)
    run_unreachable()

    emitted = event_arguments(seen, "agent.llm.unreachable")
    assert len(emitted) == 1
    assert_no_url_in_arguments(emitted[0])


# --------------------------------------------------------------------------- #
# what is actually written, by any logger
# --------------------------------------------------------------------------- #


@pytest.mark.parametrize("scenario", ["check_unreachable", "check_status", "check_ok", "run_lost"])
def test_no_captured_log_record_contains_the_url_or_the_port(
    scenario: str, tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    sink = tmp_path / "memory-log"
    configure_memory_sink(sink, level=logging.DEBUG, session_id="test-session")
    caplog.set_level(logging.DEBUG)

    if scenario == "check_unreachable":
        connect_check_unreachable()
    elif scenario == "check_status":
        with pytest.raises(AgentError):
            build(FakeOpenAI(models_error=status_error())).check_connection()
    elif scenario == "check_ok":
        build(FakeOpenAI(models=["qwen2.5:7b"])).check_connection()
    else:
        run_unreachable()

    written = [str(record) for record in read_lines(sink)]
    assert written, "the scenario produced no telemetry, so this proves nothing"
    assert not any(leaks(line) for line in written)
    # Every logger, not just ours: httpx and openai log request URLs too.
    assert not any(leaks(record.getMessage()) for record in caplog.records)
    assert not any(leaks(str(record.__dict__)) for record in caplog.records)
