"""The log must tell the story of a turn on its own.

These drive the real ReAct loop against a scripted fake model and assert on the
JSON-lines output: the sequence of events, the context attached to them, and
what must never appear in them.
"""

from __future__ import annotations

import json
import logging
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest
from openai import APIConnectionError, APIStatusError

import observability as obs
from agent import AgentConfig, AgentError, ReActAgent
from tests.fakes import FakeOpenAI
from tests.log_capture import configure_memory_sink, reset_capture
from tests.log_capture import read_lines as read_memory_lines


@pytest.fixture(autouse=True)
def _clean_logging() -> Iterator[None]:
    reset_capture()
    yield
    reset_capture()


@pytest.fixture
def log_file(tmp_path: Path) -> Path:
    path = tmp_path / "omniagent.jsonl"
    configure_memory_sink(path, level=logging.DEBUG, session_id="test-session")
    return path


def records(path: Path) -> list[dict[str, Any]]:
    return read_memory_lines(path)


def events(path: Path) -> list[str]:
    return [record["event"] for record in records(path)]


def only(path: Path, name: str) -> dict[str, Any]:
    matches = [record for record in records(path) if record["event"] == name]
    assert len(matches) == 1, f"expected exactly one {name}, got {len(matches)}"
    return matches[0]


def build(fake: FakeOpenAI, **overrides: Any) -> ReActAgent:
    # retry_backoff=0: the retry policy is tested by counting attempts, never by
    # making the suite wait for them.
    overrides.setdefault("retry_backoff", 0.0)
    config = AgentConfig(verbose=False, **overrides)
    return ReActAgent(config=config, client=fake.as_client(), printer=lambda _: None)


# --------------------------------------------------------------------------- #
# the happy path
# --------------------------------------------------------------------------- #


def test_a_tool_using_turn_logs_the_whole_story(log_file: Path) -> None:
    fake = FakeOpenAI(
        replies=[
            "Thought: I need maths.\nAction: calculate\nAction Input: 2 + 2",
            "Thought: Done.\nFinal Answer: It is 4.",
        ]
    )
    agent = build(fake)

    assert agent.run("What is 2 + 2?") == "It is 4."

    assert events(log_file) == [
        "agent.created",
        "agent.turn.start",
        "agent.llm.request",
        "agent.llm.response",
        "agent.tool.call",
        "agent.tool.result",
        "agent.llm.request",
        "agent.llm.response",
        "agent.step.final_answer",
        "agent.turn.end",
    ]


def test_only_step_count_telemetry_is_persisted(log_file: Path) -> None:
    fake = FakeOpenAI(
        replies=[
            "Thought: maths\nAction: calculate\nAction Input: 2 + 2",
            "Thought: done\nFinal Answer: 4",
        ]
    )
    agent = build(fake)
    agent.run("What is 2 + 2?")

    by_event = {record["event"]: record for record in records(log_file)}
    assert by_event["agent.tool.call"]["step_count"] == 1
    assert by_event["agent.step.final_answer"]["step_count"] == 2
    assert by_event["agent.turn.end"]["step_count"] == 2
    assert all("turn" not in record and "step" not in record for record in by_event.values())


def test_turn_counter_increments_in_memory_without_logging_it(log_file: Path) -> None:
    fake = FakeOpenAI(
        replies=["Thought: done\nFinal Answer: one", "Thought: done\nFinal Answer: two"]
    )
    agent = build(fake)
    agent.run("first")
    agent.run("second")

    assert agent._turn == 2
    turn_records = [r for r in records(log_file) if r["event"] == "agent.turn.start"]
    assert len(turn_records) == 2
    assert all("turn" not in r for r in turn_records)


def test_session_id_is_not_persisted(log_file: Path) -> None:
    fake = FakeOpenAI(replies=["Thought: done\nFinal Answer: 4"])
    build(fake).run("What is 2 + 2?")

    assert all("session_id" not in record for record in records(log_file))


def test_tool_result_carries_only_safe_telemetry(log_file: Path) -> None:
    fake = FakeOpenAI(
        replies=[
            "Thought: maths\nAction: calculate\nAction Input: 2 + 2",
            "Thought: done\nFinal Answer: 4",
        ]
    )
    build(fake).run("What is 2 + 2?")

    result = only(log_file, "agent.tool.result")
    assert result["tool_name"] == "calculate"
    assert result["status"] == "succeeded"
    assert isinstance(result["duration_ms"], int | float)
    assert "observation" not in result


def test_llm_response_carries_only_safe_telemetry(log_file: Path) -> None:
    fake = FakeOpenAI(replies=["Thought: done\nFinal Answer: 4"])
    build(fake).run("What is 2 + 2?")

    response = only(log_file, "agent.llm.response")
    assert "model_tag" not in response
    assert response["status"] == "completed"
    assert isinstance(response["duration_ms"], int | float)
    assert "reply" not in response
    assert "prompt_tokens" not in response


def test_turn_end_reports_steps_used(log_file: Path) -> None:
    fake = FakeOpenAI(
        replies=[
            "Thought: maths\nAction: calculate\nAction Input: 2 + 2",
            "Thought: more\nAction: calculate\nAction Input: 4 * 2",
            "Thought: done\nFinal Answer: 8",
        ]
    )
    build(fake).run("go")

    assert only(log_file, "agent.turn.end")["step_count"] == 3


# --------------------------------------------------------------------------- #
# the unhappy paths
# --------------------------------------------------------------------------- #


def test_a_failing_tool_is_logged_as_not_ok(log_file: Path) -> None:
    fake = FakeOpenAI(
        replies=[
            "Thought: maths\nAction: calculate\nAction Input: 1 / 0",
            "Thought: done\nFinal Answer: cannot divide by zero",
        ]
    )
    build(fake).run("What is 1 / 0?")

    result = only(log_file, "agent.tool.result")
    assert result["status"] == "failed"
    assert result["tool_name"] == "calculate"
    assert "observation" not in result


def test_an_unknown_tool_is_logged_by_the_registry(log_file: Path) -> None:
    fake = FakeOpenAI(
        replies=[
            "Thought: hmm\nAction: send_email\nAction Input: hi",
            "Thought: done\nFinal Answer: I cannot do that.",
        ]
    )
    build(fake).run("email someone")

    unknown = only(log_file, "agent.tool.policy_violation")
    assert unknown["status"] == "rejected"
    assert "requested" not in unknown
    assert "available" not in unknown


def test_the_agent_recovers_from_bad_tool_arguments(log_file: Path) -> None:
    """The validation error has to be good enough to fix the next attempt.

    Step 1 invents a field name; the Observation names the real one, and the
    model's next attempt succeeds.
    """
    fake = FakeOpenAI(
        replies=[
            'Thought: maths\nAction: calculate\nAction Input: {"formula": "2 + 2"}',
            "Thought: retry\nAction: calculate\nAction Input: 2 + 2",
            "Thought: done\nFinal Answer: It is 4.",
        ]
    )
    agent = build(fake)

    assert agent.run("What is 2 + 2?") == "It is 4."

    invalid = only(log_file, "tool.invalid_args")
    assert invalid["tool_name"] == "calculate"
    assert "reason" not in invalid

    results = [r for r in records(log_file) if r["event"] == "agent.tool.result"]
    assert [r["status"] for r in results] == ["failed", "succeeded"]
    assert "observation" not in results[1]


def test_a_format_violation_is_logged_without_the_offending_reply(log_file: Path) -> None:
    fake = FakeOpenAI(
        replies=["Sure! The answer is probably 4.", "Thought: done\nFinal Answer: It is 4."]
    )
    build(fake).run("What is 2 + 2?")

    violation = only(log_file, "agent.format.violation")
    assert violation["status"] == "invalid_format"
    assert "reply" not in violation


def test_running_out_of_steps_is_logged(log_file: Path) -> None:
    loop = "Thought: again\nAction: calculate\nAction Input: 1 + 1"
    fake = FakeOpenAI(replies=[loop, loop, "Thought: done\nFinal Answer: 2"])
    agent = build(fake, max_steps=2)

    assert agent.run("go") == "2"

    assert "agent.budget.exhausted" in events(log_file)
    assert only(log_file, "agent.budget.exhausted")["step_count"] == 2


def test_an_unreachable_server_is_logged_with_a_traceback(log_file: Path) -> None:
    error = APIConnectionError(request=None)  # type: ignore[arg-type]
    fake = FakeOpenAI(completion_error=error)
    agent = build(fake)

    with pytest.raises(AgentError, match="Lost the connection"):
        agent.run("What is 2 + 2?")

    record = only(log_file, "agent.llm.unreachable")
    assert record["status"] == "unreachable"
    assert "error" not in record


def test_a_server_error_logs_the_status_code(log_file: Path) -> None:
    error = APIStatusError("not found", response=_stub_response(404), body=None)
    fake = FakeOpenAI(completion_error=error)
    agent = build(fake)

    with pytest.raises(AgentError, match="ollama pull"):
        agent.run("What is 2 + 2?")

    assert only(log_file, "agent.llm.error")["status"] == "error"


def test_model_server_exception_details_are_sanitized_for_users() -> None:
    raw_detail = "RAW_MODEL_SERVER_BODY_CANARY"
    error = APIStatusError(raw_detail, response=_stub_response(500), body=None)
    agent = build(FakeOpenAI(models_error=error))

    with pytest.raises(AgentError) as raised:
        agent.check_connection()

    assert "HTTP 500" in str(raised.value)
    assert raw_detail not in str(raised.value)


def test_connection_check_logs_whether_the_model_is_installed(log_file: Path) -> None:
    fake = FakeOpenAI(models=["gemma2:2b"])
    agent = build(fake, model="qwen2.5:7b")

    agent.check_connection()

    record = only(log_file, "agent.connection.ok")
    assert record["status"] == "failed"
    assert "model_tag" not in record
    assert "available" not in record


# --------------------------------------------------------------------------- #
# what must never reach the log
# --------------------------------------------------------------------------- #


def test_the_api_key_never_appears_in_the_log(log_file: Path) -> None:
    fake = FakeOpenAI(replies=["Thought: done\nFinal Answer: 4"])
    agent = build(fake, api_key="sk-this-must-never-be-logged")
    agent.run("What is 2 + 2?")

    raw = json.dumps(records(log_file))
    assert "sk-this-must-never-be-logged" not in raw
    assert "model_tag" not in only(log_file, "agent.created")
    assert "config" not in only(log_file, "agent.created")


def test_logging_stays_off_stdout(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    obs.configure(level=logging.DEBUG)
    fake = FakeOpenAI(replies=["Thought: done\nFinal Answer: 4"])
    build(fake).run("What is 2 + 2?")

    captured = capsys.readouterr()
    assert captured.out == ""
    assert captured.err == ""


def test_the_agent_runs_fine_with_logging_never_configured() -> None:
    """Importing the agent must not require anyone to set logging up."""
    fake = FakeOpenAI(replies=["Thought: done\nFinal Answer: 4"])
    assert build(fake).run("What is 2 + 2?") == "4"


def _stub_response(status_code: int) -> Any:
    """Minimal stand-in for the httpx.Response that APIStatusError wants."""

    class _Response:
        def __init__(self) -> None:
            self.status_code = status_code
            self.headers: dict[str, str] = {}
            self.request = None

    return _Response()
