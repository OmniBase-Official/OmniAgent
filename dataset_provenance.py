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
import os
import re
import stat
import tempfile
from collections.abc import Iterator
from contextlib import suppress
from hashlib import sha256
from pathlib import Path
from typing import Any

from agent import SYSTEM_PROMPT_TEMPLATE
from tools import describe_tools, tool_names
from validate_dataset import (
    MAX_DATASET_BYTES as _MAX_DATASET_BYTES,
)
from validate_dataset import (
    MAX_DATASET_EXAMPLES as _MAX_DATASET_EXAMPLES,
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
    _DuplicateJSONKeyError,
    _json_nesting_is_too_deep,
    _unique_json_object,
    check_shape,
)

#: Appended to the dataset's own name, so the two travel together and a copy
#: that leaves the sidecar behind is detectably unprovenanced.
SIDECAR_SUFFIX = ".provenance.json"
MAX_SIDECAR_BYTES = 16 * 1024
MAX_DATASET_BYTES = _MAX_DATASET_BYTES
MAX_DATASET_LINE_BYTES = _MAX_DATASET_LINE_BYTES
MAX_DATASET_LINES = _MAX_DATASET_LINES
MAX_DATASET_EXAMPLES = _MAX_DATASET_EXAMPLES
MAX_JSON_NESTING = _MAX_JSON_NESTING
_SHA256_HEX = re.compile(r"[0-9a-f]{64}\Z")


class ProvenanceError(RuntimeError):
    """Raised when a dataset cannot say what prompt it was collected under."""


def render_system_prompt() -> str:
    """The prompt the agent builds, rendered the same way it builds it."""
    return SYSTEM_PROMPT_TEMPLATE.format(tools=describe_tools(), tool_names=tool_names())


def prompt_fingerprint() -> str:
    return sha256(render_system_prompt().encode("utf-8")).hexdigest()



def _prompts_in_record(dataset_name: str, number: int, line: str) -> tuple[str, ...]:
    """Validate one exported row and return its system prompt strings."""
    if _json_nesting_is_too_deep(line, MAX_JSON_NESTING):
        raise ProvenanceError(
            f"{dataset_name} line {number} exceeds the "
            f"{MAX_JSON_NESTING}-level JSON nesting limit"
        )
    try:
        record = json.loads(line, object_pairs_hook=_unique_json_object)
    except _DuplicateJSONKeyError as exc:
        raise ProvenanceError(
            f"{dataset_name} line {number} contains a duplicate object key"
        ) from exc
    except json.JSONDecodeError as exc:
        raise ProvenanceError(f"{dataset_name} line {number} is not valid JSON") from exc
    except (ValueError, RecursionError, MemoryError) as exc:
        raise ProvenanceError(
            f"{dataset_name} line {number} contains invalid or oversized JSON"
        ) from exc
    if not isinstance(record, dict) or "messages" not in record:
        raise ProvenanceError(f"{dataset_name} line {number} is not an exported chat record")
    if set(record) != {"messages"}:
        raise ProvenanceError(f"{dataset_name} line {number} has unsupported top-level fields")
    messages = record["messages"]
    if not isinstance(messages, list):
        raise ProvenanceError(f"{dataset_name} line {number} has an invalid message schema")
    if not any(
        isinstance(message, dict) and message.get("role") == "system" for message in messages
    ):
        raise ProvenanceError(
            f"{dataset_name} line {number} has no system turn, so it cannot say "
            "which prompt it was collected under"
        )
    if check_shape(messages, f"{dataset_name} line {number}"):
        raise ProvenanceError(f"{dataset_name} line {number} has an invalid message schema")
    prompts = [message["content"] for message in messages if message["role"] == "system"]
    return tuple(prompts)


def _iter_dataset_prompts(dataset: Path) -> Iterator[tuple[str, ...]]:
    """Yield prompts from bounded JSONL without retaining full rows or the file."""
    try:
        if not dataset.is_file():
            raise ProvenanceError(f"no dataset found at {dataset.name}")
        size = dataset.stat().st_size
        if size > MAX_DATASET_BYTES:
            raise ProvenanceError(
                f"{dataset.name} exceeds the {MAX_DATASET_BYTES}-byte dataset limit"
            )
    except OSError as exc:
        raise ProvenanceError(f"could not inspect dataset {dataset.name}") from exc

    lines = 0
    records = 0
    total_bytes = 0
    try:
        with dataset.open("rb") as handle:
            while True:
                remaining = MAX_DATASET_BYTES - total_bytes
                raw = handle.readline(min(MAX_DATASET_LINE_BYTES + 1, remaining + 1))
                if not raw:
                    break
                lines += 1
                total_bytes += len(raw)
                if total_bytes > MAX_DATASET_BYTES:
                    raise ProvenanceError(
                        f"{dataset.name} exceeded the {MAX_DATASET_BYTES}-byte read limit"
                    )
                if lines > MAX_DATASET_LINES:
                    raise ProvenanceError(
                        f"{dataset.name} exceeded the {MAX_DATASET_LINES}-line limit"
                    )
                if len(raw) > MAX_DATASET_LINE_BYTES:
                    raise ProvenanceError(
                        f"{dataset.name} line {lines} exceeds the "
                        f"{MAX_DATASET_LINE_BYTES}-byte line limit"
                    )
                try:
                    line = raw.decode("utf-8").strip()
                except UnicodeDecodeError as exc:
                    raise ProvenanceError(
                        f"{dataset.name} line {lines} is not valid UTF-8"
                    ) from exc
                if not line:
                    continue
                records += 1
                if records > MAX_DATASET_EXAMPLES:
                    raise ProvenanceError(
                        f"{dataset.name} exceeded the {MAX_DATASET_EXAMPLES}-record limit"
                    )
                yield _prompts_in_record(dataset.name, lines, line)
    except OSError as exc:
        raise ProvenanceError(f"could not read dataset {dataset.name}") from exc


def _dataset_provenance(dataset: Path) -> tuple[str, int]:
    """Fingerprint a bounded dataset and return its nonempty record count."""
    seen: set[str] = set()
    records = 0
    for prompts in _iter_dataset_prompts(dataset):
        records += 1
        seen.update(sha256(prompt.encode("utf-8")).hexdigest() for prompt in prompts)
    if not seen:
        raise ProvenanceError(f"{dataset.name} is empty, so it has no prompt to fingerprint")
    if len(seen) > 1:
        raise ProvenanceError(
            f"{dataset.name} mixes {len(seen)} distinct system prompts "
            f"({', '.join(sorted(h[:12] for h in seen))}), so it is training data for "
            "none of them"
        )
    return seen.pop(), records


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
    return _dataset_provenance(dataset)[0]


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
    recorded, examples = _dataset_provenance(dataset)
    live = prompt_fingerprint()
    path = sidecar_path(dataset)
    payload = json.dumps(
        {
            "dataset": dataset.name,
            "examples": examples,
            "system_prompt_sha256": recorded,
            "live_prompt_sha256": live,
            "matches_live_prompt": recorded == live,
        },
        indent=2,
    ) + "\n"
    temporary: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w", encoding="utf-8", dir=path.parent,
            prefix=f".{path.name}.", suffix=".tmp", delete=False,
        ) as handle:
            temporary = Path(handle.name)
            handle.write(payload)
            handle.flush()
            os.fsync(handle.fileno())
        temporary.replace(path)
    except OSError as exc:
        if temporary is not None:
            with suppress(OSError):
                temporary.unlink(missing_ok=True)
        raise ProvenanceError(f"could not write provenance sidecar {path.name}") from exc
    return path


def read_sidecar(dataset: Path) -> dict[str, Any]:
    """Read and validate the complete provenance record for ``dataset``.

    A missing sidecar is never treated as agreement: a dataset that cannot
    say what prompt it was collected under has not been shown to match the
    prompt in force now.
    """
    path = sidecar_path(dataset)
    try:
        metadata = path.lstat()
    except FileNotFoundError as exc:
        raise ProvenanceError(
            f"no provenance recorded for {dataset.name}: {path.name} is missing"
        ) from exc
    except OSError as exc:
        raise ProvenanceError(f"could not inspect provenance sidecar {path.name}") from exc
    attributes = getattr(metadata, "st_file_attributes", 0)
    reparse_flag = getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0)
    if (
        stat.S_ISLNK(metadata.st_mode)
        or (reparse_flag and attributes & reparse_flag)
        or not stat.S_ISREG(metadata.st_mode)
    ):
        raise ProvenanceError(f"provenance sidecar {path.name} must be a regular non-link file")
    if metadata.st_size > MAX_SIDECAR_BYTES:
        raise ProvenanceError(f"provenance sidecar {path.name} exceeds its size limit")
    try:
        with path.open("rb") as handle:
            raw = handle.read(MAX_SIDECAR_BYTES + 1)
        if len(raw) > MAX_SIDECAR_BYTES:
            raise ProvenanceError(f"provenance sidecar {path.name} exceeds its size limit")
        loaded: object = json.loads(raw, object_pairs_hook=_unique_json_object)
    except _DuplicateJSONKeyError as exc:
        raise ProvenanceError(f"provenance sidecar {path.name} contains duplicate keys") from exc
    except (OSError, UnicodeDecodeError, json.JSONDecodeError, ValueError, RecursionError) as exc:
        raise ProvenanceError(f"provenance sidecar {path.name} is unreadable") from exc
    required = {
        "dataset",
        "examples",
        "system_prompt_sha256",
        "live_prompt_sha256",
        "matches_live_prompt",
    }
    if not isinstance(loaded, dict) or set(loaded) != required:
        raise ProvenanceError(f"provenance sidecar {path.name} has an invalid schema")
    name = loaded["dataset"]
    examples = loaded["examples"]
    recorded = loaded["system_prompt_sha256"]
    live = loaded["live_prompt_sha256"]
    matches = loaded["matches_live_prompt"]
    if not isinstance(name, str) or name != dataset.name:
        raise ProvenanceError(f"provenance sidecar {path.name} identifies a different dataset")
    if type(examples) is not int or examples < 1:
        raise ProvenanceError(f"provenance sidecar {path.name} has an invalid example count")
    if (
        not isinstance(recorded, str)
        or not _SHA256_HEX.fullmatch(recorded)
        or not isinstance(live, str)
        or not _SHA256_HEX.fullmatch(live)
    ):
        raise ProvenanceError(f"provenance sidecar {path.name} has an invalid prompt digest")
    if type(matches) is not bool or matches != (recorded == live):
        raise ProvenanceError(f"provenance sidecar {path.name} has inconsistent prompt metadata")
    return loaded
