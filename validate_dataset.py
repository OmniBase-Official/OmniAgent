"""Refuse to train on a bad dataset.

The notebook calls this before it loads a single weight. Three things are
checked, in order of how expensive they are to discover later:

1. **Shape.** Every example must be a chat conversation the trainer can read:
   a system turn, then alternating user/assistant, ending on the assistant.
2. **Secrets.** A dataset is built from real runs, and a model trained on a
   leaked key will happily reproduce it. Anything that looks like a credential
   stops the run.
3. **Size and balance.** Too few examples, or every example identical, is not a
   training set. These are warnings, not errors -- the user decides.

Usage::

    python validate_dataset.py data/dataset.jsonl
    python validate_dataset.py data/dataset.jsonl --min-examples 50
"""

from __future__ import annotations

import argparse
import json
import re
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

#: Below this, a fine-tune is not worth starting. A warning, not an error.
DEFAULT_MIN_EXAMPLES = 10

VALID_ROLES = frozenset({"system", "user", "assistant"})

#: Patterns that mean "stop, there is a credential in the training data".
#: Deliberately broad: a false positive costs a conversation, a false negative
#: bakes a secret into model weights.
SECRET_PATTERNS: tuple[tuple[str, re.Pattern[str]], ...] = (
    ("OpenAI-style key", re.compile(r"\bsk-[A-Za-z0-9_-]{16,}")),
    ("AWS access key", re.compile(r"\bAKIA[0-9A-Z]{16}\b")),
    ("GitHub token", re.compile(r"\bgh[pousr]_[A-Za-z0-9]{20,}")),
    ("Slack token", re.compile(r"\bxox[abprs]-[A-Za-z0-9-]{10,}")),
    ("Google API key", re.compile(r"\bAIza[0-9A-Za-z_-]{35}\b")),
    ("private key block", re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----")),
    ("bearer token", re.compile(r"\bBearer\s+[A-Za-z0-9._-]{20,}")),
    # The assigned value must look like a literal, not like code. OmniAgent's
    # file tools read source, and source is full of lines like
    # `api_key=self.api_key,` -- a reference to a credential, not one. A
    # validator that cries wolf on every such line gets ignored, which is worse
    # than one that is slightly narrower. So a value containing attribute
    # access or a call is not a finding; `API_KEY=sk-abc123...` still is.
    (
        "assigned secret",
        re.compile(
            # No \b before the hint: it would not match inside OMNIAGENT_API_KEY
            # or DB_PASSWORD, because an underscore is a word character, so every
            # prefixed environment-variable name slipped through.
            r"(?i)(api[_-]?key|secret|password|passwd)\s*[=:]\s*"
            r"(?![^\s]*(?:\.[A-Za-z_]|\())"
            r"['\"]?\S{8,}"
        ),
    ),
)


@dataclass
class Report:
    """What validation found. Errors block; warnings are advisory."""

    examples: int = 0
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    roles: Counter[str] = field(default_factory=Counter)
    actions: Counter[str] = field(default_factory=Counter)
    turn_lengths: list[int] = field(default_factory=list)
    chars: int = 0

    @property
    def ok(self) -> bool:
        return not self.errors and self.examples > 0

    def render(self) -> str:
        lines = [f"examples   : {self.examples}"]
        if self.turn_lengths:
            lines.append(
                f"messages   : min {min(self.turn_lengths)}, "
                f"max {max(self.turn_lengths)}, "
                f"mean {sum(self.turn_lengths) / len(self.turn_lengths):.1f}"
            )
            lines.append(f"characters : {self.chars:,}")
        if self.actions:
            tools = ", ".join(f"{name}: {n}" for name, n in self.actions.most_common())
            lines.append(f"tools      : {tools}")
        else:
            lines.append("tools      : (no Action lines found)")
        for warning in self.warnings:
            lines.append(f"WARNING    : {warning}")
        for error in self.errors:
            lines.append(f"ERROR      : {error}")
        lines.append("verdict    : " + ("OK" if self.ok else "REFUSED"))
        return "\n".join(lines)


def find_secrets(text: str) -> list[str]:
    """Names of every credential pattern the text matches."""
    return [label for label, pattern in SECRET_PATTERNS if pattern.search(text)]


def check_shape(messages: Any, where: str) -> list[str]:
    """Structural problems with one example's message list."""
    if not isinstance(messages, list) or not messages:
        return [f"{where}: 'messages' must be a non-empty list"]

    problems: list[str] = []
    for index, message in enumerate(messages):
        if not isinstance(message, dict):
            problems.append(f"{where}: message {index} is not an object")
            continue
        role, content = message.get("role"), message.get("content")
        if role not in VALID_ROLES:
            problems.append(f"{where}: message {index} has role {role!r}")
        if not isinstance(content, str) or not content.strip():
            problems.append(f"{where}: message {index} has empty content")
    if problems:
        return problems

    roles = [str(message["role"]) for message in messages]
    if roles[0] != "system":
        problems.append(f"{where}: must start with a system turn, not {roles[0]!r}")
    if roles[-1] != "assistant":
        problems.append(f"{where}: must end with an assistant turn, not {roles[-1]!r}")
    expected = "user"
    for position, role in enumerate(roles[1:], start=1):
        if role != expected:
            problems.append(
                f"{where}: roles stop alternating at message {position} "
                f"(expected {expected!r}, found {role!r})"
            )
            break
        expected = "assistant" if expected == "user" else "user"
    return problems


def _actions_in(reply: str) -> list[str]:
    return [
        line.split(":", 1)[1].strip()
        for line in reply.splitlines()
        if line.strip().lower().startswith("action:")
    ]


def validate_file(  # noqa: PLR0912 - one branch per thing a dataset gets wrong
    path: Path, *, min_examples: int = DEFAULT_MIN_EXAMPLES
) -> Report:
    """Validate a JSON-lines chat dataset."""
    report = Report()

    if not path.is_file():
        report.errors.append(f"no such dataset: {path}")
        return report

    digests: Counter[str] = Counter()
    for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        stripped = line.strip()
        if not stripped:
            continue
        where = f"line {number}"

        try:
            example = json.loads(stripped)
        except json.JSONDecodeError as exc:
            report.errors.append(f"{where}: not valid JSON ({exc.msg})")
            continue
        if not isinstance(example, dict) or "messages" not in example:
            report.errors.append(f"{where}: missing a 'messages' key")
            continue

        messages = example["messages"]
        problems = check_shape(messages, where)
        if problems:
            report.errors.extend(problems)
            continue

        report.examples += 1
        report.turn_lengths.append(len(messages))
        digests[json.dumps(messages, sort_keys=True)] += 1

        for message in messages:
            role, content = str(message["role"]), str(message["content"])
            report.roles[role] += 1
            report.chars += len(content)
            for label in find_secrets(content):
                report.errors.append(f"{where}: {label} found in the {role} turn")
            if role == "assistant":
                report.actions.update(_actions_in(content))

    if report.examples == 0 and not report.errors:
        report.errors.append("the dataset is empty")
    if 0 < report.examples < min_examples:
        report.warnings.append(
            f"only {report.examples} examples; at least {min_examples} is advisable "
            "before fine-tuning"
        )
    repeated = sum(count - 1 for count in digests.values() if count > 1)
    if repeated:
        report.warnings.append(f"{repeated} duplicate example(s)")
    if report.examples > 1 and len(digests) == 1:
        report.warnings.append("every example is identical")
    if report.examples and not report.actions:
        report.warnings.append(
            "no Action lines found; this dataset will not teach tool use"
        )
    return report


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="validate_dataset",
        description="Check a chat-format SFT dataset before training on it.",
    )
    parser.add_argument("dataset", type=Path, help="JSON-lines dataset to check.")
    parser.add_argument(
        "--min-examples",
        type=int,
        default=DEFAULT_MIN_EXAMPLES,
        help=f"Warn below this many examples (default: {DEFAULT_MIN_EXAMPLES}).",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    report = validate_file(args.dataset, min_examples=args.min_examples)
    print(report.render())
    return 0 if report.ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
