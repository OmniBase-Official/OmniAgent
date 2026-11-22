"""Runner for the first pass against the real local model.

Not the contract's cohort and not an instrument: it measures a handful of
questions that are in no bank, one process per question, so a number can be
reproduced from this file. It is deliberately not a record layer -- brief 12's
is absent from the canonical line and porting it is a separate decision.

Usage (the measured tree is a *different* directory from this runner, so the
agent can never read the runner and the measured commit is exactly the tree)::

    python scripts/first_measurement.py --project <tree> --out <dir> --passes 10

Each run writes its own file and a finished file is never run again, so a
session that dies mid-run resumes instead of restarting. Raw outputs hold the
model's replies; keep ``--out`` outside the repository.
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
import time
from dataclasses import dataclass
from pathlib import Path

MODEL = "omniagent-v2:latest"
MAX_STEPS = 8
TIMEOUT_SECONDS = 600
DONE_MARKER = "--- EXIT "

_STEP = re.compile(r"^\s*\[step \d+\]\s*$", re.MULTILINE)
_ACTION = re.compile(r"^\s*Action\s*:\s*(\S+)\s*$", re.MULTILINE)
_OBSERVATION = re.compile(r"^\s*Observation\s*:\s*(.*)$", re.MULTILINE)
_ANSWER_PREFIX = re.compile(r"^OmniAgent:[ \t]?", re.MULTILINE)


@dataclass(frozen=True)
class Trace:
    steps: int
    tools: list[str]
    tool_errors: int


def answer_region(output: str) -> str:
    """The text the agent answered with: what follows the last ``OmniAgent:``.

    Everything above it -- the banner, the endpoint, the workspace path, the
    trace -- is the program talking, not the model, and must never be graded.
    The first measurement graded the whole output and the endpoint line's
    ``127.0.0.1`` satisfied an expectation of ``12``.
    """
    matches = list(_ANSWER_PREFIX.finditer(output))
    if not matches:
        return ""
    return output[matches[-1].end() :].split(DONE_MARKER, maxsplit=1)[0].strip()


def parse_trace(output: str) -> Trace:
    """Steps, tool names in order, and how many observations were errors."""
    return Trace(
        steps=len(_STEP.findall(output)),
        tools=_ACTION.findall(output),
        tool_errors=sum(o.startswith("Error:") for o in _OBSERVATION.findall(output)),
    )


def grade(answer: str, expected: str | None) -> bool | None:
    """True when the answer contains the expectation as a whole token.

    A bare substring is not enough: ``12`` is inside ``120`` and inside
    ``3.12``. ``None`` means the question has no expectation (abstention).
    """
    if expected is None:
        return None
    pattern = rf"(?<![\w.]){re.escape(expected)}(?![\w]|\.\d)"
    return re.search(pattern, answer, re.IGNORECASE) is not None


def _lines(project: Path, relative: str) -> str:
    return str(len((project / relative).read_text(encoding="utf-8").splitlines()))


def _questions(project: Path) -> list[tuple[str, str, str | None, str | None]]:
    """(id, text, expectation derived from the tree, tool it calls for)."""
    first = (project / "requirements.txt").read_text(encoding="utf-8").splitlines()[0].strip()
    scripts = len([p for p in (project / "scripts").iterdir() if p.suffix == ".py"])
    return [
        ("q1-arith", "What is 23 multiplied by 17, plus 44?", str(23 * 17 + 44), "calculate"),
        (
            "q2-lines",
            "How many lines does config.py have?",
            _lines(project, "config.py"),
            "file_info",
        ),
        ("q3-firstline", "What is the first line of requirements.txt?", first, "file_info"),
        (
            "q4-count",
            "How many Python files are in the scripts directory?",
            str(scripts),
            "list_directory",
        ),
        ("q5-abstain", "What is the current share price of Anthropic?", None, None),
        (
            "q6-pm-wording",
            "How many .py files are directly inside the scripts directory?",
            str(scripts),
            "list_directory",
        ),
    ]


def _git(project: Path, *arguments: str) -> str:
    done = subprocess.run(  # noqa: S603 - fixed argv, no shell
        ["git", "-C", str(project), *arguments],  # noqa: S607
        capture_output=True,
        text=True,
        check=True,
        timeout=15,
    )
    return done.stdout.strip()


def _revision(project: Path) -> tuple[str, bool]:
    return _git(project, "rev-parse", "--short", "HEAD"), not _git(project, "status", "--porcelain")


def _banks_overlap(project: Path, texts: list[str]) -> list[str]:
    """Question texts that appear in a bank. Importing a bank must not fail."""
    sys.path.insert(0, str(project))
    sys.path.insert(0, str(project / "scripts"))
    import collect_dataset
    import grounding_cohort
    import holdout_eval
    import session_eval

    banked = {
        " ".join(t.split()).casefold()
        for t in [
            *(q.text for s in holdout_eval.SESSIONS_UNDER_TEST for q in s),
            *(q.text for q in session_eval.WALK),
            *(q for s in collect_dataset.SESSIONS for q in s),
            *(t.prompt for t in grounding_cohort.TASKS),
        ]
    }
    return [t for t in texts if " ".join(t.split()).casefold() in banked]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project", type=Path, required=True, help="tree to measure")
    parser.add_argument("--out", type=Path, required=True, help="directory for raw outputs")
    parser.add_argument("--passes", type=int, default=1)
    args = parser.parse_args(argv)
    project, out = args.project.resolve(), args.out.resolve()
    out.mkdir(parents=True, exist_ok=True)

    questions = _questions(project)
    overlap = _banks_overlap(project, [q[1] for q in questions])
    print("bank overlap:", overlap or "none")
    if overlap:
        print("ABORT: nothing was run")
        return 2

    before = _revision(project)
    print("revision before:", before)
    rows: list[dict[str, object]] = []
    for number in range(1, args.passes + 1):
        for qid, text, expected, wants in questions:
            path = out / f"p{number:02d}-{qid}.txt"
            cached = path.exists() and DONE_MARKER in path.read_text(encoding="utf-8")
            if cached:
                blob = path.read_text(encoding="utf-8")
                seconds = float("nan")
            else:
                started = time.perf_counter()
                try:
                    done = subprocess.run(  # noqa: S603 - fixed argv, no shell
                        [sys.executable, "main.py", "--ask", text, "--model", MODEL,
                         "--max-steps", str(MAX_STEPS), "--verbose"],
                        capture_output=True,
                        text=True,
                        cwd=project,
                        timeout=TIMEOUT_SECONDS,
                        check=False,
                    )
                    code, body = str(done.returncode), done.stdout + "\n--STDERR--\n" + done.stderr
                except subprocess.TimeoutExpired:
                    code, body = "TIMEOUT", ""
                seconds = round(time.perf_counter() - started, 1)
                blob = f"{body}\n{DONE_MARKER}{code} ---\n"
                path.write_text(blob, encoding="utf-8")
            trace = parse_trace(blob)
            answer = answer_region(blob)
            rows.append(
                {
                    "pass": number,
                    "id": qid,
                    "seconds": seconds,
                    "steps": trace.steps,
                    "tools": trace.tools,
                    "tool_errors": trace.tool_errors,
                    "blank": answer == "",
                    "correct": grade(answer, expected),
                    "wants_tool": wants,
                    "used_wanted_tool": (wants in trace.tools) if wants else None,
                }
            )
            if not cached:
                # One row per executed run, written as it happens so a dead session loses
                # nothing, with the commit and tree state read *at this run* rather than once.
                commit, clean = _revision(project)
                rows[-1]["commit"] = commit
                rows[-1]["tree_clean"] = clean
                with (out / "runs.jsonl").open("a", encoding="utf-8") as handle:
                    handle.write(json.dumps(rows[-1]) + chr(10))
            print(json.dumps(rows[-1]), flush=True)

    after = _revision(project)
    print("revision after:", after, "VOID" if before != after or not after[1] else "held")
    (out / "summary.json").write_text(
        json.dumps({"before": before, "after": after, "rows": rows}, indent=1), encoding="utf-8"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
