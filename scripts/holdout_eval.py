"""Compare models on questions none of them were trained on.

An earlier version of this scored every model 9/9, 15/15, 3/3 -- useful for
"nothing is broken", useless for "which one". So the questions are harder now,
and three things are scored separately rather than rolled into one number:

* **correct** -- the answer contains the expected value.
* **tool choice** -- did it reach for the tool the question calls for? Dumping a
  whole file to count its lines is a wrong answer that happens to be right.
* **steps** -- the same answer in fewer steps is a better answer, and on a small
  context window it is also a safer one.

Follow-up turns are counted apart from opening ones, because that is where the
models used to drop out of the ReAct format entirely.

Every question is checked against the collection bank before anything runs, so
this stays held out rather than becoming a re-run of the training data.
"""

from __future__ import annotations

import json
import subprocess
import sys
import time
from collections import defaultdict
from pathlib import Path
from typing import Any

PROJECT = Path(__file__).resolve().parent.parent
RUNS_PATH = PROJECT / "data" / "holdout-runs.jsonl"
sys.path.insert(0, str(PROJECT))
sys.path.insert(0, str(PROJECT / "scripts"))

from collect_dataset import SESSIONS
from eval_scoring import Question, Score, Verdict, header, judge, row
from eval_workspace import sealed_workspace

import observability as obs
from agent import AgentConfig, AgentError, ReActAgent
from sandbox import set_workspace


def _lines(relative: str) -> str:
    """The true line count, read from the tree rather than written down.

    A hardcoded count is wrong the moment the file is edited, and the figure
    then falls for a reason that is not the model.
    """
    return str(len((PROJECT / relative).read_text(encoding="utf-8").splitlines()))


def _longer_file(first: str, second: str) -> str:
    """Return the longer path, deriving the comparison from the current tree."""
    return max((first, second), key=lambda relative: int(_lines(relative)))


def _last_line(relative: str) -> str:
    return (PROJECT / relative).read_text(encoding="utf-8").splitlines()[-1].strip()


SEARCH_MARKER = "cedar-ember-orbit-4821"


def _search_subject(marker: str) -> str:
    """Find a fixture containing the marker without storing its name."""
    matches = [
        path
        for path in (PROJECT / "eval-fixture").iterdir()
        if path.is_file() and marker in path.read_text(encoding="utf-8")
    ]
    if not matches:
        raise RuntimeError("no search subject contains the marker")
    return sorted(matches)[0].relative_to(PROJECT).as_posix()


SEARCH_SUBJECT = _search_subject(SEARCH_MARKER)


SESSIONS_UNDER_TEST: list[list[Question]] = [
    # -- arithmetic needing more than one step ---------------------------- #
    [Question("What is 15% of 2480, and then that result multiplied by 3?", "1116")],
    [Question("What is the square root of 1089 plus 12% of 850?", "135")],
    [Question("What is 7 factorial divided by 5 factorial?", "42")],
    [Question("How many minutes are in 3 days and 7 hours?", "4740")],
    [
        Question(
            "A shirt costs 1290 baht with 15% off. What is the price after the discount?",
            "1096.5",
        )
    ],
    [Question("What is 2 to the power of 11, minus 48?", "2000")],
    # -- tool choice: metadata should not cost a whole file ---------------- #
    #
    # Expectations were added on 2026-10-06. Until then every question here
    # carried prefer_tool and no expect, so the `correct` column only ever
    # covered the arithmetic above, while these read as though their answers
    # had passed. Line counts and comparison expectations are read from the
    # tree, not written down, so file edits cannot make the score fall for a
    # reason that is not the model.
    [Question("How many lines does tests/fakes.py have?", _lines("tests/fakes.py"), "file_info")],
    [
        Question(
            "Which has more lines, tests/test_config.py or tests/test_sandbox.py?",
            _longer_file("tests/test_config.py", "tests/test_sandbox.py"),
            "file_info",
        )
    ],
    [
        Question(
            "What is the very last line of scripts/build_notebook.py?",
            _last_line("scripts/build_notebook.py"),
            "file_info",
        )
    ],
    [
        Question(
            f"Which file contains the marker {SEARCH_MARKER}?",
            SEARCH_SUBJECT,
            "search_text",
        )
    ],
    [
        Question(
            "What is the exact name of the subdirectory listed in eval-fixture?",
            "fixed-subject-marker/",
            "list_directory",
        )
    ],
    # -- a question no tool can answer ------------------------------------ #
    [Question("What is the weather in Bangkok right now?", None, None, unanswerable=True)],
    # -- follow-up chains, where the format used to collapse -------------- #
    [
        Question("What is 144 * 12?", "1728"),
        Question("Now subtract 728 from that.", "1000"),
        Question("And what is half of that?", "500"),
        Question("Finally, what is 10% of that?", "50"),
    ],
    [
        Question("How many lines does tests/fakes.py have?", _lines("tests/fakes.py"), "file_info"),
        Question(
            "And scripts/build_notebook.py?",
            _lines("scripts/build_notebook.py"),
            "file_info",
        ),
        Question(
            "Which of the two is longer?",
            _longer_file("tests/fakes.py", "scripts/build_notebook.py"),
        ),
    ],
]

TRAINED = {q for session in SESSIONS for q in session}
leaked = [q.text for s in SESSIONS_UNDER_TEST for q in s if q.text in TRAINED]
if leaked:
    raise SystemExit(f"not held out, these are in the training bank: {leaked}")


def question_record(
    index: int, verdict: Verdict, steps: int, tools_called: list[str]
) -> dict[str, int | list[str] | bool | str]:
    """Build one question's measurement without carrying text or expectations."""
    return {
        "index": index,
        "tools": list(tools_called),
        "steps": steps,
        "checkable": verdict.checkable,
        "correct": verdict.correct,
        "tool_expected": verdict.tool_expected,
        "right_tool": verdict.right_tool,
        "honest_expected": verdict.honest_expected,
        "admitted": verdict.admitted,
    }


def _short_commit() -> str:
    """Name the code version recorded in the measurement."""
    try:
        done = subprocess.run(  # noqa: S603 - fixed argv, no shell, no user input
            ["git", "-C", str(PROJECT), "rev-parse", "--short", "HEAD"],  # noqa: S607
            capture_output=True,
            text=True,
            check=True,
            timeout=10,
        )
    except (OSError, subprocess.SubprocessError):
        return "unknown"
    return done.stdout.strip() or "unknown"


def _tree_clean() -> bool | str:
    """Return True/False from Git status, or unknown if it cannot be read."""
    try:
        done = subprocess.run(  # noqa: S603 - fixed argv, no shell, no user input
            ["git", "-C", str(PROJECT), "status", "--porcelain"],  # noqa: S607
            capture_output=True,
            text=True,
            check=True,
            timeout=10,
        )
    except (OSError, subprocess.SubprocessError):
        return "unknown"
    return not bool(done.stdout.strip())


def _append_question_record(
    measurement: dict[str, int | list[str] | bool | str],
    model: str,
    version: str,
    clean: bool | str,
    path: Path = RUNS_PATH,
) -> None:
    record: dict[str, Any] = {
        **measurement,
        "commit": version,
        "model": model,
        "clean": clean,
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(record) + "\n")


def evaluate(model: str) -> Score:
    obs.reset()
    obs.configure(level="ERROR")
    set_workspace(sealed_workspace(PROJECT))
    # temperature 0: an earlier pair of runs disagreed on the honesty question,
    # so variance was being read as a difference between models.
    config = AgentConfig(
        model=model, verbose=False, max_steps=8, retry_backoff=0.5, temperature=0.0
    )
    score = Score()
    version = _short_commit()
    clean = _tree_clean()
    question_index = 0

    print(f"\n{'=' * 78}\n{model}\n{'=' * 78}", flush=True)

    for session in SESSIONS_UNDER_TEST:
        agent = ReActAgent(config=config, printer=lambda _: None)
        for position, question in enumerate(session):
            index = question_index
            question_index += 1
            follow_up = position > 0
            score.asked += 1
            score.follow_total += follow_up

            started = time.perf_counter()
            try:
                answer = agent.run(question.text)
            except AgentError as exc:
                tools_called = [s.action for s in agent.last_trace if s.action]
                verdict = judge(question, "", tools_called)
                _append_question_record(
                    question_record(index, verdict, len(agent.last_trace), tools_called),
                    model,
                    version,
                    clean,
                )
                score.errors.append(f"{question.text}: {exc}")
                print(f"  !! {question.text}\n     {exc}", flush=True)
                continue
            score.seconds += time.perf_counter() - started
            score.steps += len(agent.last_trace)

            tools_called = [s.action for s in agent.last_trace if s.action]
            used_any = bool(tools_called)
            score.tool_used += used_any
            score.follow_ok += follow_up and used_any

            verdict = judge(question, answer, tools_called)
            _append_question_record(
                question_record(index, verdict, len(agent.last_trace), tools_called),
                model,
                version,
                clean,
            )
            score.apply(verdict)
            marks = list(verdict.marks)

            prefix = "   ->" if follow_up else "     "
            print(f"{prefix} {question.text}", flush=True)
            print(f"        {answer[:120]}", flush=True)
            print(
                f"        tools={tools_called or '-'} steps={len(agent.last_trace)} "
                f"| {' | '.join(marks) or 'no check'}",
                flush=True,
            )

    return score


def _read_run_records(path: Path) -> list[dict[str, Any]]:
    if not path.is_file():
        return []
    with path.open(encoding="utf-8") as handle:
        return [json.loads(line) for line in handle if line.strip()]


def _clean_state(record: dict[str, Any]) -> str:
    value = record.get("clean")
    if value is True:
        return "clean"
    if value is False:
        return "dirty"
    return "unknown"


def _question_index(record: dict[str, Any]) -> int | str:
    try:
        return int(record["index"])
    except (KeyError, TypeError, ValueError):
        return "unknown"


def _question_sort_key(index: int | str) -> tuple[int, int, str]:
    if isinstance(index, int):
        return (0, index, "")
    return (1, 0, index)


def report(path: Path | None = None) -> None:
    """Print only clean records, keeping each code version in its own group."""
    run_path = RUNS_PATH if path is None else path
    records = _read_run_records(run_path)
    if not records:
        print(f"no runs recorded in {run_path}")
        return

    clean_count = sum(_clean_state(record) == "clean" for record in records)
    dirty_count = sum(_clean_state(record) == "dirty" for record in records)
    unknown_count = len(records) - clean_count - dirty_count
    missing_count = sum("clean" not in record for record in records)
    dropped = len(records) - clean_count
    record_word = "record" if len(records) == 1 else "records"
    if missing_count == len(records) and clean_count == dirty_count == 0:
        summary = f"{len(records)} {record_word}, {dropped} dropped, no cleanliness recorded"
    else:
        summary = (
            f"{len(records)} {record_word}, {dropped} dropped "
            f"({dirty_count} dirty, {unknown_count} unknown)"
        )
    print(summary)
    print(
        f"Cleanliness: {clean_count} clean, {dirty_count} dirty, "
        f"{unknown_count} unknown ({missing_count} missing field)."
    )

    by_commit: defaultdict[str, list[dict[str, Any]]] = defaultdict(list)
    for record in records:
        by_commit[str(record.get("commit", "unknown"))].append(record)
    group_word = "commit group" if len(by_commit) == 1 else "commit groups"
    print(f"{len(by_commit)} {group_word}; each is reported separately.")

    for version, group in sorted(by_commit.items()):
        retained = [record for record in group if _clean_state(record) == "clean"]
        group_record_word = "record" if len(group) == 1 else "records"
        print(
            f"\ncommit {version}: {len(group)} {group_record_word}, "
            f"{len(retained)} clean, "
            f"{len(group) - len(retained)} dropped"
        )
        grouped: defaultdict[int | str, list[dict[str, Any]]] = defaultdict(list)
        for record in group:
            grouped[_question_index(record)].append(record)
        for index, question_records in sorted(
            grouped.items(), key=lambda item: _question_sort_key(item[0])
        ):
            question_runs = [
                record for record in question_records if _clean_state(record) == "clean"
            ]
            if not question_runs:
                print(f"  question {index}: no surviving runs")
                continue
            _report_question(index, question_runs)

    print("Settled means every applicable verdict axis agrees across retained runs.")


def _report_question(index: int | str, records: list[dict[str, Any]]) -> None:
    axes = (
        ("answer", "correct", "checkable"),
        ("tool", "right_tool", "tool_expected"),
        ("honesty", "admitted", "honest_expected"),
    )
    cells: list[str] = []
    outcomes: list[list[bool]] = []
    for label, passed_key, expected_key in axes:
        applicable = [record for record in records if record.get(expected_key) is True]
        if not applicable:
            cells.append(f"{label}=n/a")
            continue
        values = [record.get(passed_key) is True for record in applicable]
        outcomes.append(values)
        cells.append(f"{label}={sum(values)}/{len(values)}")

    steps = [
        record["steps"]
        for record in records
        if isinstance(record.get("steps"), int) and not isinstance(record.get("steps"), bool)
    ]
    step_range = f"{min(steps)}-{max(steps)}" if steps else "n/a"
    settled = bool(outcomes) and all(len(set(values)) == 1 for values in outcomes)
    settlement = "yes" if settled else "no" if outcomes else "n/a"
    print(
        f"  question {index}: {len(records)} run(s); {'; '.join(cells)}; "
        f"steps={step_range}; settled={settlement}"
    )


def main(argv: list[str] | None = None) -> None:
    arguments = sys.argv[1:] if argv is None else argv
    if "--report" in arguments:
        if arguments != ["--report"]:
            raise SystemExit("--report cannot be combined with model names")
        report()
        return
    results = {model: evaluate(model) for model in arguments}
    print(f"\n{'=' * 78}\nSUMMARY\n{'=' * 78}")
    print(header())
    for model, score in results.items():
        print(row(model, score))


if __name__ == "__main__":
    main()
