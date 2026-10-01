"""One place that decides what every setting is, and where it came from.

Settings arrived from three directions and nobody owned the order: argparse
defaults, ``AgentConfig`` defaults, and a handful of ad-hoc environment
variables. This module collapses that into one model and one documented
precedence:

    command line  >  environment  >  .env file  >  [profile.NAME]  >  [defaults]  >  built-in

Every resolved value remembers which layer it came from, so ``--print-config``
can show not just what the agent will do but why.

A config file is TOML, read with the standard library -- no new dependency::

    [defaults]
    model = "qwen2.5:7b"
    log_level = "INFO"

    [profile.demo]
    model = "qwen2.5-coder:7b"
    log_file = "data/demo.jsonl"
    max_steps = 10
"""

from __future__ import annotations

import os
import tomllib
from collections.abc import Mapping
from pathlib import Path
from typing import Any, Final

from pydantic import BaseModel, Field, ValidationError

from agent import DEFAULT_API_KEY, DEFAULT_BASE_URL, DEFAULT_MODEL, AgentConfig

#: Looked for in the working directory when --config is not given.
DEFAULT_CONFIG_NAME: Final = "omniagent.toml"
DEFAULT_ENV_NAME: Final = ".env"

#: Environment variables are OMNIAGENT_<FIELD>, upper-cased.
ENV_PREFIX: Final = "OMNIAGENT_"

LOG_LEVELS: Final = ("DEBUG", "INFO", "WARNING", "ERROR")

#: Shortest string that can still be wrapped in a matching pair of quotes.
_MIN_QUOTED_LENGTH: Final = 2


class ConfigError(ValueError):
    """Raised when a config file or a setting cannot be used."""


class Settings(BaseModel):
    """Everything the CLI and the agent need, resolved from all layers."""

    model: str = Field(default=DEFAULT_MODEL)
    base_url: str = Field(default=DEFAULT_BASE_URL)
    api_key: str = Field(default=DEFAULT_API_KEY)
    temperature: float = Field(default=0.1, ge=0.0, le=2.0)
    max_steps: int = Field(default=8, ge=1, le=50)
    timeout: float = Field(default=180.0, gt=0)
    max_retries: int = Field(default=2, ge=0, le=10)
    retry_backoff: float = Field(default=1.0, ge=0.0)
    max_repeated_actions: int = Field(default=2, ge=1, le=10)
    workspace: Path = Field(default_factory=Path.cwd)
    log_file: Path | None = Field(default=None)
    log_level: str = Field(default="INFO")
    log_console: bool = Field(default=False)
    verbose: bool = Field(default=True)

    def agent_config(self) -> AgentConfig:
        """The subset the agent itself cares about."""
        return AgentConfig(
            model=self.model,
            base_url=self.base_url,
            api_key=self.api_key,
            temperature=self.temperature,
            max_steps=self.max_steps,
            timeout=self.timeout,
            max_retries=self.max_retries,
            retry_backoff=self.retry_backoff,
            max_repeated_actions=self.max_repeated_actions,
            verbose=self.verbose,
        )


FIELDS: Final[tuple[str, ...]] = tuple(Settings.model_fields)

#: Never printed back, whatever layer it came from.
SECRET_FIELDS: Final[frozenset[str]] = frozenset({"api_key"})


# --------------------------------------------------------------------------- #
# the layers
# --------------------------------------------------------------------------- #


def parse_env_file(text: str) -> dict[str, str]:
    """Parse a .env file.

    Deliberately boring: ``KEY=value`` lines, ``#`` comments, optional
    surrounding quotes, an optional ``export`` prefix. No command substitution,
    no variable expansion, nothing executed.
    """
    values: dict[str, str] = {}
    for raw in text.splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        key = key.strip().removeprefix("export ").strip()
        if not key:
            continue
        value = value.strip()
        if len(value) >= _MIN_QUOTED_LENGTH and value[0] == value[-1] and value[0] in "\"'":
            value = value[1:-1]
        values[key] = value
    return values


def read_env_file(path: Path) -> dict[str, str]:
    if not path.is_file():
        return {}
    try:
        return parse_env_file(path.read_text(encoding="utf-8"))
    except OSError as exc:
        raise ConfigError(f"could not read {path}: {exc}") from exc


def read_config_file(path: Path) -> dict[str, Any]:
    """Load a TOML config file, or raise :class:`ConfigError`."""
    try:
        with path.open("rb") as handle:
            data: dict[str, Any] = tomllib.load(handle)
    except FileNotFoundError as exc:
        raise ConfigError(f"no such config file: {path}") from exc
    except tomllib.TOMLDecodeError as exc:
        raise ConfigError(f"{path} is not valid TOML: {exc}") from exc
    except OSError as exc:
        raise ConfigError(f"could not read {path}: {exc}") from exc
    return data


def _section(data: Mapping[str, Any], name: str) -> dict[str, Any]:
    section = data.get(name, {})
    if not isinstance(section, dict):
        raise ConfigError(f"[{name}] must be a table")
    return dict(section)


def _profile(data: Mapping[str, Any], profile: str) -> dict[str, Any]:
    profiles = _section(data, "profile")
    if profile not in profiles:
        known = ", ".join(sorted(profiles)) or "(none defined)"
        raise ConfigError(f"no profile named {profile!r}. Available: {known}")
    chosen = profiles[profile]
    if not isinstance(chosen, dict):
        raise ConfigError(f"[profile.{profile}] must be a table")
    return dict(chosen)


def _reject_unknown(values: Mapping[str, Any], where: str) -> None:
    unknown = sorted(set(values) - set(FIELDS))
    if unknown:
        raise ConfigError(
            f"{where}: unknown setting(s) {', '.join(unknown)}. "
            f"Valid settings: {', '.join(FIELDS)}"
        )


def _from_env(env: Mapping[str, str]) -> dict[str, Any]:
    found: dict[str, Any] = {}
    for field in FIELDS:
        key = f"{ENV_PREFIX}{field.upper()}"
        if key in env and env[key] != "":
            found[field] = env[key]
    return found


# --------------------------------------------------------------------------- #
# resolution
# --------------------------------------------------------------------------- #


def resolve(  # noqa: PLR0913 - every layer needs its own override for tests
    cli: Mapping[str, Any] | None = None,
    *,
    config_path: Path | None = None,
    profile: str | None = None,
    env: Mapping[str, str] | None = None,
    cwd: Path | None = None,
    use_env_file: bool = True,
) -> tuple[Settings, dict[str, str]]:
    """Merge every layer into one :class:`Settings`, and say where each value came from.

    :param cli: values the user actually passed; ``None`` entries are ignored,
        so an unused flag does not outrank the config file.
    :returns: the settings, and a ``{field: source}`` map for ``--print-config``.
    """
    cwd = cwd or Path.cwd()
    environment = dict(os.environ if env is None else env)

    layers: list[tuple[str, dict[str, Any]]] = []

    file_path = config_path
    if file_path is None:
        discovered = cwd / DEFAULT_CONFIG_NAME
        file_path = discovered if discovered.is_file() else None

    if file_path is not None:
        data = read_config_file(file_path)
        defaults = _section(data, "defaults")
        _reject_unknown(defaults, f"{file_path} [defaults]")
        layers.append(("file:defaults", defaults))
        if profile:
            chosen = _profile(data, profile)
            _reject_unknown(chosen, f"{file_path} [profile.{profile}]")
            layers.append((f"profile:{profile}", chosen))
    elif profile:
        raise ConfigError(
            f"--profile {profile!r} needs a config file; none was given and no "
            f"{DEFAULT_CONFIG_NAME} was found in {cwd}"
        )

    if use_env_file:
        # The real environment wins because its layer comes after this one.
        # Filtering here as well would be a second mechanism for one rule, and
        # would disagree with it when a variable is set to the empty string.
        dotenv = read_env_file(cwd / DEFAULT_ENV_NAME)
        layers.append((f"{DEFAULT_ENV_NAME} file", _from_env(dotenv)))

    env_values = _from_env(environment)
    layers.append(("environment", env_values))

    supplied = {key: value for key, value in (cli or {}).items() if value is not None}
    _reject_unknown(supplied, "command line")
    layers.append(("command line", supplied))

    merged: dict[str, Any] = {}
    sources: dict[str, str] = {}
    for name, values in layers:
        for field, value in values.items():
            merged[field] = value
            sources[field] = name

    try:
        settings = Settings(**merged)
    except ValidationError as exc:
        problems = "; ".join(
            f"{'.'.join(str(part) for part in item['loc']) or 'setting'} "
            f"({sources.get(str(item['loc'][0]) if item['loc'] else '', 'built-in')}): "
            f"{item['msg']}"
            for item in exc.errors()
        )
        raise ConfigError(f"invalid settings -- {problems}") from exc

    if settings.log_level.upper() not in LOG_LEVELS:
        raise ConfigError(
            f"log_level ({sources.get('log_level', 'built-in')}): "
            f"{settings.log_level!r} is not one of {', '.join(LOG_LEVELS)}"
        )
    settings = settings.model_copy(update={"log_level": settings.log_level.upper()})

    for field in FIELDS:
        sources.setdefault(field, "built-in")
    return settings, sources


def render(settings: Settings, sources: Mapping[str, str]) -> str:
    """A table of every setting, its value and the layer that supplied it."""
    width = max(len(field) for field in FIELDS)
    lines = []
    for field in FIELDS:
        value = getattr(settings, field)
        shown = "***redacted***" if field in SECRET_FIELDS else value
        lines.append(f"{field:<{width}}  {shown!s:<34}  {sources.get(field, 'built-in')}")
    return "\n".join(lines)
