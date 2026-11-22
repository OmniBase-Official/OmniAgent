"""An empty answer is a failure, not a success with nothing to say.

Measured on ``b164aaa`` with the real model: asked how many ``.py`` files sit
directly in ``scripts``, the model listed the directory correctly and then asked
for ``count_lines``, which is not in the registry. The agent ends such a turn with
``""`` (guard G2e, pinned in ``tests/test_tool_allowlist_guards.py``) and
``main.answer`` printed an empty ``OmniAgent:`` line and returned 0. A script
that checks the exit code was told it had an answer.

The fix is in ``main.answer`` only. ``agent.run`` and G2e are deliberately
unchanged; this file asserts on what the CLI does with the empty result.

Static: the fake client never opens a socket.
"""

from __future__ import annotations

from typing import cast

import pytest

import main
from agent import AgentConfig, ReActAgent
from tests.fakes import FakeOpenAI

#: A reply the allowlist refuses. Distinctive words, so a test can prove none of
#: them was echoed back to the user.
ASK_DISALLOWED = "Thought: zebra-ponder\nAction: read_file\nAction Input: quokka-path.toml"
FINAL = "Thought: done\nFinal Answer: finished"

MODEL_WORDS = ("zebra-ponder", "quokka-path", "read_file", "Action Input")


def build(fake: FakeOpenAI) -> ReActAgent:
    return ReActAgent(
        config=AgentConfig(verbose=False, retry_backoff=0.0),
        client=fake.as_client(),
        printer=lambda _: None,
        allowed_tools={"calculate"},
    )


class _StubAgent:
    """Returns a fixed result from ``run``; ``answer`` needs nothing else."""

    def __init__(self, result: str) -> None:
        self._result = result

    def run(self, question: str) -> str:  # noqa: ARG002
        return self._result


def stub(result: str) -> ReActAgent:
    return cast("ReActAgent", _StubAgent(result))


def test_a_disallowed_tool_request_exits_nonzero_with_a_message_and_no_model_text(
    capsys: pytest.CaptureFixture[str],
) -> None:
    """The end-to-end case: a real agent, a fake model, and the allowlist refusing."""
    fake = FakeOpenAI(replies=[ASK_DISALLOWED, FINAL])

    code = main.answer(build(fake), "How many files?")

    out = capsys.readouterr().out
    assert code != 0
    assert "[!] No answer:" in out
    for word in MODEL_WORDS:
        assert word not in out
    # The turn really ended on the refusal: the scripted Final Answer was never
    # asked for, so "finished" cannot be in the output for that reason either.
    assert len(fake.calls) == 1


@pytest.mark.parametrize("result", ["", " ", "\n", " \t\n "], ids=repr)
def test_an_empty_or_whitespace_result_is_not_an_answer(
    result: str, capsys: pytest.CaptureFixture[str]
) -> None:
    code = main.answer(stub(result), "q")

    out = capsys.readouterr().out
    assert code != 0
    assert "[!] No answer:" in out
    assert "OmniAgent:" not in out


def test_a_real_answer_still_exits_zero_and_is_printed(
    capsys: pytest.CaptureFixture[str],
) -> None:
    """The control: without it, 'always fail' would pass every test above."""
    code = main.answer(stub("4"), "q")

    out = capsys.readouterr().out
    assert code == 0
    assert "OmniAgent: 4" in out
    assert "No answer" not in out


def test_the_repl_path_reports_the_same_failure(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """``repl`` prints through ``answer``, so it inherits the fix; this proves the
    inheritance rather than assuming it."""
    typed = iter(["a question", "/quit"])
    monkeypatch.setattr("builtins.input", lambda _prompt="": next(typed))

    main.repl(stub(""))

    out = capsys.readouterr().out
    assert "[!] No answer:" in out
    assert "OmniAgent:" not in out
