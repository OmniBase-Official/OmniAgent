"""Disabled persistent dataset collector pending privacy approvals.

Operational logs are never dataset inputs. Persistent capture requires an
approved separate sink, explicit opt-in and field preview, plus approved
retention/deletion rules. User-workspace data is prohibited from evaluation
and training. This command currently exits before reading inputs or contacting
a model server.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sandbox import Workspace

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



def collection_workspace(root: Path, log_file: Path | None = None) -> Workspace:
    """A collection workspace that cannot expose user files or directories."""
    _ = log_file  # kept for call-site compatibility; the full root is denied
    resolved_root = root.expanduser().resolve()
    return Workspace.at(resolved_root, denied_paths=frozenset({resolved_root}))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Disabled persistent dataset capture."
    )
    parser.add_argument("--model", help="Ollama model tag.")
    parser.add_argument(
        "--log-file",
        type=Path,
        default=Path("data/collect-operational.jsonl"),
        help="Operational log path option; persistent file logging is disabled.",
    )
    parser.add_argument("--workspace", type=Path, help="Directory the file tools may read.")
    parser.add_argument("--questions", type=Path, help="Question bank file to use instead.")
    parser.add_argument("--limit", type=int, help="Only run this many sessions.")
    parser.add_argument(
        "--resume",
        action="store_true",
        help="Unavailable while persistent dataset capture is disabled.",
    )
    parser.add_argument(
        "--dry-run", action="store_true", help="List what would be asked, run nothing."
    )
    parser.add_argument(
        "--opt-in-dataset",
        action="store_true",
        help=(
            "Request dataset capture (disabled pending sink, provenance, field preview, "
            "and retention approval)."
        ),
    )
    parser.add_argument(
        "--dataset-sink",
        type=Path,
        help="Separate dataset sink path; it must never be the operational log path.",
    )
    args = parser.parse_args(argv)

    if args.resume:
        parser.error("--resume is unavailable while persistent dataset capture is disabled")
    if not args.opt_in_dataset:
        parser.error(
            "dataset capture is disabled pending approval of a separate sink, "
            "field preview, and retention/deletion policy"
        )
    if args.dataset_sink is None:
        parser.error("dataset collection requires a separate --dataset-sink path")
    if args.dataset_sink.expanduser().resolve() == args.log_file.expanduser().resolve():
        parser.error("dataset sink must be separate from the operational log")
    parser.error(
        "dataset capture is disabled pending approval of a separate sink, "
        "field preview, and retention/deletion policy"
    )


if __name__ == "__main__":
    raise SystemExit(main())
