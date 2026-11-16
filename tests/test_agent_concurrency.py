"""Concurrent calls on one agent must not mix a serialized conversation."""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from threading import Event

import pytest

from agent import AgentConfig, AgentError, ReActAgent
from tests.fakes import FakeOpenAI


def test_overlapping_runs_fail_fast_without_cross_task_state_contamination() -> None:
    request_started = Event()
    release_first_request = Event()
    fake = FakeOpenAI(
        replies=[
            "Thought: answer the first request.\nFinal Answer: ALPHA_RESULT_CANARY",
            "Thought: answer the second request.\nFinal Answer: BETA_RESULT_CANARY",
        ]
    )

    def pause_first_response() -> None:
        request_started.set()
        if not release_first_request.wait(timeout=10):
            raise AssertionError("test did not release the first model request")

    fake.completions.after_create = pause_first_response
    agent = ReActAgent(
        config=AgentConfig(verbose=False, retry_backoff=0.0),
        client=fake.as_client(),
        printer=lambda _: None,
    )

    with ThreadPoolExecutor(max_workers=1) as executor:
        first_run = executor.submit(agent.run, "ALPHA_REQUEST_CANARY")
        try:
            assert request_started.wait(timeout=5)

            with pytest.raises(AgentError, match="separate instance"):
                agent.run("BETA_REQUEST_CANARY")
            with pytest.raises(AgentError, match="concurrent operations"):
                agent.reset()

            assert len(fake.calls) == 1
            assert agent.history == []
            assert agent.last_trace == []
        finally:
            release_first_request.set()

        assert first_run.result(timeout=5) == "ALPHA_RESULT_CANARY"

    first_request_text = str(fake.calls[0]["messages"])
    assert "ALPHA_REQUEST_CANARY" in first_request_text
    assert "BETA_REQUEST_CANARY" not in first_request_text
    first_history_text = str(agent.history)
    assert "ALPHA_REQUEST_CANARY" in first_history_text
    assert "ALPHA_RESULT_CANARY" in first_history_text
    assert "BETA_REQUEST_CANARY" not in first_history_text
    assert "BETA_RESULT_CANARY" not in first_history_text
    assert len(agent.last_trace) == 1
    assert agent.last_trace[0].final_answer == "ALPHA_RESULT_CANARY"
    assert agent._turn == 1

    assert agent.run("BETA_REQUEST_CANARY") == "BETA_RESULT_CANARY"

    second_request_text = str(fake.calls[1]["messages"])
    assert "ALPHA_REQUEST_CANARY" in second_request_text
    assert "BETA_REQUEST_CANARY" in second_request_text
    final_history_text = str(agent.history)
    assert "ALPHA_RESULT_CANARY" in final_history_text
    assert "BETA_RESULT_CANARY" in final_history_text
    assert "BETA_REQUEST_CANARY" in final_history_text
    assert len(agent.last_trace) == 1
    assert agent.last_trace[0].final_answer == "BETA_RESULT_CANARY"
    assert agent._turn == 2
