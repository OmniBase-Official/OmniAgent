"""``dataset_limits`` is the one home of the dataset input limits.

Each guard is asserted on its own: a file that trips one limit must not also trip
another, or deleting that guard would leave the test green.
"""

from __future__ import annotations

import os
from pathlib import Path
from types import SimpleNamespace

import pytest

import dataset_limits
import validate_dataset
from dataset_limits import DatasetInputLimitError, has_excessive_json_nesting, iter_dataset_lines


def lines(path: Path) -> list[int]:
    return [number for number, _ in iter_dataset_lines(path)]


def test_a_file_within_every_limit_is_read_line_by_line(tmp_path: Path) -> None:
    path = tmp_path / "ok.jsonl"
    path.write_bytes(b'{"a": 1}\n\n{"b": 2}\n')

    assert lines(path) == [1, 2, 3]


def test_an_oversized_file_is_refused_before_any_line_is_read(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(dataset_limits, "MAX_DATASET_BYTES", 32)
    path = tmp_path / "big.jsonl"
    path.write_bytes(b"{}\n" + b"\n" * 40)  # lines are tiny: only the file size is over

    with pytest.raises(DatasetInputLimitError, match="file size"):
        next(iter_dataset_lines(path))


def test_the_byte_total_is_enforced_while_reading(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A size that was small when checked, then grew: the running total still stops it."""
    path = tmp_path / "grows.jsonl"
    path.write_bytes(b"{}\n" * 4)
    monkeypatch.setattr(dataset_limits, "MAX_DATASET_BYTES", 9)
    monkeypatch.setattr(os, "fstat", lambda _fd: SimpleNamespace(st_size=1))

    with pytest.raises(DatasetInputLimitError, match="file size"):
        lines(path)


def test_an_overlong_line_is_refused_and_named(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(dataset_limits, "MAX_DATASET_LINE_BYTES", 8)
    path = tmp_path / "long.jsonl"
    path.write_bytes(b"{}\n" + b"x" * 9 + b"\n")

    with pytest.raises(DatasetInputLimitError, match="line 2 exceeds"):
        lines(path)


def test_too_many_records_are_refused_but_blank_lines_do_not_count(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(dataset_limits, "MAX_DATASET_EXAMPLES", 2)
    path = tmp_path / "records.jsonl"
    path.write_bytes(b"{}\n\n\n{}\n")
    assert lines(path) == [1, 2, 3, 4]

    path.write_bytes(b"{}\n{}\n{}\n")
    with pytest.raises(DatasetInputLimitError, match="record count"):
        lines(path)


def test_too_many_physical_lines_are_refused_even_when_blank(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(dataset_limits, "MAX_DATASET_LINES", 3)
    path = tmp_path / "blank.jsonl"
    path.write_bytes(b"\n\n\n\n")

    with pytest.raises(DatasetInputLimitError, match="physical line count"):
        lines(path)


@pytest.mark.parametrize(
    ("text", "excessive"),
    [
        ("[" * dataset_limits.MAX_JSON_NESTING, False),
        ("[" * (dataset_limits.MAX_JSON_NESTING + 1), True),
        ('"' + "[" * 500 + '"', False),
        ('"\\"' + "[" * 500 + '"', False),
        ("[" * 100 + "]" * 100 + "[" * 100, False),
    ],
    ids=["at-limit", "over-limit", "in-string", "escaped-quote", "closed-then-reopened"],
)
def test_nesting_depth_ignores_brackets_inside_strings(text: str, excessive: bool) -> None:
    assert has_excessive_json_nesting(text) is excessive


def test_validate_dataset_uses_these_same_limits() -> None:
    for name in (
        "MAX_DATASET_BYTES",
        "MAX_DATASET_LINE_BYTES",
        "MAX_DATASET_EXAMPLES",
        "MAX_DATASET_LINES",
        "MAX_JSON_NESTING",
    ):
        assert getattr(validate_dataset, name) == getattr(dataset_limits, name)
