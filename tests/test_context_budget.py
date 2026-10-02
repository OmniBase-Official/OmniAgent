"""Tests for the context budget and for file_info, which exist for one reason.

Asked how many lines `tools.py` had, a 7B model on Ollama's default 4096-token
context replied "The current date and time is Friday, 2 October 2026." The file
read had filled the window, Ollama had dropped tokens from the front, and both
the format instructions and the question had gone with them.

Two defences came out of that. The agent now decides for itself what to drop,
so the system prompt never is; and a tool answers "how big is this file"
without quoting the file at all.
"""

from __future__ import annotations

import json
import logging
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest

import observability as obs
from agent import AgentConfig, ReActAgent, cap_observation
from sandbox import SandboxError, Workspace, get_workspace, set_workspace
from tests.fakes import FakeOpenAI
from tools import describe_tools, file_info, run_tool

FINAL = "Thought: done\nFinal Answer: 4"


@pytest.fixture(autouse=True)
def _clean_logging() -> Iterator[None]:
    obs.reset()
    yield
    obs.reset()


def build(fake: FakeOpenAI, **overrides: Any) -> ReActAgent:
    overrides.setdefault("retry_backoff", 0.0)
    config = AgentConfig(verbose=False, **overrides)
    return ReActAgent(config=config, client=fake.as_client(), printer=lambda _: None)


def sent(fake: FakeOpenAI, call: int = 0) -> list[dict[str, Any]]:
    return list(fake.calls[call]["messages"])


# --------------------------------------------------------------------------- #
# the budget
# --------------------------------------------------------------------------- #


def test_a_small_conversation_is_sent_untouched() -> None:
    fake = FakeOpenAI(replies=[FINAL])
    build(fake).run("What is 2 + 2?")

    contents = [str(m["content"]) for m in sent(fake)]
    assert contents[1] == "What is 2 + 2?"
    assert not any("omitted" in c for c in contents)


def test_the_system_prompt_survives_a_conversation_that_does_not_fit() -> None:
    """The thing Ollama would have dropped first is the thing we must keep."""
    huge = "x" * 40_000
    fake = FakeOpenAI(
        replies=[
            "Thought: read it\nAction: calculate\nAction Input: 2 + 2",
            FINAL,
        ]
    )
    agent = build(fake, context_window=2048)
    agent.history.append({"role": "user", "content": huge})
    agent.history.append({"role": "assistant", "content": huge})

    agent.run("What is 2 + 2?")

    messages = sent(fake)
    assert messages[0]["role"] == "system"
    assert "OmniAgent" in str(messages[0]["content"])
    assert "Thought:" in str(messages[0]["content"])


def test_the_question_and_the_latest_exchange_survive() -> None:
    huge = "y" * 40_000
    fake = FakeOpenAI(
        replies=["Thought: a\nAction: calculate\nAction Input: 2 + 2", FINAL]
    )
    agent = build(fake, context_window=2048)
    agent.history.append({"role": "user", "content": huge})
    agent.history.append({"role": "assistant", "content": huge})

    agent.run("What is 2 + 2?")

    last_two = [str(m["content"]) for m in sent(fake, 1)[-2:]]
    assert any("2 + 2 = 4" in c for c in last_two)
    assert not any("omitted" in c for c in last_two)


def test_earlier_turns_go_before_anything_else() -> None:
    """An earlier turn is the least relevant thing in the request, so it goes first."""
    huge = "z" * 40_000
    fake = FakeOpenAI(replies=[FINAL])
    agent = build(fake, context_window=2048)
    agent.history.append({"role": "user", "content": huge})
    agent.history.append({"role": "assistant", "content": huge})

    agent.run("What is 2 + 2?")

    contents = [str(m["content"]) for m in sent(fake)]
    assert huge not in contents
    # Nothing had to be elided or clipped: dropping the old turn was enough.
    assert not any("omitted" in c or "clipped" in c for c in contents)
    assert contents[-1] == "What is 2 + 2?"


def test_this_turn_s_older_observations_are_elided_next() -> None:
    """With no history to drop, the OLDEST tool output is what gives way.

    Asserted precisely: the old bulk is replaced by the marker while the newest
    observation arrives whole. A looser "something was trimmed" assertion passed
    even with the elision step disabled, because clipping the newest message
    also satisfied it -- which is the opposite of the intended behaviour.
    """
    long_answer = "9" * 30_000
    fake = FakeOpenAI(
        replies=[
            "Thought: a\nAction: calculate\nAction Input: " + long_answer,
            "Thought: b\nAction: calculate\nAction Input: 2 + 2",
            FINAL,
        ]
    )
    agent = build(fake, context_window=2048)

    agent.run("What is 2 + 2?")

    contents = [str(m["content"]) for m in sent(fake, 2)]
    assert contents[0].startswith("You are OmniAgent")
    assert contents[1] == "What is 2 + 2?"
    assert long_answer not in "".join(contents), "the old bulk should be gone"
    assert any("omitted" in c for c in contents[2:-1]), "the old output should be elided"
    assert contents[-1] == "Observation: 2 + 2 = 4", "the newest output must arrive whole"


def test_the_question_survives_being_surrounded_by_bulk() -> None:
    """Eliding must start after the question, never on it."""
    long_answer = "7" * 30_000
    question = "What is 2 + 2, and please be precise about it?"
    fake = FakeOpenAI(
        replies=[
            "Thought: a\nAction: calculate\nAction Input: " + long_answer,
            "Thought: b\nAction: calculate\nAction Input: 2 + 2",
            FINAL,
        ]
    )
    agent = build(fake, context_window=2048)

    agent.run(question)

    contents = [str(m["content"]) for m in sent(fake, 2)]
    assert question in contents, "the question itself was trimmed away"


def test_the_newest_message_is_clipped_only_as_a_last_resort() -> None:
    """A question too big for the window on its own still gets sent, clipped."""
    fake = FakeOpenAI(replies=[FINAL])
    agent = build(fake, context_window=1024)

    agent.run("x" * 30_000)

    contents = [str(m["content"]) for m in sent(fake)]
    assert contents[0].startswith("You are OmniAgent")
    assert contents[-1].endswith("[clipped to fit the context window]")
    assert len(contents[-1]) < 30_000


def test_trimming_is_logged_with_the_numbers(tmp_path: Path) -> None:
    log = tmp_path / "log.jsonl"
    obs.configure(level=logging.DEBUG, log_file=log, session_id="s1")

    fake = FakeOpenAI(replies=[FINAL])
    agent = build(fake, context_window=2048)
    agent.history.append({"role": "user", "content": "q" * 40_000})
    agent.history.append({"role": "assistant", "content": "a" * 40_000})
    agent.run("What is 2 + 2?")

    for handler in obs.get_logger().handlers:
        handler.flush()
    records = [json.loads(line) for line in log.read_text(encoding="utf-8").splitlines()]
    trims = [r for r in records if r["event"] == "agent.context.trimmed"]

    assert trims
    assert trims[0]["level"] == "WARNING"
    assert trims[0]["estimated_tokens_after"] < trims[0]["estimated_tokens_before"]
    assert trims[0]["context_window"] == 2048


def test_the_budget_leaves_room_for_the_reply() -> None:
    """Sized so only the reserve forces the trim.

    The prompt is about 1,800 tokens: under a 2,048 window on its own, over the
    1,536 that remains once 512 are held back for the reply. If the reserve were
    ignored this would be sent untouched, so the clip is the evidence.
    """
    fake = FakeOpenAI(replies=[FINAL])
    agent = build(fake, context_window=2048, reply_reserve=512)

    agent.run("x" * 7_000)

    contents = [str(m["content"]) for m in sent(fake)]
    assert contents[-1].endswith("[clipped to fit the context window]")
    estimate = sum(len(c) // 4 + 4 for c in contents)
    assert estimate <= 2048 - 512


# --------------------------------------------------------------------------- #
# file_info
# --------------------------------------------------------------------------- #


@pytest.fixture
def workspace(tmp_path: Path) -> Iterator[Workspace]:
    root = tmp_path / "work"
    root.mkdir()
    (root / "three.txt").write_text("alpha\nbeta\ngamma\n", encoding="utf-8")
    (root / "empty.txt").write_text("", encoding="utf-8")
    (root / "blob.dat").write_bytes(b"\x00\x01binary\x00")
    (root / "sub").mkdir()

    installed = Workspace.at(root)
    original = get_workspace()
    set_workspace(installed)
    yield installed
    set_workspace(original)


def test_file_info_reports_lines_and_bytes(workspace: Workspace) -> None:
    result = file_info("three.txt")

    assert result.startswith("three.txt: 3 lines, ")
    assert "bytes" in result
    assert "first line: alpha" in result
    assert "last line : gamma" in result


def test_file_info_does_not_return_the_contents(workspace: Workspace) -> None:
    """The whole point: the middle of the file never reaches the model."""
    (workspace.root / "secretish.txt").write_text(
        "first\nMIDDLE_MARKER\nlast\n", encoding="utf-8"
    )

    result = file_info("secretish.txt")

    assert "MIDDLE_MARKER" not in result
    assert "3 lines" in result


def test_file_info_works_on_a_file_too_large_to_read(workspace: Workspace) -> None:
    """read_file refuses over 100 KB; counting lines must still work."""
    big = workspace.root / "big.txt"
    big.write_text("line\n" * 40_000, encoding="utf-8")

    assert run_tool("read_file", "big.txt").startswith("Error:")
    assert "40,000 lines" in file_info("big.txt")


def test_file_info_reports_an_empty_file(workspace: Workspace) -> None:
    assert "0 lines" in file_info("empty.txt")
    assert "empty" in file_info("empty.txt")


def test_file_info_says_when_a_file_is_binary(workspace: Workspace) -> None:
    result = file_info("blob.dat")

    assert "binary" in result
    assert "lines" not in result


def test_file_info_refuses_a_directory(workspace: Workspace) -> None:
    assert file_info("sub").startswith("Error:")
    assert "list_directory" in file_info("sub")


def test_file_info_reports_a_missing_file(workspace: Workspace) -> None:
    assert file_info("nope.txt").startswith("Error: no such file")


@pytest.mark.parametrize("escape", ["../outside", "/etc/passwd", ".env"])
def test_file_info_obeys_the_sandbox(workspace: Workspace, escape: str) -> None:
    assert file_info(escape).startswith("Error:")


def test_file_info_is_reachable_by_name(workspace: Workspace) -> None:
    assert run_tool("file_info", "three.txt").startswith("three.txt: 3 lines,")


def test_the_prompt_tells_the_model_when_to_prefer_file_info() -> None:
    """A tool the model does not reach for is a tool that does not exist."""
    rendered = describe_tools()

    assert "file_info(path: str)" in rendered
    assert "WITHOUT returning the file" in rendered
    assert "not read_file" in rendered


def test_describe_refuses_what_read_text_refuses(workspace: Workspace) -> None:
    with pytest.raises(SandboxError):
        workspace.describe("../outside/secret.txt")


# --------------------------------------------------------------------------- #
# one observation among many
# --------------------------------------------------------------------------- #


def test_one_tool_observation_cannot_dominate_the_prompt(
    workspace: Workspace, tmp_path: Path
) -> None:
    """The trimmer watches the total; this is about one message's share of it.

    Asked for a line count, the fine-tune read the whole 257-line file instead
    of asking for its metadata. That observation took 71% of a 5,091-token
    prompt without coming anywhere near the 16,384-token window, so the budget
    never objected -- and the model then continued the file's text instead of
    the format: an empty reply, a Thought lifted from the file's own docstring,
    and a call to get_current_time that nobody had asked for. The date reached
    the final answer.
    """
    body = "\n".join(f"line {number}" for number in range(1, 801))
    (tmp_path / "work" / "big.py").write_text(body, encoding="utf-8")
    fake = FakeOpenAI(
        replies=["Thought: read it\nAction: read_file\nAction Input: big.py", FINAL]
    )

    build(fake, context_window=16384).run("How many lines does big.py have?")

    messages = [str(message["content"]) for message in sent(fake, 1)]
    observations = [text for text in messages if text.startswith("Observation:")]
    assert len(observations) == 1
    share = len(observations[0]) / sum(len(text) for text in messages)
    assert share < 0.5, f"one observation took {share:.0%} of the prompt"


def test_a_short_observation_is_left_alone() -> None:
    text = "tools.py: 689 lines, 23,949 bytes"
    assert cap_observation(text, 600) == text


def test_a_capped_observation_keeps_its_head() -> None:
    """A tool's summary line is the first line, and is usually the answer."""
    body = "\n".join(f"{number:>5}  line {number}" for number in range(1, 401))
    capped = cap_observation(f"big.py (400 lines, 5,000 bytes):\n{body}", 60)

    assert capped.startswith("big.py (400 lines, 5,000 bytes):")
    assert "line 400" not in capped


def test_a_capped_observation_says_it_was_capped() -> None:
    body = "\n".join(f"line {number}" for number in range(1, 101))
    capped = cap_observation(body, 20)

    assert "the rest of this output was not shown" in capped
    assert capped.count("[observation capped") == 1


def test_the_cap_note_carries_no_number_of_its_own() -> None:
    """A counting question must not be answerable from the note.

    Capped, read_file's output began "sandbox.py (257 lines, 10,988 bytes):"
    and ended "[observation capped: 34 of 258 lines shown]". Asked how many
    lines the file had, the model had 34, 257 and 258 in front of it and two of
    those three were put there by this function -- at the tail, which is where
    a small model attends hardest. The log keeps the full observation, so the
    counts are not lost; they are only kept out of the prompt.
    """
    body = "\n".join(f"line {number}" for number in range(1, 401))
    capped = cap_observation(f"big.py (400 lines, 5,000 bytes):\n{body}", 60)

    note = capped[capped.index("[observation capped") :]
    assert not any(character.isdigit() for character in note), note


def test_a_single_unbroken_line_is_capped_too() -> None:
    """A minified file gives the line-based cut nothing to work with."""
    capped = cap_observation("x" * 40_000, 50)

    assert len(capped) < 1_000
    assert "the rest of this output was not shown" in capped


def test_the_cap_is_configurable() -> None:
    body = "\n".join(f"line {number}" for number in range(1, 401))
    assert len(cap_observation(body, 500)) > len(cap_observation(body, 100))


def test_the_console_trace_shows_what_the_model_was_given(
    workspace: Workspace, tmp_path: Path
) -> None:
    """The trace is for reading the model's reasoning, not the file's contents.

    Rehearsing the demo, one read_file scrolled 257 numbered lines past the
    screen while the model was shown only the first 35. A trace that disagrees
    with the prompt is worse than a short one: the log keeps the whole
    observation, so nothing is lost by printing what was actually sent.
    """
    body = "\n".join(f"line {number}" for number in range(1, 801))
    (tmp_path / "work" / "big.py").write_text(body, encoding="utf-8")
    printed: list[str] = []
    fake = FakeOpenAI(
        replies=["Thought: read it\nAction: read_file\nAction Input: big.py", FINAL]
    )
    agent = ReActAgent(
        config=AgentConfig(verbose=True, retry_backoff=0.0),
        client=fake.as_client(),
        printer=printed.append,
    )

    agent.run("How many lines does big.py have?")

    trace = "\n".join(printed)
    assert "line 1\n" in trace, "the head of the file should still be shown"
    assert "line 800" not in trace, "the whole file reached the console"
    assert "the rest of this output was not shown" in trace
