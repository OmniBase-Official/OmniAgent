"""Tests for the structured logging core."""

from __future__ import annotations

import json
import logging
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest

import observability as obs


@pytest.fixture(autouse=True)
def _clean_logging() -> Iterator[None]:
    """Every test starts and ends with no handlers and an empty context."""
    obs.reset()
    yield
    obs.reset()


def read_lines(path: Path) -> list[dict[str, Any]]:
    """Parse a JSON-lines log file into dictionaries."""
    for handler in obs.get_logger().handlers:
        handler.flush()
    text = path.read_text(encoding="utf-8").strip()
    if not text:
        return []
    return [json.loads(line) for line in text.splitlines()]


def test_event_writes_one_json_object_per_line(tmp_path: Path) -> None:
    log_file = tmp_path / "omniagent.jsonl"
    obs.configure(log_file=log_file)

    obs.event("agent.turn.start", question="What is 2 + 2?")
    obs.event("agent.turn.end", answer="4")

    records = read_lines(log_file)
    assert [record["event"] for record in records] == ["agent.turn.start", "agent.turn.end"]
    assert records[0]["question"] == "What is 2 + 2?"
    assert records[0]["level"] == "INFO"
    assert records[0]["logger"] == obs.LOGGER_NAME
    assert records[0]["ts"].endswith("Z")


def test_message_defaults_to_the_event_name(tmp_path: Path) -> None:
    log_file = tmp_path / "log.jsonl"
    obs.configure(log_file=log_file)

    obs.event("agent.step.start")
    obs.event("agent.step.end", "finished cleanly")

    records = read_lines(log_file)
    assert records[0]["message"] == "agent.step.start"
    assert records[1]["message"] == "finished cleanly"


def test_configure_returns_a_session_id_and_binds_it(tmp_path: Path) -> None:
    log_file = tmp_path / "log.jsonl"
    session_id = obs.configure(log_file=log_file, session_id="fixed-session")

    assert session_id == "fixed-session"
    obs.event("agent.turn.start")
    assert read_lines(log_file)[0]["session_id"] == "fixed-session"


def test_generated_session_ids_are_unique(tmp_path: Path) -> None:
    first = obs.configure(log_file=tmp_path / "a.jsonl")
    obs.reset()
    second = obs.configure(log_file=tmp_path / "b.jsonl")

    assert first
    assert second
    assert first != second


def test_bind_attaches_and_restores_context(tmp_path: Path) -> None:
    log_file = tmp_path / "log.jsonl"
    obs.configure(log_file=log_file, session_id="s1")

    with obs.bind(turn=1):
        obs.event("outer")
        with obs.bind(step=2):
            obs.event("inner")
        obs.event("after_inner")
    obs.event("after_outer")

    outer, inner, after_inner, after_outer = read_lines(log_file)
    assert outer["turn"] == 1
    assert "step" not in outer
    assert (inner["turn"], inner["step"]) == (1, 2)
    assert "step" not in after_inner
    assert "turn" not in after_outer
    assert after_outer["session_id"] == "s1"


def test_bind_restores_context_when_the_block_raises() -> None:
    obs.configure()
    with pytest.raises(ValueError, match="boom"), obs.bind(turn=1):
        raise ValueError("boom")
    assert "turn" not in obs.current_context()


def test_explicit_field_beats_bound_context(tmp_path: Path) -> None:
    log_file = tmp_path / "log.jsonl"
    obs.configure(log_file=log_file)

    with obs.bind(step=1):
        obs.event("agent.step.start", step=9)

    assert read_lines(log_file)[0]["step"] == 9


@pytest.mark.parametrize(
    "field",
    ["api_key", "API_KEY", "openai_api_key", "auth_token", "password", "client_secret"],
)
def test_credentials_are_redacted(tmp_path: Path, field: str) -> None:
    log_file = tmp_path / "log.jsonl"
    obs.configure(log_file=log_file)

    # Annotated as Any so mypy does not read the dynamic key as a possible
    # collision with event()'s keyword-only level/logger/exc_info parameters.
    secret_field: dict[str, Any] = {field: "sk-super-secret-value"}
    obs.event("agent.llm.request", **secret_field)

    record = read_lines(log_file)[0]
    assert record[field] == "***redacted***"
    assert "sk-super-secret-value" not in json.dumps(record)


@pytest.mark.parametrize(
    "field", ["prompt_tokens", "completion_tokens", "total_tokens", "max_tokens", "tokens"]
)
def test_token_counters_are_not_mistaken_for_credentials(tmp_path: Path, field: str) -> None:
    """Regression: the 'token' hint matched prompt_tokens and redacted the counts.

    The policy stays default-deny; these names are on an explicit allow-list.
    """
    log_file = tmp_path / "log.jsonl"
    obs.configure(log_file=log_file)

    counters: dict[str, Any] = {field: 1234}
    obs.event("agent.llm.response", **counters)

    assert read_lines(log_file)[0][field] == 1234


def test_nested_credentials_are_redacted(tmp_path: Path) -> None:
    log_file = tmp_path / "log.jsonl"
    obs.configure(log_file=log_file)

    obs.event("agent.llm.request", config={"model": "qwen2.5:7b", "api_key": "sk-secret"})

    record = read_lines(log_file)[0]
    assert record["config"]["model"] == "qwen2.5:7b"
    assert record["config"]["api_key"] == "***redacted***"


def test_long_fields_are_truncated(tmp_path: Path) -> None:
    log_file = tmp_path / "log.jsonl"
    obs.configure(log_file=log_file)

    obs.event("agent.llm.request", prompt="x" * (obs.MAX_FIELD_LENGTH + 500))

    prompt = read_lines(log_file)[0]["prompt"]
    assert prompt.startswith("x" * 100)
    assert prompt.endswith(f"...(truncated, {obs.MAX_FIELD_LENGTH + 500} chars)")
    assert len(prompt) < obs.MAX_FIELD_LENGTH + 100


def test_non_serialisable_values_do_not_break_the_line(tmp_path: Path) -> None:
    log_file = tmp_path / "log.jsonl"
    obs.configure(log_file=log_file)

    obs.event("agent.tool.call", tool=object(), numbers=[1, 2.5, None, True])

    record = read_lines(log_file)[0]
    assert "object object at" in record["tool"]
    assert record["numbers"] == [1, 2.5, None, True]


def test_exceptions_are_captured(tmp_path: Path) -> None:
    log_file = tmp_path / "log.jsonl"
    obs.configure(log_file=log_file)

    def explode() -> None:
        raise RuntimeError("tool exploded")

    try:
        explode()
    except RuntimeError:
        obs.event("agent.tool.error", level=logging.ERROR, exc_info=True)

    record = read_lines(log_file)[0]
    assert record["level"] == "ERROR"
    assert "RuntimeError: tool exploded" in record["error"]


def test_events_without_an_exception_carry_no_error_field(tmp_path: Path) -> None:
    """Regression: logging stores exc_info=False verbatim, not as None.

    Formatting that bool as a traceback raised inside the handler and silently
    dropped every ordinary record.
    """
    log_file = tmp_path / "log.jsonl"
    obs.configure(log_file=log_file)

    obs.event("agent.turn.start", question="hello")

    record = read_lines(log_file)[0]
    assert "error" not in record


def test_level_filters_events_out(tmp_path: Path) -> None:
    log_file = tmp_path / "log.jsonl"
    obs.configure(level=logging.WARNING, log_file=log_file)

    obs.event("agent.debug", level=logging.DEBUG)
    obs.event("agent.info", level=logging.INFO)
    obs.event("agent.warning", level=logging.WARNING)

    assert [record["event"] for record in read_lines(log_file)] == ["agent.warning"]


def test_configure_is_idempotent(tmp_path: Path) -> None:
    log_file = tmp_path / "log.jsonl"
    obs.configure(log_file=log_file, session_id="s1")
    obs.configure(log_file=log_file, session_id="s2")

    obs.event("agent.turn.start")

    records = read_lines(log_file)
    assert len(records) == 1, "the second configure() must not add a duplicate handler"
    assert records[0]["session_id"] == "s1"


def test_force_reconfigures(tmp_path: Path) -> None:
    first = tmp_path / "first.jsonl"
    second = tmp_path / "second.jsonl"
    obs.configure(log_file=first, session_id="s1")
    obs.configure(log_file=second, session_id="s2", force=True)

    obs.event("agent.turn.start")

    assert read_lines(first) == []
    assert read_lines(second)[0]["session_id"] == "s2"


def test_quiet_by_default(capsys: pytest.CaptureFixture[str]) -> None:
    """With no log file and no console flag, nothing reaches the terminal."""
    obs.configure()
    obs.event("agent.turn.start", question="hello")

    captured = capsys.readouterr()
    assert captured.out == ""
    assert captured.err == ""


def test_console_streams_to_stderr(capsys: pytest.CaptureFixture[str]) -> None:
    """stdout belongs to the human-readable trace; JSON goes to stderr."""
    obs.configure(console=True, session_id="s1")
    obs.event("agent.turn.start", question="hello")

    captured = capsys.readouterr()
    assert captured.out == ""
    assert json.loads(captured.err.strip())["question"] == "hello"


def test_agent_logs_do_not_propagate_to_the_root_logger(tmp_path: Path) -> None:
    """An embedding application's root handlers must not pick up our records."""
    obs.configure(log_file=tmp_path / "log.jsonl")
    assert obs.get_logger().propagate is False


def test_get_logger_returns_children() -> None:
    assert obs.get_logger().name == obs.LOGGER_NAME
    assert obs.get_logger("tools").name == f"{obs.LOGGER_NAME}.tools"


def test_child_logger_events_carry_context(tmp_path: Path) -> None:
    log_file = tmp_path / "log.jsonl"
    obs.configure(log_file=log_file, session_id="s1")

    with obs.bind(turn=3):
        obs.event("tool.call", logger=obs.get_logger("tools"), tool="calculate")

    record = read_lines(log_file)[0]
    assert record["logger"] == f"{obs.LOGGER_NAME}.tools"
    assert record["turn"] == 3
    assert record["session_id"] == "s1"
