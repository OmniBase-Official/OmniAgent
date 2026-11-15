"""Workspace selection stays local to each scoped agent execution."""

from __future__ import annotations

from collections.abc import Iterator
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from threading import Barrier, Event

import pytest

import main as cli
from agent import (
    MAX_HISTORY_BYTES,
    MAX_HISTORY_TURNS,
    MAX_QUESTION_BYTES,
    AgentConfig,
    AgentError,
    ReActAgent,
)
from sandbox import Workspace, get_workspace, set_workspace, workspace_scope
from tests.fakes import FakeOpenAI
from tools import read_file


@pytest.fixture(autouse=True)
def _explicit_test_workspace(tmp_path: Path) -> Iterator[None]:
    with workspace_scope(Workspace.at(tmp_path)):
        yield


def test_legacy_set_get_and_nested_scope_restore_after_exception(tmp_path: Path) -> None:
    previous = get_workspace()
    for name in ("legacy", "outer", "inner"):
        (tmp_path / name).mkdir()
    legacy = Workspace.at(tmp_path / "legacy")
    outer = Workspace.at(tmp_path / "outer")
    inner = Workspace.at(tmp_path / "inner")

    def fail_inside_inner_scope() -> None:
        with workspace_scope(inner):
            assert get_workspace() is inner
            raise RuntimeError("scope failure")

    try:
        set_workspace(legacy)
        assert get_workspace() is legacy

        with workspace_scope(outer):
            assert get_workspace() is outer
            with pytest.raises(RuntimeError, match="scope failure"):
                fail_inside_inner_scope()
            assert get_workspace() is outer

        assert get_workspace() is legacy
    finally:
        set_workspace(previous)


def test_workspace_root_handle_survives_nested_scopes_until_owner_closes(
    tmp_path: Path,
) -> None:
    root = tmp_path / "owned"
    root.mkdir()
    (root / "note.txt").write_text("still open", encoding="utf-8")
    workspace = Workspace.at(root)
    pinned = workspace._secure_root
    with workspace_scope(workspace):
        assert workspace.read_text("note.txt") == "still open"
        with workspace_scope(workspace):
            assert workspace._secure_root is pinned
            assert workspace.read_text("note.txt") == "still open"
        assert workspace.read_text("note.txt") == "still open"
    workspace.close()
    workspace.close()  # idempotent explicit owner cleanup


def test_legacy_set_workspace_is_context_local_across_threads(tmp_path: Path) -> None:
    roots = [tmp_path / "worker-a", tmp_path / "worker-b"]
    for root in roots:
        root.mkdir()
    barrier = Barrier(2)

    def select_and_read(root: Path) -> Workspace:
        workspace = Workspace.at(root)
        set_workspace(workspace)
        barrier.wait(timeout=10)
        return get_workspace()

    with ThreadPoolExecutor(max_workers=2) as executor:
        first = executor.submit(select_and_read, roots[0])
        second = executor.submit(select_and_read, roots[1])
        first_workspace = first.result(timeout=20)
        second_workspace = second.result(timeout=20)

    assert first_workspace.root == roots[0].resolve()
    assert second_workspace.root == roots[1].resolve()


def test_main_tool_mode_uses_scoped_workspace_without_leaking_it(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    previous = get_workspace()
    (tmp_path / "legacy").mkdir()
    legacy = Workspace.at(tmp_path / "legacy")
    requested = tmp_path / "requested"
    requested.mkdir()
    (requested / "private.txt").write_text("CLI_PRIVATE_CANARY", encoding="utf-8")
    try:
        set_workspace(legacy)
        result = cli.main(
            [
                "--workspace",
                str(requested),
                "--tool",
                "read_file",
                "--tool-input",
                '{"path":"private.txt"}',
            ]
        )

        assert result == 0
        assert "CLI_PRIVATE_CANARY" in capsys.readouterr().out
        assert get_workspace() is legacy
    finally:
        set_workspace(previous)


def test_concurrent_agents_keep_file_reads_and_denials_in_their_own_workspaces(
    tmp_path: Path,
) -> None:
    previous = get_workspace()
    (tmp_path / "fallback").mkdir()
    fallback = Workspace.at(tmp_path / "fallback")
    alpha_root = tmp_path / "alpha"
    beta_root = tmp_path / "beta"
    alpha_root.mkdir()
    beta_root.mkdir()
    (alpha_root / "secret.txt").write_text("ALPHA_PRIVATE_CANARY", encoding="utf-8")
    (beta_root / "secret.txt").write_text("BETA_PRIVATE_CANARY", encoding="utf-8")
    (beta_root / "only-beta.txt").write_text("BETA_ONLY_CANARY", encoding="utf-8")

    barrier = Barrier(2)

    def synchronize_requests() -> None:
        barrier.wait(timeout=10)

    replies = [
        "Thought: read the secret.\nAction: read_file\nAction Input: secret.txt",
        "Thought: try the beta-only file.\nAction: read_file\nAction Input: only-beta.txt",
        "Thought: done.\nFinal Answer: finished",
    ]
    agents = [
        ReActAgent(
            config=AgentConfig(verbose=False, max_steps=3, retry_backoff=0.0),
            client=FakeOpenAI(replies=list(replies)).as_client(),
            printer=lambda _: None,
            before_model_request=synchronize_requests,
            workspace=Workspace.at(root),
        )
        for root in (alpha_root, beta_root)
    ]

    def execute(agent: ReActAgent) -> list[str | None]:
        agent.run("Read the private files.")
        return [step.observation for step in agent.last_trace]

    try:
        set_workspace(fallback)
        with ThreadPoolExecutor(max_workers=2) as executor:
            alpha_future = executor.submit(execute, agents[0])
            beta_future = executor.submit(execute, agents[1])
            alpha_observations = alpha_future.result(timeout=20)
            beta_observations = beta_future.result(timeout=20)

        assert "ALPHA_PRIVATE_CANARY" in str(alpha_observations[0])
        assert "BETA_PRIVATE_CANARY" not in " ".join(map(str, alpha_observations))
        assert str(alpha_observations[1]).startswith("Error:")
        assert "BETA_ONLY_CANARY" not in str(alpha_observations[1])
        assert "BETA_PRIVATE_CANARY" in str(beta_observations[0])
        assert "BETA_ONLY_CANARY" in str(beta_observations[1])
        assert "ALPHA_PRIVATE_CANARY" not in " ".join(map(str, beta_observations))
        assert get_workspace() is fallback
    finally:
        set_workspace(previous)


def test_agent_refuses_to_run_without_an_explicit_workspace(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    sentinel = tmp_path / "cwd-sentinel.txt"
    sentinel.write_text("CWD_PRIVATE_CANARY", encoding="utf-8")
    monkeypatch.chdir(tmp_path)
    fake = FakeOpenAI(replies=["Thought: done\nFinal Answer: finished"])
    agent = ReActAgent(
        config=AgentConfig(verbose=False),
        client=fake.as_client(),
        printer=lambda _: None,
    )

    with workspace_scope(None), pytest.raises(AgentError, match="explicit workspace is required"):
        agent.run("Read cwd-sentinel.txt")

    assert fake.calls == []
    assert agent.history == []
    assert "CWD_PRIVATE_CANARY" not in " ".join(str(call) for call in fake.calls)


def test_oversized_question_is_rejected_before_model_request(tmp_path: Path) -> None:
    fake = FakeOpenAI(replies=["Thought: done\nFinal Answer: finished"])
    agent = ReActAgent(
        config=AgentConfig(verbose=False),
        client=fake.as_client(),
        printer=lambda _: None,
        workspace=Workspace.at(tmp_path),
    )
    question_at_limit = "界" * (MAX_QUESTION_BYTES // 3) + "x"
    assert len(question_at_limit.encode("utf-8")) == MAX_QUESTION_BYTES
    assert agent.run(question_at_limit) == "finished"
    assert len(fake.calls) == 1

    with pytest.raises(AgentError, match="UTF-8 limit"):
        agent.run(question_at_limit + "x")

    assert len(fake.calls) == 1
    assert len(agent.history) == 2


def test_history_byte_cap_discards_oldest_complete_turns(tmp_path: Path) -> None:
    turn_count = 5
    fake = FakeOpenAI(replies=["Thought: done\nFinal Answer: ok"] * turn_count)
    agent = ReActAgent(
        config=AgentConfig(verbose=False),
        client=fake.as_client(),
        printer=lambda _: None,
        workspace=Workspace.at(tmp_path),
    )
    long_question = "q" * (MAX_QUESTION_BYTES - 2)

    for index in range(turn_count):
        agent.run(f"{index}:{long_question}")

    retained_bytes = sum(
        len(str(message["role"]).encode("utf-8")) + len(str(message["content"]).encode("utf-8"))
        for message in agent.history
    )
    retained_text = " ".join(str(message["content"]) for message in agent.history)
    assert retained_bytes <= MAX_HISTORY_BYTES
    assert "0:" not in retained_text
    assert f"{turn_count - 1}:" in retained_text


def test_answer_larger_than_history_cap_is_returned_but_not_retained(
    tmp_path: Path,
) -> None:
    answer = "A" * (MAX_HISTORY_BYTES + 1)
    fake = FakeOpenAI(replies=[f"Thought: done\nFinal Answer: {answer}"])
    agent = ReActAgent(
        config=AgentConfig(verbose=False),
        client=fake.as_client(),
        printer=lambda _: None,
        workspace=Workspace.at(tmp_path),
    )

    assert agent.run("Keep the reply intact") == answer
    assert agent.history == []


def test_cli_refuses_to_start_without_an_explicit_tenant_workspace(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    (tmp_path / "cwd-sentinel.txt").write_text("CWD_PRIVATE_CANARY", encoding="utf-8")
    monkeypatch.chdir(tmp_path)

    with workspace_scope(None):
        result = cli.main(["--ask", "Read cwd-sentinel.txt"])

    assert result == 2
    assert "explicit tenant workspace" in capsys.readouterr().out


def test_agent_session_cannot_change_its_bound_workspace(tmp_path: Path) -> None:
    alpha_root = tmp_path / "alpha"
    beta_root = tmp_path / "beta"
    alpha_root.mkdir()
    beta_root.mkdir()
    fake = FakeOpenAI(replies=["Thought: done\nFinal Answer: finished"])
    agent = ReActAgent(
        config=AgentConfig(verbose=False),
        client=fake.as_client(),
        printer=lambda _: None,
    )

    with workspace_scope(Workspace.at(alpha_root)):
        agent.run("first")
    with (
        workspace_scope(Workspace.at(beta_root)),
        pytest.raises(AgentError, match="cannot change its workspace"),
    ):
        agent.run("second")

    assert len(fake.calls) == 1
    assert agent._turn == 1


def test_agent_session_rejects_weaker_same_root_policy_before_model_request(
    tmp_path: Path,
) -> None:
    root = tmp_path / "same-root"
    root.mkdir()
    canary = root / "DENIED_POLICY_CANARY.txt"
    canary.write_text("UNIQUE-DENIED-POLICY-CANARY", encoding="utf-8")
    restricted = Workspace.at(root, denied_paths=frozenset({canary.resolve()}))
    weaker = Workspace.at(root)
    fake = FakeOpenAI(
        replies=[
            "Thought: done\nFinal Answer: first",
            "Thought: read the file\nAction: read_file\nAction Input: DENIED_POLICY_CANARY.txt",
            "Thought: done\nFinal Answer: UNIQUE-DENIED-POLICY-CANARY",
        ]
    )
    agent = ReActAgent(
        config=AgentConfig(verbose=False),
        client=fake.as_client(),
        printer=lambda _: None,
    )
    try:
        with workspace_scope(restricted):
            agent.run("first turn")
        with (
            workspace_scope(weaker),
            pytest.raises(AgentError, match="cannot change its workspace or security policy"),
        ):
            agent.run("try to read the denied canary")
        with workspace_scope(restricted):
            denied = read_file(canary.name)

        assert len(fake.calls) == 1
        assert denied.startswith("Error:")
        assert "UNIQUE-DENIED-POLICY-CANARY" not in denied
        assert "UNIQUE-DENIED-POLICY-CANARY" not in str(agent.last_trace)
    finally:
        restricted.close()
        weaker.close()


def test_omitted_identity_is_one_local_session_and_caller_cannot_select_identity(
    tmp_path: Path,
) -> None:
    fake = FakeOpenAI(
        replies=[
            "Thought: done\nFinal Answer: first answer",
            "Thought: done\nFinal Answer: second answer",
        ]
    )
    agent = ReActAgent(
        config=AgentConfig(verbose=False),
        client=fake.as_client(),
        printer=lambda _: None,
        workspace=Workspace.at(tmp_path),
    )

    agent.run("FIRST_LOCAL_SESSION_CANARY")
    method_name = "run"
    run = getattr(agent, method_name)
    with pytest.raises(TypeError):
        run("forged identity", principal_id="caller-selected")
    assert len(fake.calls) == 1

    agent.run("SECOND_LOCAL_SESSION_CANARY")

    assert "FIRST_LOCAL_SESSION_CANARY" in str(fake.calls[1]["messages"])
    assert "SECOND_LOCAL_SESSION_CANARY" in str(fake.calls[1]["messages"])
    assert agent._turn == 2
    assert len(agent.history) == 4


def test_separate_local_agent_sessions_keep_workspace_state_separate(
    tmp_path: Path,
) -> None:
    roots = [tmp_path / "alpha", tmp_path / "beta"]
    for root, canary in zip(roots, ("ALPHA_PRIVATE_CANARY", "BETA_PRIVATE_CANARY"), strict=True):
        root.mkdir()
        (root / "secret.txt").write_text(canary, encoding="utf-8")
    fake = FakeOpenAI(
        replies=[
            "Thought: read alpha\nAction: read_file\nAction Input: secret.txt",
            "Thought: done\nFinal Answer: alpha complete",
            "Thought: read beta\nAction: read_file\nAction Input: secret.txt",
            "Thought: done\nFinal Answer: beta complete",
            "Thought: done\nFinal Answer: alpha follow-up",
        ]
    )
    alpha = ReActAgent(
        config=AgentConfig(verbose=False),
        client=fake.as_client(),
        printer=lambda _: None,
        workspace=Workspace.at(roots[0]),
    )
    beta = ReActAgent(
        config=AgentConfig(verbose=False),
        client=fake.as_client(),
        printer=lambda _: None,
        workspace=Workspace.at(roots[1]),
    )

    alpha.run("ALPHA_QUESTION_CANARY")
    alpha_history = [str(message["content"]) for message in alpha.history]
    alpha_trace = [step.model_dump() for step in alpha.last_trace]
    beta.run("BETA_QUESTION_CANARY")
    beta_history = [str(message["content"]) for message in beta.history]
    beta_trace = [step.model_dump() for step in beta.last_trace]
    alpha.run("ALPHA_FOLLOWUP_CANARY")
    followup_messages = str(fake.calls[4]["messages"])

    assert alpha._turn == 2
    assert beta._turn == 1
    assert "ALPHA_QUESTION_CANARY" in " ".join(alpha_history)
    assert "BETA_QUESTION_CANARY" not in " ".join(alpha_history)
    assert "ALPHA_PRIVATE_CANARY" not in " ".join(alpha_history)
    assert "BETA_PRIVATE_CANARY" not in " ".join(alpha_history)
    assert "BETA_QUESTION_CANARY" in " ".join(beta_history)
    assert "ALPHA_QUESTION_CANARY" not in " ".join(beta_history)
    assert "BETA_PRIVATE_CANARY" not in " ".join(beta_history)
    assert "ALPHA_PRIVATE_CANARY" not in " ".join(beta_history)
    assert "ALPHA_PRIVATE_CANARY" in str(alpha_trace)
    assert "BETA_PRIVATE_CANARY" not in str(alpha_trace)
    assert "BETA_PRIVATE_CANARY" in str(beta_trace)
    assert "ALPHA_PRIVATE_CANARY" not in str(beta_trace)
    assert "ALPHA_QUESTION_CANARY" in followup_messages
    assert "BETA_QUESTION_CANARY" not in followup_messages
    assert "ALPHA_PRIVATE_CANARY" not in followup_messages
    assert "BETA_PRIVATE_CANARY" not in followup_messages

    alpha_run_messages = str(fake.calls[:2])
    beta_run_messages = str(fake.calls[2:4])
    assert "ALPHA_PRIVATE_CANARY" in alpha_run_messages
    assert "BETA_PRIVATE_CANARY" not in alpha_run_messages
    assert "BETA_PRIVATE_CANARY" in beta_run_messages
    assert "ALPHA_PRIVATE_CANARY" not in beta_run_messages


def test_separate_local_sessions_can_run_concurrently_without_leaks(
    tmp_path: Path,
) -> None:
    roots = [tmp_path / "alpha", tmp_path / "beta"]
    for root, canary in zip(roots, ("ALPHA_PRIVATE_CANARY", "BETA_PRIVATE_CANARY"), strict=True):
        root.mkdir()
        (root / "secret.txt").write_text(canary, encoding="utf-8")
    barrier = Barrier(2)

    def synchronize() -> None:
        barrier.wait(timeout=10)

    fakes = [
        FakeOpenAI(
            replies=[
                "Thought: read file\nAction: read_file\nAction Input: secret.txt",
                "Thought: done\nFinal Answer: finished",
            ]
        )
        for _ in roots
    ]
    agents = [
        ReActAgent(
            config=AgentConfig(verbose=False),
            client=fake.as_client(),
            printer=lambda _: None,
            before_model_request=synchronize,
            workspace=Workspace.at(root),
        )
        for fake, root in zip(fakes, roots, strict=True)
    ]

    def execute(
        agent: ReActAgent, fake: FakeOpenAI, question: str
    ) -> tuple[list[str], list[str], int, str]:
        agent.run(question)
        history = [str(message["content"]) for message in agent.history]
        trace = [str(step.observation) for step in agent.last_trace]
        return history, trace, agent._turn, str(fake.calls)

    with ThreadPoolExecutor(max_workers=2) as executor:
        alpha = executor.submit(execute, agents[0], fakes[0], "ALPHA_QUESTION_CANARY")
        beta = executor.submit(execute, agents[1], fakes[1], "BETA_QUESTION_CANARY")
        alpha_history, alpha_trace, alpha_turn, alpha_messages = alpha.result(timeout=30)
        beta_history, beta_trace, beta_turn, beta_messages = beta.result(timeout=30)

    assert alpha_turn == beta_turn == 1
    assert "ALPHA_PRIVATE_CANARY" in " ".join(alpha_history + alpha_trace + [alpha_messages])
    assert "BETA_PRIVATE_CANARY" not in " ".join(alpha_history + alpha_trace + [alpha_messages])
    assert "BETA_PRIVATE_CANARY" in " ".join(beta_history + beta_trace + [beta_messages])
    assert "ALPHA_PRIVATE_CANARY" not in " ".join(beta_history + beta_trace + [beta_messages])


def test_concurrent_reuse_of_one_agent_session_fails_closed(tmp_path: Path) -> None:
    entered = Event()
    release = Event()

    def pause_first_request() -> None:
        entered.set()
        if not release.wait(timeout=10):
            raise TimeoutError("test did not release the first request")

    fake = FakeOpenAI(replies=["Thought: done\nFinal Answer: finished"])
    workspace = Workspace.at(tmp_path)
    agent = ReActAgent(
        config=AgentConfig(verbose=False),
        client=fake.as_client(),
        printer=lambda _: None,
        before_model_request=pause_first_request,
        workspace=workspace,
    )

    with ThreadPoolExecutor(max_workers=1) as executor:

        def first_turn() -> tuple[str, int]:
            answer = agent.run("first")
            return answer, agent._turn

        first = executor.submit(first_turn)
        assert entered.wait(timeout=10)
        with pytest.raises(AgentError, match="already has an active turn"):
            agent.run("second")
        with pytest.raises(AgentError, match="cannot reset while"):
            agent.reset()
        release.set()
        assert first.result(timeout=20) == ("finished", 1)

    assert len(fake.calls) == 1
    assert len(agent.history) == 2

    agent.reset()

    assert agent.history == []
    assert agent.last_trace == []


def test_agent_history_is_bounded_and_reset_cleans_session_state(tmp_path: Path) -> None:
    turn_count = MAX_HISTORY_TURNS + 5
    fake = FakeOpenAI(replies=["Thought: done\nFinal Answer: finished"] * turn_count)
    agent = ReActAgent(
        config=AgentConfig(verbose=False),
        client=fake.as_client(),
        printer=lambda _: None,
        workspace=Workspace.at(tmp_path),
    )

    for index in range(turn_count):
        agent.run(f"QUESTION_{index}")

    remembered = [str(message["content"]) for message in agent.history]
    assert len(remembered) == 2 * MAX_HISTORY_TURNS
    assert "QUESTION_0" not in " ".join(remembered)
    assert f"QUESTION_{turn_count - MAX_HISTORY_TURNS}" in remembered[0]
    assert f"QUESTION_{turn_count - 1}" in remembered[-2]
    assert agent._turn == turn_count

    agent.reset()

    assert agent.history == []
    assert agent.last_trace == []
