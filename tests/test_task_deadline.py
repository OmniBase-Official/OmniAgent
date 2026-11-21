"""Task-wide deadline and cooperative cancellation tests."""

from __future__ import annotations

import json
import traceback
from pathlib import Path
from threading import Event
from typing import Any

import httpx
import pytest
from openai import APIConnectionError

import agent as agent_module
from agent import AgentCancelledError, AgentConfig, AgentTimeoutError, ReActAgent
from tests.fakes import FakeOpenAI
from tests.log_capture import configure_memory_sink, read_lines, reset_capture

ACTION = "Thought: calculate\nAction: calculate\nAction Input: 1 + 1"
FINAL = "Thought: done\nFinal Answer: completed"


class FakeClock:
    def __init__(self, now: float = 100.0) -> None:
        self.now = now

    def monotonic(self) -> float:
        return self.now

    def advance(self, seconds: float) -> None:
        self.now += seconds


class CancelWhenWaiting(Event):
    def __init__(self) -> None:
        super().__init__()
        self.waits: list[float | None] = []

    def wait(self, timeout: float | None = None) -> bool:
        self.waits.append(timeout)
        self.set()
        return True


def build(fake: FakeOpenAI, **overrides: Any) -> ReActAgent:
    overrides.setdefault("retry_backoff", 0.0)
    client = overrides.pop("client", fake.as_client())
    return ReActAgent(
        config=AgentConfig(verbose=False, **overrides),
        client=client,
        printer=lambda _: None,
    )


def install_clock(monkeypatch: pytest.MonkeyPatch, clock: FakeClock) -> None:
    monkeypatch.setattr(agent_module, "_monotonic", clock.monotonic)
    monkeypatch.setattr(agent_module, "_sleep", clock.advance)


def test_one_soft_budget_caps_multiple_model_requests(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    clock = FakeClock()
    install_clock(monkeypatch, clock)
    fake = FakeOpenAI(replies=[ACTION, FINAL])
    fake.completions.after_create = lambda: clock.advance(2.0)

    assert build(fake, timeout=20.0).run("find the README", task_timeout=5.0) == "completed"

    assert [call["timeout"] for call in fake.calls] == [5.0, 3.0]
    assert clock.now == 104.0


def test_deadline_never_lengthens_injected_httpx_timeout() -> None:
    fake = FakeOpenAI(replies=[FINAL])
    client = fake.as_client()
    client._client = httpx.Client(
        timeout=httpx.Timeout(connect=0.5, read=1.0, write=2.0, pool=0.25)
    )
    agent = build(fake, client=client, timeout=20.0)

    assert agent.run("question", task_timeout=5.0) == "completed"

    timeout = fake.calls[0]["timeout"]
    assert isinstance(timeout, httpx.Timeout)
    assert (timeout.connect, timeout.read, timeout.write, timeout.pool) == (
        0.5,
        1.0,
        2.0,
        0.25,
    )
    client._client.close()


def test_public_openai_timeout_caps_looser_transport_timeout() -> None:
    fake = FakeOpenAI(replies=[FINAL])
    client = fake.as_client()
    client.timeout = httpx.Timeout(5.0)
    client._client = httpx.Client(timeout=60.0)

    assert build(fake, client=client, timeout=20.0).run(
        "question", task_timeout=10.0
    ) == "completed"

    timeout = fake.calls[0]["timeout"]
    assert isinstance(timeout, httpx.Timeout)
    assert (timeout.connect, timeout.read, timeout.write, timeout.pool) == (5.0,) * 4
    client._client.close()


def test_built_httpx_timeout_is_capped_by_remaining_budget(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    clock = FakeClock()
    install_clock(monkeypatch, clock)
    fake = FakeOpenAI(replies=[ACTION, FINAL])
    client = fake.as_client()
    client.timeout = 20.0
    client._client = httpx.Client(timeout=20.0)
    fake.completions.after_create = lambda: clock.advance(2.0)

    assert build(fake, client=client, timeout=20.0).run("question", task_timeout=5.0) == "completed"

    first, second = (call["timeout"] for call in fake.calls)
    assert isinstance(first, httpx.Timeout)
    assert isinstance(second, httpx.Timeout)
    assert (first.connect, first.read, first.write, first.pool) == (5.0,) * 4
    assert (second.connect, second.read, second.write, second.pool) == (3.0,) * 4
    client._client.close()


def test_retry_backoff_is_capped_and_budget_expires_before_next_attempt(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    clock = FakeClock()
    install_clock(monkeypatch, clock)
    error_canary = "PRIVATE_API_EXCEPTION_CANARY"
    api_error = APIConnectionError(message=error_canary, request=None)  # type: ignore[arg-type]
    fake = FakeOpenAI(completion_error=api_error)
    agent = build(fake, max_retries=3, retry_backoff=4.0)

    with pytest.raises(AgentTimeoutError, match=r"^Task time budget exhausted\.$") as exc_info:
        agent.run("SECRET_PROMPT_CANARY", task_timeout=1.0)

    assert len(fake.calls) == 1
    assert clock.now == 101.0
    assert "SECRET_PROMPT_CANARY" not in str(exc_info.value)
    assert error_canary not in "".join(traceback.format_exception(exc_info.value))


def test_cancellation_during_retry_backoff_prevents_the_next_attempt() -> None:
    cancellation = CancelWhenWaiting()
    error_canary = "PRIVATE_CANCEL_API_EXCEPTION_CANARY"
    api_error = APIConnectionError(message=error_canary, request=None)  # type: ignore[arg-type]
    fake = FakeOpenAI(completion_error=api_error)
    agent = build(fake, max_retries=3, retry_backoff=2.5)

    with pytest.raises(AgentCancelledError, match=r"^Task cancelled\.$") as exc_info:
        agent.run("SECRET_RETRY_CANARY", cancellation_event=cancellation)

    assert cancellation.waits == [2.5]
    assert len(fake.calls) == 1
    assert "SECRET_RETRY_CANARY" not in str(exc_info.value)
    assert error_canary not in "".join(traceback.format_exception(exc_info.value))


def test_slow_tool_is_not_aborted_but_deadline_is_checked_after_it(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    clock = FakeClock()
    install_clock(monkeypatch, clock)
    fake = FakeOpenAI(replies=[ACTION, FINAL])
    tool_finished: list[bool] = []

    def slow_tool(*_args: object, **_kwargs: object) -> str:
        clock.advance(7.0)
        tool_finished.append(True)
        return "tool completed"

    monkeypatch.setattr(agent_module, "run_tool", slow_tool)
    agent = build(fake)

    with pytest.raises(AgentTimeoutError, match=r"^Task time budget exhausted\.$"):
        agent.run("SECRET_TOOL_CANARY", task_timeout=5.0)

    assert tool_finished == [True]
    assert len(fake.calls) == 1
    assert clock.now == 107.0


@pytest.mark.parametrize("failure", ["timeout", "cancellation"])
def test_abort_after_sync_tool_emits_sanitized_terminal_event(
    monkeypatch: pytest.MonkeyPatch, failure: str, tmp_path: Path
) -> None:
    clock = FakeClock()
    install_clock(monkeypatch, clock)
    cancellation = Event()
    fake = FakeOpenAI(replies=[ACTION, FINAL])
    canaries = ["QUESTION_SECRET_CANARY", "TOOL_INPUT_SECRET_CANARY", "TOOL_OUTPUT_SECRET_CANARY"]
    log_key = tmp_path / "events"
    reset_capture()
    configure_memory_sink(log_key, level="DEBUG")

    def slow_or_cancelled_tool(*_args: object, **_kwargs: object) -> str:
        if failure == "timeout":
            clock.advance(7.0)
        else:
            cancellation.set()
        return canaries[2]

    monkeypatch.setattr(agent_module, "run_tool", slow_or_cancelled_tool)
    try:
        with pytest.raises((AgentTimeoutError, AgentCancelledError)):
            build(fake).run(
                canaries[0],
                task_timeout=5.0 if failure == "timeout" else None,
                cancellation_event=cancellation if failure == "cancellation" else None,
            )
        records = read_lines(log_key)
    finally:
        reset_capture()

    abort = [record for record in records if record["event"] == "agent.run.aborted"]
    assert len(abort) == 1
    assert abort[0]["status"] == "aborted"
    assert abort[0]["step_count"] == 1
    serialized_records = json.dumps(records)
    assert all(canary not in serialized_records for canary in canaries)


def test_sync_model_call_can_return_after_soft_budget_expires(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    clock = FakeClock()
    install_clock(monkeypatch, clock)
    fake = FakeOpenAI(replies=[FINAL])
    fake.completions.after_create = lambda: clock.advance(7.0)

    with pytest.raises(AgentTimeoutError, match=r"^Task time budget exhausted\.$"):
        build(fake, timeout=20.0).run("SECRET_MODEL_CANARY", task_timeout=5.0)

    assert fake.calls[0]["timeout"] == 5.0
    assert clock.now == 107.0


def test_cancellation_after_tool_prevents_the_next_model_step(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    cancellation = Event()
    fake = FakeOpenAI(replies=[ACTION, FINAL])
    tool_calls: list[str] = []

    def cancel_after_tool(*_args: object, **_kwargs: object) -> str:
        tool_calls.append("called")
        cancellation.set()
        return "tool completed"

    monkeypatch.setattr(agent_module, "run_tool", cancel_after_tool)

    with pytest.raises(AgentCancelledError, match=r"^Task cancelled\.$") as exc_info:
        build(fake).run(
            "SECRET_CANCELLATION_CANARY", cancellation_event=cancellation
        )

    assert tool_calls == ["called"]
    assert len(fake.calls) == 1
    assert "SECRET_CANCELLATION_CANARY" not in str(exc_info.value)


def test_cancelled_request_is_observed_immediately_after_sync_model_call() -> None:
    cancellation = Event()
    fake = FakeOpenAI(replies=[FINAL])
    fake.completions.after_create = cancellation.set

    with pytest.raises(AgentCancelledError, match=r"^Task cancelled\.$"):
        build(fake).run("private question", cancellation_event=cancellation)

    assert len(fake.calls) == 1


@pytest.mark.parametrize("failure", ["timeout", "cancellation"])
def test_run_lock_is_released_after_timeout_or_cancellation(
    monkeypatch: pytest.MonkeyPatch, failure: str
) -> None:
    clock = FakeClock()
    install_clock(monkeypatch, clock)
    cancellation = Event()
    fake = FakeOpenAI(replies=[FINAL, FINAL])
    calls = 0

    def finish_first_request() -> None:
        nonlocal calls
        calls += 1
        if calls != 1:
            return
        if failure == "timeout":
            clock.advance(2.0)
        else:
            cancellation.set()

    fake.completions.after_create = finish_first_request
    agent = build(fake)

    if failure == "timeout":
        with pytest.raises(AgentTimeoutError, match=r"^Task time budget exhausted\.$"):
            agent.run("first request", task_timeout=1.0)
    else:
        with pytest.raises(AgentCancelledError, match=r"^Task cancelled\.$"):
            agent.run("first request", cancellation_event=cancellation)

    assert agent.run("follow-up request") == "completed"
    assert len(fake.calls) == 2
    assert agent._turn == 2
    agent.reset()
    assert agent.history == []


@pytest.mark.parametrize("task_timeout", [0.0, -1.0, float("inf"), float("nan")])
def test_invalid_task_timeout_is_rejected_before_run_state_changes(
    task_timeout: float,
) -> None:
    fake = FakeOpenAI(replies=[FINAL])
    agent = build(fake)

    with pytest.raises(ValueError, match=r"^task_timeout must be finite and greater than zero$"):
        agent.run("question", task_timeout=task_timeout)

    assert agent._turn == 0
    assert fake.calls == []
