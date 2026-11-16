"""What prompt a dataset was collected under.

Every training example carries the system prompt in force when it was
recorded, so a dataset is only training data for the prompt it was collected
against. ``read_file``'s description changed in ``58bb801`` and
``data/dataset.jsonl`` predates it, which means the served model was trained
against a prompt it is no longer given. That was found by reading a commit
log. This module is how it gets found by a check instead.

The hash is the one the agent already writes into its ``agent.created``
event, so there is one fingerprint for the prompt and not two that can
disagree.
"""

from __future__ import annotations

import json
from collections.abc import Iterator
from hashlib import sha256
from pathlib import Path
from typing import Any

import validate_dataset as dataset_validation
from agent import SYSTEM_PROMPT_TEMPLATE
from tools import describe_tools, tool_names

#: Appended to the dataset's own name, so the two travel together and a copy
#: that leaves the sidecar behind is detectably unprovenanced.
SIDECAR_SUFFIX = ".provenance.json"
MAX_SIDECAR_BYTES = 64 * 1024


class DatasetBoundsError(ValueError):
    """Raised when an input exceeds the shared JSONL resource policy."""


def iter_bounded_lines(dataset: Path) -> Iterator[tuple[int, bytes]]:
    """Yield bounded JSONL lines under the validator's existing input limits.

    Limits apply to each file. Concurrent mutation during a read remains
    outside the current threat model.
    """
    total_bytes = 0
    records = 0
    try:
        size = dataset.stat().st_size
        if size > dataset_validation.MAX_DATASET_BYTES:
            raise DatasetBoundsError(
                    "dataset exceeds maximum file size of "
                    f"{dataset_validation.MAX_DATASET_BYTES} bytes"
            )
        with dataset.open("rb") as stream:
            line_number = 0
            while True:
                remaining = dataset_validation.MAX_DATASET_BYTES - total_bytes
                raw_line = stream.readline(
                    min(dataset_validation.MAX_DATASET_LINE_BYTES + 1, remaining + 1)
                )
                if not raw_line:
                    return
                total_bytes += len(raw_line)
                line_number += 1
                if total_bytes > dataset_validation.MAX_DATASET_BYTES:
                    raise DatasetBoundsError(
                        "dataset exceeds maximum file size of "
                        f"{dataset_validation.MAX_DATASET_BYTES} bytes"
                    )
                if line_number > dataset_validation.MAX_DATASET_LINES:
                    raise DatasetBoundsError(
                        "dataset exceeds maximum physical line count of "
                        f"{dataset_validation.MAX_DATASET_LINES}"
                    )
                if len(raw_line) > dataset_validation.MAX_DATASET_LINE_BYTES:
                    raise DatasetBoundsError(
                        f"line {line_number} exceeds maximum line size of "
                        f"{dataset_validation.MAX_DATASET_LINE_BYTES} bytes"
                    )
                if raw_line.strip():
                    records += 1
                    if records > dataset_validation.MAX_DATASET_EXAMPLES:
                        raise DatasetBoundsError(
                            "dataset exceeds maximum record count of "
                            f"{dataset_validation.MAX_DATASET_EXAMPLES}"
                        )
                yield line_number, raw_line
    except OSError as exc:
        raise DatasetBoundsError(f"could not read {dataset.name}: {exc.strerror or exc}") from exc


class ProvenanceError(RuntimeError):
    """Raised when a dataset cannot say what prompt it was collected under."""


def render_system_prompt() -> str:
    """The prompt the agent builds, rendered the same way it builds it."""
    return SYSTEM_PROMPT_TEMPLATE.format(tools=describe_tools(), tool_names=tool_names())


def prompt_fingerprint() -> str:
    return sha256(render_system_prompt().encode("utf-8")).hexdigest()



def _dataset_fingerprint_and_count(  # noqa: PLR0912 - validates independent input failure modes
    dataset: Path,
) -> tuple[str, int]:
    """Return the sole system-prompt digest and nonblank record count."""
    recorded: str | None = None
    examples = 0
    for number, raw_line in iter_bounded_lines(dataset):
        if not raw_line.strip():
            continue
        try:
            line = raw_line.decode("utf-8")
        except UnicodeDecodeError as exc:
            raise ProvenanceError(f"{dataset.name} line {number} is not valid UTF-8") from exc
        if dataset_validation._json_nesting_is_too_deep(  # noqa: SLF001 - reuse validator policy
            line
        ):
            raise ProvenanceError(
                f"{dataset.name} line {number} has JSON nesting that is too deep"
            )
        try:
            example = json.loads(line)
        except json.JSONDecodeError as exc:
            raise ProvenanceError(
                f"{dataset.name} line {number} is not valid JSON ({exc.msg})"
            ) from exc
        except (RecursionError, ValueError) as exc:
            raise ProvenanceError(f"{dataset.name} line {number} has invalid JSON") from exc
        if not isinstance(example, dict):
            raise ProvenanceError(f"{dataset.name} line {number} is not an object")
        messages = example.get("messages")
        if not isinstance(messages, list):
            raise ProvenanceError(
                f"{dataset.name} line {number} has no system turn, so it cannot say "
                "which prompt it was collected under"
            )
        found = False
        for message in messages:
            if not isinstance(message, dict) or message.get("role") != "system":
                continue
            prompt = message.get("content")
            if not isinstance(prompt, str):
                raise ProvenanceError(f"{dataset.name} line {number} has an invalid system turn")
            digest = sha256(prompt.encode("utf-8")).hexdigest()
            if recorded is None:
                recorded = digest
            elif digest != recorded:
                raise ProvenanceError(
                    f"{dataset.name} mixes 2 distinct system prompts, so it is training data "
                    "for none of them"
                )
            found = True
        if not found:
            raise ProvenanceError(
                f"{dataset.name} line {number} has no system turn, so it cannot say "
                "which prompt it was collected under"
            )
        examples += 1

    if recorded is None:
        raise ProvenanceError(f"{dataset.name} is empty, so it has no prompt to fingerprint")
    return recorded, examples


def dataset_fingerprint(dataset: Path) -> str:
    """The digest of the system prompt the dataset itself carries.

    Measured, not claimed. Every example records the prompt in force when the
    turn was logged, and the exporter replays it verbatim as the system turn,
    so the fingerprint can be read out of the file rather than asserted about
    whichever checkout the file happens to be sitting in.

    This is what makes this module's stated purpose reachable. Hashing the
    prompt the code renders today stamps today's fingerprint onto a dataset of
    any age, which cannot detect the one thing worth detecting: data collected
    under a prompt that no longer exists. On the real files the difference is
    the whole point -- ``data/dataset.jsonl`` carries ``ee43a4af...`` in all
    109 of its examples while the live prompt is ``36397f37...``.

    A dataset mixing two prompts is refused rather than reduced to one of
    them: a pooled collection is training data for neither.
    """
    try:
        return _dataset_fingerprint_and_count(dataset)[0]
    except DatasetBoundsError as exc:
        raise ProvenanceError(str(exc)) from exc


def sidecar_path(dataset: Path) -> Path:
    return dataset.with_name(dataset.name + SIDECAR_SUFFIX)


def write_sidecar(dataset: Path) -> Path:
    """Record beside ``dataset`` which prompt it carries, and say where it went.

    ``system_prompt_sha256`` is the dataset's **own** fingerprint, read out of
    its examples. ``live_prompt_sha256`` is what the code renders now, and
    ``matches_live_prompt`` is the comparison between them -- the question this
    module was written to answer, and the one an earlier version of this
    function could not, because it recorded the live prompt as though it were
    the data's own.
    """
    try:
        recorded, examples = _dataset_fingerprint_and_count(dataset)
    except DatasetBoundsError as exc:
        raise ProvenanceError(str(exc)) from exc
    live = prompt_fingerprint()
    path = sidecar_path(dataset)
    path.write_text(
        json.dumps(
            {
                "dataset": dataset.name,
                "examples": examples,
                "system_prompt_sha256": recorded,
                "live_prompt_sha256": live,
                "matches_live_prompt": recorded == live,
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    return path


def read_sidecar(dataset: Path) -> dict[str, Any]:
    """The recorded provenance, or an error.

    A missing sidecar is never treated as agreement: a dataset that cannot
    say what prompt it was collected under has not been shown to match the
    prompt in force now.
    """
    path = sidecar_path(dataset)
    if not path.is_file():
        raise ProvenanceError(
            f"no provenance recorded for {dataset.name}: {path.name} is missing, so there is "
            "nothing to compare against the prompt in force now"
        )
    try:
        with path.open("rb") as stream:
            if stream.seek(0, 2) > MAX_SIDECAR_BYTES:
                raise ProvenanceError(
                    f"provenance sidecar exceeds the {MAX_SIDECAR_BYTES}-byte size limit"
                )
            stream.seek(0)
            raw = stream.read(MAX_SIDECAR_BYTES + 1)
        if len(raw) > MAX_SIDECAR_BYTES:
            raise ProvenanceError(
                f"provenance sidecar exceeds the {MAX_SIDECAR_BYTES}-byte size limit"
            )
        text = raw.decode("utf-8")
        if dataset_validation._json_nesting_is_too_deep(  # noqa: SLF001 - reuse validator policy
            text
        ):
            raise ProvenanceError("provenance sidecar JSON nesting is too deep")
        loaded = json.loads(text)
    except (OSError, UnicodeDecodeError, json.JSONDecodeError, RecursionError, ValueError) as exc:
        if isinstance(exc, ProvenanceError):
            raise
        raise ProvenanceError(f"invalid provenance sidecar {path.name}") from exc
    if not isinstance(loaded, dict):
        raise ProvenanceError("provenance sidecar must be an object")
    return loaded
