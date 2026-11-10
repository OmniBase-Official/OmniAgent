"""Tests for the structured logging core."""

from __future__ import annotations

import json
import logging
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest

import observability as obs
from tests.log_capture import (
    configure_memory_sink,
    reset_capture,
)
from tests.log_capture import (
    read_lines as read_memory_lines,
)


@pytest.fixture(autouse=True)
def _clean_logging() -> Iterator[None]:
    """Every test starts and ends with no handlers and an empty context."""
    reset_capture()
    yield
    reset_capture()


def read_lines(path: Path) -> list[dict[str, Any]]:
    """Read the test-only in-memory JSON-lines sink keyed by ``path``."""
    return read_memory_lines(path)


def test_event_writes_one_json_object_per_line(tmp_path: Path) -> None:
    log_file = tmp_path / "omniagent.jsonl"
    configure_memory_sink(log_file)

    obs.event("agent.turn.start", status="started", question="QUESTION_CANARY")
    obs.event("agent.turn.end", status="completed", answer="ANSWER_CANARY")

    records = read_lines(log_file)
    assert [record["event"] for record in records] == ["agent.turn.start", "agent.turn.end"]
    assert records[0]["status"] == "started"
    assert records[1]["status"] == "completed"
    assert records[0]["runtime_version"]
    assert "QUESTION_CANARY" not in json.dumps(records)
    assert "ANSWER_CANARY" not in json.dumps(records)


def test_message_defaults_to_the_event_name(tmp_path: Path) -> None:
    log_file = tmp_path / "log.jsonl"
    configure_memory_sink(log_file)

    obs.event("agent.turn.start", status="started")
    obs.event("agent.turn.end", "MESSAGE_CANARY", status="completed")

    records = read_lines(log_file)
    assert "message" not in records[0]
    assert "message" not in records[1]
    assert "MESSAGE_CANARY" not in json.dumps(records)


def test_configure_returns_a_session_id_and_binds_it(tmp_path: Path) -> None:
    log_file = tmp_path / "log.jsonl"
    session_id = configure_memory_sink(log_file, session_id="fixed-session")

    assert session_id == "fixed-session"
    obs.event("agent.turn.start", status="started")
    record = read_lines(log_file)[0]
    assert record["event"] == "agent.turn.start"
    assert "session_id" not in record


def test_generated_session_ids_are_unique(tmp_path: Path) -> None:
    first = configure_memory_sink(tmp_path / "a.jsonl")
    obs.reset()
    second = configure_memory_sink(tmp_path / "b.jsonl")

    assert first
    assert second
    assert first != second


def test_bind_attaches_and_restores_context(tmp_path: Path) -> None:
    log_file = tmp_path / "log.jsonl"
    configure_memory_sink(log_file, session_id="s1")

    with obs.bind(turn=1, question="BOUND_CANARY"):
        obs.event("agent.turn.start", status="started")
        with obs.bind(step=2):
            obs.event("agent.llm.request", status="requested", step_count=2)
        obs.event("agent.turn.end", status="completed", step_count=1)
    obs.event("agent.turn.start", status="started")

    outer, inner, after_inner, after_outer = read_lines(log_file)
    assert [record["event"] for record in (outer, inner, after_inner, after_outer)] == [
        "agent.turn.start",
        "agent.llm.request",
        "agent.turn.end",
        "agent.turn.start",
    ]
    assert inner["step_count"] == 2
    assert "turn" not in outer
    assert "step" not in inner
    assert "BOUND_CANARY" not in json.dumps([outer, inner, after_inner, after_outer])


def test_bind_restores_context_when_the_block_raises() -> None:
    obs.configure()
    with pytest.raises(ValueError, match="boom"), obs.bind(turn=1):
        raise ValueError("boom")
    assert "turn" not in obs.current_context()


def test_explicit_field_beats_bound_context(tmp_path: Path) -> None:
    log_file = tmp_path / "log.jsonl"
    configure_memory_sink(log_file)

    with obs.bind(step_count=1):
        obs.event("agent.turn.start", status="started", step_count=9)

    assert read_lines(log_file)[0]["step_count"] == 9


@pytest.mark.parametrize(
    "field",
    ["api_key", "API_KEY", "openai_api_key", "auth_token", "password", "client_secret"],
)
def test_credentials_are_dropped(tmp_path: Path, field: str) -> None:
    log_file = tmp_path / "log.jsonl"
    configure_memory_sink(log_file)

    # Annotated as Any so mypy does not read the dynamic key as a possible
    # collision with event()'s keyword-only level/logger/exc_info parameters.
    secret_field: dict[str, Any] = {field: "sk-super-secret-value"}
    obs.event("agent.llm.request", **secret_field)

    record = read_lines(log_file)[0]
    assert field not in record
    assert "sk-super-secret-value" not in json.dumps(record)


def test_secret_shaped_model_tag_is_dropped(tmp_path: Path) -> None:
    log_file = tmp_path / "log.jsonl"
    configure_memory_sink(log_file)

    obs.event("agent.llm.request", model_tag="token-abc123")

    record = read_lines(log_file)[0]
    assert "model_tag" not in record
    assert "token-abc123" not in json.dumps(record)


@pytest.mark.parametrize(
    "field", ["prompt_tokens", "completion_tokens", "total_tokens", "max_tokens", "tokens"]
)
def test_token_counters_are_not_mistaken_for_credentials(tmp_path: Path, field: str) -> None:
    """Regression: the 'token' hint matched prompt_tokens and redacted the counts.

    The policy stays default-deny; these names are on an explicit allow-list.
    """
    log_file = tmp_path / "log.jsonl"
    configure_memory_sink(log_file)

    counters: dict[str, Any] = {field: 1234}
    obs.event("agent.llm.response", **counters)

    assert field not in read_lines(log_file)[0]


def test_nested_credentials_are_dropped(tmp_path: Path) -> None:
    log_file = tmp_path / "log.jsonl"
    configure_memory_sink(log_file)

    obs.event("agent.llm.request", config={"model": "qwen2.5:7b", "api_key": "sk-secret"})

    record = read_lines(log_file)[0]
    assert "config" not in record


def test_long_fields_are_dropped(tmp_path: Path) -> None:
    log_file = tmp_path / "log.jsonl"
    configure_memory_sink(log_file)

    obs.event("agent.llm.request", prompt="x" * 2_500)

    record = read_lines(log_file)[0]
    assert "prompt" not in record
    assert "x" * 100 not in json.dumps(record)


def test_non_serialisable_values_do_not_break_the_line(tmp_path: Path) -> None:
    log_file = tmp_path / "log.jsonl"
    configure_memory_sink(log_file)

    obs.event("agent.tool.call", tool=object(), numbers=[1, 2.5, None, True])

    record = read_lines(log_file)[0]
    assert "tool" not in record
    assert "numbers" not in record


def test_sanitizer_rejects_spoofed_string_subclasses() -> None:
    class SpoofedText(str):
        allowed_value: str

        def __new__(cls, value: str, allowed_value: str) -> SpoofedText:
            instance = super().__new__(cls, value)
            instance.allowed_value = allowed_value
            return instance

        def __hash__(self) -> int:
            return hash(self.allowed_value)

        def __eq__(self, other: object) -> bool:
            return other == self.allowed_value

    canary_text = "SECRET_TELEMETRY_CANARY"
    spoofed_status = SpoofedText(canary_text, "created")
    spoofed_tool = SpoofedText(canary_text, "calculate")
    spoofed_digest = SpoofedText(canary_text, "a" * 64)
    spoofed_key = SpoofedText(canary_text, "status")
    spoofed_event = SpoofedText(canary_text, "agent.created")

    payload = obs._sanitise_event(
        "agent.created",
        {
            "status": spoofed_status,
            "tool_name": spoofed_tool,
            "model_digest": spoofed_digest,
        },
    )
    assert payload is not None
    serialised = json.dumps(payload)
    assert canary_text not in serialised
    assert "status" not in payload
    assert "tool_name" not in payload
    assert "model_digest" not in payload
    key_payload = obs._sanitise_event("agent.created", {spoofed_key: "created"})
    assert key_payload is not None
    assert "status" not in key_payload
    assert obs._sanitise_event(spoofed_event, {"status": "created"}) is None


def test_sanitizer_rejects_int_subclasses_for_step_count() -> None:
    class SpoofedInt(int):
        pass

    payload = obs._sanitise_event(
        "agent.turn.start",
        {"status": "started", "step_count": SpoofedInt(4)},
    )

    assert payload is not None
    assert "step_count" not in payload


def test_exception_details_are_never_captured(tmp_path: Path) -> None:
    log_file = tmp_path / "log.jsonl"
    configure_memory_sink(log_file)

    def explode() -> None:
        raise RuntimeError("tool exploded")

    try:
        explode()
    except RuntimeError:
        obs.event(
            "tool.crashed",
            level=logging.ERROR,
            status="error",
            tool_name="calculate",
            exc_info=True,
        )

    record = read_lines(log_file)[0]
    assert record["status"] == "error"
    assert "error" not in record


def test_events_without_an_exception_carry_no_error_field(tmp_path: Path) -> None:
    """Regression: logging stores exc_info=False verbatim, not as None.

    Formatting that bool as a traceback raised inside the handler and silently
    dropped every ordinary record.
    """
    log_file = tmp_path / "log.jsonl"
    configure_memory_sink(log_file)

    obs.event("agent.turn.start", question="hello")

    record = read_lines(log_file)[0]
    assert "error" not in record


def test_level_filters_events_out(tmp_path: Path) -> None:
    log_file = tmp_path / "log.jsonl"
    configure_memory_sink(log_file, level=logging.WARNING)

    obs.event("agent.turn.start", level=logging.DEBUG, status="started")
    obs.event("agent.turn.start", level=logging.INFO, status="started")
    obs.event("agent.turn.start", level=logging.WARNING, status="started")

    assert [record["event"] for record in read_lines(log_file)] == ["agent.turn.start"]


def test_configure_is_idempotent(tmp_path: Path) -> None:
    log_file = tmp_path / "log.jsonl"
    configure_memory_sink(log_file, session_id="s1")
    configure_memory_sink(log_file, session_id="s2")

    obs.event("agent.turn.start", status="started")

    records = read_lines(log_file)
    assert len(records) == 1, "the second configure() must not add a duplicate handler"
    assert records[0]["event"] == "agent.turn.start"
    assert "session_id" not in records[0]


def test_force_reconfigures(tmp_path: Path) -> None:
    first = tmp_path / "first.jsonl"
    second = tmp_path / "second.jsonl"
    configure_memory_sink(first, session_id="s1")
    configure_memory_sink(second, session_id="s2", force=True)

    obs.event("agent.turn.start", status="started")

    assert read_lines(first) == []
    assert read_lines(second)[0]["event"] == "agent.turn.start"
    assert "session_id" not in read_lines(second)[0]


@pytest.mark.parametrize(
    ("configured", "force"), [(False, False), (True, False), (True, True)]
)
def test_configure_rejects_log_file_before_any_path_side_effect(
    tmp_path: Path, configured: bool, force: bool
) -> None:
    if configured:
        obs.configure()
    target = tmp_path / "not-created" / "operational.jsonl"
    handlers_before = tuple(obs.get_logger().handlers)

    with pytest.raises(RuntimeError, match="persistent operational log files are disabled"):
        obs.configure(log_file=target, force=force)

    assert not target.parent.exists()
    assert not target.exists()
    assert tuple(obs.get_logger().handlers) == handlers_before


def test_quiet_by_default(capsys: pytest.CaptureFixture[str]) -> None:
    """With no log file and no console flag, nothing reaches the terminal."""
    obs.configure()
    obs.event("agent.turn.start", status="started", question="hello")

    captured = capsys.readouterr()
    assert captured.out == ""
    assert captured.err == ""


def test_console_streams_to_stderr(capsys: pytest.CaptureFixture[str]) -> None:
    """stdout belongs to the human-readable trace; JSON goes to stderr."""
    obs.configure(console=True, session_id="s1")
    obs.event("agent.turn.start", status="started", question="hello")

    captured = capsys.readouterr()
    assert captured.out == ""
    record = json.loads(captured.err.strip())
    assert record["event"] == "agent.turn.start"
    assert record["record_type"] == "operational_telemetry"
    assert "question" not in record


def test_console_sink_does_not_emit_raw_canaries(capsys: pytest.CaptureFixture[str]) -> None:
    obs.configure(console=True, session_id="console-canary")
    obs.event(
        "agent.llm.response",
        reply="RAW_REPLY_CANARY",
        question="RAW_PROMPT_CANARY",
        tool_input="RAW_ARGUMENT_CANARY",
        observation="RAW_OBSERVATION_CANARY",
        answer="RAW_ANSWER_CANARY",
        error="RAW_ERROR_CANARY",
        status="succeeded",
    )

    captured = capsys.readouterr()
    assert captured.out == ""
    assert all(
        canary not in captured.err
        for canary in (
            "RAW_REPLY_CANARY",
            "RAW_PROMPT_CANARY",
            "RAW_ARGUMENT_CANARY",
            "RAW_OBSERVATION_CANARY",
            "RAW_ANSWER_CANARY",
            "RAW_ERROR_CANARY",
            "console-canary",
        )
    )
    record = json.loads(captured.err.strip())
    assert record["record_type"] == "operational_telemetry"
    assert record["status"] == "succeeded"


def test_agent_logs_do_not_propagate_to_the_root_logger(tmp_path: Path) -> None:
    """An embedding application's root handlers must not pick up our records."""
    configure_memory_sink(tmp_path / "log.jsonl")
    assert obs.get_logger().propagate is False


def test_get_logger_returns_children() -> None:
    assert obs.get_logger().name == obs.LOGGER_NAME
    assert obs.get_logger("tools").name == f"{obs.LOGGER_NAME}.tools"


def test_child_logger_events_do_not_persist_context_or_logger_names(tmp_path: Path) -> None:
    log_file = tmp_path / "log.jsonl"
    configure_memory_sink(log_file, session_id="s1")

    with obs.bind(turn=3):
        obs.event("tool.unknown", logger=obs.get_logger("tools"), status="rejected")

    record = read_lines(log_file)[0]
    assert record["event"] == "tool.unknown"
    assert "logger" not in record
    assert "turn" not in record
    assert "session_id" not in record
