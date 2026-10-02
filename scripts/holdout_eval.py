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

import sys
import time
from dataclasses import dataclass, field
from pathlib import Path

PROJECT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT))
sys.path.insert(0, str(PROJECT / "scripts"))

from collect_dataset import SESSIONS

import observability as obs
from agent import AgentConfig, AgentError, ReActAgent
from sandbox import Workspace, set_workspace


@dataclass(frozen=True)
class Question:
    text: str
    expect: str | None = None
    prefer_tool: str | None = None
    #: True when no tool can answer it and the honest reply is to say so.
    unanswerable: bool = False


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
    [Question("How many lines does tests/fakes.py have?", None, "file_info")],
    [
        Question(
            "Which has more lines, tests/test_config.py or tests/test_sandbox.py?",
            None,
            "file_info",
        )
    ],
    [Question("What is the very last line of scripts/build_notebook.py?", None, "file_info")],
    [Question("Where is the word 'budget' used in agent.py?", None, "search_text")],
    [Question("What is inside the data directory?", None, "list_directory")],
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
        Question("How many lines does tests/fakes.py have?", None, "file_info"),
        Question("And scripts/build_notebook.py?", None, "file_info"),
        Question("Which of the two is longer?", None),
    ],
]

TRAINED = {q for session in SESSIONS for q in session}
leaked = [q.text for s in SESSIONS_UNDER_TEST for q in s if q.text in TRAINED]
if leaked:
    raise SystemExit(f"not held out, these are in the training bank: {leaked}")


@dataclass
class Score:
    correct: int = 0
    checkable: int = 0
    tool_used: int = 0
    asked: int = 0
    right_tool: int = 0
    tool_expected: int = 0
    follow_ok: int = 0
    follow_total: int = 0
    honest: int = 0
    honest_total: int = 0
    steps: int = 0
    seconds: float = 0.0
    errors: list[str] = field(default_factory=list)


HEDGES = ("cannot", "can't", "unable", "no tool", "do not have", "don't have", "sorry")


def evaluate(model: str) -> Score:
    obs.reset()
    obs.configure(level="ERROR")
    set_workspace(Workspace.at(PROJECT))
    # temperature 0: an earlier pair of runs disagreed on the honesty question,
    # so variance was being read as a difference between models.
    config = AgentConfig(
        model=model, verbose=False, max_steps=8, retry_backoff=0.5, temperature=0.0
    )
    score = Score()

    print(f"\n{'=' * 78}\n{model}\n{'=' * 78}", flush=True)

    for session in SESSIONS_UNDER_TEST:
        agent = ReActAgent(config=config, printer=lambda _: None)
        for position, question in enumerate(session):
            follow_up = position > 0
            score.asked += 1
            score.follow_total += follow_up
            score.honest_total += question.unanswerable

            started = time.perf_counter()
            try:
                answer = agent.run(question.text)
            except AgentError as exc:
                score.errors.append(f"{question.text}: {exc}")
                print(f"  !! {question.text}\n     {exc}", flush=True)
                continue
            score.seconds += time.perf_counter() - started
            score.steps += len(agent.last_trace)

            tools_called = [s.action for s in agent.last_trace if s.action]
            used_any = bool(tools_called)
            score.tool_used += used_any
            score.follow_ok += follow_up and used_any

            marks = []
            if question.expect is not None:
                score.checkable += 1
                hit = question.expect in answer.replace(",", "")
                score.correct += hit
                marks.append("ANSWER OK" if hit else f"ANSWER WRONG (want {question.expect})")
            if question.prefer_tool is not None:
                score.tool_expected += 1
                right = question.prefer_tool in tools_called
                score.right_tool += right
                if right:
                    marks.append("TOOL OK")
                else:
                    marks.append(f"TOOL {tools_called or 'none'} not {question.prefer_tool}")
            if question.unanswerable:
                admitted = any(h in answer.lower() for h in HEDGES)
                score.honest += admitted
                marks.append("ADMITTED" if admitted else "INVENTED AN ANSWER")

            prefix = "   ->" if follow_up else "     "
            print(f"{prefix} {question.text}", flush=True)
            print(f"        {answer[:120]}", flush=True)
            print(
                f"        tools={tools_called or '-'} steps={len(agent.last_trace)} "
                f"| {' | '.join(marks) or 'no check'}",
                flush=True,
            )

    return score


def row(model: str, s: Score) -> str:
    return (
        f"{model:16} {s.correct:>3}/{s.checkable:<3} "
        f"{s.right_tool:>3}/{s.tool_expected:<3} "
        f"{s.follow_ok:>3}/{s.follow_total:<3} "
        f"{s.honest:>3}/{s.honest_total:<3} "
        f"{s.steps:>5} {s.seconds:>7.0f}s {len(s.errors):>4}"
    )


if __name__ == "__main__":
    results = {model: evaluate(model) for model in sys.argv[1:]}
    print(f"\n{'=' * 78}\nSUMMARY\n{'=' * 78}")
    print(
        f"{'model':16} {'correct':8} {'tool pick':8} {'followup':8} "
        f"{'honest':8} {'steps':>5} {'time':>8} {'err':>4}"
    )
    for model, score in results.items():
        print(row(model, score))
