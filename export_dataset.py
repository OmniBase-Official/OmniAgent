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

import validate_dataset as dataset_validation
from dataset_provenance import DatasetBoundsError, iter_bounded_lines, write_sidecar
from observability import TRUNCATION_MARKER
from trajectory_utils import actions_in as _actions_in

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

# Event turn numbers are retained in dictionary keys by collect_turns(). Keep
# the magnitude within a signed 64-bit domain, which covers realistic logs.
MAX_TURN_NUMBER = (1 << 63) - 1


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
        matches = sorted(glob.glob(pattern))  # noqa: PTH207 - pattern, not a path
        if matches:
            paths.extend(Path(match) for match in matches)
        else:
            paths.append(Path(pattern))

    missing = [path for path in paths if not path.is_file()]
    if missing:
        raise DatasetError(f"no such log file: {', '.join(str(p) for p in missing)}")
    if not paths:
        raise DatasetError("no log files given")
    return paths


def read_records(  # noqa: PLR0912 - separate handling for malformed input and resource bounds
    paths: Iterable[Path],
) -> Iterator[dict[str, Any]]:
    """Yield every well-formed JSON object across the given log files.

    A half-written final line is normal for a log that is still open, so a
    malformed line is skipped rather than fatal.
    """
    total_bytes = 0
    total_lines = 0
    total_records = 0
    for path in paths:
        try:
            for number, raw_line in iter_bounded_lines(path):
                total_bytes += len(raw_line)
                total_lines += 1
                if total_bytes > dataset_validation.MAX_DATASET_BYTES:
                    raise DatasetError(
                        "input logs exceed the "
                        f"{dataset_validation.MAX_DATASET_BYTES}-byte total limit"
                    )
                if total_lines > dataset_validation.MAX_DATASET_LINES:
                    raise DatasetError(
                        "input logs exceed the "
                        f"{dataset_validation.MAX_DATASET_LINES}-line total limit"
                    )
                if not raw_line.strip():
                    continue
                total_records += 1
                if total_records > dataset_validation.MAX_DATASET_EXAMPLES:
                    raise DatasetError(
                        "input logs exceed the "
                        f"{dataset_validation.MAX_DATASET_EXAMPLES}-record total limit"
                    )
                try:
                    stripped = raw_line.decode("utf-8").strip()
                except UnicodeDecodeError as exc:
                    raise DatasetError(f"{path.name} line {number} is not valid UTF-8") from exc
                if dataset_validation._json_nesting_is_too_deep(  # noqa: SLF001 - reuse validator policy
                    stripped
                ):
                    raise DatasetError(
                        f"{path.name} line {number} has JSON nesting that is too deep"
                    )
                try:
                    record = json.loads(stripped)
                except json.JSONDecodeError:
                    continue
                except RecursionError:
                    raise DatasetError(
                        f"{path.name} line {number} has JSON nesting that is too deep"
                    ) from None
                except ValueError as exc:
                    raise DatasetError(
                        f"{path.name} line {number} has an invalid or oversized JSON value"
                    ) from exc
                if isinstance(record, dict) and "event" in record:
                    yield record
        except DatasetBoundsError as exc:
            raise DatasetError(str(exc)) from exc


# --------------------------------------------------------------------------- #
# rebuilding turns
# --------------------------------------------------------------------------- #


def _is_truncated(*values: object) -> bool:
    return any(isinstance(v, str) and TRUNCATION_MARKER in v for v in values)


def _bounded_session_id(value: object, record_number: int) -> str:
    if isinstance(value, str):
        return value
    if value is None or isinstance(value, bool | float):
        return str(value)
    if isinstance(value, int):
        if value.bit_length() > dataset_validation.MAX_DATASET_LINE_BYTES * 4:
            raise DatasetError(f"input record {record_number} has an oversized session_id")
        try:
            return str(value)
        except ValueError:
            raise DatasetError(
                f"input record {record_number} has an oversized session_id"
            ) from None
    raise DatasetError(f"input record {record_number} has an unsupported session_id type")


def _bounded_text_bytes(values: Iterable[str], record_number: int) -> int:
    total = 0
    for value in values:
        if len(value) > dataset_validation.MAX_DATASET_LINE_BYTES:
            raise DatasetError(
                f"input record {record_number} exceeds the "
                f"{dataset_validation.MAX_DATASET_LINE_BYTES}-byte text limit"
            )
        try:
            total += len(value.encode("utf-8"))
        except UnicodeEncodeError as exc:
            raise DatasetError(
                f"input record {record_number} contains invalid UTF-8 text"
            ) from exc
        if total > dataset_validation.MAX_DATASET_LINE_BYTES:
            raise DatasetError(
                f"input record {record_number} exceeds the "
                f"{dataset_validation.MAX_DATASET_LINE_BYTES}-byte text limit"
            )
    return total


def _account_retained_record(
    record: dict[str, Any], record_number: int, retained_total: int
) -> tuple[Any, str, int]:
    session_id = _bounded_session_id(record.get("session_id", ""), record_number)
    event = record.get("event")
    if event is not None and not isinstance(event, str):
        raise DatasetError(f"input record {record_number} has an invalid event name")
    raw_turn = record.get("turn")
    turn_size = 0
    if isinstance(raw_turn, int):
        if raw_turn.bit_length() > MAX_TURN_NUMBER.bit_length():
            raise DatasetError(
                f"input record {record_number} turn number exceeds {MAX_TURN_NUMBER}"
            )
        turn_size = sys.getsizeof(raw_turn)
    relevant_fields: tuple[str, ...] = {
        "agent.created": ("system_prompt",),
        "agent.turn.start": ("question",),
        "agent.llm.response": ("reply",),
        "agent.tool.result": ("observation",),
        "agent.turn.end": ("answer",),
    }.get(event, ()) if isinstance(event, str) else ()
    retained_text = [session_id]
    if isinstance(event, str):
        retained_text.append(event)
    for field_name in relevant_fields:
        value = record.get(field_name)
        if isinstance(value, str) and (field_name != "reply" or value):
            retained_text.append(value)
            if field_name == "observation":
                retained_text.append("Observation: ")

    record_bytes = _bounded_text_bytes(retained_text, record_number) + turn_size
    if record_bytes > dataset_validation.MAX_DATASET_LINE_BYTES:
        raise DatasetError(
            f"input record {record_number} exceeds the "
            f"{dataset_validation.MAX_DATASET_LINE_BYTES}-byte retained-data limit"
        )
    retained_total += record_bytes
    if retained_total > dataset_validation.MAX_DATASET_BYTES:
        raise DatasetError(
            f"input logs exceed the {dataset_validation.MAX_DATASET_BYTES}-byte total limit"
        )
    return event, session_id, retained_total


def collect_turns(  # noqa: PLR0912 - one branch per log event we replay
    records: Iterable[dict[str, Any]],
) -> tuple[list[Turn], dict[str, str]]:
    """Group bounded records into turns and collect each session's system prompt.

    Direct callers may provide records without going through ``read_records``,
    so retained text is bounded here as well. The limits match the JSONL reader:
    each record's retained UTF-8 text plus turn identifier storage is limited to
    ``MAX_DATASET_LINE_BYTES``; the complete retained input is limited to
    ``MAX_DATASET_BYTES``. Turn numbers must fit the signed 64-bit domain.
    """
    turns: dict[tuple[str, int], Turn] = {}
    order: list[tuple[str, int]] = []
    prompts: dict[str, str] = {}

    record_count = 0
    retained_bytes = 0
    for record in records:
        record_count += 1
        if record_count > dataset_validation.MAX_DATASET_EXAMPLES:
            raise DatasetError(
                f"input logs exceed the {dataset_validation.MAX_DATASET_EXAMPLES}-record limit"
            )

        event, session_id, retained_bytes = _account_retained_record(
            record, record_count, retained_bytes
        )

        if event == "agent.created":
            prompt = record.get("system_prompt")
            if isinstance(prompt, str) and prompt:
                prompts[session_id] = prompt
            continue

        raw_turn = record.get("turn")
        if not isinstance(raw_turn, int):
            continue

        key = (session_id, raw_turn)
        if key not in turns:
            turns[key] = Turn(session_id=session_id, turn=raw_turn)
            order.append(key)
        turn = turns[key]

        if event in UNRECONSTRUCTIBLE_EVENTS:
            turn.problems.add(str(event))

        elif event == "agent.turn.start":
            question = record.get("question")
            if isinstance(question, str):
                turn.question = question
                turn.truncated |= _is_truncated(question)

        elif event == "agent.llm.response":
            reply = record.get("reply")
            if isinstance(reply, str) and reply:
                turn.exchange.append({"role": "assistant", "content": reply})
                turn.truncated |= _is_truncated(reply)

        elif event == "agent.tool.result":
            observation = record.get("observation")
            if isinstance(observation, str):
                turn.exchange.append(
                    {"role": "user", "content": f"Observation: {observation}"}
                )
                turn.truncated |= _is_truncated(observation)
            if record.get("ok") is False:
                turn.tool_failed = True

        elif event == "agent.turn.end":
            answer = record.get("answer")
            if isinstance(answer, str):
                turn.answer = answer
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

    try:
        turns, prompts = collect_turns(read_records(paths))
    except DatasetError as exc:
        print(f"[!] {exc}", file=sys.stderr)
        return 1
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
