"""Memory-only telemetry capture helpers for tests."""

from __future__ import annotations

import io
import json
import logging
from pathlib import Path
from typing import Any

import observability as obs

_STREAMS: dict[Path, io.StringIO] = {}


def reset_capture() -> None:
    obs.reset()
    _STREAMS.clear()


def configure_memory_sink(
    key: Path,
    *,
    level: int | str = logging.INFO,
    session_id: str | None = None,
    force: bool = False,
) -> str:
    """Configure telemetry in memory; ``key`` is never opened as a path."""
    session = obs.configure(level=level, session_id=session_id, force=force)
    logger = obs.get_logger()
    capture = next(
        (
            handler
            for handler in logger.handlers
            if getattr(handler, "_omniagent_memory_capture", False)
        ),
        None,
    )
    if force or capture is None:
        stream = io.StringIO()
        handler = logging.StreamHandler(stream)
        handler.setFormatter(obs.JsonLinesFormatter())
        handler._omniagent_memory_capture = True  # type: ignore[attr-defined]
        logger.addHandler(handler)
    else:
        assert isinstance(capture, logging.StreamHandler)
        stream = capture.stream
        assert isinstance(stream, io.StringIO)
    _STREAMS[key] = stream
    return session


def read_lines(key: Path) -> list[dict[str, Any]]:
    stream = _STREAMS[key]
    text = stream.getvalue().strip()
    return [json.loads(line) for line in text.splitlines()] if text else []
