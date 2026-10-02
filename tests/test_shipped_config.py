"""Tests for the config file we actually ship.

Every other settings test builds its own TOML in a ``tmp_path``, which is how
``[profile.demo]`` came to inherit the stock 7B from ``[defaults]`` while 444
tests stayed green -- the demo profile was never resolved against the real
file. These assertions read ``omniagent.toml`` itself, so the thing the demo
runs on is covered by the suite.
"""

from __future__ import annotations

import tomllib
from pathlib import Path

import pytest

from config import DEFAULT_CONFIG_NAME, Settings, resolve

REPO_ROOT = Path(__file__).resolve().parent.parent
CONFIG_PATH = REPO_ROOT / DEFAULT_CONFIG_NAME

# The fine-tune, whose Modelfile pins ``num_ctx 16384``. The stock 7B defaults
# to 4096 and truncates from the front, taking the system prompt with it.
DEMO_MODEL = "omniagent"


def _resolve(profile: str | None) -> tuple[Settings, dict[str, str]]:
    """Resolve the shipped file on its own: no environment, no .env, no CLI."""
    return resolve(
        config_path=CONFIG_PATH,
        profile=profile,
        env={},
        cwd=REPO_ROOT,
        use_env_file=False,
    )


def _profile_names() -> list[str]:
    with CONFIG_PATH.open("rb") as handle:
        data: dict[str, object] = tomllib.load(handle)
    profiles = data.get("profile", {})
    return sorted(profiles) if isinstance(profiles, dict) else []


def test_shipped_config_is_present() -> None:
    assert CONFIG_PATH.is_file(), f"{CONFIG_PATH} is what --profile reads"


@pytest.mark.parametrize("profile", _profile_names())
def test_every_shipped_profile_resolves(profile: str) -> None:
    """A stale key in any profile is a crash at startup, not a warning."""
    settings, _ = _resolve(profile)
    assert settings.model


def test_demo_profile_pins_the_fine_tune() -> None:
    """Without its own model the demo silently falls back to the stock 7B."""
    settings, sources = _resolve("demo")
    assert settings.model == DEMO_MODEL
    assert sources["model"] == "profile:demo"


def test_demo_profile_is_deterministic() -> None:
    """The rehearsal and the demo have to produce the same answers."""
    settings, _ = _resolve("demo")
    assert settings.temperature == 0.0


def test_demo_profile_records_the_run() -> None:
    settings, _ = _resolve("demo")
    assert settings.log_file is not None
