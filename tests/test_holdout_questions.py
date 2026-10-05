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

from holdout_eval import SESSIONS_UNDER_TEST, _last_line, _lines

#: The only questions scored on tool choice alone, and on purpose: a substring
#: cannot score a comparison, since "fakes.py is longer than build_notebook.py"
#: contains every word a right answer would.
COMPARISONS = (
    "Which has more lines, tests/test_config.py or tests/test_sandbox.py?",
    "Which of the two is longer?",
)

QUESTIONS = [question for session in SESSIONS_UNDER_TEST for question in session]


def test_only_the_comparisons_are_scored_on_tool_choice_alone() -> None:
    unchecked = [q.text for q in QUESTIONS if q.expect is None and not q.unanswerable]

    assert sorted(unchecked) == sorted(COMPARISONS)


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
