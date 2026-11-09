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

import main as main_module
import observability as obs
from agent import DEFAULT_MODEL
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


def test_shipped_default_model_matches_the_code_default() -> None:
    with CONFIG_PATH.open("rb") as handle:
        data: dict[str, object] = tomllib.load(handle)
    defaults = data.get("defaults", {})
    assert isinstance(defaults, dict)
    assert defaults.get("model") == DEFAULT_MODEL

    settings, sources = _resolve(None)
    assert settings.model == DEFAULT_MODEL
    assert sources["model"] == "file:defaults"


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


def test_shipped_profiles_do_not_enable_persistent_operational_logs() -> None:
    for profile in _profile_names():
        settings, _ = _resolve(profile)
        assert settings.log_file is None


@pytest.mark.parametrize(
    "source", ["cli", "environment", "dotenv", "toml-defaults", "toml-profile"]
)
def test_log_file_is_rejected_from_every_config_source_before_startup(
    source: str,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    output_path = tmp_path / "not-created" / "operational.jsonl"
    config_path = tmp_path / "settings.toml"
    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv("OMNIAGENT_LOG_FILE", raising=False)
    arguments = ["--ask", "synthetic prompt"]

    if source == "cli":
        arguments.extend(["--log-file", str(output_path)])
    elif source == "environment":
        monkeypatch.setenv("OMNIAGENT_LOG_FILE", str(output_path))
    elif source == "dotenv":
        (tmp_path / ".env").write_text(
            f"OMNIAGENT_LOG_FILE={output_path}\n", encoding="utf-8"
        )
    elif source in {"toml-defaults", "toml-profile"}:
        section = (
            f'[defaults]\nlog_file = "{output_path.as_posix()}"\n'
            if source == "toml-defaults"
            else f'[profile.review]\nlog_file = "{output_path.as_posix()}"\n'
        )
        config_path.write_text(section, encoding="utf-8")
        arguments.extend(["--config", str(config_path)])
        if source == "toml-profile":
            arguments.extend(["--profile", "review"])

    monkeypatch.setattr(
        main_module,
        "ReActAgent",
        lambda *_args, **_kwargs: pytest.fail("agent must not be constructed"),
    )
    monkeypatch.setattr(
        main_module,
        "preflight",
        lambda *_args, **_kwargs: pytest.fail("model preflight must not run"),
    )
    monkeypatch.setattr(
        obs,
        "configure",
        lambda *_args, **_kwargs: pytest.fail("logging must not be configured"),
    )

    result = main_module.main(arguments)

    assert result == 2
    assert "retention and deletion policy" in capsys.readouterr().out
    assert not output_path.parent.exists()
    assert not output_path.exists()


def test_the_demo_runs_the_step_budget_the_evaluations_measure() -> None:
    """The demo should not be the one configuration nobody has measured.

    Every figure in the frozen evaluation baseline comes from max_steps=8. The demo profile
    shipped 12, and rehearsing it there the question "What is inside the data
    directory?" spent all twelve steps and returned "I ran out of reasoning
    steps before reaching an answer" -- a question that is 10/10 at 3-9 steps
    in the evaluation. One rehearsal does not prove twelve is the cause, but
    it is reason enough for the demo to run what was measured.
    """
    measured = inspect.signature(run_walk).parameters["max_steps"].default
    settings, _ = _resolve("demo")

    assert settings.max_steps == measured
