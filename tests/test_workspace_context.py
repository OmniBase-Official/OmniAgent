"""Workspace selection stays local to each scoped agent execution."""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from threading import Barrier

import pytest

import main as cli
from agent import AgentConfig, ReActAgent
from sandbox import Workspace, get_workspace, set_workspace, workspace_scope
from tests.fakes import FakeOpenAI


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
