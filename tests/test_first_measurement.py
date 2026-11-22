"""The first-pass runner's grader must read the answer, never the banner.

The first measurement scored 4 of 4 and one of the four was wrong: the
expectation "12" matched 127.0.0.1 in the endpoint line main.py prints above
the answer. These tests hold that regression and the trace parser.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path
from typing import Any

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

import first_measurement
from first_measurement import answer_region, grade, parse_trace

BANNER = (
    "    workspace: D:\\somewhere\\tree\n"
    "    endpoint : http://127.0.0.1:11434/v1\n"
    "    model    : omniagent-v2:latest\n"
)


def _output(answer: str, trace: str = "") -> str:
    return f"{BANNER}\n{trace}\nOmniAgent: {answer}\n\n"


def test_a_wrong_answer_is_not_rescued_by_digits_in_the_banner() -> None:
    """The regression: expectation 12, answer 50, banner holding 127.0.0.1."""
    output = _output("There are 50 Python files in the scripts directory.")

    assert "12" in output, "the banner really does carry the expectation"
    assert grade(answer_region(output), "12") is False


def test_a_whole_token_in_the_banner_cannot_satisfy_an_expectation() -> None:
    """The guard the q4 case does not isolate.

    In q4 two guards agree: the answer region excludes the banner, and the
    token boundary rejects ``12`` inside ``127``. Remove either and that test
    stays green, so it cannot prove either. Here the banner carries the
    expectation as a whole token (the port), so only reading the answer region
    alone can reject it.
    """
    output = _output("There are 50 Python files in the scripts directory.")

    assert grade(output, "11434") is True, "graded whole, the banner would pass it"
    assert grade(answer_region(output), "11434") is False


def test_a_right_answer_is_still_scored_right() -> None:
    output = _output("There are 12 Python files in the scripts directory.")

    assert grade(answer_region(output), "12") is True


def test_an_expectation_inside_a_longer_number_does_not_count() -> None:
    assert grade("There are 120 files.", "12") is False
    assert grade("Version 3.12 shipped.", "12") is False


def test_an_empty_answer_is_blank_not_wrong_and_not_right() -> None:
    """exit code 0 with nothing printed after the prefix must stay visible."""
    output = f"{BANNER}\nOmniAgent: \n\n"

    assert answer_region(output) == ""
    assert grade(answer_region(output), "12") is False


def test_no_answer_prefix_at_all_yields_a_blank_region() -> None:
    assert answer_region(BANNER) == ""


def test_the_trace_yields_tool_names_steps_and_tool_errors() -> None:
    trace = (
        "\n  [step 1]\n  Thought      : look\n  Action       : list_directory\n"
        "  Action Input : scripts\n  Observation  : a.py\n"
        "\n  [step 2]\n  Action       : count_lines\n  Action Input : x\n"
        "  Observation  : Error: tool is not allowed for this task.\n"
    )

    parsed = parse_trace(_output("", trace))

    assert parsed.steps == 2
    assert parsed.tools == ["list_directory", "count_lines"]
    assert parsed.tool_errors == 1


# --------------------------------------------------------------------------- #
# main(): the wiring the unit tests above cannot see
# --------------------------------------------------------------------------- #
#
# grade() and answer_region() are right in isolation, but the fix for the
# original defect is that main() hands the *answer region* to grade(). Replacing
# that call with the whole output left the suite green, so these run main()
# against a stubbed model process.

# every expectation main() derives from the tiny tree below, as a whole token
_BANNER_TOKENS = "435 3 # dep 12"


def _tree(tmp_path: Path) -> Path:
    project = tmp_path / "tree"
    (project / "scripts").mkdir(parents=True)
    (project / "config.py").write_text("a\nb\nc\n", encoding="utf-8")  # 3 lines
    (project / "requirements.txt").write_text("# dep\nmore\n", encoding="utf-8")
    for number in range(12):  # 12 python files
        (project / "scripts" / f"s{number}.py").write_text("x\n", encoding="utf-8")
    return project


def _run_main(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    *,
    answer: str,
    revision: tuple[str, bool] = ("abc1234", True),
) -> tuple[list[dict[str, Any]], Path]:
    """Run main() with the model process stubbed; the banner carries every expectation."""
    project = _tree(tmp_path)
    out = tmp_path / "out"
    stdout = f"{BANNER}    check    : {_BANNER_TOKENS}\n\nOmniAgent: {answer}\n\n"

    def fake_run(args: list[str], **_: object) -> subprocess.CompletedProcess[str]:
        return subprocess.CompletedProcess(args, 0, stdout=stdout, stderr="")

    monkeypatch.setattr(subprocess, "run", fake_run)
    monkeypatch.setattr(first_measurement, "_banks_overlap", lambda _p, _t: [])
    monkeypatch.setattr(first_measurement, "_revision", lambda _p: revision)

    code = first_measurement.main(["--project", str(project), "--out", str(out), "--passes", "1"])

    assert code == 0
    summary = json.loads((out / "summary.json").read_text(encoding="utf-8"))
    return summary["rows"], out


def test_main_grades_the_answer_region_not_the_whole_output(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """The banner holds every expectation as a whole token; the answer line is wrong."""
    rows, _ = _run_main(monkeypatch, tmp_path, answer="Nothing useful.")

    graded = [row for row in rows if row["id"] != "q5-abstain"]
    assert len(graded) == 5
    assert [row["correct"] for row in graded] == [False] * 5
    assert next(row for row in rows if row["id"] == "q5-abstain")["correct"] is None


def test_main_still_scores_a_right_answer_right(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """The positive control: without it a grader that always says no passes the test above."""
    rows, _ = _run_main(monkeypatch, tmp_path, answer=_BANNER_TOKENS)

    graded = [row for row in rows if row["id"] != "q5-abstain"]
    assert [row["correct"] for row in graded] == [True] * 5


def test_every_executed_run_leaves_a_row_with_the_commit_and_the_tree_state(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    rows, out = _run_main(
        monkeypatch, tmp_path, answer="Nothing useful.", revision=("abc1234", False)
    )

    lines = [json.loads(line) for line in (out / "runs.jsonl").read_text("utf-8").splitlines()]
    assert len(lines) == len(rows) == 6
    assert {line["commit"] for line in lines} == {"abc1234"}
    assert {line["tree_clean"] for line in lines} == {False}


def test_a_run_row_carries_no_question_answer_or_output(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    _, out = _run_main(monkeypatch, tmp_path, answer="ANSWER-CANARY-5521")

    blob = (out / "runs.jsonl").read_text(encoding="utf-8")
    assert "ANSWER-CANARY-5521" not in blob
    assert "127.0.0.1" not in blob
    assert "multiplied" not in blob
