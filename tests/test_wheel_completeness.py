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
#: if anything that got loaded resolved out of ``sys.argv[2]``, the checkout.
#: Run under ``-I -S``: ``-I`` drops the cwd, the user site and the
#: environment, and ``-S`` stops ``site`` from processing the ``.pth`` file
#: that installs an editable-install finder pointing at the source tree.
IMPORT_CHILD = """\
import importlib
import sys
from pathlib import Path

unpacked, project_root, module_name = sys.argv[1], sys.argv[2], sys.argv[3]
sys.path[:0] = [unpacked, *sys.argv[4:]]

importlib.import_module(module_name)

root = Path(project_root).resolve()
leaked = []
for module in list(sys.modules.values()):
    origin = getattr(module, "__file__", None)
    if not origin:
        continue
    try:
        resolved = Path(origin).resolve()
    except OSError:
        continue
    if resolved == root or root in resolved.parents:
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


def _import_from_wheel(module_name: str, unpacked: Path) -> subprocess.CompletedProcess[str]:
    """Import one module in a fresh interpreter that cannot see the checkout."""
    return subprocess.run(  # noqa: S603 - fixed interpreter, pytest-owned paths
        [
            sys.executable,
            "-I",
            "-S",
            "-c",
            IMPORT_CHILD,
            str(unpacked),
            str(PROJECT_ROOT),
            module_name,
            *_dependency_paths(),
        ],
        capture_output=True,
        text=True,
        check=False,
    )


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
