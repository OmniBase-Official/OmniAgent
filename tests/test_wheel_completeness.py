r"""The built artifact ships every module it needs, proved against the archive.

The wheel this project builds shipped eight of the repository's nine root
modules on 2026-11-04. ``dataset_provenance.py`` was absent from
``[tool.setuptools] py-modules``, and ``export_dataset.py`` imports
``write_sidecar`` from it at module scope, so ``import export_dataset`` out of
an installed wheel raised ``ModuleNotFoundError``. Nothing in this repository
caught that: mypy's own file list knew about the module, CI installs with
``-e`` -- which puts the checkout on ``sys.path`` and resolves the missing
module from the source tree -- and every other test here imports the checkout
for the same reason.

So this module refuses to look at the checkout when it checks imports. It
builds a wheel from a copy of the tree, unpacks it, and imports each module
the archive contains in a fresh interpreter that has the unpacked wheel on
``sys.path`` and nothing of this project anywhere else -- then fails if any
module that ended up loaded came out of the repository after all. That last
check is the one that matters: ``-I`` alone is not enough, because an editable
install leaves a finder on ``sys.meta_path`` that maps module names straight
back to the checkout, which is a live path into the source tree from inside an
otherwise isolated child.

The module names are read out of the archive rather than written down here. A
list in a test is the same defect one level up, and a stale list is what broke
this in the first place. Nothing assumes the modules are top-level either, so
the same assertions hold if the flat layout ever becomes ``src/omniagent/``.

Marked ``wheel`` so the build can be deselected with ``-m "not wheel"``.
"""

from __future__ import annotations

import shutil
import subprocess
import sys
import sysconfig
import time
import zipfile
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from pathlib import Path, PurePosixPath

import pytest

PROJECT_ROOT = Path(__file__).resolve().parent.parent

#: Written into the tree by a build that was told to work elsewhere. The point
#: of staging the source somewhere else is that these never appear; the
#: assertion exists so a future change back to building in place is caught.
BUILD_LEFTOVERS = ("build", "dist")

#: Root-level files that are build or test machinery by definition rather than
#: modules of the distribution. This is deliberately not a list of the
#: project's own modules -- that kind of list is the defect being fixed.
NOT_DISTRIBUTED = frozenset({"setup.py", "conftest.py"})

#: Imports ``sys.argv[3]`` with ``sys.argv[1]`` (the unpacked wheel) and
#: ``sys.argv[4:]`` (the dependency directories) on ``sys.path``, then fails
#: if anything that got loaded resolved out of ``sys.argv[2]``, the source
#: root, from somewhere it was not handed.
#:
#: Run under ``-I -S``: ``-I`` drops the cwd, the user site and the
#: environment, and ``-S`` stops ``site`` from processing the ``.pth`` file
#: that installs an editable-install finder pointing at the source tree.
#:
#: "Under the source root, and not under a directory it was given" is the
#: boundary, rather than a list of the source files it knows about. The list
#: would be the stale-list defect this whole module exists to catch, one more
#: level up, and it would have to be rewritten the day the layout changes.
#: The cost is that the two allowed sets have to be exactly right -- which is
#: why they have tests of their own at the bottom of this file.
IMPORT_CHILD = """\
import importlib
import sys
from pathlib import Path

unpacked, project_root, module_name = sys.argv[1], sys.argv[2], sys.argv[3]
dependency_paths = sys.argv[4:]
sys.path[:0] = [unpacked, *dependency_paths]

importlib.import_module(module_name)


def _resolve(raw):
    try:
        return Path(raw).resolve()
    except OSError:
        return None


root = _resolve(project_root)

# Everything the child was handed on purpose. The virtualenv normally lives
# at <root>/.venv, so the dependency directories are inside the source root
# and a module resolving out of one of them is an installed wheel finding its
# dependencies, not a leak. The unpacked wheel can be inside the root too,
# whenever pytest's basetemp is (.gitignore records that sandboxed sessions
# put it in .scratch/). Resolved here because sysconfig can hand back a
# non-canonical path while module paths are already canonical.
allowed = [path for path in (_resolve(unpacked), *map(_resolve, dependency_paths)) if path]

leaked = []
for module in list(sys.modules.values()):
    origin = getattr(module, "__file__", None)
    if not origin:
        continue
    resolved = _resolve(origin)
    if resolved is None:
        continue
    if root is None or (resolved != root and root not in resolved.parents):
        continue
    if any(resolved == path or path in resolved.parents for path in allowed):
        continue
    leaked.append(f"{module.__name__} <- {resolved}")

if leaked:
    sys.stderr.write("RESOLVED FROM THE CHECKOUT: " + ", ".join(sorted(leaked)) + "\\n")
    raise SystemExit(3)
"""


@dataclass(frozen=True)
class BuiltWheel:
    """One wheel, built once per session, with what was learned building it."""

    archive: Path
    unpacked: Path
    modules: tuple[str, ...]
    seconds: float
    root_before: tuple[str, ...]


def _dependency_paths() -> list[str]:
    """Where the third-party dependencies live, for a child run under ``-S``.

    ``-S`` is what keeps the editable-install finder out of the child, and it
    also costs it ``site-packages``. The directories go back on ``sys.path``
    by hand, which is not the same thing: putting a directory on ``sys.path``
    does not process the ``.pth`` files inside it.
    """
    paths: list[str] = []
    for key in ("purelib", "platlib"):
        path = sysconfig.get_path(key)
        if path and path not in paths:
            paths.append(path)
    return paths


def _copy_source_tree(destination: Path) -> None:
    """Stage the working tree somewhere the build may write.

    ``pip wheel . -w elsewhere`` still creates ``build/`` in the source tree,
    and a stray ``build/lib/agent.py`` fails ``tests/test_eval_workspace.py``
    -- a test that poisons the suite it belongs to is worse than the defect it
    catches. So the build never sees the checkout. Tracked files plus
    untracked ones git would not ignore: that is the working tree as it
    stands, minus the virtualenvs, the caches and the model checkouts, and it
    keeps meaning the same thing if the layout changes.
    """
    git = shutil.which("git")
    if git is None:
        pytest.skip("needs git to stage the source tree outside the checkout")
    listing = subprocess.run(  # noqa: S603 - fixed argv, no shell, no user input
        [
            git,
            "-C",
            str(PROJECT_ROOT),
            "ls-files",
            "--cached",
            "--others",
            "--exclude-standard",
            "-z",
        ],
        capture_output=True,
        text=True,
        check=True,
    )
    for entry in listing.stdout.split("\0"):
        if not entry:
            continue
        source = PROJECT_ROOT / entry
        if not source.is_file():
            continue
        target = destination / entry
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source, target)


def _modules_in_archive(names: list[str]) -> tuple[str, ...]:
    """The importable module names an archive holds, read out of the archive.

    Nothing here assumes the modules are top-level, so a wheel that ships
    ``omniagent/agent.py`` yields ``omniagent.agent`` and a wheel that ships
    ``agent.py`` yields ``agent``.
    """
    found: set[str] = set()
    for name in names:
        path = PurePosixPath(name)
        if path.suffix != ".py":
            continue
        if any(part.endswith((".dist-info", ".data")) for part in path.parts):
            continue
        parts = list(path.with_suffix("").parts)
        if parts[-1] == "__init__":
            parts.pop()
        if parts:
            found.add(".".join(parts))
    return tuple(sorted(found))


def _modules_in_tree() -> tuple[str, ...]:
    """The importable module names the working tree holds, by the same rule.

    Root-level ``*.py`` today; ``src/`` as well if it ever exists, named
    relative to it, so this keeps meaning the same thing after a move to
    ``src/omniagent/``.
    """
    found = {
        path.stem for path in PROJECT_ROOT.glob("*.py") if path.name not in NOT_DISTRIBUTED
    }
    source_dir = PROJECT_ROOT / "src"
    if source_dir.is_dir():
        for path in source_dir.rglob("*.py"):
            parts = list(path.relative_to(source_dir).with_suffix("").parts)
            if parts and parts[-1] == "__init__":
                parts.pop()
            if parts:
                found.add(".".join(parts))
    return tuple(sorted(found))


def _run_import_child(
    module_name: str,
    unpacked: Path,
    source_root: Path,
    dependency_paths: list[str],
) -> subprocess.CompletedProcess[str]:
    """Run ``IMPORT_CHILD`` against roots the caller chooses.

    Every argument the child decides anything with comes through here, so the
    canary's boundary can be driven over a constructed tree rather than only
    over the real checkout. That matters: the real checkout keeps its
    virtualenv inside ``PROJECT_ROOT``, a git worktree does not, and the one
    bug this test module has shipped was invisible from a worktree for exactly
    that reason.
    """
    return subprocess.run(  # noqa: S603 - fixed interpreter, pytest-owned paths
        [
            sys.executable,
            "-I",
            "-S",
            "-c",
            IMPORT_CHILD,
            str(unpacked),
            str(source_root),
            module_name,
            *dependency_paths,
        ],
        capture_output=True,
        text=True,
        check=False,
    )


def _import_from_wheel(module_name: str, unpacked: Path) -> subprocess.CompletedProcess[str]:
    """Import one module in a fresh interpreter that cannot see the checkout."""
    return _run_import_child(module_name, unpacked, PROJECT_ROOT, _dependency_paths())


@pytest.fixture(scope="session")
def built_wheel(tmp_path_factory: pytest.TempPathFactory) -> BuiltWheel:
    """Build the wheel once, outside the checkout, without the network.

    ``--no-build-isolation`` is the no-network choice: it builds against the
    ``setuptools`` already in this environment instead of fetching a build
    backend. ``--no-index`` says so a second time, and ``--no-cache-dir``
    stops pip handing back a wheel it built earlier -- a cached artifact would
    make this whole module prove nothing.
    """
    workspace = tmp_path_factory.mktemp("wheel")
    staging = workspace / "source"
    staging.mkdir()
    wheelhouse = workspace / "wheelhouse"
    unpacked = workspace / "unpacked"

    root_before = tuple(sorted(path.name for path in PROJECT_ROOT.iterdir()))
    _copy_source_tree(staging)

    started = time.perf_counter()
    done = subprocess.run(  # noqa: S603 - fixed interpreter, pytest-owned paths
        [
            sys.executable,
            "-m",
            "pip",
            "wheel",
            ".",
            "--no-deps",
            "--no-build-isolation",
            "--no-index",
            "--no-cache-dir",
            "--disable-pip-version-check",
            "-w",
            str(wheelhouse),
        ],
        cwd=staging,
        capture_output=True,
        text=True,
        check=False,
    )
    seconds = time.perf_counter() - started
    if done.returncode != 0:
        pytest.fail(f"building the wheel failed:\n{done.stdout}\n{done.stderr}")

    archives = sorted(wheelhouse.glob("*.whl"))
    assert len(archives) == 1, f"expected one wheel, got {[path.name for path in archives]}"

    with zipfile.ZipFile(archives[0]) as archive:
        modules = _modules_in_archive(archive.namelist())
        archive.extractall(unpacked)

    return BuiltWheel(
        archive=archives[0],
        unpacked=unpacked,
        modules=modules,
        seconds=seconds,
        root_before=root_before,
    )


@pytest.mark.wheel
def test_the_wheel_ships_every_module_in_the_tree(built_wheel: BuiltWheel) -> None:
    """Both sides are read off disk. A list written here would go stale too."""
    in_tree = _modules_in_tree()
    missing = sorted(set(in_tree) - set(built_wheel.modules))

    assert not missing, (
        f"the wheel ships {len(built_wheel.modules)} modules and the tree has "
        f"{len(in_tree)}; absent from the archive: {missing}. "
        "Add them to [tool.setuptools] py-modules."
    )


@pytest.mark.wheel
def test_every_module_in_the_wheel_imports_from_the_unpacked_wheel(
    built_wheel: BuiltWheel,
) -> None:
    """The artifact has to stand on its own, with the checkout unreachable."""
    assert built_wheel.modules, "the wheel shipped no modules at all"

    # One interpreter per module, run side by side: each is its own process,
    # so the wall clock is one import rather than the sum of them.
    with ThreadPoolExecutor(max_workers=len(built_wheel.modules)) as pool:
        results = list(
            pool.map(
                lambda name: (name, _import_from_wheel(name, built_wheel.unpacked)),
                built_wheel.modules,
            )
        )

    failures: dict[str, str] = {}
    for module_name, done in results:
        if done.returncode != 0:
            tail = done.stderr.strip().splitlines()
            failures[module_name] = tail[-1] if tail else f"exit {done.returncode}"

    assert not failures, "modules in the wheel that do not import from it: " + "; ".join(
        f"{name}: {reason}" for name, reason in sorted(failures.items())
    )


@pytest.mark.wheel
def test_the_import_child_cannot_reach_the_checkout(built_wheel: BuiltWheel) -> None:
    """The guard on the test above, because an in-process import proves nothing.

    ``tests`` is a package in the repository root that no wheel ships. If the
    child can import it, the child is reading the source tree, and every
    import it reported as working is worthless.
    """
    assert "tests" not in built_wheel.modules, "the wheel should not ship the test suite"

    done = _import_from_wheel("tests", built_wheel.unpacked)

    assert done.returncode != 0, (
        "the child imported the repository's own test package, so it is reading "
        "the checkout rather than the unpacked wheel"
    )
    assert "ModuleNotFoundError" in done.stderr, done.stderr


@pytest.mark.wheel
def test_the_build_leaves_the_checkout_alone(built_wheel: BuiltWheel) -> None:
    """A test that poisons the suite it belongs to is worse than the defect.

    ``build/lib/agent.py`` is a second reachable copy of the agent, and
    ``tests/test_eval_workspace.py`` walks the tree by the sandbox's rules,
    which prune hidden and denied paths -- not gitignored ones.
    """
    for name in BUILD_LEFTOVERS:
        assert not (PROJECT_ROOT / name).exists(), (
            f"the build left {name}/ in the checkout; "
            "it has to run against a staged copy, not the source tree"
        )

    root_after = tuple(sorted(path.name for path in PROJECT_ROOT.iterdir()))

    assert root_after == built_wheel.root_before, (
        "the repository root changed across the build: "
        f"{sorted(set(root_after) - set(built_wheel.root_before))} appeared"
    )


# --------------------------------------------------------------------------- #
# The canary's own tests.
#
# The leak check above is the part of this module that decides whether an
# import proved anything, and it shipped with the wrong boundary: it flagged
# everything under the source root, and the virtualenv lives at
# ``<root>/.venv``, so every third-party module a wheel module imports counted
# as a leak. It passed here and failed on main, because a git worktree has no
# virtualenv inside it -- the end-to-end tests above cannot reproduce that
# from where this branch was written, and did not.
#
# So the boundary gets driven directly, over a tree built for the purpose: a
# source root with a dependency directory inside it, an unpacked wheel inside
# it, and a module hidden somewhere else inside it. No wheel, no build, a
# fifth of a second, and it reproduces anywhere.
# --------------------------------------------------------------------------- #


@dataclass(frozen=True)
class CanaryTree:
    """A source root shaped like the real one: venv and all, inside itself."""

    root: Path
    unpacked: Path
    dependencies: Path


@pytest.fixture
def canary_tree(tmp_path: Path) -> CanaryTree:
    """A source root whose dependency directory and wheel are both inside it."""
    root = tmp_path / "source-root"
    unpacked = root / "unpacked-wheel"
    dependencies = root / ".venv" / "Lib" / "site-packages"
    smuggled = root / "somewhere-else"
    for directory in (unpacked, dependencies, smuggled):
        directory.mkdir(parents=True)

    (dependencies / "pretend_dependency.py").write_text("VALUE = 1\n", encoding="utf-8")
    (unpacked / "lonely.py").write_text("import json  # stdlib only\n", encoding="utf-8")
    (smuggled / "smuggled.py").write_text("VALUE = 2\n", encoding="utf-8")
    (unpacked / "reaches_into_the_tree.py").write_text(
        "import sys\n"
        f"sys.path.insert(0, r{str(smuggled)!r})\n"
        "import smuggled\n",
        encoding="utf-8",
    )

    return CanaryTree(root=root, unpacked=unpacked, dependencies=dependencies)


def test_the_canary_ignores_the_dependency_directories_it_was_handed(
    canary_tree: CanaryTree,
) -> None:
    """``<root>/.venv/Lib/site-packages`` is under the root and is not a leak.

    This is the bug. ``pydantic`` resolving out of the project's own
    virtualenv is how an installed wheel is supposed to find its
    dependencies, and the child is handed those directories itself.
    """
    done = _run_import_child(
        "pretend_dependency",
        canary_tree.unpacked,
        canary_tree.root,
        [str(canary_tree.dependencies)],
    )

    assert done.returncode == 0, (
        "the canary flagged a module from a dependency directory it was handed "
        f"itself:\n{done.stderr}"
    )


def test_the_canary_ignores_the_unpacked_wheel_even_inside_the_source_root(
    canary_tree: CanaryTree,
) -> None:
    """The artifact under test is never the leak, wherever it was unpacked.

    ``tmp_path`` is outside the repository on this machine, but .gitignore
    records that sandboxed sessions put pytest's basetemp in ``.scratch/``
    inside the checkout. There the unpacked wheel is under the source root,
    and the same wrong boundary would call every module in it a leak.
    """
    done = _run_import_child(
        "lonely",
        canary_tree.unpacked,
        canary_tree.root,
        [str(canary_tree.dependencies)],
    )

    assert done.returncode == 0, (
        f"the canary flagged a module from the wheel it was testing:\n{done.stderr}"
    )


def test_the_canary_fires_on_a_module_pulled_in_from_the_source_tree(
    canary_tree: CanaryTree,
) -> None:
    """And the fix must not blind it: this is what it is for.

    ``reaches_into_the_tree`` comes out of the unpacked wheel and pulls in a
    module from elsewhere under the source root -- which is what the editable
    install's finder does to a child run under ``-I`` without ``-S``. Green
    before the boundary was fixed and green after; that is the point.
    """
    done = _run_import_child(
        "reaches_into_the_tree",
        canary_tree.unpacked,
        canary_tree.root,
        [str(canary_tree.dependencies)],
    )

    assert done.returncode != 0, "the canary missed a module from the source tree"
    assert "RESOLVED FROM THE CHECKOUT" in done.stderr, done.stderr
    assert "smuggled" in done.stderr, done.stderr
