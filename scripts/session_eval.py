"""Measure what a long conversation costs, by changing only one thing.

holdout_eval.py builds a fresh agent for each of its sessions, and its longest
session is four questions on one topic. So it cannot see the failure that
spoiled the demo rehearsal: asked what was inside the data directory, the
agent listed it correctly at step 1, then said "Now, I need to find out what
'budget' refers to" -- the previous question's topic, still in history -- and
spent eleven more steps on it. 463 tests and a 300-second evaluation both
scored that question as passing.

This runs the same held-out questions twice. Once with a fresh agent for each,
which is the arrangement holdout_eval already measures, and once through a
single agent so that history accumulates the way it does in a real session.
The questions, the model, the temperature and the order are identical in both
passes. The only variable is whether the agent remembers the earlier
questions, so any difference in the scores is what the conversation cost.

One run is not a measurement. Two runs of identical code over identical
questions at temperature 0 produced the same verdict on every question and
different behaviour getting there: one answered the weather question in 3
steps with a single search, the other took 9 steps and seven searches, and the
accumulated total moved 31 to 37. Ollama at temperature 0 is not
deterministic -- on a 4 GB card the batch split alone is enough, since floating
point addition is not associative. So every run is appended to a JSONL file
and `--report` reads them together: a question that passes three times out of
three isolated and none out of three accumulated has drifted, while 2/3
against 1/3 has not been shown to.

Usage:

    .venv/Scripts/python.exe scripts/session_eval.py omniagent > data/session-<tag>.txt 2>&1
    .venv/Scripts/python.exe scripts/session_eval.py --report
"""

from __future__ import annotations

import json
import subprocess
import sys
import time
from collections import defaultdict
from collections.abc import Iterable, Mapping
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING, Any

PROJECT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT))
sys.path.insert(0, str(PROJECT / "scripts"))

from collect_dataset import SESSIONS
from eval_scoring import Question, Score, Verdict, header, judge, row
from eval_workspace import sealed_workspace

import observability as obs
from agent import AgentConfig, AgentError, ReActAgent
from sandbox import set_workspace

if TYPE_CHECKING:
    from openai import OpenAI


#: Three of these carried no expected answer until 2026-10-06, so a third of
#: the walk was scored on tool choice alone and read as though the answers had
#: passed. They had not: the data-directory question reached for
#: list_directory in all ten runs and described the data directory in four of
#: them, answering something else in the other six.
#:
#: The expectations are taken from the answers the agent actually gave, and two
#: of them depend on the working tree: agent.py has to keep containing
#: "agent.budget.exhausted", and data/ has to keep containing collect-run.log.
#: If either stops being true the question stops being answerable and the
#: figure will fall without the agent changing.
#: One session, mixed on purpose. Every question is already in holdout_eval's
#: bank, so the isolated pass should reproduce figures we have measured before
#: and the shared pass can be read against them. The topics alternate -- maths,
#: a file, maths, a directory -- because the drift that broke the rehearsal was
#: the agent carrying the previous topic into the next question.
WALK: tuple[Question, ...] = (
    Question("What is 15% of 2480, and then that result multiplied by 3?", "1116"),
    Question("How many lines does tests/fakes.py have?", "122", "file_info"),
    Question("What is 7 factorial divided by 5 factorial?", "42"),
    Question(
        "Where is the word 'budget' used in agent.py?",
        "agent.budget.exhausted",
        "search_text",
    ),
    Question("What is 2 to the power of 11, minus 48?", "2000"),
    Question("What is inside the data directory?", "collect-run.log", "list_directory"),
    Question("How many minutes are in 3 days and 7 hours?", "4740"),
    Question("What is the weather in Bangkok right now?", None, None, unanswerable=True),
)

TRAINED = {question for session in SESSIONS for question in session}
_leaked = [question.text for question in WALK if question.text in TRAINED]
if _leaked:
    raise SystemExit(f"not held out, these are in the training bank: {_leaked}")


#: Every run appends to this, so runs can be read together rather than one at
#: a time. Under data/, which is gitignored: these are measurements of a local
#: model on one machine, not something to carry between checkouts.
RUNS_PATH = PROJECT / "data" / "session-runs.jsonl"


@dataclass
class Outcome:
    """One pass over the walk: the tally, and each question's result in order."""

    score: Score
    verdicts: list[Verdict]
    steps: list[int] = field(default_factory=list)


def run_walk(
    model: str,
    *,
    shared_history: bool,
    client: OpenAI | None = None,
    max_steps: int = 8,
) -> Outcome:
    """Ask every question in WALK once, and judge each answer.

    :param shared_history: True to reuse one agent for the whole walk, so each
        question is asked with the previous ones in history. False to build a
        fresh agent per question, which is what holdout_eval.py does.
    :param client: injected for tests, so the accumulation can be asserted
        without a model server.
    """
    config = AgentConfig(
        model=model, verbose=False, max_steps=max_steps, retry_backoff=0.5, temperature=0.0
    )
    outcome = Outcome(score=Score(), verdicts=[])

    def fresh() -> ReActAgent:
        return ReActAgent(config=config, client=client, printer=lambda _: None)

    shared = fresh() if shared_history else None

    for position, question in enumerate(WALK, start=1):
        agent = shared or fresh()
        outcome.score.asked += 1
        # Only the accumulated pass has follow-ups. In the isolated pass every
        # question is a first question, so counting them would report a figure
        # for something that did not happen.
        if shared_history:
            outcome.score.follow_total += position > 1

        started = time.perf_counter()
        try:
            answer = agent.run(question.text)
        except AgentError as exc:
            outcome.score.errors.append(f"{question.text}: {exc}")
            outcome.verdicts.append(Verdict(marks=("CRASHED",)))
            outcome.steps.append(0)
            print(f"  !! {position}. {question.text}\n     {exc}", flush=True)
            continue
        outcome.score.seconds += time.perf_counter() - started
        outcome.score.steps += len(agent.last_trace)

        tools_called = [step.action for step in agent.last_trace if step.action]
        outcome.score.tool_used += bool(tools_called)
        if shared_history:
            outcome.score.follow_ok += (position > 1) and bool(tools_called)

        verdict = judge(question, answer, tools_called)
        outcome.score.apply(verdict)
        outcome.verdicts.append(verdict)
        outcome.steps.append(len(agent.last_trace))

        print(f"  {position}. {question.text}", flush=True)
        print(f"     {answer[:110]}", flush=True)
        print(
            f"     tools={tools_called or '-'} steps={len(agent.last_trace)} "
            f"| {' | '.join(verdict.marks) or 'no check'}",
            flush=True,
        )

    return outcome


def _passed(verdict: Verdict) -> bool:
    """Whether a question's own checks were all met.

    A question with nothing to check counts as passing: it contributes to no
    denominator, so it cannot be the thing that moved.
    """
    return (
        (verdict.correct or not verdict.checkable)
        and (verdict.right_tool or not verdict.tool_expected)
        and (verdict.admitted or not verdict.honest_expected)
    )


def drift(isolated: Outcome, shared: Outcome) -> list[tuple[int, Question, str]]:
    """Questions whose result changed when history was allowed to accumulate.

    Reported in both directions. A question that only passes with history is
    not a win to bank -- it is the same instability as a question that only
    passes without it, and a single run cannot tell either from noise.
    """
    moved = []
    for position, (question, before, after) in enumerate(
        zip(WALK, isolated.verdicts, shared.verdicts, strict=True), start=1
    ):
        was, now = _passed(before), _passed(after)
        if was and not now:
            moved.append((position, question, "LOST with history"))
        elif now and not was:
            moved.append((position, question, "GAINED with history"))
    return moved


@dataclass(frozen=True)
class Spread:
    """One question in one arrangement, across however many runs there are."""

    passed: int
    runs: int
    steps_low: int
    steps_high: int

    @property
    def settled(self) -> bool:
        """True when every run agreed. Anything else is not yet a result."""
        return self.passed in (0, self.runs)


def commit() -> str:
    """The code a run came from, so runs of different code are not pooled.

    Without it the file mixed three runs of yesterday's agent with one of
    today's and reported a single figure over both, which is not a
    measurement of either.
    """
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


def record(outcome: Outcome, model: str, arrangement: str, path: Path = RUNS_PATH) -> None:
    """Append one pass, so that later runs can be read alongside it."""
    path.parent.mkdir(parents=True, exist_ok=True)
    row = {
        "model": model,
        "commit": commit(),
        "arrangement": arrangement,
        "questions": [question.text for question in WALK],
        "passed": [_passed(verdict) for verdict in outcome.verdicts],
        "steps": outcome.steps,
    }
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(row) + "\n")


def read_runs(path: Path = RUNS_PATH) -> list[dict[str, Any]]:
    if not path.is_file():
        return []
    with path.open(encoding="utf-8") as handle:
        return [json.loads(line) for line in handle if line.strip()]


def aggregate(runs: Iterable[Mapping[str, Any]]) -> dict[tuple[str, str], Spread]:
    """Fold every recorded run into one spread per arrangement and question.

    Keyed by the question's text rather than its position, so re-ordering the
    walk does not silently pool two different questions into one figure.
    """
    passes: defaultdict[tuple[str, str], list[bool]] = defaultdict(list)
    steps: defaultdict[tuple[str, str], list[int]] = defaultdict(list)
    for run in runs:
        for question, passed, step_count in zip(
            run["questions"], run["passed"], run["steps"], strict=True
        ):
            key = (str(run["arrangement"]), str(question))
            passes[key].append(bool(passed))
            steps[key].append(int(step_count))
    return {
        key: Spread(
            passed=sum(results),
            runs=len(results),
            steps_low=min(steps[key]),
            steps_high=max(steps[key]),
        )
        for key, results in passes.items()
    }


def report(path: Path = RUNS_PATH) -> None:
    """Print what the recorded runs do and do not establish, per code version."""
    runs = read_runs(path)
    if not runs:
        print(f"no runs recorded in {path}")
        return

    by_commit: defaultdict[str, list[Mapping[str, Any]]] = defaultdict(list)
    for run in runs:
        by_commit[str(run.get("commit", "unknown"))].append(run)

    for version, group in by_commit.items():
        _report_group(version, group)
    if len(by_commit) > 1:
        print(
            f"\n{len(by_commit)} code versions are listed separately above. Numbers from "
            "different versions are not comparable question by question, because any edit "
            "that reaches a prompt reshuffles the whole set."
        )


def _report_group(version: str, group: list[Mapping[str, Any]]) -> None:
    spreads = aggregate(group)
    runs = max(spread.runs for spread in spreads.values())
    print(f"\n{'=' * 78}\n{version}: across {runs} recorded run(s)\n{'=' * 78}")
    print(f"{'question':58} {'isolated':>10} {'accumulated':>12}")
    for question in WALK:
        before = spreads.get(("isolated", question.text))
        after = spreads.get(("accumulated", question.text))
        print(
            f"{question.text[:58]:58} "
            f"{_cell(before):>10} {_cell(after):>12}"
            + ("   <- DRIFT" if _is_drift(before, after) else "")
        )
    print("\nA question is only drifting when both arrangements settled and they disagree.")
    print("Steps in brackets are the range across runs; at temperature 0 they still move.")


def _cell(spread: Spread | None) -> str:
    if spread is None:
        return "-"
    return f"{spread.passed}/{spread.runs}[{spread.steps_low}-{spread.steps_high}]"


def _is_drift(before: Spread | None, after: Spread | None) -> bool:
    if before is None or after is None:
        return False
    if not (before.settled and after.settled):
        return False
    return (before.passed > 0) != (after.passed > 0)


def main(model: str) -> None:
    obs.reset()
    obs.configure(level="ERROR")
    set_workspace(sealed_workspace(PROJECT))

    print(f"\n{'=' * 78}\n{model}: a fresh agent for every question\n{'=' * 78}", flush=True)
    isolated = run_walk(model, shared_history=False)
    record(isolated, model, "isolated")

    print(f"\n{'=' * 78}\n{model}: one agent for the whole walk\n{'=' * 78}", flush=True)
    shared = run_walk(model, shared_history=True)
    record(shared, model, "accumulated")

    print(f"\n{'=' * 78}\nSUMMARY\n{'=' * 78}")
    print(header("arrangement"))
    print(row("isolated", isolated.score))
    print(row("accumulated", shared.score))

    moved = drift(isolated, shared)
    print(f"\nquestions that changed: {len(moved)} of {len(WALK)}")
    for position, question, direction in moved:
        print(f"  {position}. {direction}: {question.text}")
    if not moved:
        print("  none -- the conversation cost nothing on this walk")
    print("\nOne run settles nothing on its own. Read it with --report.")
    report()


if __name__ == "__main__":
    try:
        (_arg,) = sys.argv[1:]
    except ValueError:
        raise SystemExit(
            "usage: session_eval.py <model> | --report   (one model per run: the 4 GB card)"
        ) from None
    if _arg == "--report":
        report()
    else:
        main(_arg)
