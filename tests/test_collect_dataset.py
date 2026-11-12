"""Tests for question-bank preview and legacy dataset export behavior."""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

from collect_dataset import SESSIONS, load_questions
from collect_dataset import main as collect_main

from export_dataset import build_examples, collect_turns


def test_collection_stops_before_model_preflight_when_persistent_logs_are_disabled(
    capsys: pytest.CaptureFixture[str],
) -> None:
    with pytest.raises(SystemExit, match="2"):
        collect_main([])

    assert "requires persistent log files" in capsys.readouterr().err


def test_dry_run_still_previews_questions_without_model_preflight(
    capsys: pytest.CaptureFixture[str],
) -> None:
    assert collect_main(["--dry-run", "--limit", "1"]) == 0

    output = capsys.readouterr().out
    assert "1 session(s)" in output
    assert "What is 15% of 2400?" in output


def test_explicit_collection_log_file_is_rejected_early(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    with pytest.raises(SystemExit, match="2"):
        collect_main(["--log-file", str(tmp_path / "transcript.jsonl")])

    assert "persistent log files are disabled" in capsys.readouterr().err


def test_environment_collection_log_file_is_rejected_before_preflight(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setenv("OMNIAGENT_LOG_FILE", "transcript.jsonl")

    with pytest.raises(SystemExit, match="2"):
        collect_main(["--dry-run"])

    assert "OMNIAGENT_LOG_FILE requests a persistent log" in capsys.readouterr().err


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
# --------------------------------------------------------------------------- #


# --------------------------------------------------------------------------- #
# export session grouping behavior
# --------------------------------------------------------------------------- #


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


# --------------------------------------------------------------------------- #
# --------------------------------------------------------------------------- #
