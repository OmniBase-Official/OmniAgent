"""Shared fixtures for tests that exercise explicit workspace behavior."""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

import pytest

from sandbox import Workspace, workspace_scope


@pytest.fixture(autouse=True)
def explicit_repository_workspace() -> Iterator[None]:
    """Give legacy tests an explicit root instead of relying on CWD fallback."""
    with workspace_scope(Workspace.at(Path.cwd())):
        yield
