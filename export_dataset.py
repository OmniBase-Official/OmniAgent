"""Turn explicitly supplied compatible trajectory files into an SFT dataset.

OmniAgent does not create persistent run transcripts under its current privacy
policy. This exporter remains available for compatible files collected through
an independently approved process and replays those records into the chat
format that TRL and transformers consume:

    {"messages": [{"role": "system", ...}, {"role": "user", ...}, ...]}

What gets left out matters as much as what goes in. Training on a turn where
the model broke format teaches it to break format, so by default only turns
that went cleanly from question to Final Answer are exported.

Usage::

    python export_dataset.py data/*.jsonl -o dataset.jsonl --stats
"""

from __future__ import annotations

import argparse
import glob
import hashlib
import json
import sys
from collections import Counter
from collections.abc import Iterable, Iterator, Sequence
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from dataset_provenance import write_sidecar
from observability import TRUNCATION_MARKER
from trajectory_utils import actions_in as _actions_in
from validate_dataset import (
    MAX_DATASET_BYTES as _MAX_DATASET_BYTES,
)
from validate_dataset import (
    MAX_DATASET_LINE_BYTES as _MAX_DATASET_LINE_BYTES,
)
from validate_dataset import (
    MAX_DATASET_LINES as _MAX_DATASET_LINES,
)
from validate_dataset import (
    MAX_JSON_NESTING as _MAX_JSON_NESTING,
)
from validate_dataset import (
    _json_nesting_is_too_deep,
)

#: Events that mean the turn contains a message the log does not record
#: verbatim -- a format correction, a rut intervention, or the forced
#: final-answer prompt. The conversation cannot be replayed faithfully, so
#: these turns are never exported, with or without --include-tool-errors.
UNRECONSTRUCTIBLE_EVENTS = frozenset(
    {
        "agent.format.violation",
        "agent.loop.repeated_action",
        "agent.budget.exhausted",
    }
)

#: Minimum messages in a usable example: system, user, assistant.
_MIN_MESSAGES = 3

#: Bounds for replaying explicit trajectory files and direct API inputs.
MAX_LOG_BYTES = _MAX_DATASET_BYTES
MAX_LOG_LINE_BYTES = _MAX_DATASET_LINE_BYTES
MAX_LOG_LINES = _MAX_DATASET_LINES
MAX_LOG_FILES = 256
MAX_LOG_RECORDS = 500_000
MAX_LOG_NESTING = _MAX_JSON_NESTING
MAX_COLLECTED_TURNS = 100_000
MAX_COLLECTED_SESSIONS = 100_000
MAX_COLLECTED_TEXT_BYTES = 64 * 1024 * 1024
MAX_LOG_TEXT_FIELD_BYTES = 4 * 1024 * 1024


class DatasetError(ValueError):
    """Raised when a log cannot be read at all."""


@dataclass
class Turn:
    """One question-to-answer turn, rebuilt from the log."""

    session_id: str
    turn: int
    question: str | None = None
    answer: str | None = None
    exchange: list[dict[str, str]] = field(default_factory=list)
    problems: set[str] = field(default_factory=set)
    tool_failed: bool = False
    truncated: bool = False

    @property
    def steps(self) -> int:
        return sum(1 for message in self.exchange if message["role"] == "assistant")


# --------------------------------------------------------------------------- #
# reading
# --------------------------------------------------------------------------- #


def expand_paths(patterns: Sequence[str]) -> list[Path]:
    """Resolve the arguments, expanding globs ourselves.

    PowerShell does not expand wildcards for native commands, so ``*.jsonl``
    would otherwise arrive as a literal string.
    """
    paths: list[Path] = []
    for pattern in patterns:
        matches: list[str] = []
        for match in glob.iglob(pattern):  # noqa: PTH207 - stop after the file cap
            matches.append(match)
            if len(paths) + len(matches) > MAX_LOG_FILES:
                raise DatasetError(f"logs exceed the {MAX_LOG_FILES}-file input limit")
        if matches:
            paths.extend(Path(match) for match in sorted(matches))
        else:
            paths.append(Path(pattern))
            if len(paths) > MAX_LOG_FILES:
                raise DatasetError(f"logs exceed the {MAX_LOG_FILES}-file input limit")

    missing = [path for path in paths if not path.is_file()]
    if missing:
        raise DatasetError(f"no such log file: {', '.join(str(p) for p in missing)}")
    if not paths:
        raise DatasetError("no log files given")
    return paths


def read_records(  # noqa: PLR0912 - one fail-closed branch per input bound
    paths: Iterable[Path],
) -> Iterator[dict[str, Any]]:
    """Yield every well-formed JSON object across the given log files.

    A half-written final line is normal for a log that is still open, so a
    malformed line is skipped rather than fatal.
    """
    total_bytes = 0
    total_lines = 0
    total_records = 0
    total_files = 0
    for path in paths:
        total_files += 1
        if total_files > MAX_LOG_FILES:
            raise DatasetError(f"logs exceed the {MAX_LOG_FILES}-file input limit")
        try:
            handle = path.open("rb")
        except OSError as exc:
            raise DatasetError(f"could not read log file {path.name}") from exc
        with handle:
            while True:
                remaining = MAX_LOG_BYTES - total_bytes
                line = handle.readline(min(MAX_LOG_LINE_BYTES + 1, remaining + 1))
                if not line:
                    break
                total_bytes += len(line)
                if total_bytes > MAX_LOG_BYTES:
                    raise DatasetError(f"logs exceed the {MAX_LOG_BYTES}-byte input limit")
                total_lines += 1
                if total_lines > MAX_LOG_LINES:
                    raise DatasetError(f"logs exceed the {MAX_LOG_LINES}-line input limit")
                if len(line) > MAX_LOG_LINE_BYTES:
                    raise DatasetError(
                        f"log line exceeds the {MAX_LOG_LINE_BYTES}-byte limit"
                    )
                stripped = line.strip()
                if not stripped:
                    continue
                try:
                    text = stripped.decode("utf-8")
                except UnicodeDecodeError as exc:
                    raise DatasetError(f"log file {path.name} is not valid UTF-8") from exc
                if _json_nesting_is_too_deep(text, max_depth=MAX_LOG_NESTING):
                    raise DatasetError(
                        f"log line exceeds the JSON nesting limit of {MAX_LOG_NESTING}"
                    )
                try:
                    record = json.loads(text)
                except json.JSONDecodeError:
                    continue
                except ValueError as exc:
                    raise DatasetError("log line contains an unsupported JSON integer") from exc
                except RecursionError as exc:
                    raise DatasetError("log line exceeds the JSON parser depth limit") from exc
                if isinstance(record, dict) and "event" in record:
                    total_records += 1
                    if total_records > MAX_LOG_RECORDS:
                        raise DatasetError(
                            f"logs exceed the {MAX_LOG_RECORDS}-record input limit"
                        )
                    yield record


# --------------------------------------------------------------------------- #
# rebuilding turns
# --------------------------------------------------------------------------- #


def _is_truncated(*values: object) -> bool:
    return any(isinstance(v, str) and TRUNCATION_MARKER in v for v in values)


def collect_turns(  # noqa: PLR0912, PLR0915 - one branch per log event and bound
    records: Iterable[dict[str, Any]],
) -> tuple[list[Turn], dict[str, str]]:
    """Group records into turns, and collect each session's system prompt."""
    turns: dict[tuple[str, int], Turn] = {}
    order: list[tuple[str, int]] = []
    prompts: dict[str, str] = {}
    record_count = 0
    retained_text_bytes = 0
    accounted_session_ids: set[str] = set()

    def bounded_text(value: str, field_name: str) -> str:
        nonlocal retained_text_bytes
        if len(value) > MAX_LOG_TEXT_FIELD_BYTES:
            raise DatasetError(
                f"{field_name} exceeds the {MAX_LOG_TEXT_FIELD_BYTES}-byte field limit"
            )
        try:
            size = len(value.encode("utf-8"))
        except UnicodeEncodeError as exc:
            raise DatasetError(f"{field_name} is not valid UTF-8 text") from exc
        if size > MAX_LOG_TEXT_FIELD_BYTES:
            raise DatasetError(
                f"{field_name} exceeds the {MAX_LOG_TEXT_FIELD_BYTES}-byte field limit"
            )
        if size > MAX_COLLECTED_TEXT_BYTES - retained_text_bytes:
            raise DatasetError(
                f"trajectory text exceeds the {MAX_COLLECTED_TEXT_BYTES}-byte aggregate limit"
            )
        retained_text_bytes += size
        return value

    for record in records:
        record_count += 1
        if record_count > MAX_LOG_RECORDS:
            raise DatasetError(f"records exceed the {MAX_LOG_RECORDS}-record input limit")
        if not isinstance(record, dict):
            raise DatasetError("trajectory records must be JSON objects")
        event = record.get("event")
        if not isinstance(event, str):
            continue
        event = bounded_text(event, "event")
        raw_session_id = record.get("session_id", "")
        session_id = str(raw_session_id)
        if len(session_id) > MAX_LOG_TEXT_FIELD_BYTES:
            raise DatasetError(
                f"session_id exceeds the {MAX_LOG_TEXT_FIELD_BYTES}-byte field limit"
            )
        try:
            session_bytes = len(session_id.encode("utf-8"))
        except UnicodeEncodeError as exc:
            raise DatasetError("session_id is not valid UTF-8 text") from exc
        if session_bytes > MAX_LOG_TEXT_FIELD_BYTES:
            raise DatasetError(
                f"session_id exceeds the {MAX_LOG_TEXT_FIELD_BYTES}-byte field limit"
            )
        if session_id not in accounted_session_ids:
            if len(accounted_session_ids) >= MAX_COLLECTED_SESSIONS:
                raise DatasetError(
                    f"logs exceed the {MAX_COLLECTED_SESSIONS}-session limit"
                )
            bounded_text(session_id, "session_id")
            accounted_session_ids.add(session_id)

        if event == "agent.created":
            prompt = record.get("system_prompt")
            if isinstance(prompt, str) and prompt:
                prompts[session_id] = bounded_text(prompt, "system_prompt")
            continue

        raw_turn = record.get("turn")
        if not isinstance(raw_turn, int) or isinstance(raw_turn, bool):
            continue
        if not -(2**63) <= raw_turn < 2**63:
            raise DatasetError("turn exceeds the signed 64-bit integer limit")

        key = (session_id, raw_turn)
        if key not in turns:
            if len(turns) >= MAX_COLLECTED_TURNS:
                raise DatasetError(f"logs exceed the {MAX_COLLECTED_TURNS}-turn limit")
            turns[key] = Turn(session_id=session_id, turn=raw_turn)
            order.append(key)
        turn = turns[key]

        if event in UNRECONSTRUCTIBLE_EVENTS:
            turn.problems.add(str(event))

        elif event == "agent.turn.start":
            question = record.get("question")
            if isinstance(question, str):
                turn.question = bounded_text(question, "question")
                turn.truncated |= _is_truncated(question)

        elif event == "agent.llm.response":
            reply = record.get("reply")
            if isinstance(reply, str) and reply:
                turn.exchange.append(
                    {"role": "assistant", "content": bounded_text(reply, "reply")}
                )
                turn.truncated |= _is_truncated(reply)

        elif event == "agent.tool.result":
            observation = record.get("observation")
            if isinstance(observation, str):
                turn.exchange.append(
                    {
                        "role": "user",
                        "content": f"Observation: {bounded_text(observation, 'observation')}",
                    }
                )
                turn.truncated |= _is_truncated(observation)
            if record.get("ok") is False:
                turn.tool_failed = True

        elif event == "agent.turn.end":
            answer = record.get("answer")
            if isinstance(answer, str):
                turn.answer = bounded_text(answer, "answer")
                turn.truncated |= _is_truncated(answer)

    return [turns[key] for key in order], prompts


def build_messages(
    turn: Turn, system_prompt: str, history: Sequence[dict[str, str]]
) -> list[dict[str, str]]:
    """Assemble the exact message list the agent sent for this turn."""
    messages: list[dict[str, str]] = [{"role": "system", "content": system_prompt}]
    messages.extend(dict(message) for message in history)
    messages.append({"role": "user", "content": turn.question or ""})
    messages.extend(dict(message) for message in turn.exchange)
    return messages


def validate(messages: Sequence[dict[str, str]]) -> str | None:
    """Return why this example is unusable, or None if it is fine."""
    if len(messages) < _MIN_MESSAGES:
        return "too few messages"
    if messages[0]["role"] != "system" or not messages[0]["content"].strip():
        return "missing system prompt"
    if messages[-1]["role"] != "assistant":
        return "does not end with an assistant turn"
    if any(not message["content"].strip() for message in messages):
        return "empty message"

    expected = "user"
    for message in messages[1:]:
        if message["role"] != expected:
            return "roles do not alternate"
        expected = "assistant" if expected == "user" else "user"
    return None


# --------------------------------------------------------------------------- #
# exporting
# --------------------------------------------------------------------------- #


@dataclass
class ExportStats:
    turns_seen: int = 0
    exported: int = 0
    skipped: Counter[str] = field(default_factory=Counter)
    tools_used: Counter[str] = field(default_factory=Counter)
    steps: Counter[int] = field(default_factory=Counter)

    def render(self) -> str:
        lines = [
            f"turns seen : {self.turns_seen}",
            f"exported   : {self.exported}",
        ]
        if self.skipped:
            lines.append("skipped    :")
            lines.extend(
                f"    {reason:28} {count}"
                for reason, count in self.skipped.most_common()
            )
        if self.steps:
            spread = ", ".join(
                f"{n} step{'s' if n != 1 else ''}: {c}" for n, c in sorted(self.steps.items())
            )
            lines.append(f"step counts: {spread}")
        if self.tools_used:
            tools = ", ".join(f"{name}: {count}" for name, count in self.tools_used.most_common())
            lines.append(f"tools      : {tools}")
        return "\n".join(lines)


def build_examples(
    turns: Sequence[Turn],
    prompts: dict[str, str],
    *,
    include_tool_errors: bool = False,
    min_steps: int = 1,
) -> tuple[list[dict[str, list[dict[str, str]]]], ExportStats]:
    """Turn rebuilt turns into validated, de-duplicated training examples."""
    stats = ExportStats()
    examples: list[dict[str, list[dict[str, str]]]] = []
    seen: set[str] = set()
    history: dict[str, list[dict[str, str]]] = {}

    for turn in turns:
        stats.turns_seen += 1
        prior = history.setdefault(turn.session_id, [])

        # The conversation continues whether or not this turn is exportable, so
        # history is extended before any skip.
        if turn.question is not None and turn.answer is not None:
            carry_on = [
                {"role": "user", "content": turn.question},
                {"role": "assistant", "content": turn.answer},
            ]
        else:
            carry_on = []

        reason = _skip_reason(
            turn, prompts, include_tool_errors=include_tool_errors, min_steps=min_steps
        )
        if reason is not None:
            stats.skipped[reason] += 1
            prior.extend(carry_on)
            continue

        messages = build_messages(turn, prompts[turn.session_id], prior)
        invalid = validate(messages)
        if invalid is not None:
            stats.skipped[f"invalid: {invalid}"] += 1
            prior.extend(carry_on)
            continue

        digest = hashlib.sha256(
            json.dumps(messages, sort_keys=True, ensure_ascii=False).encode("utf-8")
        ).hexdigest()
        if digest in seen:
            stats.skipped["duplicate"] += 1
            prior.extend(carry_on)
            continue
        seen.add(digest)

        examples.append({"messages": messages})
        stats.exported += 1
        stats.steps[turn.steps] += 1
        for message in turn.exchange:
            if message["role"] == "assistant":
                stats.tools_used.update(_actions_in(message["content"]))
        prior.extend(carry_on)

    return examples, stats


def _skip_reason(
    turn: Turn,
    prompts: dict[str, str],
    *,
    include_tool_errors: bool,
    min_steps: int,
) -> str | None:
    if turn.problems:
        return f"unreconstructible ({sorted(turn.problems)[0]})"
    if turn.session_id not in prompts:
        return "no system prompt logged"
    if turn.question is None:
        return "no question"
    if turn.answer is None:
        return "no final answer"
    # The prompt lives on the session rather than the turn, so it needs its own
    # check: a shortened system prompt is corrupt training data just the same.
    if turn.truncated or TRUNCATION_MARKER in prompts[turn.session_id]:
        return "truncated field"
    if turn.tool_failed and not include_tool_errors:
        return "tool error"
    if turn.steps < min_steps:
        return f"fewer than {min_steps} steps"
    return None


def write_examples(examples: Iterable[dict[str, list[dict[str, str]]]], path: Path) -> int:
    path.parent.mkdir(parents=True, exist_ok=True)
    written = 0
    with path.open("w", encoding="utf-8") as handle:
        for example in examples:
            handle.write(json.dumps(example, ensure_ascii=False) + "\n")
            written += 1
    return written


# --------------------------------------------------------------------------- #
# CLI
# --------------------------------------------------------------------------- #


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="export_dataset",
        description="Turn OmniAgent run logs into a chat-format SFT dataset.",
    )
    parser.add_argument("logs", nargs="+", help="JSON-lines log files (globs allowed).")
    parser.add_argument(
        "-o",
        "--output",
        type=Path,
        default=Path("data/dataset.jsonl"),
        help="Where to write the dataset (default: data/dataset.jsonl).",
    )
    parser.add_argument(
        "--include-tool-errors",
        action="store_true",
        help="Also export turns where a tool returned an error.",
    )
    parser.add_argument(
        "--min-steps",
        type=int,
        default=1,
        help="Drop turns with fewer than this many assistant replies (default: 1).",
    )
    parser.add_argument("--stats", action="store_true", help="Print a breakdown.")
    parser.add_argument(
        "--dry-run", action="store_true", help="Report what would be exported, write nothing."
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)

    try:
        paths = expand_paths(args.logs)
    except DatasetError as exc:
        print(f"[!] {exc}", file=sys.stderr)
        return 1

    turns, prompts = collect_turns(read_records(paths))
    examples, stats = build_examples(
        turns,
        prompts,
        include_tool_errors=args.include_tool_errors,
        min_steps=args.min_steps,
    )

    if args.stats or args.dry_run:
        print(stats.render())

    if args.dry_run:
        return 0

    if not examples:
        print("[!] nothing to export", file=sys.stderr)
        return 1

    written = write_examples(examples, args.output)
    # After the dataset, so a failed export leaves no sidecar claiming to
    # describe it. The prompt in force now is what these examples were
    # collected under, and nothing else records that.
    sidecar = write_sidecar(args.output)
    print(f"wrote {written} example{'s' if written != 1 else ''} to {args.output}")
    print(f"recorded the system prompt it was collected under in {sidecar}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
