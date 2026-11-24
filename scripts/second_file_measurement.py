"""Second-file runner: does the ``read_file`` next-call sentence work beyond config.py?

Not the contract's cohort and not an instrument. Two trees (a parent commit and a child
commit, both *different* directories from this runner), one question per file, arms
interleaved in one server session so session drift lands on both. The spend is on
more FILES, not more passes: at temperature 0 one file gives one answer and one tool
sequence in ten passes, so ten passes of one file are one observation.

Per row it records whether the oversize error was *reached* (the text under test), the
first call's input (a malformed ``"<path> 1"`` never reaches it), whether ``file_info``
was called, and whether the answer matches the line count taken from git. Rows hold no
question and no reply; raw outputs go in ``--out``, outside git.

    python scripts/second_file_measurement.py --parent <tree> --child <tree> --out <dir> \
        --files a.py,b.py --wording "How many lines does {file} have?" --passes 2

``--probe`` runs each file for ONE step in the parent tree and prints only the first
call's input; it scores nothing and writes no rows (use it to pick a wording).
"""

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
import time
from pathlib import Path

import first_measurement as fm

TOO_LONG = re.compile(r"^\s*Observation\s*:\s*Error:.*too long to return in full", re.MULTILINE)
_FIRST_INPUT = re.compile(r"^\s*Action Input\s*:[ \t]*(.*)$", re.MULTILINE)
_NUMBER = re.compile(r"\d[\d,]*")


def first_input(output: str) -> str | None:
    """The input of the model's first tool call, exactly as printed (None if no call)."""
    match = _FIRST_INPUT.search(output)
    return None if match is None else match.group(1).strip()


def reached_oversize(output: str) -> bool:
    """True when a tool observation was the oversize error (the text under test)."""
    return TOO_LONG.search(output) is not None


def answer_numbers(answer: str) -> list[str]:
    return [n.replace(",", "").strip() for n in _NUMBER.findall(answer) if n.replace(",", "")]


def lines_in_commit(tree: Path, relative: str) -> int:
    """True line count of ``relative`` at the tree's HEAD, from git, not from the model."""
    done = subprocess.run(  # noqa: S603 - fixed argv, no shell
        ["git", "-C", str(tree), "show", f"HEAD:{relative}"],  # noqa: S607
        capture_output=True,
        check=True,
        timeout=15,
    )
    return len(done.stdout.decode("utf-8").splitlines())


def expectations(parent: Path, child: Path, files: list[str]) -> dict[str, str]:
    """File -> expected line count, refusing a file that differs between the commits."""
    result: dict[str, str] = {}
    for name in files:
        a, b = lines_in_commit(parent, name), lines_in_commit(child, name)
        if a != b:
            raise SystemExit(f"{name} has {a} lines at the parent and {b} at the child")
        result[name] = str(a)
    return result


def arm_order(number: int, index: int) -> tuple[str, str]:
    """Alternate which arm runs first, by pass and by file, so neither is always second."""
    return ("parent", "child") if (number + index) % 2 == 1 else ("child", "parent")


def slug(name: str) -> str:
    return re.sub(r"[^A-Za-z0-9]+", "-", name).strip("-")


def _run(tree: Path, text: str, steps: int, temperature_args: list[str]) -> tuple[str, str]:
    env = {**os.environ, "PYTHONDONTWRITEBYTECODE": "1"}
    try:
        done = subprocess.run(  # noqa: S603 - fixed argv, no shell
            [sys.executable, "-B", "main.py", "--ask", text, "--model", fm.MODEL,
             "--max-steps", str(steps), "--verbose", *temperature_args],
            capture_output=True,
            text=True,
            cwd=tree,
            timeout=fm.TIMEOUT_SECONDS,
            check=False,
            env=env,
        )
        return str(done.returncode), f"{done.stdout}\n{fm.STDERR_MARKER}\n{done.stderr}"
    except subprocess.TimeoutExpired:
        return "TIMEOUT", ""


def _root_names(tree: Path) -> list[str]:
    return sorted(p.name for p in tree.iterdir() if p.name != ".git")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--parent", type=Path, required=True)
    parser.add_argument("--child", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--files", required=True, help="comma-separated paths inside the trees")
    parser.add_argument("--wording", required=True, help="question template containing {file}")
    parser.add_argument("--passes", type=int, default=1)
    parser.add_argument("--temperature", type=float, default=0.0)
    parser.add_argument("--probe", action="store_true")
    args = parser.parse_args(argv)
    if "{file}" not in args.wording:
        parser.error("--wording must contain {file}")
    parent, child, out = args.parent.resolve(), args.child.resolve(), args.out.resolve()
    files = [f.strip() for f in args.files.split(",") if f.strip()]
    out.mkdir(parents=True, exist_ok=True)
    temperature_args = ["--temperature", f"{args.temperature:g}"]

    questions = {f: args.wording.format(file=f) for f in files}
    overlap = fm._banks_overlap(parent, list(questions.values()))
    print("bank overlap:", overlap or "none")
    if overlap:
        print("ABORT: nothing was run")
        return 2

    if args.probe:
        for name, text in questions.items():
            _, blob = _run(parent, text, 1, temperature_args)
            print(json.dumps({"file": name, "first_input": first_input(blob)}), flush=True)
        return 0

    expected = expectations(parent, child, files)
    arms = {"parent": parent, "child": child}
    for arm, tree in arms.items():
        if fm._revision(tree)[1] is not True:
            print(f"ABORT: {arm} tree is not clean")
            return 3
    if _root_names(parent) != _root_names(child):
        print("ABORT: the two trees have different root listings:", _root_names(parent), _root_names(child))
        return 4
    for number in range(1, args.passes + 1):
        for index, name in enumerate(files):
            for arm in arm_order(number, index):
                tree = arms[arm]
                path = out / arm / f"p{number:02d}-{slug(name)}.txt"
                path.parent.mkdir(parents=True, exist_ok=True)
                if path.exists() and fm.DONE_MARKER in path.read_text(encoding="utf-8"):
                    continue
                started = time.perf_counter()
                code, body = _run(tree, questions[name], fm.MAX_STEPS, temperature_args)
                seconds = round(time.perf_counter() - started, 1)
                blob = f"{body}\n{fm.DONE_MARKER}{code} ---\n"
                path.write_text(blob, encoding="utf-8")
                commit, clean = fm._revision(tree)
                trace, answer = fm.parse_trace(blob), fm.answer_region(blob)
                row = {
                    "arm": arm, "commit": commit, "tree_clean": clean, "pass": number,
                    "file": name, "seconds": seconds, "temperature": args.temperature,
                    "exit_code": fm.exit_code(blob), "steps": trace.steps, "tools": trace.tools,
                    "first_input": first_input(blob), "reached": reached_oversize(blob),
                    "file_info_called": "file_info" in trace.tools, "blank": answer == "",
                    "answer_numbers": answer_numbers(answer), "expected": expected[name],
                    "correct": fm.grade(answer, expected[name]),
                }
                with (out / "runs.jsonl").open("a", encoding="utf-8") as handle:
                    handle.write(json.dumps(row) + chr(10))
                print(json.dumps(row), flush=True)
    print("root listings equal after:", _root_names(parent) == _root_names(child))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
