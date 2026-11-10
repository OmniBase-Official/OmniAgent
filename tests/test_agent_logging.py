"""The agent must not persist raw user or model content in telemetry."""

from __future__ import annotations

import json
import logging
from pathlib import Path

from agent import AgentConfig, ReActAgent
from tests.fakes import FakeOpenAI
from tests.log_capture import configure_memory_sink, read_lines, reset_capture


def test_raw_turn_content_never_reaches_persisted_telemetry(tmp_path: Path) -> None:
    path = tmp_path / "omniagent.jsonl"
    reset_capture()
    configure_memory_sink(path, level=logging.DEBUG, session_id="SESSION_CANARY")
    question = "QUESTION_PRIVATE_CANARY"
    reply = "Thought: PRIVATE_THOUGHT_CANARY\nFinal Answer: PRIVATE_ANSWER_CANARY"
    agent = ReActAgent(
        config=AgentConfig(verbose=False),
        client=FakeOpenAI(replies=[reply]).as_client(),
        printer=lambda _: None,
    )

    assert agent.run(question) == "PRIVATE_ANSWER_CANARY"
    serialized = json.dumps(read_lines(path))
    assert "QUESTION_PRIVATE_CANARY" not in serialized
    assert "PRIVATE_THOUGHT_CANARY" not in serialized
    assert "PRIVATE_ANSWER_CANARY" not in serialized
    assert "SESSION_CANARY" not in serialized
    reset_capture()
