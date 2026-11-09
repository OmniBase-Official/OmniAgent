"""Frozen MVP acceptance tests for operational privacy and tool policy.

These tests use only synthetic data and fake model responses. They intentionally
describe security behavior the runtime must implement before an evaluation
trial can run.
"""

from __future__ import annotations

import json
import logging
import shutil
import sys
from collections.abc import Callable, Collection, Iterator
from dataclasses import replace
from pathlib import Path
from typing import Any, cast

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

import httpx
import pytest
from grounding_cohort import FIXTURE, POLICY_VIOLATION, TASKS, Preflight, run_cohort
from openai import APIStatusError

import agent as agent_module
import main as main_module
import observability as obs
import tools as tools_module
from agent import AgentConfig, ReActAgent
from sandbox import Workspace, get_workspace, set_workspace
from tests.fakes import FakeOpenAI
from tests.log_capture import configure_memory_sink, read_lines, reset_capture


@pytest.fixture(autouse=True)
def _reset_logging() -> Iterator[None]:
    reset_capture()
    yield
    reset_capture()


@pytest.mark.parametrize("sink", ["memory", "console"])
def test_operational_logs_never_persist_raw_turn_material(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str], sink: str,
) -> None:
    """Canaries cover every raw field prohibited by the MVP contract."""
    log_path = tmp_path / "not-created" / "operational.jsonl"
    if sink == "memory":
        configure_memory_sink(log_path, level=logging.DEBUG, session_id="synthetic-session")
    else:
        obs.configure(level=logging.DEBUG, console=True, session_id="synthetic-session")

    root = tmp_path / "workspace"
    root.mkdir()
    (root / "ARGUMENT_CANARY.txt").write_text("FILE_CONTENT_CANARY\n", encoding="utf-8")
    previous = get_workspace()
    set_workspace(Workspace.at(root))

    real_run_tool = cast(Callable[..., str], agent_module.__dict__["run_tool"])

    def fake_tool_error(
        name: str,
        raw_input: str,
        *,
        allowed_tools: Collection[str] | None = None,
    ) -> str:
        if name == "calculate":
            return "Error: RAW_ERROR_CANARY"
        return real_run_tool(name, raw_input, allowed_tools=allowed_tools)

    monkeypatch.setattr(agent_module, "run_tool", fake_tool_error)
    monkeypatch.setattr(
        agent_module,
        "SYSTEM_PROMPT_TEMPLATE",
        "SYSTEM_PROMPT_CANARY\n{tools}\n{tool_names}",
    )

    fake = FakeOpenAI(
        replies=[
            (
                "Thought: THOUGHT_CANARY; REPLY_CANARY\n"
                "Action: read_file\nAction Input: ARGUMENT_CANARY.txt"
            ),
            (
                "Thought: ERROR_THOUGHT_CANARY\n"
                "Action: calculate\nAction Input: ERROR_ARGUMENT_CANARY"
            ),
            "Thought: FINAL_THOUGHT_CANARY\nFinal Answer: ANSWER_CANARY",
        ]
    )
    printed: list[str] = []
    agent = ReActAgent(
        config=AgentConfig(api_key="SECRET_CANARY", max_retries=0),
        client=fake.as_client(),
        printer=printed.append,
    )

    try:
        assert agent.run("PROMPT_CANARY") == "ANSWER_CANARY"
    finally:
        set_workspace(previous)

    for handler in obs.get_logger().handlers:
        handler.flush()
    if sink == "memory":
        records = read_lines(log_path)
    else:
        records = [json.loads(line) for line in capsys.readouterr().err.splitlines()]
    operational_log = json.dumps(records)
    forbidden = (
        "SYSTEM_PROMPT_CANARY",
        "PROMPT_CANARY",
        "REPLY_CANARY",
        "THOUGHT_CANARY",
        "ERROR_THOUGHT_CANARY",
        "FINAL_THOUGHT_CANARY",
        "ARGUMENT_CANARY.txt",
        "ERROR_ARGUMENT_CANARY",
        "FILE_CONTENT_CANARY",
        "ANSWER_CANARY",
        "RAW_ERROR_CANARY",
        "SECRET_CANARY",
    )
    leaked = tuple(value for value in forbidden if value in operational_log)
    assert leaked == (), f"raw operational data leaked: {leaked}"
    assert printed == [], "quiet-by-default must not print raw reasoning or tool output"

    assert any(record["event"] == "agent.tool.result" for record in records)
    assert any(record["event"] == "agent.llm.response" for record in records)
    assert all("event" in record for record in records)
    assert not log_path.parent.exists()
    assert not log_path.exists()


@pytest.mark.parametrize(
    ("configured", "force"), [(False, False), (True, False), (True, True)]
)
def test_file_log_configuration_is_refused_without_side_effects(
    tmp_path: Path, configured: bool, force: bool
) -> None:
    if configured:
        obs.configure(console=True)
    target = tmp_path / "not-created" / "operational.jsonl"
    handlers_before = tuple(obs.get_logger().handlers)

    with pytest.raises(RuntimeError, match="persistent operational log files are disabled"):
        obs.configure(log_file=target, force=force)

    assert not target.parent.exists()
    assert not target.exists()
    assert tuple(obs.get_logger().handlers) == handlers_before


@pytest.mark.parametrize("verbose", [False, True])
def test_cli_answer_is_human_output_not_console_telemetry(
    capsys: pytest.CaptureFixture[str], verbose: bool,
) -> None:
    obs.configure(console=True)
    fake = FakeOpenAI(replies=["Thought: PRIVATE_THOUGHT\nFinal Answer: ANSWER_CANARY"])
    agent = ReActAgent(config=AgentConfig(max_retries=0, verbose=verbose), client=fake.as_client())
    assert main_module.answer(agent, "PROMPT_CANARY") == 0
    output = capsys.readouterr()
    assert "ANSWER_CANARY" in output.out
    assert "PROMPT_CANARY" not in output.out
    assert ("PRIVATE_THOUGHT" in output.out) is verbose
    assert all(value not in output.err for value in (
        "ANSWER_CANARY", "PROMPT_CANARY", "PRIVATE_THOUGHT"
    ))
    assert any(
        json.loads(line)["event"] == "agent.llm.response" for line in output.err.splitlines()
    )


@pytest.mark.parametrize("phase", ["preflight", "request"])
def test_cli_server_error_hides_raw_details(
    phase: str, capsys: pytest.CaptureFixture[str],
) -> None:
    obs.configure(console=True)
    response = httpx.Response(500, request=httpx.Request("GET", "http://localhost/test"))
    error = APIStatusError("SERVER_ERROR_CANARY", response=response, body=None)
    fake = FakeOpenAI(models_error=error if phase == "preflight" else None,
                      completion_error=error if phase == "request" else None)
    agent = ReActAgent(config=AgentConfig(max_retries=0), client=fake.as_client())
    if phase == "preflight":
        assert not main_module.preflight(agent)
    else:
        assert main_module.answer(agent, "PROMPT_CANARY") == 1
    output = capsys.readouterr()
    assert "HTTP 500" in output.out
    assert "SERVER_ERROR_CANARY" not in output.out + output.err
    assert "PROMPT_CANARY" not in output.out + output.err
    assert any(json.loads(line)["status"] == "error" for line in output.err.splitlines()
               if "status" in json.loads(line))


def test_disallowed_task_tool_is_stopped_before_dispatch(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A globally registered but task-disallowed tool must never execute."""
    shutil.copytree(FIXTURE, tmp_path / FIXTURE.name)
    task = TASKS[0]  # Allows read_file/list_directory, not calculate.
    preflight = Preflight(
        commit="1234567",
        tree_clean=True,
        model_tag="omniagent-v2",
        model_digest="sha256:" + "0" * 64,
        endpoint="loopback",
        runtime_version="fake-runtime",
        temperature=0.0,
        max_steps=8,
        max_retries=0,
    )

    calculate = tools_module.TOOLS["calculate"]
    dispatched: list[Any] = []

    def count_dispatch(args: Any) -> str:
        dispatched.append(args)
        return calculate.run(args)

    monkeypatch.setitem(
        tools_module.TOOLS,
        "calculate",
        replace(calculate, run=count_dispatch),
    )
    fake = FakeOpenAI(
        replies=[
            "Thought: use arithmetic\nAction: calculate\nAction Input: 2 + 2",
            "Thought: stop\nFinal Answer: trial stopped",
        ]
    )

    result = run_cohort(
        preflight=preflight,
        client=fake.as_client(),
        cohort_id="synthetic-policy-test",
        tasks=(task,),
        repeats=1,
        root=tmp_path,
        observe_revision=lambda: (preflight.commit, True),
    )

    assert result.records[0]["execution_status"] == POLICY_VIOLATION
    assert dispatched == [], "allowlist rejection must happen before Tool.run"
    assert len(fake.calls) == 1, "a policy violation must stop before another model request"
    assert result.started == 1, "a policy violation must not be silently replaced"
