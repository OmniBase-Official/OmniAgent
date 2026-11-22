"""The preflight must not repeat the model server's error body to the user.

``check_connection`` used to build its ``AgentError`` from ``exc.message``, which
``main.preflight`` prints on stdout. The request path already printed only the
status code. The body is text a server chose, so neither path should echo it.

The needle ``DUMMY_ERROR_BODY_CANARY`` is an obvious dummy. Four things are
asserted separately, because each can break without the others noticing:
the exception text, what the CLI prints, the arguments a call site hands to
``obs.event`` (the closed log schema would hide a bad argument), and the
records actually written (``exc_info=True`` is accepted but never persisted).
"""

from __future__ import annotations

import json
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import httpx
import pytest
from openai import APIStatusError

import main as main_module
import observability as obs
from agent import AgentConfig, AgentError, ReActAgent
from tests.fakes import FakeOpenAI
from tests.log_capture import configure_memory_sink, read_lines, reset_capture

CANARY = "DUMMY_ERROR_BODY_CANARY"
STATUS = 503


@pytest.fixture(autouse=True)
def _clean_logging() -> Iterator[None]:
    reset_capture()
    yield
    reset_capture()


def agent_whose_model_list_fails() -> ReActAgent:
    request = httpx.Request("GET", "http://127.0.0.1:1/v1/models")
    response = httpx.Response(STATUS, request=request)
    error = APIStatusError(CANARY, response=response, body={"message": CANARY})
    config = AgentConfig(verbose=False, max_retries=0, retry_backoff=0.0)
    return ReActAgent(
        config=config, client=FakeOpenAI(models_error=error).as_client(), printer=lambda _: None
    )


def test_the_error_text_carries_the_status_and_not_the_body() -> None:
    with pytest.raises(AgentError) as caught:
        agent_whose_model_list_fails().check_connection()
    assert str(caught.value) == f"Model server returned HTTP {STATUS}."
    assert CANARY not in str(caught.value)


def test_the_cli_preflight_prints_neither_the_body_nor_logs_it(
    capsys: pytest.CaptureFixture[str],
) -> None:
    assert main_module.preflight(agent_whose_model_list_fails()) is False
    captured = capsys.readouterr()
    assert f"HTTP {STATUS}" in captured.out
    assert CANARY not in captured.out + captured.err


def test_the_error_event_is_given_no_body_and_writes_none(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    configure_memory_sink(tmp_path / "unused.jsonl", force=True)
    seen: list[tuple[str, dict[str, Any]]] = []
    real = obs.event

    def spy(name: str, *args: Any, **fields: Any) -> None:
        seen.append((name, dict(fields)))
        real(name, *args, **fields)

    monkeypatch.setattr(obs, "event", spy)
    with pytest.raises(AgentError):
        agent_whose_model_list_fails().check_connection()

    arguments = [fields for name, fields in seen if name == "agent.connection.error"]
    assert len(arguments) == 1
    assert CANARY not in repr(arguments)
    written = read_lines(tmp_path / "unused.jsonl")
    assert any(line["event"] == "agent.connection.error" for line in written)
    assert CANARY not in json.dumps(written)
