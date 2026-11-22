"""``pyproject.toml`` must list every module the shipped modules import.

``tests/test_wheel_install.py`` proves this end to end but is skipped wherever
the build tools are missing. This one needs only the repository: a flat-layout
wheel ships exactly the modules in ``py-modules``, so a module that one of them
imports but that is not listed installs fine and fails on first import. The same
goes for ``[tool.mypy] files``: an unlisted module is not type-checked.
"""

from __future__ import annotations

import ast
import tomllib
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent


def _pyproject() -> dict[str, Any]:
    with (ROOT / "pyproject.toml").open("rb") as handle:
        return tomllib.load(handle)


def py_modules() -> list[str]:
    modules: list[str] = _pyproject()["tool"]["setuptools"]["py-modules"]
    return modules


def local_imports(module: str) -> set[str]:
    """Top-level repository modules that ``module`` imports (absolute imports only)."""
    tree = ast.parse((ROOT / f"{module}.py").read_text(encoding="utf-8"))
    names: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            names.update(alias.name.split(".")[0] for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.level == 0 and node.module:
            names.add(node.module.split(".")[0])
    return {name for name in names if (ROOT / f"{name}.py").is_file()}


def test_every_listed_module_exists() -> None:
    assert [m for m in py_modules() if not (ROOT / f"{m}.py").is_file()] == []


def test_every_local_import_of_a_shipped_module_is_shipped() -> None:
    listed = set(py_modules())
    missing = {
        f"{module} imports {name}"
        for module in sorted(listed)
        for name in sorted(local_imports(module) - listed)
    }
    assert missing == set()


def test_every_shipped_module_is_type_checked() -> None:
    checked: set[str] = set(_pyproject()["tool"]["mypy"]["files"])
    assert [m for m in py_modules() if f"{m}.py" not in checked] == []
