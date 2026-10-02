"""Tests for the failure handling the demo depends on.

Two things go wrong in practice with a local model: the first request after an
idle period times out while Ollama pages the model in, and a small model gets
stuck resending an Action that cannot work. Both are handled here.
"""

from __future__ import annotations

import json
import logging
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest
from openai import APIConnectionError, APIStatusError, APITimeoutError

import observability as obs
from agent import AgentConfig, AgentError, ReActAgent
from tests.fakes import FakeOpenAI

FINAL = "Thought: done\nFinal Answer: {answer}"
BAD_CALL = "Thought: maths\nAction: calculate\nAction Input: 1 / 0"


@pytest.fixture(autouse=True)
def _clean_logging() -> Iterator[None]:
    obs.reset()
    yield
    obs.reset()


@pytest.fixture
def log_file(tmp_path: Path) -> Path:
    path = tmp_path / "omniagent.jsonl"
    obs.configure(level=logging.DEBUG, log_file=path, session_id="test-session")
    return path


def records(path: Path) -> list[dict[str, Any]]:
    for handler in obs.get_logger().handlers:
        handler.flush()
    text = path.read_text(encoding="utf-8").strip()
    return [json.loads(line) for line in text.splitlines()] if text else []


def events_named(path: Path, name: str) -> list[dict[str, Any]]:
    return [record for record in records(path) if record["event"] == name]


def build(fake: FakeOpenAI, **overrides: Any) -> ReActAgent:
    overrides.setdefault("retry_backoff", 0.0)
    config = AgentConfig(verbose=False, **overrides)
    return ReActAgent(config=config, client=fake.as_client(), printer=lambda _: None)


def connection_error() -> APIConnectionError:
    return APIConnectionError(request=None)  # type: ignore[arg-type]


def timeout_error() -> APITimeoutError:
    return APITimeoutError(request=None)  # type: ignore[arg-type]


def status_error(code: int) -> APIStatusError:
    class _Response:
        def __init__(self) -> None:
            self.status_code = code
            self.headers: dict[str, str] = {}
            self.request = None

    return APIStatusError("boom", response=_Response(), body=None)  # type: ignore[arg-type]


# --------------------------------------------------------------------------- #
# retrying what is worth retrying
# --------------------------------------------------------------------------- #


def test_a_transient_connection_failure_is_retried_and_succeeds() -> None:
    fake = FakeOpenAI(script=[connection_error(), FINAL.format(answer="4")])
    agent = build(fake)

    assert agent.run("What is 2 + 2?") == "4"
    assert len(fake.calls) == 2


def test_a_slow_first_request_is_retried() -> None:
    """Ollama paging a model in is the most likely demo-day failure."""
    fake = FakeOpenAI(script=[timeout_error(), timeout_error(), FINAL.format(answer="4")])
    agent = build(fake, max_retries=2)

    assert agent.run("What is 2 + 2?") == "4"
    assert len(fake.calls) == 3


@pytest.mark.parametrize("code", [429, 500, 502, 503, 504])
def test_a_busy_server_is_retried(code: int) -> None:
    fake = FakeOpenAI(script=[status_error(code), FINAL.format(answer="4")])
    agent = build(fake)

    assert agent.run("hi") == "4"
    assert len(fake.calls) == 2


def test_retries_stop_at_the_configured_limit() -> None:
    fake = FakeOpenAI(completion_error=connection_error())
    agent = build(fake, max_retries=2)

    with pytest.raises(AgentError, match="after 3 attempts"):
        agent.run("hi")

    assert len(fake.calls) == 3


def test_retries_can_be_turned_off() -> None:
    fake = FakeOpenAI(completion_error=connection_error())
    agent = build(fake, max_retries=0)

    with pytest.raises(AgentError, match="after 1 attempt"):
        agent.run("hi")

    assert len(fake.calls) == 1


# --------------------------------------------------------------------------- #
# not retrying what will never work
# --------------------------------------------------------------------------- #


def test_a_missing_model_is_not_retried() -> None:
    """No amount of waiting will create a model tag that was never pulled."""
    fake = FakeOpenAI(completion_error=status_error(404))
    agent = build(fake, max_retries=5)

    with pytest.raises(AgentError, match="ollama pull"):
        agent.run("hi")

    assert len(fake.calls) == 1


@pytest.mark.parametrize("code", [400, 401, 403, 404, 422])
def test_client_errors_are_not_retried(code: int) -> None:
    fake = FakeOpenAI(completion_error=status_error(code))
    agent = build(fake, max_retries=3)

    with pytest.raises(AgentError):
        agent.run("hi")

    assert len(fake.calls) == 1


def test_the_client_does_not_retry_underneath_us() -> None:
    """Retry counting is only honest if the SDK is not also retrying."""
    agent = build(FakeOpenAI(replies=[FINAL.format(answer="4")]))
    real = ReActAgent(config=agent.config, printer=lambda _: None)

    assert real.client.max_retries == 0


# --------------------------------------------------------------------------- #
# backoff
# --------------------------------------------------------------------------- #


def test_the_backoff_doubles_and_is_logged(log_file: Path) -> None:
    fake = FakeOpenAI(
        script=[connection_error(), connection_error(), FINAL.format(answer="4")]
    )
    agent = build(fake, max_retries=2, retry_backoff=0.5)

    assert agent.run("hi") == "4"

    retries = events_named(log_file, "agent.llm.retry")
    assert [r["attempt"] for r in retries] == [1, 2]
    assert [r["delay_seconds"] for r in retries] == [0.5, 1.0]
    assert all(r["level"] == "WARNING" for r in retries)


def test_a_successful_first_attempt_logs_no_retry(log_file: Path) -> None:
    build(FakeOpenAI(replies=[FINAL.format(answer="4")])).run("hi")

    assert events_named(log_file, "agent.llm.retry") == []


def test_the_failure_record_counts_the_attempts(log_file: Path) -> None:
    fake = FakeOpenAI(completion_error=connection_error())
    agent = build(fake, max_retries=2)

    with pytest.raises(AgentError):
        agent.run("hi")

    assert events_named(log_file, "agent.llm.unreachable")[0]["attempts"] == 3


# --------------------------------------------------------------------------- #
# getting out of a rut
# --------------------------------------------------------------------------- #


def test_a_repeated_failing_action_gets_an_intervention(log_file: Path) -> None:
    fake = FakeOpenAI(
        replies=[BAD_CALL, BAD_CALL, FINAL.format(answer="I could not divide by zero.")]
    )
    agent = build(fake, max_repeated_actions=2)

    assert agent.run("What is 1 / 0?") == "I could not divide by zero."

    rut = events_named(log_file, "agent.loop.repeated_action")
    assert len(rut) == 1
    assert rut[0]["tool"] == "calculate"
    assert rut[0]["attempts"] == 2

    sent = [str(m["content"]) for m in fake.calls[2]["messages"]]
    assert any("Do not send it again" in message for message in sent)


def test_the_intervention_waits_for_a_genuine_repeat(log_file: Path) -> None:
    """Two different failing inputs are progress, not a rut."""
    fake = FakeOpenAI(
        replies=[
            BAD_CALL,
            "Thought: retry\nAction: calculate\nAction Input: 2 +",
            FINAL.format(answer="gave up"),
        ]
    )
    build(fake, max_repeated_actions=2).run("go")

    assert events_named(log_file, "agent.loop.repeated_action") == []


def test_the_same_succeeding_action_twice_is_allowed(log_file: Path) -> None:
    """Re-reading one file while working through a comparison is reasonable."""
    good = "Thought: maths\nAction: calculate\nAction Input: 2 + 2"
    fake = FakeOpenAI(replies=[good, good, FINAL.format(answer="4")])
    build(fake, max_repeated_actions=2).run("go")

    assert events_named(log_file, "agent.loop.repeated_action") == []


def test_a_third_identical_succeeding_action_is_a_rut(log_file: Path) -> None:
    """A succeeding call repeated verbatim is a rut too.

    Asked which of two files was longer, both fine-tuned models read the same
    file nine times. Every read succeeded, so the failure-only check never
    fired, and the entire step budget went on re-reading text that was already
    in the conversation.
    """
    good = "Thought: maths\nAction: calculate\nAction Input: 2 + 2"
    fake = FakeOpenAI(replies=[good, good, good, FINAL.format(answer="4")])
    agent = build(fake, max_repeated_actions=2)

    assert agent.run("go") == "4"

    rut = events_named(log_file, "agent.loop.repeated_action")
    assert len(rut) == 1
    assert rut[0]["failing"] is False
    assert rut[0]["attempts"] == 3

    sent = [str(m["content"]) for m in fake.calls[3]["messages"]]
    assert any("succeeded every time" in message for message in sent)


def test_a_failing_action_still_intervenes_one_attempt_sooner(log_file: Path) -> None:
    """Failures get the tighter threshold: nothing is learned by repeating them."""
    fake = FakeOpenAI(replies=[BAD_CALL, BAD_CALL, FINAL.format(answer="no")])
    build(fake, max_repeated_actions=2).run("go")

    rut = events_named(log_file, "agent.loop.repeated_action")
    assert len(rut) == 1
    assert rut[0]["failing"] is True
    assert rut[0]["attempts"] == 2


def test_the_rut_counter_resets_between_turns(log_file: Path) -> None:
    fake = FakeOpenAI(
        replies=[
            BAD_CALL,
            FINAL.format(answer="one"),
            BAD_CALL,
            FINAL.format(answer="two"),
        ]
    )
    agent = build(fake, max_repeated_actions=2)
    agent.run("first")
    agent.run("second")

    assert events_named(log_file, "agent.loop.repeated_action") == []


def test_the_threshold_is_configurable(log_file: Path) -> None:
    fake = FakeOpenAI(replies=[BAD_CALL, FINAL.format(answer="done")])
    build(fake, max_repeated_actions=1).run("go")

    assert len(events_named(log_file, "agent.loop.repeated_action")) == 1
