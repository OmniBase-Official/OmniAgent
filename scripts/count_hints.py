"""Count the stray-argument hint in the raw outputs of a second-file run (brief 39).

A hint is the text "Did you mean" in a tool observation. It SHOULD appear exactly when a
``read_file``/``file_info`` call whose input is ``<path> <int>`` or ``<path> <int> <int>``
failed as "no such file" and ``<path>`` is an existing regular file inside the tree. Anywhere
else it must not: a hint for a path the tool should not confirm would be a leak. This reads
the stored raw output of every run, so it needs no model and no change to the runner.

    python scripts/count_hints.py --out <run dir> --parent <tree> --child <tree>
"""

from __future__ import annotations

import argparse
import json
import re
from collections import defaultdict
from pathlib import Path

HINT = "Did you mean"
_STEP = re.compile(r"^\s*\[step \d+\]\s*$", re.MULTILINE)
_ACTION = re.compile(r"^\s*Action\s*:\s*(\S+)\s*$", re.MULTILINE)
_INPUT = re.compile(r"^\s*Action Input\s*:[ \t]*(.*)$", re.MULTILINE)
_OBSERVATION = re.compile(r"^\s*Observation\s*:[ \t]?(.*)", re.MULTILINE | re.DOTALL)
_STRAY = re.compile(r"(.+?)((?:[ \t]+-?[0-9]+){1,2})")


def steps(output: str) -> list[tuple[str, str, str]]:
    """(tool, input, observation) per step, from the verbose trace."""
    parts = _STEP.split(output)[1:]
    result = []
    for part in parts:
        action, given, observed = (
            _ACTION.search(part),
            _INPUT.search(part),
            _OBSERVATION.search(part),
        )
        result.append(
            (
                action.group(1) if action else "",
                given.group(1).strip() if given else "",
                observed.group(1).strip() if observed else "",
            )
        )
    return result


def candidate(given: str, tree: Path) -> str | None:
    """The path with its numeric tail removed, if that is an existing file inside ``tree``."""
    found = _STRAY.fullmatch(given.strip())
    if not found:
        return None
    target = (tree / found[1]).resolve()
    return found[1] if target.is_file() and tree.resolve() in target.parents else None


def count(output: str, tree: Path) -> dict[str, int]:
    """Hints shown, hints expected, hints shown where none was expected, expected but absent."""
    shown = expected = unexpected = missing = 0
    for tool, given, observed in steps(output):
        has = HINT in observed
        should = (
            tool in {"read_file", "file_info"}
            and observed.lstrip().startswith("Error: no such file:")
            and candidate(given, tree) is not None
        )
        shown += has
        expected += should
        unexpected += has and not should
        missing += should and not has
    return {"shown": shown, "expected": expected, "unexpected": unexpected, "missing": missing}


def _slug(name: str) -> str:
    return re.sub(r"[^A-Za-z0-9]+", "-", name).strip("-")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--parent", type=Path, required=True)
    parser.add_argument("--child", type=Path, required=True)
    args = parser.parse_args(argv)
    trees = {"parent": args.parent.resolve(), "child": args.child.resolve()}
    totals: dict[tuple[str, str], dict[str, int]] = defaultdict(
        lambda: {"shown": 0, "expected": 0, "unexpected": 0, "missing": 0}
    )
    for line in (args.out / "runs.jsonl").read_text(encoding="utf-8").splitlines():
        row = json.loads(line)
        raw = args.out / row["arm"] / f"p{row['pass']:02d}-{_slug(row['file'])}.txt"
        for key, value in count(raw.read_text(encoding="utf-8"), trees[row["arm"]]).items():
            totals[(row["file"], row["arm"])][key] += value
    for (name, arm), counts in totals.items():
        print(json.dumps({"file": name, "arm": arm, **counts}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
