"""Tests for the log-to-SFT exporter.

The exporter decides what becomes training data, so most of these are about
what it *refuses*: a turn where the model broke format, a record whose text was
truncated, a conversation whose system prompt was never logged.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from export_dataset import (
    DatasetError,
    build_examples,
    collect_turns,
    expand_paths,
    main,
    read_records,
    validate,
)
from observability import TRUNCATION_MARKER

SYSTEM = "You are OmniAgent. Use the tools."
CALL = "Thought: maths\nAction: calculate\nAction Input: 2 + 2"
DONE = "Thought: done\nFinal Answer: It is 4."


def record(event: str, **fields: Any) -> dict[str, Any]:
    base: dict[str, Any] = {"event": event, "session_id": "s1", "level": "INFO"}
    base.update(fields)
    return base


def created(system_prompt: str = SYSTEM, session_id: str = "s1") -> dict[str, Any]:
    return record("agent.created", session_id=session_id, system_prompt=system_prompt)


def clean_turn(
    turn: int = 1,
    question: str = "What is 2 + 2?",
    answer: str = "It is 4.",
    session_id: str = "s1",
) -> list[dict[str, Any]]:
    """One question, one tool call, one answer."""
    return [
        record("agent.turn.start", turn=turn, session_id=session_id, question=question),
        record("agent.llm.response", turn=turn, session_id=session_id, step=1, reply=CALL),
        record(
            "agent.tool.result",
            turn=turn,
            session_id=session_id,
            step=1,
            tool="calculate",
            ok=True,
            observation="2 + 2 = 4",
        ),
        record(
            "agent.llm.response",
            turn=turn,
            session_id=session_id,
            step=2,
            reply=f"Thought: done\nFinal Answer: {answer}",
        ),
        record("agent.turn.end", turn=turn, session_id=session_id, answer=answer),
    ]


def _tool_result(records: list[dict[str, Any]]) -> dict[str, Any]:
    """The one agent.tool.result record, found by name rather than by index."""
    return next(r for r in records if r["event"] == "agent.tool.result")


def export(records: list[dict[str, Any]], **kwargs: Any) -> tuple[list[Any], Any]:
    turns, prompts = collect_turns(records)
    return build_examples(turns, prompts, **kwargs)


# --------------------------------------------------------------------------- #
# rebuilding a conversation
# --------------------------------------------------------------------------- #


def test_a_clean_turn_becomes_one_example() -> None:
    examples, stats = export([created(), *clean_turn()])

    assert stats.exported == 1
    messages = examples[0]["messages"]
    assert [m["role"] for m in messages] == ["system", "user", "assistant", "user", "assistant"]
    assert messages[0]["content"] == SYSTEM
    assert messages[1]["content"] == "What is 2 + 2?"
    assert messages[2]["content"] == CALL
    assert messages[3]["content"] == "Observation: 2 + 2 = 4"
    assert messages[4]["content"].startswith("Thought: done")


def test_the_observation_prefix_is_restored() -> None:
    """The log stores the bare observation; the conversation had the prefix."""
    examples, _ = export([created(), *clean_turn()])
    assert examples[0]["messages"][3]["content"] == "Observation: 2 + 2 = 4"


def test_a_later_turn_carries_the_earlier_question_and_answer() -> None:
    records = [
        created(),
        *clean_turn(turn=1, question="first?", answer="one"),
        *clean_turn(turn=2, question="second?", answer="two"),
    ]
    examples, stats = export(records)

    assert stats.exported == 2
    second = examples[1]["messages"]
    assert [m["role"] for m in second][:5] == [
        "system",
        "user",
        "assistant",
        "user",
        "assistant",
    ]
    assert second[1]["content"] == "first?"
    assert second[2]["content"] == "one"
    assert second[3]["content"] == "second?"


def test_sessions_do_not_share_history() -> None:
    records = [
        created(session_id="s1"),
        created(session_id="s2"),
        *clean_turn(turn=1, question="in s1", answer="a1", session_id="s1"),
        *clean_turn(turn=1, question="in s2", answer="a2", session_id="s2"),
    ]
    examples, _ = export(records)

    for example in examples:
        assert len(example["messages"]) == 5, "no history should have leaked in"


def test_each_session_uses_its_own_system_prompt() -> None:
    records = [
        created(system_prompt="prompt A", session_id="s1"),
        created(system_prompt="prompt B", session_id="s2"),
        *clean_turn(session_id="s1"),
        *clean_turn(session_id="s2", question="other?", answer="other"),
    ]
    examples, _ = export(records)

    assert {e["messages"][0]["content"] for e in examples} == {"prompt A", "prompt B"}


# --------------------------------------------------------------------------- #
# what must never become training data
# --------------------------------------------------------------------------- #


@pytest.mark.parametrize(
    "event",
    ["agent.format.violation", "agent.loop.repeated_action", "agent.budget.exhausted"],
)
def test_turns_with_unreplayable_messages_are_dropped(event: str) -> None:
    """These turns contain a message the log does not record verbatim."""
    records = [created(), *clean_turn(), record(event, turn=1)]
    examples, stats = export(records)

    assert examples == []
    assert stats.exported == 0
    assert any("unreconstructible" in reason for reason in stats.skipped)


def test_a_turn_with_no_system_prompt_is_dropped() -> None:
    examples, stats = export(clean_turn())

    assert examples == []
    assert stats.skipped["no system prompt logged"] == 1


def test_a_turn_with_no_final_answer_is_dropped() -> None:
    records = [created(), *clean_turn()[:-1]]
    examples, stats = export(records)

    assert examples == []
    assert stats.skipped["no final answer"] == 1


@pytest.mark.parametrize("field", ["question", "reply", "observation", "answer"])
def test_a_truncated_field_disqualifies_the_turn(field: str) -> None:
    """A shortened prompt or reply would be corrupt training data."""
    records = [created(), *clean_turn()]
    for item in records:
        if field in item:
            item[field] = f"text{TRUNCATION_MARKER}, 9999 chars)"

    examples, stats = export(records)
    assert examples == []
    assert stats.skipped["truncated field"] == 1


def test_a_truncated_system_prompt_disqualifies_the_turn() -> None:
    records = [created(system_prompt=f"You are{TRUNCATION_MARKER}, 9999 chars)"), *clean_turn()]
    examples, _ = export(records)
    assert examples == []


def test_a_failed_tool_call_is_dropped_by_default() -> None:
    records = [created(), *clean_turn()]
    _tool_result(records)["ok"] = False
    examples, stats = export(records)

    assert examples == []
    assert stats.skipped["tool error"] == 1


def test_a_failed_tool_call_can_be_kept_on_purpose() -> None:
    records = [created(), *clean_turn()]
    _tool_result(records)["ok"] = False
    examples, stats = export(records, include_tool_errors=True)

    assert stats.exported == 1
    assert len(examples) == 1


def test_the_same_question_in_a_later_turn_is_not_a_duplicate() -> None:
    """Turn 2 carries turn 1 in its history, so the conversations differ."""
    records = [created(), *clean_turn(turn=1), *clean_turn(turn=2)]
    _, stats = export(records)

    assert stats.exported == 2
    assert stats.skipped["duplicate"] == 0


def test_an_identical_conversation_is_exported_once() -> None:
    """Two sessions that went exactly the same way are one training example."""
    records = [
        created(session_id="s1"),
        created(session_id="s2"),
        *clean_turn(session_id="s1"),
        *clean_turn(session_id="s2"),
    ]
    _, stats = export(records)

    assert stats.exported == 1
    assert stats.skipped["duplicate"] == 1


def test_min_steps_filters_trivial_turns() -> None:
    records = [created(), *clean_turn()]
    _, stats = export(records, min_steps=5)
    assert stats.skipped["fewer than 5 steps"] == 1


def test_a_dropped_turn_still_counts_as_history() -> None:
    """Turn 2 must see turn 1's Q/A even though turn 1 was not exported."""
    records = [
        created(),
        *clean_turn(turn=1, question="first?", answer="one"),
        record("agent.format.violation", turn=1),
        *clean_turn(turn=2, question="second?", answer="two"),
    ]
    examples, stats = export(records)

    assert stats.exported == 1
    assert examples[0]["messages"][1]["content"] == "first?"


# --------------------------------------------------------------------------- #
# validation
# --------------------------------------------------------------------------- #


def test_a_turn_that_rebuilds_into_an_invalid_example_is_dropped() -> None:
    """The validator has to be wired in, not merely unit-tested.

    This log ends on a tool result -- a run cut short after the observation was
    written -- so the rebuilt conversation would end on a user turn.
    """
    records = [
        created(),
        record("agent.turn.start", turn=1, question="What is 2 + 2?"),
        record("agent.llm.response", turn=1, step=1, reply=CALL),
        record(
            "agent.tool.result", turn=1, step=1, tool="calculate", ok=True,
            observation="2 + 2 = 4",
        ),
        record("agent.turn.end", turn=1, answer="It is 4."),
    ]
    examples, stats = export(records)

    assert examples == []
    assert stats.skipped["invalid: does not end with an assistant turn"] == 1


def test_validate_accepts_a_well_formed_example() -> None:
    assert (
        validate(
            [
                {"role": "system", "content": SYSTEM},
                {"role": "user", "content": "q"},
                {"role": "assistant", "content": "a"},
            ]
        )
        is None
    )


@pytest.mark.parametrize(
    ("messages", "expected"),
    [
        ([{"role": "system", "content": SYSTEM}], "too few messages"),
        (
            [
                {"role": "user", "content": "q"},
                {"role": "assistant", "content": "a"},
                {"role": "user", "content": "b"},
            ],
            "missing system prompt",
        ),
        (
            [
                {"role": "system", "content": SYSTEM},
                {"role": "user", "content": "q"},
                {"role": "assistant", "content": "a"},
                {"role": "assistant", "content": "a2"},
            ],
            "roles do not alternate",
        ),
        (
            [
                {"role": "system", "content": SYSTEM},
                {"role": "user", "content": "q"},
                {"role": "assistant", "content": "a"},
                {"role": "user", "content": "obs"},
            ],
            "does not end with an assistant turn",
        ),
        (
            [
                {"role": "system", "content": SYSTEM},
                {"role": "user", "content": "   "},
                {"role": "assistant", "content": "a"},
            ],
            "empty message",
        ),
    ],
)
def test_validate_rejects_malformed_examples(
    messages: list[dict[str, str]], expected: str
) -> None:
    assert validate(messages) == expected


# --------------------------------------------------------------------------- #
# reading logs
# --------------------------------------------------------------------------- #


def test_malformed_lines_are_skipped_not_fatal(tmp_path: Path) -> None:
    """A log still being written often ends mid-line."""
    log = tmp_path / "log.jsonl"
    log.write_text(
        json.dumps(created())
        + "\n\n"
        + "not json at all\n"
        + json.dumps({"no": "event key"})
        + "\n"
        + json.dumps(clean_turn()[0])
        + "\n"
        + '{"event": "agent.turn.end", "tru',
        encoding="utf-8",
    )

    records = list(read_records([log]))
    assert [r["event"] for r in records] == ["agent.created", "agent.turn.start"]


def test_expand_paths_resolves_a_glob(tmp_path: Path) -> None:
    (tmp_path / "a.jsonl").write_text("", encoding="utf-8")
    (tmp_path / "b.jsonl").write_text("", encoding="utf-8")
    (tmp_path / "c.txt").write_text("", encoding="utf-8")

    found = expand_paths([str(tmp_path / "*.jsonl")])
    assert [p.name for p in found] == ["a.jsonl", "b.jsonl"]


def test_expand_paths_reports_a_missing_file(tmp_path: Path) -> None:
    with pytest.raises(DatasetError, match="no such log file"):
        expand_paths([str(tmp_path / "nope.jsonl")])


# --------------------------------------------------------------------------- #
# the CLI
# --------------------------------------------------------------------------- #


def write_log(path: Path, records: list[dict[str, Any]]) -> Path:
    path.write_text(
        "\n".join(json.dumps(item) for item in records) + "\n", encoding="utf-8"
    )
    return path


def test_the_cli_writes_a_jsonl_dataset(tmp_path: Path) -> None:
    log = write_log(tmp_path / "log.jsonl", [created(), *clean_turn()])
    out = tmp_path / "out" / "dataset.jsonl"

    assert main([str(log), "-o", str(out)]) == 0

    lines = out.read_text(encoding="utf-8").strip().splitlines()
    assert len(lines) == 1
    assert json.loads(lines[0])["messages"][0]["role"] == "system"


def test_the_cli_dry_run_writes_nothing(tmp_path: Path) -> None:
    log = write_log(tmp_path / "log.jsonl", [created(), *clean_turn()])
    out = tmp_path / "dataset.jsonl"

    assert main([str(log), "-o", str(out), "--dry-run"]) == 0
    assert not out.exists()


def test_the_cli_fails_when_there_is_nothing_to_export(tmp_path: Path) -> None:
    log = write_log(tmp_path / "log.jsonl", clean_turn())
    out = tmp_path / "dataset.jsonl"

    assert main([str(log), "-o", str(out)]) == 1
    assert not out.exists()


def test_the_cli_reports_a_missing_log(tmp_path: Path) -> None:
    assert main([str(tmp_path / "missing.jsonl")]) == 1


def test_stats_name_the_tools_that_were_used(tmp_path: Path) -> None:
    _, stats = export([created(), *clean_turn()])
    rendered = stats.render()

    assert "exported   : 1" in rendered
    assert "calculate: 1" in rendered
