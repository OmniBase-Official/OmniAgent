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

Usage:

    .venv/Scripts/python.exe scripts/session_eval.py omniagent > data/session-<tag>.txt 2>&1
"""

from __future__ import annotations

import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING

PROJECT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT))
sys.path.insert(0, str(PROJECT / "scripts"))

from collect_dataset import SESSIONS
from eval_scoring import Question, Score, Verdict, header, judge, row

import observability as obs
from agent import AgentConfig, AgentError, ReActAgent
from sandbox import Workspace, set_workspace

if TYPE_CHECKING:
    from openai import OpenAI


#: One session, mixed on purpose. Every question is already in holdout_eval's
#: bank, so the isolated pass should reproduce figures we have measured before
#: and the shared pass can be read against them. The topics alternate -- maths,
#: a file, maths, a directory -- because the drift that broke the rehearsal was
#: the agent carrying the previous topic into the next question.
WALK: tuple[Question, ...] = (
    Question("What is 15% of 2480, and then that result multiplied by 3?", "1116"),
    Question("How many lines does tests/fakes.py have?", None, "file_info"),
    Question("What is 7 factorial divided by 5 factorial?", "42"),
    Question("Where is the word 'budget' used in agent.py?", None, "search_text"),
    Question("What is 2 to the power of 11, minus 48?", "2000"),
    Question("What is inside the data directory?", None, "list_directory"),
    Question("How many minutes are in 3 days and 7 hours?", "4740"),
    Question("What is the weather in Bangkok right now?", None, None, unanswerable=True),
)

TRAINED = {question for session in SESSIONS for question in session}
_leaked = [question.text for question in WALK if question.text in TRAINED]
if _leaked:
    raise SystemExit(f"not held out, these are in the training bank: {_leaked}")


@dataclass
class Outcome:
    """One pass over the walk: the tally, and each question's verdict in order."""

    score: Score
    verdicts: list[Verdict]


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


def main(model: str) -> None:
    obs.reset()
    obs.configure(level="ERROR")
    set_workspace(Workspace.at(PROJECT))

    print(f"\n{'=' * 78}\n{model}: a fresh agent for every question\n{'=' * 78}", flush=True)
    isolated = run_walk(model, shared_history=False)

    print(f"\n{'=' * 78}\n{model}: one agent for the whole walk\n{'=' * 78}", flush=True)
    shared = run_walk(model, shared_history=True)

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


if __name__ == "__main__":
    try:
        (_model,) = sys.argv[1:]
    except ValueError:
        raise SystemExit(
            "usage: session_eval.py <model>   (one model per run: the 4 GB card)"
        ) from None
    main(_model)
