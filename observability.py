"""Structured logging for OmniAgent.

The console output a user reads (the Thought/Action/Observation trace in
``main.py``) and the log stream a machine reads are two different products.
This module owns the second one: newline-delimited JSON, one object per event,
with ambient context -- session, turn, step -- attached automatically.

Usage::

    import observability as obs

    obs.configure(level="INFO", log_file=Path("omniagent.jsonl"))
    with obs.bind(turn=1):
        obs.event("agent.turn.start", question="What is 2 + 2?")

Every record carries ``ts``, ``level``, ``logger``, ``event`` and ``message``,
plus whatever fields were bound or passed. Values that look like credentials
are masked and long strings are truncated, so a log file stays safe to paste
into a bug report.
"""

from __future__ import annotations

import contextvars
import json
import logging
import sys
import uuid
from collections.abc import Mapping
from datetime import UTC, datetime
from pathlib import Path
from types import TracebackType
from typing import Any, Final

LOGGER_NAME: Final[str] = "omniagent"

#: Fields longer than this are truncated in the log output.
MAX_FIELD_LENGTH: Final[int] = 2_000

#: Fields the dataset exporter reads back verbatim. A truncated prompt or reply
#: would become corrupt training data, so these get a far larger budget -- still
#: bounded, so a runaway tool output cannot write an unbounded line.
MAX_TRAINING_FIELD_LENGTH: Final[int] = 32_000

TRAINING_FIELDS: Final[frozenset[str]] = frozenset(
    {
        "system_prompt",
        "question",
        "answer",
        "reply",
        "observation",
        "tool_input",
    }
)

#: Substrings that mark a field as a credential, matched case-insensitively.
_SENSITIVE_HINTS: Final[tuple[str, ...]] = (
    "api_key",
    "apikey",
    "secret",
    "password",
    "passwd",
    "token",
    "authorization",
)

_REDACTED: Final[str] = "***redacted***"

#: Appended to any value that had to be shortened. The dataset exporter looks
#: for it and refuses to turn a truncated record into a training example.
TRUNCATION_MARKER: Final[str] = "...(truncated"

#: Names that contain a sensitive hint but are plainly not credentials. The
#: policy is default-deny -- over-redacting a counter is cheap, leaking a key is
#: not -- so anything new has to be listed here explicitly.
_SAFE_FIELDS: Final[frozenset[str]] = frozenset(
    {
        "tokens",
        "token_count",
        "prompt_tokens",
        "completion_tokens",
        "total_tokens",
        "cached_tokens",
        "reasoning_tokens",
        "max_tokens",
    }
)

#: Attributes that :class:`logging.LogRecord` always defines. Anything else a
#: caller attaches via ``extra=`` is treated as a structured field.
_RESERVED_ATTRS: Final[frozenset[str]] = frozenset(
    {
        "args",
        "asctime",
        "created",
        "exc_info",
        "exc_text",
        "filename",
        "funcName",
        "levelname",
        "levelno",
        "lineno",
        "message",
        "module",
        "msecs",
        "msg",
        "name",
        "pathname",
        "process",
        "processName",
        "relativeCreated",
        "stack_info",
        "taskName",
        "thread",
        "threadName",
    }
)

_EMPTY_CONTEXT: Final[Mapping[str, Any]] = {}

_context: contextvars.ContextVar[Mapping[str, Any]] = contextvars.ContextVar(
    "omniagent_log_context", default=_EMPTY_CONTEXT
)

_configured = False


# --------------------------------------------------------------------------- #
# sanitising
# --------------------------------------------------------------------------- #


def _is_sensitive(key: str, value: Any) -> bool:
    """Whether a field should be masked.

    Name-matching alone needed a hand-maintained allow-list, and the list was
    always one field behind: `prompt_tokens` was caught during M2, and
    `estimated_tokens_before` slipped past the fix. The general rule is simpler
    and does not need maintaining -- a field named "...tokens..." holding a
    *number* is a count, because a credential is never an int. Singular
    "token" (auth_token, access_token) is untouched by this, and so is any
    string or list however it is named.
    """
    lowered = key.lower()
    if lowered in _SAFE_FIELDS:
        return False
    if "tokens" in lowered and isinstance(value, (int, float)) and not isinstance(value, bool):
        return False
    return any(hint in lowered for hint in _SENSITIVE_HINTS)


def _sanitise(key: str, value: Any) -> Any:
    """Mask credentials, shorten long strings, and make a value JSON-safe."""
    if _is_sensitive(key, value):
        return _REDACTED
    limit = MAX_TRAINING_FIELD_LENGTH if key in TRAINING_FIELDS else MAX_FIELD_LENGTH
    return _coerce(value, limit)


def _coerce(value: Any, limit: int = MAX_FIELD_LENGTH) -> Any:
    if value is None or isinstance(value, (bool, int, float)):
        return value
    if isinstance(value, str):
        if len(value) > limit:
            return f"{value[:limit]}{TRUNCATION_MARKER}, {len(value)} chars)"
        return value
    if isinstance(value, Mapping):
        return {str(k): _sanitise(str(k), v) for k, v in value.items()}
    if isinstance(value, (list, tuple, set)):
        return [_coerce(item, limit) for item in value]
    return _coerce(repr(value), limit)


# --------------------------------------------------------------------------- #
# formatter / filter
# --------------------------------------------------------------------------- #


class ContextFilter(logging.Filter):
    """Copy the ambient :func:`bind` context onto every record."""

    def filter(self, record: logging.LogRecord) -> bool:
        for key, value in _context.get().items():
            if key not in _RESERVED_ATTRS and not hasattr(record, key):
                setattr(record, key, value)
        return True


class JsonLinesFormatter(logging.Formatter):
    """Render a record as a single-line JSON object."""

    def format(self, record: logging.LogRecord) -> str:
        created = datetime.fromtimestamp(record.created, tz=UTC)
        payload: dict[str, Any] = {
            "ts": created.isoformat(timespec="milliseconds").replace("+00:00", "Z"),
            "level": record.levelname,
            "logger": record.name,
            "event": str(getattr(record, "event", record.name)),
            "message": record.getMessage(),
        }

        for key, value in record.__dict__.items():
            if key in _RESERVED_ATTRS or key in payload or key.startswith("_"):
                continue
            payload[key] = _sanitise(key, value)

        # logging stores a falsy exc_info verbatim, so this is False far more
        # often than it is None. Checking `is not None` would try to format a
        # bool as a traceback and lose the record.
        if record.exc_info and isinstance(record.exc_info, tuple):
            payload["error"] = _coerce(self.formatException(record.exc_info))

        return json.dumps(payload, ensure_ascii=False, default=repr)


# --------------------------------------------------------------------------- #
# configuration
# --------------------------------------------------------------------------- #


def configure(
    *,
    level: int | str = logging.INFO,
    log_file: Path | None = None,
    console: bool = False,
    session_id: str | None = None,
    force: bool = False,
) -> str:
    """Install the JSON-lines handlers and return the session id.

    Calling this twice is a no-op unless ``force`` is set, so importing a module
    that configures logging cannot silently double every line.

    :param level: minimum level to emit, as a name or a ``logging`` constant.
    :param log_file: file to append JSON lines to; its parent is created.
    :param console: also stream the JSON lines to stderr (stdout stays free for
        the human-readable trace).
    :param session_id: reuse an id instead of generating one.
    :param force: replace handlers that a previous call installed.
    """
    global _configured  # noqa: PLW0603 - module-level singleton by design

    logger = logging.getLogger(LOGGER_NAME)
    if _configured and not force:
        return str(_context.get().get("session_id", ""))

    for handler in list(logger.handlers):
        logger.removeHandler(handler)
        handler.close()

    logger.setLevel(level)
    # Keep agent logs out of whatever the embedding application configured.
    logger.propagate = False

    formatter = JsonLinesFormatter()
    context_filter = ContextFilter()

    if log_file is not None:
        log_file.parent.mkdir(parents=True, exist_ok=True)
        file_handler = logging.FileHandler(log_file, encoding="utf-8")
        file_handler.setFormatter(formatter)
        file_handler.addFilter(context_filter)
        logger.addHandler(file_handler)

    if console:
        stream_handler = logging.StreamHandler(sys.stderr)
        stream_handler.setFormatter(formatter)
        stream_handler.addFilter(context_filter)
        logger.addHandler(stream_handler)

    if not logger.handlers:
        # Nothing to write to: swallow records rather than letting logging fall
        # back to its "no handlers" warning on stderr.
        logger.addHandler(logging.NullHandler())

    resolved = session_id or uuid.uuid4().hex[:12]
    _context.set({**_context.get(), "session_id": resolved})
    _configured = True
    return resolved


def reset() -> None:
    """Tear down the handlers and clear the context. Intended for tests."""
    global _configured  # noqa: PLW0603 - module-level singleton by design

    logger = logging.getLogger(LOGGER_NAME)
    for handler in list(logger.handlers):
        logger.removeHandler(handler)
        handler.close()
    _context.set(_EMPTY_CONTEXT)
    _configured = False


def get_logger(name: str | None = None) -> logging.Logger:
    """Return the shared agent logger, or a child of it."""
    if name is None:
        return logging.getLogger(LOGGER_NAME)
    return logging.getLogger(f"{LOGGER_NAME}.{name}")


# --------------------------------------------------------------------------- #
# context + emission
# --------------------------------------------------------------------------- #


class _BoundContext:
    """Context manager returned by :func:`bind`.

    Written as a class rather than a ``@contextmanager`` generator so that the
    ``Any``-typed fields do not leak through a decorator, which mypy's
    ``disallow_any_decorated`` rejects.
    """

    __slots__ = ("_fields", "_token")

    def __init__(self, fields: Mapping[str, Any]) -> None:
        self._fields = fields
        self._token: contextvars.Token[Mapping[str, Any]] | None = None

    def __enter__(self) -> None:
        self._token = _context.set({**_context.get(), **self._fields})

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        if self._token is not None:
            _context.reset(self._token)
            self._token = None


def bind(**fields: Any) -> _BoundContext:
    """Attach fields to every record emitted inside the block.

    Nested binds merge, and the previous context is restored on exit even if the
    block raises.
    """
    return _BoundContext(fields)


def current_context() -> dict[str, Any]:
    """Snapshot of the fields :func:`bind` would currently attach."""
    return dict(_context.get())


def event(
    name: str,
    message: str | None = None,
    *,
    level: int = logging.INFO,
    logger: logging.Logger | None = None,
    exc_info: bool = False,
    **fields: Any,
) -> None:
    """Emit one structured event.

    :param name: dotted event name, e.g. ``agent.tool.call``.
    :param message: optional human-readable text; defaults to the event name.
    :param fields: arbitrary structured data, sanitised before it is written.
    """
    target = logger or get_logger()
    if not target.isEnabledFor(level):
        return
    extra = {key: value for key, value in fields.items() if key not in _RESERVED_ATTRS}
    extra["event"] = name
    target.log(
        level,
        message if message is not None else name,
        extra=extra,
        exc_info=exc_info or None,
    )
