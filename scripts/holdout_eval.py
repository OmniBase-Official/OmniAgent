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

import argparse
import subprocess
import sys
import time
from pathlib import Path
from uuid import uuid4

PROJECT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT))
sys.path.insert(0, str(PROJECT / "scripts"))

from collect_dataset import SESSIONS
from eval_scoring import Question, Score, header, judge, row
from eval_workspace import sealed_workspace
from promote_model import (
    PromotionEvaluationError,
    check_run,
    validate_evaluation_report_path,
    verified_run_gguf,
    verified_run_modelfile,
    write_evaluation_report,
)

import observability as obs
from agent import AgentConfig, AgentError, ReActAgent
from sandbox import set_workspace


def _lines(relative: str) -> str:
    """The true line count, read from the tree rather than written down.

    A hardcoded count is wrong the moment the file is edited, and the figure
    then falls for a reason that is not the model.
    """
    return str(len((PROJECT / relative).read_text(encoding="utf-8").splitlines()))


def _last_line(relative: str) -> str:
    return (PROJECT / relative).read_text(encoding="utf-8").splitlines()[-1].strip()


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
    # had passed. Line counts are read from the tree, not written down, so an
    # edit to a file cannot make the figure fall for a reason that is not the
    # model. The two comparison questions still carry no expectation, which is
    # deliberate: a substring cannot score a comparison.
    [Question("How many lines does tests/fakes.py have?", _lines("tests/fakes.py"), "file_info")],
    [
        Question(
            "Which has more lines, tests/test_config.py or tests/test_sandbox.py?",
            None,
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
            "Where is the word 'budget' used in agent.py?",
            "agent.budget.exhausted",
            "search_text",
        )
    ],
    [Question("What is inside the data directory?", "collect-run.log", "list_directory")],
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
        # No expectation, and not an oversight: a substring cannot score a
        # comparison. "fakes.py is longer than build_notebook.py" contains
        # every word a right answer would. Scored on tool choice only.
        Question("Which of the two is longer?", None),
    ],
]

TRAINED = {q for session in SESSIONS for q in session}
leaked = [q.text for s in SESSIONS_UNDER_TEST for q in s if q.text in TRAINED]
if leaked:
    raise SystemExit(f"not held out, these are in the training bank: {leaked}")


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

    print(f"\n{'=' * 78}\n{model}\n{'=' * 78}", flush=True)

    for session in SESSIONS_UNDER_TEST:
        agent = ReActAgent(config=config, printer=lambda _: None)
        for position, question in enumerate(session):
            follow_up = position > 0
            score.asked += 1
            score.follow_total += follow_up

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

            verdict = judge(question, answer, tools_called)
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


def evaluate_promotion_run(run: Path, report_path: Path | None = None) -> Score:
    """Evaluate this run's GGUF under a temporary tag and return its live score."""
    if report_path is not None:
        validate_evaluation_report_path(report_path, run)
    reasons = check_run(run)
    if reasons:
        raise ValueError("run did not pass promotion preflight")
    gguf_path, original_sha256, artifact_error = verified_run_gguf(run)
    if artifact_error or gguf_path is None or original_sha256 is None:
        raise ValueError("run GGUF cannot be verified")
    _, modelfile_error = verified_run_modelfile(run)
    if modelfile_error:
        raise ValueError("run Modelfile does not load its manifest GGUF")

    staging_tag = f"omniagent-eval-{uuid4().hex}"
    subprocess.run(  # noqa: S603 - fixed argv; the run path and tag are validated/generated
        ["ollama", "create", staging_tag, "-f", "Modelfile"],  # noqa: S607
        cwd=run,
        check=True,
    )
    score: Score | None = None
    evaluation_error: Exception | None = None
    try:
        score = evaluate(staging_tag)
    except Exception as exc:  # noqa: BLE001 - cleanup must run for every evaluator failure
        evaluation_error = exc

    try:
        subprocess.run(  # noqa: S603 - fixed argv with a generated temporary tag
            ["ollama", "rm", staging_tag], check=True  # noqa: S607
        )
    except Exception as exc:
        raise PromotionEvaluationError(
            "temporary evaluation tag cleanup failed; promotion is refused"
        ) from exc

    if evaluation_error is not None:
        raise PromotionEvaluationError(
            "holdout evaluation failed; promotion is refused"
        ) from evaluation_error
    if score is None:
        raise PromotionEvaluationError(
            "holdout evaluation returned no score; promotion is refused"
        )

    _, final_sha256, final_artifact_error = verified_run_gguf(run)
    if final_artifact_error or final_sha256 != original_sha256:
        raise ValueError("run GGUF changed during evaluation")
    if report_path is not None:
        write_evaluation_report(report_path, run, score)
    return score


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Evaluate holdout questions or write a sanitized evaluation report."
    )
    parser.add_argument("models", nargs="*", help="Existing Ollama model tags to evaluate.")
    parser.add_argument(
        "--promotion-run",
        type=Path,
        help="Evaluate this run's GGUF under a temporary tag for a sanitized report.",
    )
    parser.add_argument("--report", type=Path, help="Destination for sanitized report JSON.")
    args = parser.parse_args(argv)

    if args.promotion_run is not None:
        if args.models:
            parser.error(
                "--promotion-run cannot be combined with model tags"
            )
        try:
            evaluate_promotion_run(args.promotion_run, args.report)
        except PromotionEvaluationError as exc:
            print(str(exc), file=sys.stderr)
            return 1
        except (OSError, ValueError, subprocess.CalledProcessError) as exc:
            print(f"promotion evaluation failed ({type(exc).__name__})", file=sys.stderr)
            return 1
        if args.report is not None:
            print(f"wrote evaluation report to {args.report}")
        return 0

    if args.report is not None:
        parser.error("--report requires --promotion-run")
    results = {model: evaluate(model) for model in args.models}
    print(f"\n{'=' * 78}\nSUMMARY\n{'=' * 78}")
    print(header())
    for model, score in results.items():
        print(row(model, score))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
