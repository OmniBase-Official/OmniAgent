"""Tests for static, sandboxed configuration-precedence inspection."""

from __future__ import annotations

import os
from collections.abc import Iterator
from pathlib import Path
from textwrap import dedent

import pytest

from agent import AgentConfig, ReActAgent
from sandbox import Workspace, get_workspace, set_workspace
from tests.fakes import FakeOpenAI
from tools import inspect_config_precedence, inspect_default_model_cli, run_tool

RESOLVER_SOURCE = dedent(
    '''\
    DEFAULT_ENV_NAME = ".env"

    def resolve(file_path, profile, use_env_file, defaults, selected, env_file, process_env, cli):
        layers = []
        if file_path is not None:
            layers.append(("file:defaults", defaults))
            if profile:
                layers.append((f"profile:{profile}", selected))
        if use_env_file:
            layers.append((f"{DEFAULT_ENV_NAME} file", env_file))
        layers.append(("environment", process_env))
        layers.append(("command line", cli))

        merged = {}
        sources = {}
        for name, values in layers:
            for field, value in values.items():
                merged[field] = value
                sources[field] = name
        return merged
    '''
)

MODEL_MAIN_SOURCE = (
    "def parse_args(argv=None):\n"
    "    parser = argparse.ArgumentParser()\n"
    '    settings = parser.add_argument_group("settings")\n'
    '    settings.add_argument("--model")\n'
    "    args = parser.parse_args(argv)\n"
    "    return args\n"
    "def cli_settings(args):\n"
    '    supplied: dict = {name: getattr(args, name) for name in ("model",) '
    "if getattr(args, name) is not None}\n"
    "    return supplied\n"
    "def main(argv=None):\n"
    "    args = parse_args(argv)\n"
    "    try:\n"
    "        result = resolve(cli_settings(args))\n"
    "    except Exception:\n"
    "        return 2\n"
    "    return result\n"
)


@pytest.fixture
def config_workspace(tmp_path: Path) -> Iterator[Workspace]:
    root = tmp_path / "workspace"
    root.mkdir()
    (root / "config.py").write_text(RESOLVER_SOURCE, encoding="utf-8")
    (root / ".hidden.py").write_text(RESOLVER_SOURCE, encoding="utf-8")
    (root / "credentials").write_text(RESOLVER_SOURCE, encoding="utf-8")
    workspace = Workspace.at(root)
    previous = get_workspace()
    set_workspace(workspace)
    try:
        yield workspace
    finally:
        set_workspace(previous)


def _source_line(snippet: str) -> int:
    return RESOLVER_SOURCE.splitlines().index(snippet) + 1


def test_config_layer_order_guards_and_merge_overwrite_are_reported(
    config_workspace: Workspace,
) -> None:
    report = inspect_config_precedence("config.py")

    expected_labels = [
        "'file:defaults' (file layer)",
        "'profile:{profile}' (configuration layer)",
        "'.env file' (file layer)",
        "'environment' (process environment)",
        "'command line' (configuration layer)",
    ]
    positions = [report.index(label) for label in expected_labels]
    assert positions == sorted(positions)

    defaults_line = _source_line('        layers.append(("file:defaults", defaults))')
    profile_line = _source_line('            layers.append((f"profile:{profile}", selected))')
    env_file_line = _source_line('        layers.append((f"{DEFAULT_ENV_NAME} file", env_file))')
    process_env_line = _source_line('    layers.append(("environment", process_env))')
    cli_line = _source_line('    layers.append(("command line", cli))')
    merge_line = _source_line("            merged[field] = value")

    assert f"line {defaults_line}; if file_path is not None" in report
    assert f"line {profile_line}; if file_path is not None; if profile" in report
    assert f"line {env_file_line}; if use_env_file" in report
    assert f"line {process_env_line}; unconditional" in report
    assert f"line {cli_line}; unconditional" in report
    assert f"line {merge_line}: merged[field] = value" in report
    assert "later layer overrides an earlier value" in report


def test_config_precedence_dispatch_is_registered_and_never_executes_source(
    config_workspace: Workspace,
) -> None:
    source_path = config_workspace.root / "config.py"
    source_path.write_text(
        'raise RuntimeError("source must not execute")\n' + RESOLVER_SOURCE,
        encoding="utf-8",
    )

    report = run_tool("inspect_config_precedence", "config.py")

    assert not report.startswith("Error:")
    assert "'command line' (configuration layer)" in report


def test_config_precedence_request_routes_to_static_tool_in_one_step(
    config_workspace: Workspace,
) -> None:
    fake = FakeOpenAI(replies=[])
    agent = ReActAgent(
        config=AgentConfig(verbose=False),
        client=fake.as_client(),
        printer=lambda _: None,
    )

    answer = agent.run("Trace the configuration precedence in config.resolve().")

    assert fake.calls == []
    assert len(agent.last_trace) == 1
    assert agent.last_trace[0].action == "inspect_config_precedence"
    assert answer.index("'file:defaults'") < answer.index("'profile:{profile}'")
    assert answer.index("'.env file'") < answer.index("'environment'")
    assert answer.index("'environment'") < answer.index("'command line'")
    assert "if file_path is not None" in answer
    assert "if profile" in answer
    assert "if use_env_file" in answer
    assert "later layer overrides an earlier value" in answer


def test_non_precedence_config_question_stays_in_the_react_loop() -> None:
    fake = FakeOpenAI(replies=["Thought: done\nFinal Answer: It validates settings."])
    agent = ReActAgent(
        config=AgentConfig(verbose=False),
        client=fake.as_client(),
        printer=lambda _: None,
    )

    answer = agent.run("What does config.resolve validate?")

    assert answer == "It validates settings."
    assert fake.calls
    assert not agent.last_trace[0].action


def test_compound_default_model_cli_precedence_request_gets_all_evidence(
    config_workspace: Workspace,
) -> None:
    (config_workspace.root / "agent.py").write_text(
        'DEFAULT_MODEL = "fallback:1b"\n', encoding="utf-8"
    )
    (config_workspace.root / "omniagent.toml").write_text(
        '[defaults]\nmodel = "configured:2b"\n', encoding="utf-8"
    )
    (config_workspace.root / "main.py").write_text(MODEL_MAIN_SOURCE, encoding="utf-8")
    fake = FakeOpenAI(replies=[])
    agent = ReActAgent(
        config=AgentConfig(verbose=False),
        client=fake.as_client(),
        printer=lambda _: None,
    )

    answer = agent.run(
        "Trace the default model and CLI --model override precedence in config.resolve()."
    )

    assert fake.calls == []
    assert len(agent.last_trace) == 1
    assert "DEFAULT_MODEL = 'fallback:1b'" in answer
    assert "[defaults].model = 'configured:2b'" in answer
    assert "parser declares --model" in answer
    assert "cli_settings forwards args.model" in answer
    assert "resolve() receives cli_settings(args) as CLI overrides" in answer
    assert "'command line'" in answer
    assert "later layer overrides an earlier value" in answer
    assert answer.count("Configuration layers in append order:") == 1


@pytest.mark.parametrize(
    "source",
    [
        MODEL_MAIN_SOURCE.replace(
            "if getattr(args, name) is not None", "if name != 'model'"
        ),
        MODEL_MAIN_SOURCE.replace(
            "def main(argv=None):\n"
            "    args = parse_args(argv)\n"
            "    try:\n"
            "        result = resolve(cli_settings(args))\n"
            "    except Exception:\n"
            "        return 2\n"
            "    return result\n",
            "def main(argv=None):\n"
            "    return 0\n"
            "def unused():\n"
            "    args = parse_args([])\n"
            "    return resolve(cli_settings(args))\n",
        ),
        MODEL_MAIN_SOURCE.replace("    return args\n", "    return Namespace()\n"),
        MODEL_MAIN_SOURCE.replace(
            '    settings = parser.add_argument_group("settings")\n'
            '    settings.add_argument("--model")\n',
            '    other = argparse.ArgumentParser()\n'
            '    other.add_argument("--model")\n'
            '    settings = parser.add_argument_group("settings")\n',
        ),
        MODEL_MAIN_SOURCE.replace(
            '    settings.add_argument("--model")\n',
            '    if False:\n        settings.add_argument("--model")\n',
        ),
        MODEL_MAIN_SOURCE.replace(
            '    settings.add_argument("--model")\n',
            '    if include_model:\n        settings.add_argument("--model")\n',
        ),
        MODEL_MAIN_SOURCE.replace(
            '    settings = parser.add_argument_group("settings")\n',
            '    other = argparse.ArgumentParser()\n'
            '    settings = other.add_argument_group("settings")\n',
        ),
        MODEL_MAIN_SOURCE.replace(
            '    settings = parser.add_argument_group("settings")\n',
            '    settings = parser.add_argument_group("settings")\n'
            '    other = ArgumentParser()\n'
            '    settings = other.add_argument_group("decoy")\n',
        ),
        MODEL_MAIN_SOURCE.replace(
            "def main(argv=None):\n"
            "    args = parse_args(argv)\n"
            "    try:\n"
            "        result = resolve(cli_settings(args))\n"
            "    except Exception:\n"
            "        return 2\n"
            "    return result\n",
            "def main(argv=None):\n"
            "    args = parse_args(argv)\n"
            "    return 0\n"
            "    try:\n"
            "        result = resolve(cli_settings(args))\n"
            "    except Exception:\n"
            "        return 2\n"
            "    return result\n",
        ),
    ],
    ids=[
        "filters-out-model", "dead-disconnected-chain", "empty-namespace",
        "different-parser-alias", "group-from-different-parser", "group-rebound-to-decoy",
        "false-flag-branch", "conditional-flag", "unreachable-resolve",
    ],
)
def test_default_model_cli_evidence_fails_closed_on_invalid_wiring(
    config_workspace: Workspace, source: str
) -> None:
    (config_workspace.root / "agent.py").write_text(
        'DEFAULT_MODEL = "fallback:1b"\n', encoding="utf-8"
    )
    (config_workspace.root / "omniagent.toml").write_text(
        '[defaults]\nmodel = "configured:2b"\n', encoding="utf-8"
    )
    (config_workspace.root / "main.py").write_text(source, encoding="utf-8")

    assert inspect_default_model_cli().startswith("Error:")


@pytest.mark.parametrize("path", ["../outside.py", ".hidden.py", "credentials"])
def test_config_precedence_respects_workspace_path_denials(
    config_workspace: Workspace, path: str
) -> None:
    assert inspect_config_precedence(path).startswith("Error:")


def test_config_precedence_respects_workspace_size_limit(
    config_workspace: Workspace,
) -> None:
    oversized = config_workspace.root / "oversized.py"
    oversized.write_text("#" + "x" * 100_000, encoding="utf-8")

    result = inspect_config_precedence("oversized.py")

    assert result.startswith("Error:")
    assert "over the 100000-byte limit" in result


def test_config_precedence_rejects_hard_linked_source(
    config_workspace: Workspace, tmp_path: Path
) -> None:
    external = tmp_path / "outside.py"
    external.write_text(RESOLVER_SOURCE, encoding="utf-8")
    alias = config_workspace.root / "linked.py"
    try:
        os.link(external, alias)
    except OSError as exc:
        pytest.skip(f"creating a hard link is unavailable: {exc}")

    result = inspect_config_precedence("linked.py")

    assert result.startswith("Error:")
    assert "hard-linked files" in result


def test_config_precedence_rejects_malformed_or_unsupported_source(
    config_workspace: Workspace,
) -> None:
    source_path = config_workspace.root / "config.py"
    source_path.write_text("def resolve(:\n    pass\n", encoding="utf-8")
    assert "malformed Python source" in inspect_config_precedence("config.py")

    source_path.write_text(
        "def resolve():\n"
        "    layers = []\n"
        "    layers.append((make_label(), {}))\n"
        "    for name, values in layers:\n"
        "        for field, value in values.items():\n"
        "            merged[field] = value\n",
        encoding="utf-8",
    )
    result = inspect_config_precedence("config.py")
    assert result.startswith("Error:")


@pytest.mark.parametrize(
    "replacement",
    [
        "            if field not in merged:\n                merged[field] = value",
        "            if value:\n                merged[field] = value",
    ],
    ids=["first-write-wins", "conditional-assignment"],
)
def test_config_precedence_rejects_conditional_merge_assignment(
    config_workspace: Workspace, replacement: str
) -> None:
    source_path = config_workspace.root / "config.py"
    source_path.write_text(
        RESOLVER_SOURCE.replace("            merged[field] = value", replacement),
        encoding="utf-8",
    )

    result = inspect_config_precedence("config.py")

    assert result.startswith("Error:")


@pytest.mark.parametrize(
    "mutation",
    [
        "    layers.reverse()\n",
        "    layers.sort()\n",
        "    layers.insert(0, (\"new\", {}))\n",
        "    layers.extend([])\n",
        "    layers = []\n",
        "    alias = layers\n",
    ],
    ids=["reverse", "sort", "insert", "extend", "reassignment", "alias"],
)
def test_config_precedence_rejects_layer_mutation_or_reassignment(
    config_workspace: Workspace, mutation: str
) -> None:
    source_path = config_workspace.root / "config.py"
    source_path.write_text(
        RESOLVER_SOURCE.replace("    merged = {}\n", mutation + "    merged = {}\n"),
        encoding="utf-8",
    )

    result = inspect_config_precedence("config.py")

    assert result.startswith("Error:")


def test_config_precedence_rejects_return_before_merge(config_workspace: Workspace) -> None:
    source_path = config_workspace.root / "config.py"
    source_path.write_text(
        RESOLVER_SOURCE.replace(
            "    for name, values in layers:\n",
            "    return merged\n    for name, values in layers:\n",
        ),
        encoding="utf-8",
    )

    assert inspect_config_precedence("config.py").startswith("Error:")


@pytest.mark.parametrize(
    "injected",
    [
        "    eval('layers.reverse()')\n",
        "    exec('merged.clear()')\n",
        "    from builtins import eval as run\n    run('layers.reverse()')\n",
        "    getattr(layers, 'reverse')()\n",
        "    import importlib\n    importlib.import_module('builtins').eval('layers.reverse()')\n",
        "    mutate(locals())\n",
        "    mutate(layers)\n",
        "    mutate(merged)\n",
    ],
    ids=[
        "eval", "exec", "eval-alias", "getattr", "importlib", "locals",
        "opaque-layer-call", "opaque-merged-call",
    ],
)
def test_config_precedence_rejects_dynamic_or_opaque_mutation(
    config_workspace: Workspace, injected: str
) -> None:
    source_path = config_workspace.root / "config.py"
    source_path.write_text(
        RESOLVER_SOURCE.replace(
            "    for name, values in layers:\n",
            injected + "    for name, values in layers:\n",
        ),
        encoding="utf-8",
    )

    assert inspect_config_precedence("config.py").startswith("Error:")


def test_guarded_profile_abort_is_reported_before_layer_construction(
    config_workspace: Workspace,
) -> None:
    source = RESOLVER_SOURCE.replace(
        "    if use_env_file:\n",
        "    elif profile:\n        raise ValueError(\"profile needs a config file\")\n"
        "    if use_env_file:\n",
        1,
    )
    (config_workspace.root / "config.py").write_text(source, encoding="utf-8")

    report = inspect_config_precedence("config.py")

    assert not report.startswith("Error:")
    assert "when file_path is None and profile is set" in report
    assert "raises ValueError and returns no resolved settings" in report


@pytest.mark.parametrize(
    "injected",
    [
        "    raise ValueError('unconditional')\n",
        "    runner = __builtins__['eval']\n    runner('layers.reverse()')\n",
        "    if profile:\n        raise ValueError('unrelated guard')\n",
        "    if file_path is not None:\n"
        "        layers.append(('before-error', defaults))\n"
        "        raise ValueError('after append')\n",
    ],
    ids=["unconditional", "builtins-eval-alias", "unrelated-guard", "after-append"],
)
def test_config_precedence_rejects_unsupported_early_raise_paths(
    config_workspace: Workspace, injected: str
) -> None:
    source_path = config_workspace.root / "config.py"
    source_path.write_text(
        RESOLVER_SOURCE.replace(
            "    for name, values in layers:\n",
            injected + "    for name, values in layers:\n",
        ),
        encoding="utf-8",
    )

    assert inspect_config_precedence("config.py").startswith("Error:")


def test_config_precedence_rejects_unrelated_raise_before_initialization(
    config_workspace: Workspace,
) -> None:
    source_path = config_workspace.root / "config.py"
    source_path.write_text(
        RESOLVER_SOURCE.replace(
            "    layers = []\n",
            "    if profile:\n        raise ValueError('unrelated')\n    layers = []\n",
            1,
        ),
        encoding="utf-8",
    )

    assert inspect_config_precedence("config.py").startswith("Error:")
