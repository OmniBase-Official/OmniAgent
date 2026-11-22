"""The one home of the input limits for a user-supplied dataset.

``validate_dataset`` and ``dataset_provenance`` read files the user points them
at, and a file is not trusted just because it is local: it may have been
downloaded, shared or truncated. These limits bound one read of such a file.
They do not protect against another process changing the file while it is read;
concurrent writers are outside the current threat model.

The numbers are conservative: the largest dataset documented in this repository
has 47 examples and 237,199 content characters, and the historical training run
had 109. They are defaults, not measurements of a current production corpus.
Keep them here and import them; a second copy of a limit drifts.
"""

from __future__ import annotations

import os
from collections.abc import Iterator
from pathlib import Path

MAX_DATASET_BYTES = 256 * 1024 * 1024
MAX_DATASET_LINE_BYTES = 4 * 1024 * 1024
MAX_DATASET_EXAMPLES = 100_000
MAX_DATASET_LINES = 1_000_000
MAX_JSON_NESTING = 128
#: A provenance sidecar is a few hundred bytes; 64 KiB is generous.
MAX_SIDECAR_BYTES = 64 * 1024


class DatasetInputLimitError(ValueError):
    """A dataset file exceeded an explicit input resource limit."""


def iter_dataset_lines(path: Path) -> Iterator[tuple[int, bytes]]:
    """Yield ``(line number, raw line)`` without ever buffering more than one line.

    Refuses a file over the byte, line-length, physical-line or record limit.
    A blank line counts toward the physical-line limit but not the record limit.
    """
    total_bytes = 0
    records = 0
    with path.open("rb") as stream:
        if os.fstat(stream.fileno()).st_size > MAX_DATASET_BYTES:
            raise DatasetInputLimitError(
                f"dataset exceeds maximum file size of {MAX_DATASET_BYTES} bytes"
            )
        number = 0
        while True:
            line = stream.readline(MAX_DATASET_LINE_BYTES + 1)
            if not line:
                return
            number += 1
            if number > MAX_DATASET_LINES:
                raise DatasetInputLimitError(
                    f"dataset exceeds maximum physical line count of {MAX_DATASET_LINES}"
                )
            total_bytes += len(line)
            if total_bytes > MAX_DATASET_BYTES:
                raise DatasetInputLimitError(
                    f"dataset exceeds maximum file size of {MAX_DATASET_BYTES} bytes"
                )
            if len(line) > MAX_DATASET_LINE_BYTES:
                raise DatasetInputLimitError(
                    f"line {number} exceeds maximum line size of {MAX_DATASET_LINE_BYTES} bytes"
                )
            if line.strip():
                records += 1
                if records > MAX_DATASET_EXAMPLES:
                    raise DatasetInputLimitError(
                        f"dataset exceeds maximum record count of {MAX_DATASET_EXAMPLES}"
                    )
            yield number, line


def has_excessive_json_nesting(text: str) -> bool:
    """Whether object/array depth exceeds the limit, ignoring brackets in strings."""
    depth = 0
    in_string = False
    escaped = False
    for character in text:
        if in_string:
            if escaped:
                escaped = False
            elif character == "\\":
                escaped = True
            elif character == '"':
                in_string = False
            continue
        if character == '"':
            in_string = True
        elif character in "[{":
            depth += 1
            if depth > MAX_JSON_NESTING:
                return True
        elif character in "]}" and depth:
            depth -= 1
    return False
