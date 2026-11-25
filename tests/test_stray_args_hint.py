"""Brief 39: read_file and file_info say what a path with stray numbers probably was.

Measured by the project manager over 40 raw rows: on four of ten files the model's
FIRST read_file call carried invented arguments (``observability.py 1``, ``-1``,
``0 100``, ``-1 -1``). The path as given does not exist, so the lookup failed with
"no such file" and the next-call text of brief 34 was never reached.

The tools stay strict. Only the error TEXT changes: when the path with its numeric
tail removed would be read by the very same call, the error says so, with the exact
next call. These tests pin the five hard conditions of the brief, each by its cause:

1. no existence oracle: for every candidate the tool refuses (sealed, denied, listing
   only, hidden, credential-named, a directory, outside the workspace, a symlink or
   junction out, a hard link, oversized, binary) the output is the string the tool
   returned before this change, character for character. A sealed control proves the
   fixture would hint if the policy check were removed;
2. an exact name wins, and a failure other than "no such file" is never decorated;
3. no new readability: nothing here reads a file that was unreadable, and a hint never
   names a path outside the workspace;
4. bounded: a long path, or thousands of numeric tokens, gets the old message;
5. what an integer is: ASCII digits with an optional leading "-", separated by a space
   or tab, one or two of them (the table below).

"Today's output" is not re-derived from the new code: ``today()`` rebuilds it from the
sandbox call the tool made before, so a change that decorates a refusal fails here.

Non-ASCII text is built from code points, so this source stays ASCII.
Static: no model, no socket.
"""

from __future__ import annotations

import os
import re
import subprocess
import sys
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

from eval_workspace import ANSWER_KEY, LISTING_ONLY, sealed_workspace

from sandbox import (
    DENIED_NAMES,
    DENIED_SUFFIXES,
    SandboxError,
    Workspace,
    get_workspace,
    set_workspace,
)
from tools import file_info, read_file, run_tool

HINT = (
    ". Did you mean {c}? Call {t} again with the path only "
    "(Action Input: {c}), no line numbers."
)


@dataclass(frozen=True)
class Tool:
    name: str
    run: Callable[[str], str]
    method: str  # the Workspace call it makes
    verb: str  # in the text of its OSError


READ = Tool("read_file", read_file, "read_text", "read")
INFO = Tool("file_info", file_info, "describe", "inspect")
TOOLS = [pytest.param(READ, id="read_file"), pytest.param(INFO, id="file_info")]
JOURNAL = "next" + "chat"


@contextmanager
def install(workspace: Workspace) -> Iterator[Workspace]:
    previous = get_workspace()
    set_workspace(workspace)
    try:
        yield workspace
    finally:
        set_workspace(previous)


def today(workspace: Workspace, tool: Tool, given: str) -> str:
    """What the tool returned for ``given`` before brief 39."""
    try:
        getattr(workspace, tool.method)(given)
    except SandboxError as exc:
        return f"Error: {exc}"
    except OSError as exc:
        return f"Error: could not {tool.verb} {given!r}: {exc.strerror or exc}"
    raise AssertionError(f"{given!r} was readable; the case proves nothing")


def link(target: Path, name: Path, *, directory: bool = False) -> None:
    try:
        name.symlink_to(target, target_is_directory=directory)
    except OSError as exc:  # no symlink privilege on this machine
        pytest.skip(f"cannot create a symlink here: {exc}")


@pytest.fixture
def outside(tmp_path: Path) -> Path:
    folder = tmp_path / "outside"
    folder.mkdir()
    (folder / "secret.txt").write_text("outside\n", encoding="utf-8")
    return folder


@pytest.fixture
def ws(tmp_path: Path, outside: Path) -> Iterator[Workspace]:
    root = tmp_path / "ws"
    (root / "sub").mkdir(parents=True)
    (root / ".hid").mkdir()
    body = "x = 1\n" * 5
    for name in ("observability.py", "sub/inner.py", "a", "solo.py", ".hidden.txt", ".hid/f.txt"):
        (root / name).write_text(body, encoding="utf-8")
    (root / "a 1").write_text("literal-marker\n", encoding="utf-8")
    (root / "blob.bin").write_bytes(b"\0" * 20)
    (root / "id_rsa").write_text(body, encoding="utf-8")
    (root / "server.pem").write_text(body, encoding="utf-8")
    os.link(root / "solo.py", root / "solo_hard.py")
    with install(Workspace.at(root)) as workspace:
        yield workspace


# -- the hint itself ------------------------------------------------------------ #

POSITIVE = [
    ("observability.py 1", "observability.py"),
    ("observability.py -1", "observability.py"),
    ("observability.py 0 100", "observability.py"),
    ("observability.py -1 -1", "observability.py"),
    ("sub/inner.py 3", "sub/inner.py"),
    ("observability.py\t5", "observability.py"),
    ("observability.py   7", "observability.py"),
    ("./observability.py 1", "observability.py"),
    ('"observability.py" 1', "observability.py"),
    ("observability.py 1\n", "observability.py"),
]


@pytest.mark.parametrize("tool", TOOLS)
@pytest.mark.parametrize(("given", "candidate"), POSITIVE)
def test_the_error_names_the_file_and_the_exact_next_call(
    ws: Workspace, tool: Tool, given: str, candidate: str
) -> None:
    expected = today(ws, tool, given) + HINT.format(c=candidate, t=tool.name)

    assert tool.run(given) == expected


def test_the_named_call_runs_as_written_through_the_dispatcher(ws: Workspace) -> None:
    first = run_tool("read_file", "observability.py 1")
    candidate = re.search(r"\(Action Input: ([^)]+)\)", first)

    assert candidate is not None
    assert first.startswith("Error: no such file: observability.py 1. Did you mean ")
    second = run_tool("read_file", candidate[1])
    assert second.startswith("observability.py (5 lines")


# What counts as an integer: ASCII digits, an optional leading "-", one or two of them,
# separated by a space or a tab. Everything else leaves today's message.
SPACE, TAB, LF, NUL = " ", "\t", "\n", "\0"
ACCEPTED = [
    SPACE + "1", SPACE + "0", SPACE + "-1", SPACE + "-0", SPACE + "007", SPACE + "1 2",
    SPACE + "-1 -1", SPACE + "0 100", TAB + "1", SPACE + SPACE + "1",
]  # fmt: skip
REJECTED = {
    "plus sign": SPACE + "+1",
    "exponent": SPACE + "1e5",
    "decimal point": SPACE + "1.5",
    "comma": SPACE + "1,5",
    "arabic-indic digit": SPACE + chr(0x661),
    "fullwidth digit": SPACE + chr(0xFF11),
    "superscript digit": SPACE + chr(0xB9),
    "unicode minus": SPACE + chr(0x2212) + "1",
    "bare minus": SPACE + "-",
    "double minus": SPACE + "--1",
    "hex": SPACE + "0x10",
    "underscore": SPACE + "1_0",
    "three integers": SPACE + "1 2 3",
    "trailing dash": SPACE + "1 -",
    "newline separator": LF + "1",
    "newline between": SPACE + "1" + LF + "2",
    "nul after": SPACE + "1" + NUL,
    "nul before": NUL + SPACE + "1",
    "no-break space": chr(0xA0) + "1",
    "ideographic space": chr(0x3000) + "1",
    "no separator": "1",
}


@pytest.mark.parametrize("tool", TOOLS)
@pytest.mark.parametrize("suffix", ACCEPTED)
def test_the_integer_table_accepts(ws: Workspace, tool: Tool, suffix: str) -> None:
    assert "Did you mean observability.py?" in tool.run("observability.py" + suffix)


@pytest.mark.parametrize("tool", TOOLS)
@pytest.mark.parametrize("suffix", list(REJECTED.values()), ids=list(REJECTED))
def test_the_integer_table_rejects_and_leaves_todays_message(
    ws: Workspace, tool: Tool, suffix: str
) -> None:
    given = "observability.py" + suffix

    assert tool.run(given) == today(ws, tool, given)


# -- 2. exact match wins --------------------------------------------------------- #


def test_a_real_file_named_with_a_trailing_number_is_read_as_named(ws: Workspace) -> None:
    assert "literal-marker" in read_file("a 1")
    assert "Did you mean" not in read_file("a 1")
    assert file_info("a 1").startswith("a 1: 1 lines")


def test_a_failure_other_than_no_such_file_is_never_decorated(ws: Workspace) -> None:
    """The real file ``a 1`` is binary here: its error is not "no such file", and the
    readable file ``a`` must not be offered in its place."""
    (ws.root / "a 1").write_bytes(b"\0" * 20)
    expected = today(ws, READ, "a 1")

    assert "binary" in expected
    assert read_file("a 1") == expected


# -- 1 and 3. no existence oracle, no new readability ---------------------------- #


def test_a_control_file_in_the_same_workspace_does_get_the_hint(ws: Workspace) -> None:
    """Without this, every refusal below could pass because nothing ever hints."""
    assert "Did you mean sub/inner.py?" in read_file("sub/inner.py 1")


def refused(ws: Workspace, outside: Path) -> dict[str, str]:
    """Given paths whose candidate the tool refuses, by what refuses it."""
    cases = {
        "directory": "sub 1",
        "hidden file": ".hidden.txt 1",
        "file in a hidden directory": ".hid/f.txt 1",
        "credential name": f"{sorted(DENIED_NAMES)[0]} 1",
        "credential suffix": f"server{sorted(DENIED_SUFFIXES)[-1]} 1",
        "hard link": "solo_hard.py 1",
        "hard link source": "solo.py 1",
        "parent traversal": "../outside/secret.txt 1",
        "absolute path": f"{outside / 'secret.txt'} 1",
        "absolute path, two numbers": f"{outside / 'secret.txt'} 1 2",
        "drive-relative or rooted": f"{(outside / 'secret.txt').anchor}outside 1",
        "UNC": "//host/share/secret.txt 1",
        "UNC backslash": "\\\\host\\share\\secret.txt 1",
        "home directory": "~/secret.txt 1",
    }
    link(outside / "secret.txt", ws.root / "to_outside.txt")
    link(outside, ws.root / "to_outside_dir", directory=True)
    cases["symlink to an outside file"] = "to_outside.txt 1"
    cases["symlink to an outside directory"] = "to_outside_dir/secret.txt 1"
    return cases


@pytest.mark.parametrize("tool", TOOLS)
def test_a_refused_candidate_gets_exactly_todays_message(
    ws: Workspace, outside: Path, tool: Tool
) -> None:
    for kind, given in refused(ws, outside).items():
        assert tool.run(given) == today(ws, tool, given), kind
        assert "Did you mean" not in tool.run(given), kind


def test_a_binary_candidate_gets_todays_message_from_read_file(ws: Workspace) -> None:
    """file_info may describe a binary file, so only read_file refuses it."""
    assert read_file("blob.bin 1") == today(ws, READ, "blob.bin 1")
    assert "Did you mean blob.bin?" in file_info("blob.bin 1")


@pytest.mark.skipif(os.name != "nt", reason="directory junctions exist on Windows only")
def test_a_junction_out_of_the_workspace_gets_todays_message(
    ws: Workspace, outside: Path
) -> None:
    result = subprocess.run(  # noqa: S603 - fixed argv, a throwaway directory
        ["cmd", "/c", "mklink", "/J", str(ws.root / "jct"), str(outside)],  # noqa: S607
        capture_output=True,
        check=False,
    )
    if result.returncode:
        pytest.skip("cannot create a junction here")
    given = "jct/secret.txt 1"

    assert read_file(given) == today(ws, READ, given)


def test_an_oversized_candidate_gets_todays_message(tmp_path: Path) -> None:
    root = tmp_path / "small"
    root.mkdir()
    (root / "big.txt").write_text("x" * 200, encoding="utf-8")
    with install(Workspace.at(root, max_file_bytes=50)) as workspace:
        given = "big.txt 1"

        assert read_file(given) == today(workspace, READ, given)
        assert "Did you mean" not in read_file(given)


@pytest.fixture
def sealed(tmp_path: Path) -> Iterator[tuple[Workspace, list[str]]]:
    """Synthetic files at the ANSWER_KEY and LISTING_ONLY paths of a fixture project.

    The removed journal's name is skipped: nothing here may create it, in any folder.
    """
    project = tmp_path / "project"
    project.mkdir()
    (project / "README.txt").write_text("open\n", encoding="utf-8")
    givens: list[str] = []
    for relative in (*ANSWER_KEY, *LISTING_ONLY):
        if JOURNAL in re.sub(r"[^a-z0-9]", "", relative.lower()):
            continue
        target = project / relative
        if target.suffix:
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text("synthetic\n", encoding="utf-8")
            givens.append(f"{relative} 1")
        else:
            target.mkdir(parents=True, exist_ok=True)
            (target / "inner.txt").write_text("synthetic\n", encoding="utf-8")
            givens += [f"{relative}/inner.txt 1", f"{relative} 1"]
    with install(sealed_workspace(project)) as workspace:
        yield workspace, givens


@pytest.mark.parametrize("tool", TOOLS)
def test_a_sealed_candidate_gets_todays_message_and_an_open_one_gets_the_hint(
    sealed: tuple[Workspace, list[str]], tool: Tool
) -> None:
    workspace, givens = sealed

    assert len(givens) >= len(ANSWER_KEY)
    assert "Did you mean README.txt?" in tool.run("README.txt 1")
    for given in givens:
        assert tool.run(given) == today(workspace, tool, given), "a sealed candidate"


# -- 4. bounded ------------------------------------------------------------------ #


def test_a_long_given_path_gets_todays_message_not_a_longer_one(ws: Workspace) -> None:
    name = "n" * 210 + ".txt"
    (ws.root / name).write_text("x\n", encoding="utf-8")
    given = f"{name} 1"
    baseline = today(ws, READ, given)

    assert read_file(given) == baseline
    assert len(read_file(given)) == len(baseline)


def test_thousands_of_numeric_tokens_get_todays_message(ws: Workspace) -> None:
    given = "observability.py" + " 1" * 3000

    assert read_file(given) == today(ws, READ, given)


def test_an_over_long_numeric_tail_gets_todays_message(ws: Workspace) -> None:
    """One integer, 5,000 digits long: the form fits, the length does not."""
    given = "observability.py 1" + "1" * 5000

    assert read_file(given) == today(ws, READ, given)


def test_a_symlink_loop_candidate_gets_todays_message(ws: Workspace) -> None:
    link(ws.root / "loop_b", ws.root / "loop_a")
    link(ws.root / "loop_a", ws.root / "loop_b")
    given = "loop_a 1"

    assert read_file(given) == today(ws, READ, given)
    assert file_info(given) == today(ws, INFO, given)


def test_a_candidate_shown_long_through_a_link_gets_todays_message(ws: Workspace) -> None:
    deep = ws.root / ("d" * 110) / ("e" * 110)
    try:
        deep.mkdir(parents=True)
    except OSError as exc:  # pragma: no cover - long paths disabled
        pytest.skip(f"cannot create a long path here: {exc}")
    (deep / "f.txt").write_text("x\n", encoding="utf-8")
    link(deep / "f.txt", ws.root / "short.txt")
    given = "short.txt 1"

    assert read_file(given) == today(ws, READ, given)


def test_a_candidate_name_with_a_bidi_override_is_not_echoed(ws: Workspace) -> None:
    name = "a" + chr(0x202E) + "b.txt"
    (ws.root / name).write_text("x\n", encoding="utf-8")
    given = f"{name} 1"

    assert read_file(given) == today(ws, READ, given)
    link(ws.root / name, ws.root / "plain.txt")
    assert read_file("plain.txt 1") == today(ws, READ, "plain.txt 1")
