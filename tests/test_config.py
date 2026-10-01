"""Tests for the settings layer.

The point of the layer is precedence, so most of these put the same setting in
two places and check which one wins -- and that the answer says where it came
from, since a wrong precedence that reports itself honestly is far easier to
debug than a silent one.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

from config import (
    DEFAULT_CONFIG_NAME,
    ConfigError,
    Settings,
    parse_env_file,
    render,
    resolve,
)

CONFIG = """
[defaults]
model = "from-defaults"
max_steps = 4

[profile.demo]
model = "from-profile"
temperature = 0.0

[profile.empty]
"""


@pytest.fixture
def project(tmp_path: Path) -> Path:
    (tmp_path / DEFAULT_CONFIG_NAME).write_text(CONFIG, encoding="utf-8")
    return tmp_path


def settings_at(
    cwd: Path, cli: dict[str, Any] | None = None, **kwargs: Any
) -> tuple[Settings, dict[str, str]]:
    kwargs.setdefault("env", {})
    return resolve(cli or {}, cwd=cwd, **kwargs)


# --------------------------------------------------------------------------- #
# precedence
# --------------------------------------------------------------------------- #


def test_built_in_defaults_when_there_is_nothing_else(tmp_path: Path) -> None:
    settings, sources = settings_at(tmp_path)

    assert settings.max_steps == 8
    assert sources["max_steps"] == "built-in"


def test_the_config_file_is_discovered_in_the_working_directory(project: Path) -> None:
    settings, sources = settings_at(project)

    assert settings.model == "from-defaults"
    assert sources["model"] == "file:defaults"


def test_a_profile_beats_the_defaults_section(project: Path) -> None:
    settings, sources = settings_at(project, profile="demo")

    assert settings.model == "from-profile"
    assert sources["model"] == "profile:demo"
    # Settings the profile does not mention still come from [defaults].
    assert (settings.max_steps, sources["max_steps"]) == (4, "file:defaults")


def test_the_environment_beats_the_profile(project: Path) -> None:
    settings, sources = settings_at(
        project, profile="demo", env={"OMNIAGENT_MODEL": "from-env"}
    )

    assert settings.model == "from-env"
    assert sources["model"] == "environment"


def test_the_command_line_beats_the_environment(project: Path) -> None:
    settings, sources = settings_at(
        project, cli={"model": "from-cli"}, profile="demo", env={"OMNIAGENT_MODEL": "from-env"}
    )

    assert settings.model == "from-cli"
    assert sources["model"] == "command line"


def test_an_unused_flag_does_not_outrank_the_file(project: Path) -> None:
    """argparse hands us None for flags the user never typed."""
    settings, sources = settings_at(project, cli={"model": None})

    assert settings.model == "from-defaults"
    assert sources["model"] == "file:defaults"


def test_an_explicit_config_path_is_used(tmp_path: Path) -> None:
    elsewhere = tmp_path / "other.toml"
    elsewhere.write_text('[defaults]\nmodel = "elsewhere"\n', encoding="utf-8")

    settings, sources = settings_at(tmp_path, config_path=elsewhere)

    assert settings.model == "elsewhere"
    assert sources["model"] == "file:defaults"


# --------------------------------------------------------------------------- #
# the .env layer
# --------------------------------------------------------------------------- #


def test_a_dotenv_file_supplies_settings(tmp_path: Path) -> None:
    (tmp_path / ".env").write_text("OMNIAGENT_MODEL=from-dotenv\n", encoding="utf-8")

    settings, sources = settings_at(tmp_path)

    assert settings.model == "from-dotenv"
    assert sources["model"] == ".env file"


def test_the_real_environment_beats_the_dotenv_file(tmp_path: Path) -> None:
    (tmp_path / ".env").write_text("OMNIAGENT_MODEL=from-dotenv\n", encoding="utf-8")

    settings, sources = settings_at(tmp_path, env={"OMNIAGENT_MODEL": "from-env"})

    assert settings.model == "from-env"
    assert sources["model"] == "environment"


def test_the_dotenv_file_beats_the_profile(project: Path) -> None:
    (project / ".env").write_text("OMNIAGENT_MODEL=from-dotenv\n", encoding="utf-8")

    settings, _ = settings_at(project, profile="demo")

    assert settings.model == "from-dotenv"


def test_an_empty_real_variable_lets_the_dotenv_value_through(tmp_path: Path) -> None:
    """`OMNIAGENT_MODEL=` means "not set", consistently at every layer."""
    (tmp_path / ".env").write_text("OMNIAGENT_MODEL=from-dotenv\n", encoding="utf-8")

    settings, sources = settings_at(tmp_path, env={"OMNIAGENT_MODEL": ""})

    assert settings.model == "from-dotenv"
    assert sources["model"] == ".env file"


def test_dotenv_loading_can_be_turned_off(tmp_path: Path) -> None:
    (tmp_path / ".env").write_text("OMNIAGENT_MODEL=from-dotenv\n", encoding="utf-8")

    settings, _ = settings_at(tmp_path, use_env_file=False)

    assert settings.model != "from-dotenv"


@pytest.mark.parametrize(
    ("line", "expected"),
    [
        ("KEY=value", {"KEY": "value"}),
        ("  KEY = value  ", {"KEY": "value"}),
        ("export KEY=value", {"KEY": "value"}),
        ('KEY="quoted value"', {"KEY": "quoted value"}),
        ("KEY='single'", {"KEY": "single"}),
        ("# a comment", {}),
        ("", {}),
        ("no equals sign", {}),
        ("KEY=", {"KEY": ""}),
        ("KEY=a=b", {"KEY": "a=b"}),
    ],
)
def test_dotenv_parsing(line: str, expected: dict[str, str]) -> None:
    assert parse_env_file(line) == expected


def test_dotenv_does_not_expand_or_execute_anything() -> None:
    """A .env is data. No substitution, no shelling out."""
    parsed = parse_env_file("A=$(whoami)\nB=${HOME}\nC=`id`\n")

    assert parsed == {"A": "$(whoami)", "B": "${HOME}", "C": "`id`"}


def test_an_empty_environment_value_is_ignored(tmp_path: Path) -> None:
    _, sources = settings_at(tmp_path, env={"OMNIAGENT_MODEL": ""})

    assert sources["model"] == "built-in"


# --------------------------------------------------------------------------- #
# refusing bad configuration
# --------------------------------------------------------------------------- #


def test_an_unknown_profile_is_refused_and_lists_the_real_ones(project: Path) -> None:
    with pytest.raises(ConfigError, match="no profile named 'nope'") as caught:
        settings_at(project, profile="nope")

    assert "demo" in str(caught.value)


def test_a_profile_without_a_config_file_is_refused(tmp_path: Path) -> None:
    with pytest.raises(ConfigError, match="needs a config file"):
        settings_at(tmp_path, profile="demo")


def test_a_missing_explicit_config_file_is_refused(tmp_path: Path) -> None:
    with pytest.raises(ConfigError, match="no such config file"):
        settings_at(tmp_path, config_path=tmp_path / "nope.toml")


def test_invalid_toml_is_refused(tmp_path: Path) -> None:
    bad = tmp_path / "bad.toml"
    bad.write_text("this is not = = toml\n", encoding="utf-8")

    with pytest.raises(ConfigError, match="not valid TOML"):
        settings_at(tmp_path, config_path=bad)


def test_an_unknown_setting_in_the_file_is_refused(tmp_path: Path) -> None:
    path = tmp_path / DEFAULT_CONFIG_NAME
    path.write_text('[defaults]\nmodle = "typo"\n', encoding="utf-8")

    with pytest.raises(ConfigError, match="unknown setting") as caught:
        settings_at(tmp_path)

    assert "modle" in str(caught.value)
    assert "model" in str(caught.value), "the error should list what is valid"


def test_an_unknown_setting_in_a_profile_is_refused(tmp_path: Path) -> None:
    path = tmp_path / DEFAULT_CONFIG_NAME
    path.write_text("[profile.x]\nnonsense = 1\n", encoding="utf-8")

    with pytest.raises(ConfigError, match="unknown setting"):
        settings_at(tmp_path, profile="x")


def test_an_out_of_range_value_is_refused_naming_its_source(tmp_path: Path) -> None:
    path = tmp_path / DEFAULT_CONFIG_NAME
    path.write_text("[defaults]\nmax_steps = 999\n", encoding="utf-8")

    with pytest.raises(ConfigError, match="invalid settings") as caught:
        settings_at(tmp_path)

    assert "max_steps" in str(caught.value)
    assert "file:defaults" in str(caught.value)


def test_a_bad_log_level_is_refused(tmp_path: Path) -> None:
    with pytest.raises(ConfigError, match="not one of"):
        settings_at(tmp_path, env={"OMNIAGENT_LOG_LEVEL": "LOUD"})


def test_a_log_level_is_normalised_to_upper_case(tmp_path: Path) -> None:
    settings, _ = settings_at(tmp_path, env={"OMNIAGENT_LOG_LEVEL": "debug"})

    assert settings.log_level == "DEBUG"


def test_a_non_table_section_is_refused(tmp_path: Path) -> None:
    path = tmp_path / DEFAULT_CONFIG_NAME
    path.write_text('defaults = "not a table"\n', encoding="utf-8")

    with pytest.raises(ConfigError, match="must be a table"):
        settings_at(tmp_path)


def test_an_empty_profile_is_allowed(project: Path) -> None:
    settings, sources = settings_at(project, profile="empty")

    assert settings.model == "from-defaults"
    assert sources["model"] == "file:defaults"


# --------------------------------------------------------------------------- #
# types and conversion
# --------------------------------------------------------------------------- #


def test_environment_strings_are_coerced_to_the_right_types(tmp_path: Path) -> None:
    settings, _ = settings_at(
        tmp_path,
        env={
            "OMNIAGENT_MAX_STEPS": "11",
            "OMNIAGENT_TEMPERATURE": "0.4",
            "OMNIAGENT_LOG_CONSOLE": "true",
            "OMNIAGENT_LOG_FILE": "logs/run.jsonl",
        },
    )

    assert settings.max_steps == 11
    assert settings.temperature == pytest.approx(0.4)
    assert settings.log_console is True
    assert settings.log_file == Path("logs/run.jsonl")


def test_the_agent_config_carries_the_resolved_values(project: Path) -> None:
    settings, _ = settings_at(project, profile="demo", cli={"max_retries": 7})
    agent_config = settings.agent_config()

    assert agent_config.model == "from-profile"
    assert agent_config.max_steps == 4
    assert agent_config.max_retries == 7
    assert agent_config.temperature == pytest.approx(0.0)


def test_the_workspace_defaults_to_the_current_directory(tmp_path: Path) -> None:
    settings, _ = settings_at(tmp_path)

    assert settings.workspace == Path.cwd()


# --------------------------------------------------------------------------- #
# reporting
# --------------------------------------------------------------------------- #


def test_the_rendered_table_never_shows_the_api_key(tmp_path: Path) -> None:
    settings, sources = settings_at(tmp_path, env={"OMNIAGENT_API_KEY": "sk-do-not-print"})
    rendered = render(settings, sources)

    assert "sk-do-not-print" not in rendered
    assert "***redacted***" in rendered


def test_the_rendered_table_covers_every_setting(tmp_path: Path) -> None:
    settings, sources = settings_at(tmp_path)
    rendered = render(settings, sources)

    for field in Settings.model_fields:
        assert field in rendered


def test_the_rendered_table_names_each_source(project: Path) -> None:
    # Override a field each layer owns, leaving max_steps to [defaults] and
    # several others to the built-ins, so every source appears exactly once.
    settings, sources = settings_at(
        project, profile="demo", cli={"timeout": 60.0}, env={"OMNIAGENT_LOG_LEVEL": "DEBUG"}
    )
    rendered = render(settings, sources)

    assert sources["max_steps"] == "file:defaults"
    assert "command line" in rendered
    assert "environment" in rendered
    assert "profile:demo" in rendered
    assert "file:defaults" in rendered
    assert "built-in" in rendered
