"""Write sanitized operational telemetry with a closed field schema.

Only event status, duration, step count, fixed tool names, model tags/digests,
and the runtime version are persisted. Trajectory data belongs in a separately
approved dataset sink and is never accepted by this module.
"""

from __future__ import annotations

import contextvars
import json
import logging
import math
import re
import sys
import uuid
from collections.abc import Mapping
from pathlib import Path
from types import TracebackType
from typing import Any, Final

LOGGER_NAME: Final[str] = "omniagent"
TRUNCATION_MARKER: Final[str] = "...(truncated"

# Operational telemetry has a separate, closed schema. This is deliberately
# much smaller than the fields the dataset exporter used to consume: trajectory
# capture needs a separately approved sink and must never piggyback on logs.
FIXED_TOOL_NAMES: Final[frozenset[str]] = frozenset(
    {
        "calculate",
        "get_current_time",
        "read_file",
        "list_directory",
        "search_text",
        "file_info",
    }
)

_EVENT_FIELDS: Final[dict[str, frozenset[str]]] = {
    "agent.created": frozenset({"status", "model_digest"}),
    "agent.reset": frozenset({"status", "step_count"}),
    "agent.connection.unreachable": frozenset({"status"}),
    "agent.connection.error": frozenset({"status"}),
    "agent.connection.ok": frozenset({"status"}),
    "agent.turn.start": frozenset({"status", "step_count"}),
    "agent.turn.end": frozenset({"status", "duration_ms", "step_count"}),
    "agent.step.final_answer": frozenset({"status", "step_count"}),
    "agent.format.violation": frozenset({"status", "step_count"}),
    "agent.budget.exhausted": frozenset({"status", "step_count"}),
    "agent.loop.repeated_action": frozenset({"status", "step_count", "tool_name"}),
    "agent.tool.call": frozenset({"status", "step_count", "tool_name"}),
    "agent.tool.result": frozenset({"status", "duration_ms", "step_count", "tool_name"}),
    "agent.fast_route.result": frozenset({"status", "step_count"}),
    "agent.tool.policy_violation": frozenset({"status", "step_count", "tool_name"}),
    "agent.context.trimmed": frozenset({"status", "step_count"}),
    "agent.llm.request": frozenset(
        {"status", "model_digest", "step_count"}
    ),
    "agent.llm.response": frozenset(
        {"status", "duration_ms", "model_digest", "step_count"}
    ),
    "agent.llm.retry": frozenset({"status", "duration_ms", "step_count"}),
    "agent.llm.unreachable": frozenset({"status", "step_count"}),
    "agent.llm.error": frozenset({"status", "step_count"}),
    "cli.interrupted": frozenset({"status", "step_count"}),
    "cli.aborted": frozenset({"status", "step_count"}),
    "tool.unknown": frozenset({"status"}),
    "tool.invalid_args": frozenset({"status", "tool_name"}),
    "tool.crashed": frozenset({"status", "tool_name"}),
}

_STATUSES: Final[frozenset[str]] = frozenset(
    {
        "created",
        "reset",
        "started",
        "completed",
        "requested",
        "succeeded",
        "failed",
        "rejected",
        "unreachable",
        "error",
        "retrying",
        "invalid_format",
        "step_budget_exhausted",
        "repeated_action",
        "trimmed",
        "interrupted",
        "aborted",
    }
)
_SHA256 = re.compile(r"^(?:sha256:)?[a-fA-F0-9]{64}$")
_TELEMETRY_FIELDS: Final[frozenset[str]] = frozenset(
    {
        "record_type",
        "event",
        "status",
        "duration_ms",
        "step_count",
        "tool_name",
        "model_digest",
        "runtime_version",
    }
)
_RUNTIME_VERSION: Final[str] = sys.version.split()[0]

_EMPTY_CONTEXT: Final[Mapping[str, Any]] = {}

_context: contextvars.ContextVar[Mapping[str, Any]] = contextvars.ContextVar(
    "omniagent_log_context", default=_EMPTY_CONTEXT
)

_configured = False


# --------------------------------------------------------------------------- #
# sanitising
# --------------------------------------------------------------------------- #


def _sanitise_event(name: str, fields: Mapping[str, Any]) -> dict[str, Any] | None:
    """Return telemetry from the closed schema, dropping every other value."""
    if type(name) is not str:
        return None
    allowed = _EVENT_FIELDS.get(name)
    if allowed is None:
        return None
    payload: dict[str, Any] = {
        "record_type": "operational_telemetry",
        "event": name,
        "runtime_version": _RUNTIME_VERSION,
    }
    for key, value in fields.items():
        if type(key) is not str:
            continue
        if key not in allowed:
            continue
        if key == "status" and type(value) is str and value in _STATUSES:
            payload[key] = value
        elif (
            key == "duration_ms"
            and isinstance(value, int | float)
            and not isinstance(value, bool)
        ):
            if math.isfinite(value) and value >= 0:
                payload[key] = round(float(value), 3)
        elif key == "step_count" and type(value) is int:
            if value >= 0:
                payload[key] = value
        elif key == "tool_name" and type(value) is str and value in FIXED_TOOL_NAMES:
            payload[key] = value
        elif key == "model_digest" and type(value) is str and _SHA256.fullmatch(value):
            payload[key] = value.lower()
    return payload


# --------------------------------------------------------------------------- #
# formatter / filter
# --------------------------------------------------------------------------- #


class ContextFilter(logging.Filter):
    """Do not copy context fields into persisted telemetry."""

    def filter(self, _record: logging.LogRecord) -> bool:
        # Context is intentionally not copied into log records. Session ids and
        # any future bound data are outside the telemetry contract.
        return True


class JsonLinesFormatter(logging.Formatter):
    """Render a record as a single-line JSON object."""

    def format(self, record: logging.LogRecord) -> str:
        event_name = str(getattr(record, "event", ""))
        fields = {
            key: value
            for key, value in record.__dict__.items()
            if key in _TELEMETRY_FIELDS and key != "event"
        }
        payload = _sanitise_event(event_name, fields)
        fallback = {
            "record_type": "operational_telemetry",
            "event": "telemetry.dropped",
            "runtime_version": _RUNTIME_VERSION,
        }
        return json.dumps(payload or fallback)


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
    """Install the JSON-lines handlers and return an in-memory session id.

    Calling this twice is a no-op unless ``force`` is set, so importing a module
    that configures logging cannot silently double every line.

    :param level: minimum level to emit, as a name or a ``logging`` constant.
    :param log_file: rejected because persistent operational files are disabled.
    :param console: also stream the JSON lines to stderr (stdout stays free for
        the human-readable trace).
    :param session_id: accepted for API compatibility but never persisted.
    :param force: replace handlers that a previous call installed.
    """
    if log_file is not None:
        raise RuntimeError(
            "persistent operational log files are disabled until an approved "
            "retention and deletion policy exists"
        )

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
    :param message: ignored. Persisted messages can contain raw user data.
    :param fields: only fields in the closed telemetry schema are persisted.
    """
    target = logger or get_logger()
    _ = message, exc_info  # accepted for API compatibility, never persisted
    if not target.isEnabledFor(level):
        return
    safe = _sanitise_event(name, fields)
    if safe is None:
        return
    # Reduce values before they enter any LogRecord or handler. No custom
    # message, exception, prompt, argument, observation, or answer is retained.
    extra = {key: value for key, value in safe.items() if key != "event"}
    extra["event"] = safe["event"]
    target.log(
        level,
        name,
        extra=extra,
        exc_info=None,
    )
