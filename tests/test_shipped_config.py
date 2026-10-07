"""Tests for the config file we actually ship.

Every other settings test builds its own TOML in a ``tmp_path``, which is how
``[profile.demo]`` came to inherit the stock 7B from ``[defaults]`` while 444
tests stayed green -- the demo profile was never resolved against the real
file. These assertions read ``omniagent.toml`` itself, so the thing the demo
runs on is covered by the suite.
"""

from __future__ import annotations

import inspect
import sys
import tomllib
from pathlib import Path

import pytest

from config import DEFAULT_CONFIG_NAME, Settings, resolve

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

from session_eval import run_walk

REPO_ROOT = Path(__file__).resolve().parent.parent
CONFIG_PATH = REPO_ROOT / DEFAULT_CONFIG_NAME

# The fine-tune, whose Modelfile pins ``num_ctx 16384``. The stock 7B defaults
# to 4096 and truncates from the front, taking the system prompt with it.
#: Moved to the second fine-tune on 2026-10-07 after ten runs of holdout_eval
#: over both tags (12/16 against 10/16, zero variance either side) and five
#: runs of the demo questions on the demo path (25/25). The constant is here so
#: the demo profile cannot drift off a measured model by accident.
DEMO_MODEL = "omniagent-v2"


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


def test_the_demo_runs_the_step_budget_the_evaluations_measure() -> None:
    """The demo should not be the one configuration nobody has measured.

    Every figure in NEXT_CHAT.md comes from max_steps=8. The demo profile
    shipped 12, and rehearsing it there the question "What is inside the data
    directory?" spent all twelve steps and returned "I ran out of reasoning
    steps before reaching an answer" -- a question that is 10/10 at 3-9 steps
    in the evaluation. One rehearsal does not prove twelve is the cause, but
    it is reason enough for the demo to run what was measured.
    """
    measured = inspect.signature(run_walk).parameters["max_steps"].default
    settings, _ = _resolve("demo")

    assert settings.max_steps == measured
