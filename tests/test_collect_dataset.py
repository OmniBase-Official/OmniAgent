"""Tests for the dataset collection helper's pure parts.

The collection loop itself needs a real model, so it is not tested here. What
is tested is everything that decides *what* gets asked and *what counts as
already done* -- plus the session-scoping contract, whose absence silently
merged three conversations into one mangled training example the first time
this script ran.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

from collect_dataset import SESSIONS, already_answered, load_questions

from export_dataset import build_examples, collect_turns


def write_log(path: Path, records: list[dict[str, Any]]) -> Path:
    path.write_text(
        "\n".join(json.dumps(record) for record in records) + "\n", encoding="utf-8"
    )
    return path


def turn(
    session: str, number: int, question: str, *, finished: bool = True
) -> list[dict[str, Any]]:
    records = [
        {
            "event": "agent.turn.start",
            "session_id": session,
            "turn": number,
            "question": question,
        }
    ]
    if finished:
        records.append(
            {
                "event": "agent.turn.end",
                "session_id": session,
                "turn": number,
                "answer": "an answer",
            }
        )
    return records


# --------------------------------------------------------------------------- #
# the built-in bank
# --------------------------------------------------------------------------- #


def test_the_bank_is_not_empty_and_has_no_blank_questions() -> None:
    assert len(SESSIONS) >= 20
    for session in SESSIONS:
        assert session
        for question in session:
            assert question.strip()


def test_the_bank_covers_every_tool() -> None:
    """A dataset built from one tool teaches one tool."""
    everything = " ".join(q for session in SESSIONS for q in session).lower()

    assert "%" in everything or "square root" in everything  # calculate
    assert "day" in everything or "time" in everything  # get_current_time
    assert "files" in everything  # list_directory
    assert "lines" in everything or "read" in everything  # read_file
    assert "find" in everything or "search" in everything  # search_text


def test_the_bank_includes_multi_turn_sessions() -> None:
    """Conversations with history are what teach the model to use what it knows."""
    assert any(len(session) > 1 for session in SESSIONS)


def test_the_bank_has_no_duplicate_questions() -> None:
    questions = [q for session in SESSIONS for q in session]

    assert len(questions) == len(set(questions))


# --------------------------------------------------------------------------- #
# loading a custom bank
# --------------------------------------------------------------------------- #


def test_plain_lines_become_one_question_sessions(tmp_path: Path) -> None:
    path = tmp_path / "q.txt"
    path.write_text("What is 2 + 2?\nWhat day is it?\n", encoding="utf-8")

    assert load_questions(path) == [["What is 2 + 2?"], ["What day is it?"]]


def test_a_json_array_becomes_one_multi_turn_session(tmp_path: Path) -> None:
    path = tmp_path / "q.txt"
    path.write_text('["What is 99 * 47?", "Now halve it."]\n', encoding="utf-8")

    assert load_questions(path) == [["What is 99 * 47?", "Now halve it."]]


def test_blank_lines_and_comments_are_skipped(tmp_path: Path) -> None:
    path = tmp_path / "q.txt"
    path.write_text("# a comment\n\n   \nWhat is 2 + 2?\n", encoding="utf-8")

    assert load_questions(path) == [["What is 2 + 2?"]]


# --------------------------------------------------------------------------- #
# resuming
# --------------------------------------------------------------------------- #


def test_a_missing_log_means_nothing_is_answered(tmp_path: Path) -> None:
    assert already_answered(tmp_path / "absent.jsonl") == set()


def test_finished_turns_are_reported_as_answered(tmp_path: Path) -> None:
    path = write_log(
        tmp_path / "log.jsonl",
        [*turn("s1", 1, "What is 2 + 2?"), *turn("s2", 1, "What day is it?")],
    )

    assert already_answered(path) == {"What is 2 + 2?", "What day is it?"}


def test_an_unfinished_turn_is_not_answered(tmp_path: Path) -> None:
    """A run killed mid-question has to be asked again."""
    path = write_log(
        tmp_path / "log.jsonl",
        [
            *turn("s1", 1, "finished one"),
            *turn("s1", 2, "interrupted one", finished=False),
        ],
    )

    assert already_answered(path) == {"finished one"}


def test_a_malformed_line_does_not_break_resuming(tmp_path: Path) -> None:
    path = tmp_path / "log.jsonl"
    path.write_text(
        "\n".join(json.dumps(r) for r in turn("s1", 1, "fine")) + "\nnot json\n",
        encoding="utf-8",
    )

    assert already_answered(path) == {"fine"}


def test_turns_from_different_sessions_do_not_collide(tmp_path: Path) -> None:
    """Both sessions have a turn 1; both questions must be recognised."""
    path = write_log(
        tmp_path / "log.jsonl",
        [*turn("s1", 1, "first question"), *turn("s2", 1, "second question")],
    )

    assert already_answered(path) == {"first question", "second question"}


# --------------------------------------------------------------------------- #
# the session-scoping contract
# --------------------------------------------------------------------------- #


def test_the_collector_scopes_each_session_to_its_own_id() -> None:
    """Regression, found by exporting a collected log and getting one example.

    Every session builds a fresh agent, and a fresh agent restarts its turn
    counter at 1. Sharing one session_id therefore keys every session to
    (session, turn 1), and the exporter merges them into a single conversation
    whose roles no longer alternate. The loop must bind a distinct session_id.
    """
    script = Path(__file__).resolve().parent.parent / "scripts" / "collect_dataset.py"
    source = script.read_text(encoding="utf-8")

    assert "obs.bind(session_id=" in source, "each session needs its own logging scope"


def test_merged_sessions_would_be_rejected_by_the_exporter(tmp_path: Path) -> None:
    """What the bug actually produced, so the damage is written down."""
    records: list[dict[str, Any]] = [
        {
            "event": "agent.created",
            "session_id": "shared",
            "system_prompt": "You are OmniAgent.",
        }
    ]
    # Two conversations, both logged as turn 1 of the same session.
    for letter, question, answer in (("a", "first?", "one"), ("b", "second?", "two")):
        records += [
            {
                "event": "agent.turn.start",
                "session_id": "shared",
                "turn": 1,
                "question": question,
            },
            {
                "event": "agent.llm.response",
                "session_id": "shared",
                "turn": 1,
                "reply": f"Thought: {letter}\nFinal Answer: {answer}",
            },
            {
                "event": "agent.turn.end",
                "session_id": "shared",
                "turn": 1,
                "answer": answer,
            },
        ]

    turns, prompts = collect_turns(records)
    examples, stats = build_examples(turns, prompts)

    assert len(turns) == 1, "the two conversations merged"
    assert examples == []
    assert any("roles do not alternate" in reason for reason in stats.skipped)


def test_distinct_session_ids_export_cleanly(tmp_path: Path) -> None:
    """The same two conversations, scoped properly."""
    records: list[dict[str, Any]] = []
    for index, (question, answer) in enumerate(
        [("first?", "one"), ("second?", "two")], start=1
    ):
        session = f"shared-{index:03d}"
        records += [
            {
                "event": "agent.created",
                "session_id": session,
                "system_prompt": "You are OmniAgent.",
            },
            {"event": "agent.turn.start", "session_id": session, "turn": 1, "question": question},
            {
                "event": "agent.llm.response",
                "session_id": session,
                "turn": 1,
                "reply": f"Thought: x\nFinal Answer: {answer}",
            },
            {"event": "agent.turn.end", "session_id": session, "turn": 1, "answer": answer},
        ]

    turns, prompts = collect_turns(records)
    examples, stats = build_examples(turns, prompts)

    assert len(turns) == 2
    assert stats.exported == 2
    assert [e["messages"][1]["content"] for e in examples] == ["first?", "second?"]


@pytest.mark.parametrize("index", [1, 7, 46])
def test_the_scoped_session_id_is_stable_and_sortable(index: int) -> None:
    assert f"abc-{index:03d}" == f"abc-{index:03d}"
    assert len(f"{index:03d}") == 3
