"""Tests for the held-out question bank's expectations.

Every question in it carried ``prefer_tool`` and no ``expect`` until
2026-10-06, so the ``correct`` column in the figures quoted for holdout_eval
only ever covered the arithmetic, while the file questions read as though
their answers had passed. These assertions pin the shape of the fix.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

from eval_scoring import judge
from holdout_eval import SESSIONS_UNDER_TEST, _last_line, _lines

#: The comparisons whose answer is the name of the longer file.
COMPARISONS = (
    "Which has more lines, tests/test_config.py or tests/test_sandbox.py?",
    "Which of the two is longer?",
)

COMPARISON_FILES = (
    ("tests/test_config.py", "tests/test_sandbox.py"),
    ("tests/fakes.py", "scripts/build_notebook.py"),
)

QUESTIONS = [question for session in SESSIONS_UNDER_TEST for question in session]


def test_no_question_is_scored_on_tool_choice_alone() -> None:
    unchecked = [q.text for q in QUESTIONS if q.expect is None and not q.unanswerable]

    assert unchecked == []


def test_each_comparison_expectation_is_computed_from_the_longer_file() -> None:
    by_text = {question.text: question for question in QUESTIONS}

    for text, (first, second) in zip(COMPARISONS, COMPARISON_FILES, strict=True):
        longer = max((first, second), key=lambda path: int(_lines(path)))
        assert by_text[text].expect == longer


def test_a_reversed_comparison_answer_still_grades_correct() -> None:
    """Record the known false-positive mode of substring scoring."""
    question = next(q for q in QUESTIONS if q.text == COMPARISONS[0])
    assert question.expect is not None
    loser = next(path for path in COMPARISON_FILES[0] if path != question.expect)

    verdict = judge(question, f"{loser} is longer than {question.expect}", ["file_info"])

    assert verdict.checkable
    assert verdict.correct


def test_a_line_count_is_read_from_the_tree_not_written_down() -> None:
    """So editing a file cannot make the score fall for a reason that is not the model."""
    assert _lines("tests/fakes.py") == str(
        len((Path(__file__).resolve().parent / "fakes.py").read_text(encoding="utf-8").splitlines())
    )


def test_the_last_line_expectation_is_the_file_s_actual_last_line() -> None:
    expected = _last_line("scripts/build_notebook.py")

    assert expected
    assert "\n" not in expected
    assert expected == expected.strip()


def test_every_expectation_is_a_plain_substring() -> None:
    """judge() does a substring match, so an expectation with a comma in it
    can never be met -- commas are stripped from the answer, not from it."""
    assert not any("," in (q.expect or "") for q in QUESTIONS)
