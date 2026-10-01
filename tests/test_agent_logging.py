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


def events(path: Path) -> list[str]:
    return [record["event"] for record in records(path)]


def only(path: Path, name: str) -> dict[str, Any]:
    matches = [record for record in records(path) if record["event"] == name]
    assert len(matches) == 1, f"expected exactly one {name}, got {len(matches)}"
    return matches[0]


def build(fake: FakeOpenAI, **overrides: Any) -> ReActAgent:
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


def test_turn_and_step_context_is_attached(log_file: Path) -> None:
    fake = FakeOpenAI(
        replies=[
            "Thought: maths\nAction: calculate\nAction Input: 2 + 2",
            "Thought: done\nFinal Answer: 4",
        ]
    )
    agent = build(fake)
    agent.run("What is 2 + 2?")

    by_event = {record["event"]: record for record in records(log_file)}
    assert by_event["agent.tool.call"]["turn"] == 1
    assert by_event["agent.tool.call"]["step"] == 1
    assert by_event["agent.step.final_answer"]["step"] == 2
    assert by_event["agent.turn.end"]["turn"] == 1
    # agent.created happens before any turn, so it carries neither.
    assert "turn" not in by_event["agent.created"]


def test_turn_counter_increments_across_questions(log_file: Path) -> None:
    fake = FakeOpenAI(
        replies=["Thought: done\nFinal Answer: one", "Thought: done\nFinal Answer: two"]
    )
    agent = build(fake)
    agent.run("first")
    agent.run("second")

    turns = [r["turn"] for r in records(log_file) if r["event"] == "agent.turn.start"]
    assert turns == [1, 2]


def test_session_id_is_on_every_record(log_file: Path) -> None:
    fake = FakeOpenAI(replies=["Thought: done\nFinal Answer: 4"])
    build(fake).run("What is 2 + 2?")

    assert all(record["session_id"] == "test-session" for record in records(log_file))


def test_tool_result_carries_the_observation_and_timing(log_file: Path) -> None:
    fake = FakeOpenAI(
        replies=[
            "Thought: maths\nAction: calculate\nAction Input: 2 + 2",
            "Thought: done\nFinal Answer: 4",
        ]
    )
    build(fake).run("What is 2 + 2?")

    result = only(log_file, "agent.tool.result")
    assert result["tool"] == "calculate"
    assert result["ok"] is True
    assert result["observation"] == "2 + 2 = 4"
    assert isinstance(result["elapsed_ms"], (int, float))


def test_llm_response_carries_timing_and_token_usage(log_file: Path) -> None:
    fake = FakeOpenAI(replies=["Thought: done\nFinal Answer: 4"])
    build(fake).run("What is 2 + 2?")

    response = only(log_file, "agent.llm.response")
    assert response["prompt_tokens"] == 100
    assert response["completion_tokens"] == 20
    assert response["finish_reason"] == "stop"
    assert isinstance(response["elapsed_ms"], (int, float))


def test_turn_end_reports_steps_used(log_file: Path) -> None:
    fake = FakeOpenAI(
        replies=[
            "Thought: maths\nAction: calculate\nAction Input: 2 + 2",
            "Thought: more\nAction: calculate\nAction Input: 4 * 2",
            "Thought: done\nFinal Answer: 8",
        ]
    )
    build(fake).run("go")

    assert only(log_file, "agent.turn.end")["steps_used"] == 3


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
    assert result["ok"] is False
    assert result["level"] == "WARNING"
    assert result["observation"].startswith("Error: division by zero")


def test_an_unknown_tool_is_logged_by_the_registry(log_file: Path) -> None:
    fake = FakeOpenAI(
        replies=[
            "Thought: hmm\nAction: send_email\nAction Input: hi",
            "Thought: done\nFinal Answer: I cannot do that.",
        ]
    )
    build(fake).run("email someone")

    unknown = only(log_file, "tool.unknown")
    assert unknown["requested"] == "send_email"
    assert unknown["level"] == "WARNING"
    assert "calculate" in unknown["available"]


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
    assert invalid["tool"] == "calculate"
    assert "expression" in invalid["reason"], "the error must name the field that was wanted"

    results = [r for r in records(log_file) if r["event"] == "agent.tool.result"]
    assert [r["ok"] for r in results] == [False, True]
    assert results[1]["observation"] == "2 + 2 = 4"


def test_a_format_violation_is_logged_with_the_offending_reply(log_file: Path) -> None:
    fake = FakeOpenAI(
        replies=["Sure! The answer is probably 4.", "Thought: done\nFinal Answer: It is 4."]
    )
    build(fake).run("What is 2 + 2?")

    violation = only(log_file, "agent.format.violation")
    assert violation["level"] == "WARNING"
    assert violation["reply"] == "Sure! The answer is probably 4."


def test_running_out_of_steps_is_logged(log_file: Path) -> None:
    loop = "Thought: again\nAction: calculate\nAction Input: 1 + 1"
    fake = FakeOpenAI(replies=[loop, loop, "Thought: done\nFinal Answer: 2"])
    agent = build(fake, max_steps=2)

    assert agent.run("go") == "2"

    assert "agent.budget.exhausted" in events(log_file)
    assert only(log_file, "agent.budget.exhausted")["max_steps"] == 2


def test_an_unreachable_server_is_logged_with_a_traceback(log_file: Path) -> None:
    error = APIConnectionError(request=None)  # type: ignore[arg-type]
    fake = FakeOpenAI(completion_error=error)
    agent = build(fake)

    with pytest.raises(AgentError, match="Lost the connection"):
        agent.run("What is 2 + 2?")

    record = only(log_file, "agent.llm.unreachable")
    assert record["level"] == "ERROR"
    assert "APIConnectionError" in record["error"]


def test_a_server_error_logs_the_status_code(log_file: Path) -> None:
    error = APIStatusError("not found", response=_stub_response(404), body=None)
    fake = FakeOpenAI(completion_error=error)
    agent = build(fake)

    with pytest.raises(AgentError, match="ollama pull"):
        agent.run("What is 2 + 2?")

    assert only(log_file, "agent.llm.error")["status_code"] == 404


def test_connection_check_logs_whether_the_model_is_installed(log_file: Path) -> None:
    fake = FakeOpenAI(models=["gemma2:2b"])
    agent = build(fake, model="qwen2.5:7b")

    agent.check_connection()

    record = only(log_file, "agent.connection.ok")
    assert record["model_installed"] is False
    assert record["available"] == ["gemma2:2b"]


# --------------------------------------------------------------------------- #
# what must never reach the log
# --------------------------------------------------------------------------- #


def test_the_api_key_never_appears_in_the_log(log_file: Path) -> None:
    fake = FakeOpenAI(replies=["Thought: done\nFinal Answer: 4"])
    agent = build(fake, api_key="sk-this-must-never-be-logged")
    agent.run("What is 2 + 2?")

    raw = log_file.read_text(encoding="utf-8")
    assert "sk-this-must-never-be-logged" not in raw
    assert only(log_file, "agent.created")["config"]["api_key"] == "***redacted***"
    # The rest of the config is still there to debug with.
    assert only(log_file, "agent.created")["config"]["model"] == "qwen2.5:7b"


def test_logging_stays_off_stdout(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    obs.configure(level=logging.DEBUG, log_file=tmp_path / "log.jsonl")
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
