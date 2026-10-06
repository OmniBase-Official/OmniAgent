"""Drive the agent through a bank of questions to build up training data.

The dataset exporter can only work with runs that happened, and four runs is
not a training set. This walks a bank of questions against a real local model,
logging every step, so an evening of unattended running turns into something
worth fine-tuning on.

Sessions matter. A session is a list of questions asked of one agent instance,
so a multi-question session produces a conversation with history -- which is
what teaches the model to use what it already knows instead of re-deriving it.

Usage::

    python scripts/collect_dataset.py --model qwen2.5-coder:7b
    python scripts/collect_dataset.py --limit 5 --dry-run
    python scripts/collect_dataset.py --resume          # top up an existing log

Then::

    python export_dataset.py "data/collect.jsonl" -o data/dataset.jsonl --stats
    python validate_dataset.py data/dataset.jsonl
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import observability as obs
from agent import AgentError, ReActAgent, model_is_installed
from config import resolve
from sandbox import Workspace, set_workspace

#: Each entry is one session: the questions are asked of a single agent, in
#: order, so later ones can refer back to earlier answers.
SESSIONS: list[list[str]] = [
    # -- calculate, on its own ------------------------------------------- #
    ["What is 15% of 2400?"],
    ["What is 23% of 1800 plus the square root of 324?"],
    ["What is (1250 * 0.07) + 12?"],
    ["What is 2 to the power of 16?"],
    ["What is the square root of 1764?"],
    ["What is 17 divided by 4, and what is the remainder?"],
    ["What is 8 factorial?"],
    ["What is the natural logarithm of 1000?"],
    ["What is 144 divided by 12, then multiplied by 7?"],
    ["What is the area of a circle with radius 7? Use pi."],
    ["If something costs 1890 baht and there is a 12% discount, what do I pay?"],
    ["A restaurant bill is 2460 baht. What is a 10% tip, and what is the total?"],
    ["What is the largest of 384, 1092 and 756?"],
    ["What is 1 kilometre in miles, if one mile is 1.609 kilometres?"],
    ["Round 3.14159265 to four decimal places."],
    ["What is 45 degrees in radians?"],
    ["What percentage of 850 is 204?"],
    ["I have 7 boxes with 23 items each. How many items is that?"],
    ["What is 1000000 divided by 7, to the nearest whole number?"],
    ["What is the sum of 15% of 800 and 25% of 600?"],
    # -- get_current_time, on its own ------------------------------------ #
    ["What day of the week is it today?"],
    ["What is today's date?"],
    ["What time is it right now?"],
    ["Is it morning or afternoon right now?"],
    ["What is the current UTC time?"],
    # -- the file tools --------------------------------------------------- #
    ["What files are in this project?"],
    ["How many lines does requirements.txt have?"],
    ["What does the first line of README.md say?"],
    ["Is there a file called pyproject.toml here? What is in it?"],
    ["What is in the tests directory?"],
    ["Find where the word 'Observation' is mentioned in tools.py."],
    ["Search this project for the text 'ReAct' and tell me which files mention it."],
    ["Which file defines the calculate tool?"],
    ["How many Python files are in the top level of this project?"],
    ["What dependencies does this project have?"],
    # -- more than one tool in one question -------------------------------- #
    ["What is 15% of 2400 plus the square root of 169? Also, what day is it today?"],
    ["How many lines are in requirements.txt, and what is that number times 10?"],
    ["What time is it, and what is 60 times 24?"],
    ["List the files here, then tell me how many characters are in the longest filename."],
    # -- sessions with history --------------------------------------------- #
    ["What is 99 * 47?", "Now divide that by 3.", "And what is 10% of that?"],
    ["What is 2400 * 0.15?", "Add the square root of 169 to that."],
    ["What day is it today?", "How many days until the end of the week?"],
    ["How many lines does pyproject.toml have?", "What about README.md?"],
    ["What is 500 * 12?", "If that is a yearly total, what is the monthly figure?"],
    ["List the files in this project.", "Now read the smallest Python file."],
    ["What is the square root of 441?", "What is that number cubed?"],
    ["What is 7 * 8?", "Is that more or less than 15% of 400?"],
    # -- more calculate ---------------------------------------------------- #
    ["What is 64% of 275?"],
    ["What is 999 * 999?"],
    ["What is 2 to the power of 20?"],
    ["What is the square root of 10000?"],
    ["What is 12 factorial?"],
    ["What is log base 10 of 1000000?"],
    ["What is 1 divided by 3, to six decimal places?"],
    ["What is 73 modulo 9?"],
    ["What is the sum of 100, 250 and 375?"],
    ["If I split 1000 baht between 7 people, how much does each get?"],
    ["How many minutes are in 2.5 hours?"],
    ["A laptop costs 32900 baht including 7% VAT. What was the price before VAT?"],
    ["What is 30% off 4590 baht?"],
    ["What is 180 degrees in radians?"],
    ["A right triangle has sides 9 and 12. How long is the hypotenuse?"],
    ["How many seconds are in a week?"],
    ["What is 1024 times 1024 times 1024?"],
    ["What is the ceiling of 7.2 plus the floor of 7.8?"],
    ["What is the absolute value of -456?"],
    ["What is 2 percent of 2 percent of 1000000?"],
    # -- more get_current_time --------------------------------------------- #
    ["What month is it?"],
    ["What year is it?"],
    ["How many hours are left until midnight?"],
    # -- more file work, now that read_file reports its own line count ------ #
    ["How many lines does agent.py have?"],
    ["How many lines does tools.py have?"],
    ["Which file is longer, main.py or sandbox.py?"],
    ["What is in the scripts directory?"],
    ["What is in the notebooks directory?"],
    ["Read the first few lines of observability.py."],
    ["Where does sandbox.py raise SandboxError?"],
    ["Search this project for 'num_ctx'."],
    ["Which files mention QLoRA?"],
    ["Find the word 'mutation' in this project."],
    ["What does omniagent.toml contain?"],
    ["How big is export_dataset.py in bytes?"],
    ["Are there any files ending in .toml here?"],
    ["Which Python file in the top level is the largest?"],
    # -- file_info: metadata without dumping the file ----------------------- #
    ["How big is agent.py, in lines and bytes?"],
    ["What is the last line of config.py?"],
    ["Is observability.py longer than sandbox.py?"],
    ["How many lines are in each of main.py and tools.py?"],
    ["What does the first line of export_dataset.py say?"],
    ["Without reading it all, how long is README.md?"],
    # -- more than one tool ------------------------------------------------- #
    ["How many lines does config.py have, and what is that times 4?"],
    ["How many lines does validate_dataset.py have? What percent of 1000 is that?"],
    ["What time is it, and how many minutes past midnight is that?"],
    ["How many entries are in the tests directory, and what is that squared?"],
    # -- more sessions with history ----------------------------------------- #
    ["What is 256 * 4?", "Now take the square root of that.", "And multiply it by 10."],
    ["How many lines does sandbox.py have?", "And tools.py?", "Which is bigger?"],
    ["What is 12% of 8500?", "Round that to the nearest hundred."],
    ["List the scripts directory.", "Now read the smallest file in it."],
    ["What is 50 * 50?", "Subtract 500 from that.", "Now halve it."],
    ["Search for 'retry' in agent.py.", "How many matches was that?"],
    ["What is 7 cubed?", "Is that more than 300?"],
    ["How many bytes is README.md?", "How many kilobytes is that?"],
    ["What is 88 * 11?", "Add the square root of 144."],
    ["What is the full date today?", "How many months are left in the year?"],
]


def load_questions(path: Path) -> list[list[str]]:
    """Read a question bank from a file.

    One session per line: either a plain question, or a JSON array of questions
    to ask in one conversation.
    """
    sessions: list[list[str]] = []
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("["):
            parsed = json.loads(line)
            sessions.append([str(item) for item in parsed])
        else:
            sessions.append([line])
    return sessions


def already_answered(log_file: Path) -> set[str]:
    """Questions a previous run already got a final answer for."""
    if not log_file.is_file():
        return set()
    answered: set[str] = set()
    started: dict[tuple[str, int], str] = {}
    for line in log_file.read_text(encoding="utf-8").splitlines():
        try:
            record = json.loads(line)
        except json.JSONDecodeError:
            continue
        key = (str(record.get("session_id", "")), int(record.get("turn", 0) or 0))
        if record.get("event") == "agent.turn.start":
            started[key] = str(record.get("question", ""))
        elif record.get("event") == "agent.turn.end" and key in started:
            answered.add(started[key])
    return answered



def collection_workspace(root: Path, log_file: Path | None) -> Workspace:
    """The workspace a collection run may read.

    Narrower than the evaluation's seal, and deliberately so. The evaluation
    seals every file holding a held-out question or its answer, which includes
    ``omniagent.toml`` -- and a training question asks whether any ``.toml``
    files are here, so reusing that seal would change the answer to a question
    being collected.

    What collection needs is that a trajectory cannot record the model reading
    an earlier answer out of a transcript, because that trajectory becomes an
    example teaching it to search the logs. So the transcripts directory is
    listable -- 41 collected examples are a ``list_directory`` observation of
    it -- and nothing inside it opens. The active log is denied by name as
    well, since it may be written outside that directory.
    """
    denied = {log_file.resolve()} if log_file else set()
    transcripts = (log_file.parent if log_file else root / "data").resolve()
    separate = transcripts.is_dir() and transcripts != root.resolve()
    listing_only = {transcripts} if separate else set()
    return Workspace.at(
        root, denied_paths=frozenset(denied), listing_only_paths=frozenset(listing_only)
    )


def main(argv: list[str] | None = None) -> int:  # noqa: PLR0915
    parser = argparse.ArgumentParser(
        description="Run a bank of questions through the agent to collect training data."
    )
    parser.add_argument("--model", help="Ollama model tag.")
    parser.add_argument(
        "--log-file",
        type=Path,
        default=Path("data/collect.jsonl"),
        help="Where to append the structured log (default: data/collect.jsonl).",
    )
    parser.add_argument("--workspace", type=Path, help="Directory the file tools may read.")
    parser.add_argument("--questions", type=Path, help="Question bank file to use instead.")
    parser.add_argument("--limit", type=int, help="Only run this many sessions.")
    parser.add_argument(
        "--resume",
        action="store_true",
        help="Skip questions the log already has an answer for.",
    )
    parser.add_argument(
        "--dry-run", action="store_true", help="List what would be asked, run nothing."
    )
    args = parser.parse_args(argv)

    sessions = load_questions(args.questions) if args.questions else list(SESSIONS)

    settings, _ = resolve(
        {
            key: value
            for key, value in {
                "model": args.model,
                "workspace": args.workspace,
                "log_file": args.log_file,
                "verbose": False,
            }.items()
            if value is not None
        }
    )

    answered = already_answered(args.log_file) if args.resume else set()
    if answered:
        sessions = [[q for q in session if q not in answered] for session in sessions]
        sessions = [session for session in sessions if session]
        print(f"resuming: {len(answered)} question(s) already answered")

    if args.limit is not None:
        sessions = sessions[: args.limit]

    questions = sum(len(session) for session in sessions)
    print(f"{len(sessions)} session(s), {questions} question(s), model {settings.model}")

    if args.dry_run:
        for index, session in enumerate(sessions, start=1):
            for position, question in enumerate(session, start=1):
                marker = f"{index}.{position}"
                print(f"  {marker:>6}  {question}")
        return 0

    if not sessions:
        print("nothing left to ask")
        return 0

    session_id = obs.configure(level="INFO", log_file=settings.log_file)
    set_workspace(collection_workspace(settings.workspace, settings.log_file))
    print(f"logging to {settings.log_file} (session {session_id})")

    probe = ReActAgent(config=settings.agent_config(), printer=lambda _: None)
    try:
        available = probe.check_connection()
    except AgentError as exc:
        print(f"[!] {exc}", file=sys.stderr)
        return 1
    if not model_is_installed(settings.model, available):
        print(f"[!] model {settings.model!r} is not installed", file=sys.stderr)
        print(f"    installed: {', '.join(available)}", file=sys.stderr)
        return 1

    started = time.perf_counter()
    answers = failures = 0

    for index, session in enumerate(sessions, start=1):
        # Each session is its own conversation, and each new agent restarts
        # its turn counter at 1. Without a distinct session_id the exporter
        # keys them all to (session, turn 1) and merges them into one mangled
        # conversation -- which is exactly what happened the first time.
        with obs.bind(session_id=f"{session_id}-{index:03d}"):
            agent = ReActAgent(config=settings.agent_config(), printer=lambda _: None)
            for position, question in enumerate(session, start=1):
                marker = f"[{index}/{len(sessions)}.{position}]"
                print(f"{marker:>14} {question}", flush=True)
                turn_started = time.perf_counter()
                try:
                    answer = agent.run(question)
                except AgentError as exc:
                    failures += 1
                    print(f"{'':>14} !! {exc}", flush=True)
                    break
                except KeyboardInterrupt:
                    print("\ninterrupted; the log keeps everything answered so far")
                    return 130
                answers += 1
                elapsed = time.perf_counter() - turn_started
                print(f"{'':>14} -> {answer[:110]}  ({elapsed:.1f}s)", flush=True)

    elapsed = time.perf_counter() - started
    print()
    print(f"answered {answers}, failed {failures}, in {elapsed / 60:.1f} min")
    print()
    print("next:")
    print(f'  python export_dataset.py "{settings.log_file}" -o data/dataset.jsonl --stats')
    print("  python validate_dataset.py data/dataset.jsonl")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
