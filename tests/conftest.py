"""Shared fixtures. Only opt-in fixtures live here; no test gets one unless it asks."""

from __future__ import annotations

import ast
import json.decoder
from typing import Any

import pytest

#: Nesting this deep overflows the parsers on Windows (measured on 3.12.10: 2,000 is read,
#: 3,000 overflows) and not on Linux (3.12.3: 7,000 is read), because the C parsers' limit is
#: not sys.getrecursionlimit() and differs by build. 2,500 sits between the two Windows figures.
FORCED_DEPTH = 2_500


def _tree_depth(tree: ast.AST) -> int:
    deepest, stack = 0, [(tree, 1)]
    while stack:
        node, depth = stack.pop()
        deepest = max(deepest, depth)
        stack.extend((child, depth + 1) for child in ast.iter_child_nodes(node))
    return deepest


def _bracket_depth(text: str) -> int:
    depth = deepest = 0
    for character in text:
        if character in "[{":
            depth += 1
            deepest = max(deepest, depth)
        elif character in "]}":
            depth -= 1
    return deepest


@pytest.fixture
def parsers_overflow_on_hostile_input(monkeypatch: pytest.MonkeyPatch) -> None:
    """Make a parser overflow on input nested past FORCED_DEPTH, whatever the platform.

    The guard tests feed a file nested a few thousand deep. Python's own parsers overflow on
    that on Windows and not on Linux, so on Linux the guard would never run and the test
    would say nothing. Each wrapper calls the real parser first (a real overflow propagates
    untouched), then raises RecursionError itself when the input was nested past the depth
    that overflows on Windows. The wrappers keep the real functions' names, which the tests
    read from the traceback, and are only in place for a test that asks for this fixture.
    """
    real_parse = ast.parse
    real_raw_decode = json.decoder.JSONDecoder.raw_decode

    def parse(source: Any, *args: Any, **kwargs: Any) -> Any:
        tree = real_parse(source, *args, **kwargs)
        if _tree_depth(tree) > FORCED_DEPTH:
            raise RecursionError("maximum recursion depth exceeded during ast construction")
        return tree

    def raw_decode(self: json.decoder.JSONDecoder, s: str, idx: int = 0) -> Any:
        result = real_raw_decode(self, s, idx)
        if _bracket_depth(s) > FORCED_DEPTH:
            raise RecursionError("maximum recursion depth exceeded while decoding a JSON array")
        return result

    monkeypatch.setattr(ast, "parse", parse)
    monkeypatch.setattr(json.decoder.JSONDecoder, "raw_decode", raw_decode)
