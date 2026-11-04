# Brief 17 — the wheel ships what it claims

**Option A of ADR-0002, which the owner accepted on 2026-11-04 as part of
option C.** Static throughout, **no model run**, and it **collides with
nothing in flight**: brief 14 holds `agent.py` and `config.py`, brief 15 holds
a new fixture directory and a new `scripts/` module. This brief touches
`pyproject.toml`, `.gitignore` and one new test module.

**Ask before you take it if you are Codex.** The verification builds a wheel
in a subprocess. The SWE sandbox has not been shown to permit that, and a
brief whose verification cannot run is worse than no brief. Say so in your
first message either way.

## What is measured, 2026-11-04, on `05e99e8`, clean tree

I reproduced every figure below myself; none of it is taken from a report.

| Fact | Value |
| --- | --- |
| modules the wheel ships | **8** — `agent, config, export_dataset, main, observability, sandbox, tools, validate_dataset` |
| modules in the repository root | **9** |
| the missing one | `dataset_provenance.py` |
| who needs it | `export_dataset.py:32` — `from dataset_provenance import write_sidecar` |
| what happens | unpack the wheel outside the checkout, project root off `sys.path`, `python -I -c "import export_dataset"` → **`ModuleNotFoundError: No module named 'dataset_provenance'`** |
| `pyproject.toml:46` `py-modules` | **omits it** |
| `pyproject.toml:166` ruff `known-first-party` | **omits it** |
| `pyproject.toml:55` mypy `files` | **includes it** |
| `.gitignore` | ignores **neither** `build/` nor `dist/` |

**The only list that knows the module exists is the one that cannot ship it.**
That is why `mypy` is clean over 45 files while the artifact is broken, and
why `.github/workflows/ci.yml:37` — which installs with `-e` — cannot see it:
an editable install puts the checkout on `sys.path` and the missing module
resolves from there.

## Goal

The built artifact is complete, and **a test proves it** rather than a person
remembering to check.

## Part 1 — ship the module

1. Add `dataset_provenance` to `py-modules` (`pyproject.toml:46`) and to
   ruff's `known-first-party` (`:166`). The mypy list already has it; leave it
   alone.
2. **Say in `## Result` whether anything else is missing from either list.**
   Two of three lists were wrong about one module; check all nine against the
   tree rather than fixing the one I named.

## Part 2 — `build/` and `dist/` stop poisoning the tree

Add both to `.gitignore`.

**This is necessary and not sufficient, and the difference matters.** The
`tests/test_eval_workspace.py` invariant walks the tree by the *sandbox's*
admission rules, which prune hidden and denied paths — not gitignored ones. So
after this change a stray `build/` **still** fails
`test_the_budget_expectation_is_not_unique_to_its_subject`, because
`build/lib/agent.py` is a second reachable carrier of the log event. I
reproduced that today.

**Do not fix that by editing `scripts/eval_workspace.py`** — it holds the
answer-key seal, it is sealed itself, and three briefs have had to route
around it. Part 3 avoids creating the directory in the first place. If you
believe the seal must learn about build artifacts, **say so in `## Result` and
stop**; it is a design question for the architect, not a line to add here.

## Part 3 — the test that makes this unrepeatable

A test that **builds a wheel and imports every module in it**.

Requirements, and the first two are things I hit today:

1. **Nothing may be left in the checkout.** `pip wheel . -w <elsewhere>`
   still created `build/` in the source tree in my run. Either direct the
   build somewhere else explicitly, or remove what it leaves and **assert the
   tree is clean afterwards**. A test that poisons the suite it belongs to is
   worse than the defect.
2. **No network.** Use `--no-build-isolation` or an equivalent, so the test
   works offline and in CI without fetching build dependencies. Say which you
   chose.
3. **Import from the unpacked wheel with the project root off `sys.path`, in
   a subprocess, under `-I`.** An in-process import finds the checkout and
   proves nothing. This is the whole point of the test.
4. **Every module in the wheel, not a list you wrote down.** Read the names
   out of the archive and import each. A hardcoded list is the same defect one
   level up — it goes stale the moment someone adds a module, which is exactly
   what happened here.
5. **Report the runtime.** My build took a few seconds. A test that adds ten
   seconds to every run gets deleted by someone in six months; if it is slow,
   mark it so it can be selected out, and say how.

## Tests that must fail first

| Test | Must fail before, pass after |
| --- | --- |
| the wheel contains every root module | **it must fail on today's `pyproject.toml`** — run it before Part 1 and paste the failure |
| every module in the wheel imports from the unpacked wheel with the root off `sys.path` | same: fails before Part 1 with the `ModuleNotFoundError` above |
| the tree is clean after the build test runs | new |

**If the first test passes before Part 1, it is not testing the wheel** —
almost certainly it imported the checkout. That is the failure mode to watch.

## Mutations that must go red

Restore from a scratchpad copy, **never `git checkout --` alone**.

| # | Mutation | Must go red |
| --- | --- | --- |
| Ma | Remove `dataset_provenance` from `py-modules` again | both wheel tests |
| Mb | Drop a tenth module into the repository root without touching `pyproject.toml` | the completeness test. **If it stays green, you hardcoded the list** |
| Mc | Make the import check run in-process instead of a subprocess | the import test must stop proving anything — demonstrate that it now passes with `py-modules` broken, and say so |

**Mb and Mc are the ones that matter.** Ma proves the fix; Mb and Mc prove the
*test* is a test.

## Files you may touch

`pyproject.toml` · `.gitignore` · one new test module — name it for what it
does and say what you chose.

## Files you may not touch

`agent.py` · `config.py` and the three test modules brief 14 holds ·
`scripts/**` — **brief 15 is in a new module there** ·
`scripts/eval_workspace.py` above all · `tools.py` · `sandbox.py` ·
`secure_search.py` and its branches · `.github/workflows/**` — **the CI fix is
a separate brief and a separate chair** · `README.md` · `NEXT_CHAT.md` ·
`docs/` except your `## Result`.

**Do not move any module and do not create a package.** That is option B, it
is a separate brief, and it cannot start until brief 14 and the four
`agent.py` defects are merged. **Your test is the instrument that will prove
option B behaviour-free** — the same test, unchanged, must pass against
`src/omniagent/` afterwards. Write it so that is possible: read the module
names from the archive, do not assume they are top-level.

## Gates

```
.venv\Scripts\python.exe -m ruff check .
.venv\Scripts\python.exe -m mypy
.venv\Scripts\python.exe -m pytest
```

Full path, **never your own `-q`** (`pyproject.toml:168` sets it; a second one
deletes the summary line). Baseline **658 passed**, mypy clean over **45**
files, ruff clean. Say what the count moved to.

## Where to work

**Branch from `main` at `05e99e8`, your own worktree, your own branch — never
`main`.** The manager merges. Push with the remote named:
`git push origin <your branch>`.

## The one thing that would make this wrong

**A test that imports the checkout.** Every variant of this defect survives a
test that is accidentally looking at the source tree: the import succeeds, the
test is green, and the wheel is still broken. Mc exists to make you prove it
is not happening, and the "must fail first" row is the other half of the same
proof. **If your new test passes before you fix `pyproject.toml`, delete it
and start again.**

The second way: **hardcoding the module list in the test.** The defect you are
fixing is a list that went stale. A test with its own copy of that list is the
same bug wearing a different hat, and Mb is how you find out you wrote one.

## Commit

```
git add pyproject.toml .gitignore tests/
git commit -m "fix(packaging): the wheel ships every module, and a test proves it"

git add docs/pm/brief-17-the-wheel-ships-what-it-claims.md
git commit -m "docs: brief 17 result -- the artifact is tested now"
```

**Do not run a bare `git push`** — two remotes, and `main` tracks the one this
work does not belong to.

## Result

<!-- Engineer: append here. Whether you are the chair that can build a wheel
in a subprocess; the failure output from each test before Part 1; what else
was missing from either pyproject list; how you kept the build out of the
checkout and how you assert the tree is clean afterwards; whether you used
--no-build-isolation or something else; the runtime the new test adds and how
it can be selected out; Ma, Mb and Mc each with what went red; the three gate
results with the count explained; the branch and commit hashes; and anything
you refuse to claim -- including that the CI fix and the package move are not
yours. -->

**Engineer: Claude (fullstack chair), 2026-11-04. Branch
`brief-17-wheel-completeness`, own worktree, commit `9b14f6b` plus the
commit carrying this report.**

I am not Codex, so the "ask first" clause does not apply: this chair builds a
wheel in a subprocess without difficulty. The build runs in about 3.4 s on
this machine and the import children are ordinary `subprocess.run` calls.

### Two things in the brief that had drifted, before anything else

**The base commit.** Both documents say branch from `main` at `05e99e8`. Both
documents were *added* in `87a1297`, which is after `05e99e8` — so at
`05e99e8` there is no `docs/pm/brief-17-*.md` and no `## Result` heading to
append to. I branched from `108708c` instead, which is what the dispatching
chair told me to use. Everything the brief measures on `05e99e8` still holds
there, exactly, and I re-measured all of it myself rather than quoting it:

| Fact | Brief | Measured on `108708c` |
| --- | --- | --- |
| modules the wheel ships | 8 | **8** |
| modules in the repository root | 9 | **9** |
| the missing one | `dataset_provenance.py` | **confirmed** |
| `pyproject.toml` `py-modules` | `:46` | **line 46, omits it** |
| `pyproject.toml` ruff `known-first-party` | `:166` | **line 166, omits it** |
| `pyproject.toml` mypy `files` | `:55` | **opens at 55, the entry is at 64, present** |
| `.github/workflows/ci.yml` installs `-e` | `:37` | **line 37, `pip install -e ".[dev]"`** |
| `.gitignore` | ignores neither | **confirmed** |
| pytest baseline | 658 passed | **658 passed** |
| mypy | clean over 45 files | **clean over 45 files** |

**The number of commits.** The brief's commit block asks for two (the fix,
then the report); the dispatch message asked for "one commit on your own
branch". I followed the brief. Nothing else in the two documents disagrees on
anything substantive — I read both.

### The defect, reproduced by hand before I wrote a line of test

```
$ .venv\Scripts\python.exe -m pip wheel . --no-deps --no-build-isolation -w <scratch>
Successfully built omniagent          (3.25 s)

$ git status --short
?? build/                              <- left in the source tree, as the brief says

# archive contents: agent.py config.py export_dataset.py main.py
# observability.py sandbox.py tools.py validate_dataset.py  -- eight, no
# dataset_provenance.py

$ python -I -c "import sys; sys.path.insert(0, r'<unpacked>'); import export_dataset"
Traceback (most recent call last):
  File "<string>", line 4, in <module>
  File "<unpacked>\export_dataset.py", line 32, in <module>
    from dataset_provenance import write_sidecar
ModuleNotFoundError: No module named 'dataset_provenance'
```

One correction to the recipe as written: `python -I -c "import export_dataset"`
run from inside the unpacked directory cannot work, because `-I` implies `-P`
and so takes the cwd *off* `sys.path` — it fails with `No module named
'export_dataset'`, which looks like the same bug and is not. The unpacked
directory has to go on `sys.path` explicitly, as above. That is what the test
does.

### The failing output before Part 1

`tests/test_wheel_completeness.py` was written and run first, against the
unfixed `pyproject.toml`:

```
$ .venv\Scripts\python.exe -m pytest tests/test_wheel_completeness.py --durations=5

E  AssertionError: the wheel ships 8 modules and the tree has 9; absent from
E  the archive: ['dataset_provenance']. Add them to [tool.setuptools] py-modules.
E  assert not ['dataset_provenance']
tests\test_wheel_completeness.py:288: AssertionError

E  AssertionError: modules in the wheel that do not import from it:
E  export_dataset: ModuleNotFoundError: No module named 'dataset_provenance'
E  assert not {'export_dataset': "ModuleNotFoundError: No module named 'dataset_provenance'"}
tests\test_wheel_completeness.py:318: AssertionError

FAILED tests/test_wheel_completeness.py::test_the_wheel_ships_every_module_in_the_tree
FAILED tests/test_wheel_completeness.py::test_every_module_in_the_wheel_imports_from_the_unpacked_wheel
2 failed, 2 passed in 6.56s
```

Pasted from a re-run of the committed test file against the pre-Part-1
`py-modules`, so the line numbers match what is on the branch. The first
run — the genuinely-before-the-fix one, written before I had touched
`pyproject.toml` at all — produced the same two assertions word for word and
took 10.50 s, because the imports were still sequential then; concurrency and
the line numbers are the only differences.

The two that passed are the clean-tree assertion and the guard described
below, neither of which is a claim about packaging. After Part 1: **4 passed
in 6.46 s**.

### Part 1 — what else was missing

Nothing. I checked all nine root modules against all three lists rather than
the one name the brief gave me:

| List | Count | Missing from it | Stale entries |
| --- | --- | --- | --- |
| `py-modules` | 8 | `dataset_provenance` | none |
| mypy `files` (root entries) | 9 | — | none |
| ruff `known-first-party` | 8 + `tests` | `dataset_provenance` | none |

`dataset_provenance` is the only name absent from either list, and no list
names a module that is not in the tree. Both lists now carry it; mypy's was
already correct and I left it alone.

### Part 2 — `build/` and `dist/`

Both added to `.gitignore`, with the comment saying why it is not sufficient.
**I do not think the seal must learn about build artifacts, so I have not
stopped** — but the exposure the brief describes is real and unchanged by my
work, and it is worth the architect's attention as a separate question: a
developer who types `pip wheel .` by hand still creates `build/lib/agent.py`
and still fails
`test_the_budget_expectation_is_not_unique_to_its_subject`, and gitignoring it
does not help because the walk prunes by the sandbox's admission rules, not by
git's. My test avoids it by never building in the checkout; nothing protects a
human who does.

### Part 3 — `tests/test_wheel_completeness.py`

Named for what it asserts. Four tests, one session-scoped build.

**How the build stays out of the checkout.** It does not build the checkout at
all. The fixture stages the working tree into a pytest temporary directory —
`git ls-files --cached --others --exclude-standard`, i.e. tracked files plus
untracked ones git would not ignore — and builds there. That is the working
tree as it stands (so a new untracked module is included, which is what makes
mutation Mb bite) minus the virtualenvs, caches and model checkouts, and it
carries no list of paths, so it keeps meaning the same thing if the layout
changes. `test_the_build_leaves_the_checkout_alone` then asserts `build/` and
`dist/` do not exist and that the set of entries in the repository root is
unchanged across the build; the "before" snapshot is taken in the fixture
before the build runs.

**No network.** `--no-build-isolation`, which builds against the `setuptools`
already in the environment instead of fetching a backend. `--no-index` says it
again, and `--no-cache-dir` stops pip returning a wheel it built on an earlier
run — a cached artifact would make the whole module prove nothing. Verified by
running the module with `HTTP_PROXY`/`HTTPS_PROXY` pointed at a dead port
(`127.0.0.1:1`): **4 passed in 6.70 s**.

**The import is a subprocess, under `-I`, with the root off `sys.path`** — and
`-S` as well, which is a finding the brief did not anticipate. `-I` alone is
**not** enough. It drops the cwd, the user site and the environment, but
`site` still processes `.venv`'s `__editable__.omniagent-0.1.0.pth`, which
installs a finder on `sys.meta_path` whose `MAPPING` points module names
straight at `D:\code-project\OmniAgent`. Demonstrated:

```
$ .venv\Scripts\python.exe -I -c "<strip the project off sys.path>; import agent"
  File "D:\code-project\OmniAgent\tools.py", line 28, in <module>   <- the checkout
    from sandbox import (
ModuleNotFoundError: No module named 'sandbox'

$ .venv\Scripts\python.exe -I -S -c "import agent"
ModuleNotFoundError: No module named 'agent'                        <- unreachable
```

So the child runs `-I -S`, with the unpacked wheel first on `sys.path` and the
dependency directories (`sysconfig` `purelib`/`platlib`) after it — putting a
directory on `sys.path` by hand does not process the `.pth` files in it. Belt
and braces, the child also walks `sys.modules` after the import and exits
non-zero if *anything* that got loaded resolved out of the repository root, and
`test_the_import_child_cannot_reach_the_checkout` asserts the child cannot
import the repository's own `tests` package — a thing no wheel ships, so it is
a permanent canary rather than a check that goes stale.

**Every module in the archive, read out of the archive.** `zipfile.namelist()`,
skipping `*.dist-info/` and `*.data/`, path separators turned into dots and a
trailing `__init__` dropped. Nothing assumes top-level: `omniagent/agent.py`
yields `omniagent.agent`. The tree side is built by the same rule — root
`*.py` today, and `src/**/*.py` named relative to `src/` if that directory
ever exists — so the same four tests, unchanged, should hold against
`src/omniagent/` after option B. The only names excluded are `setup.py` and
`conftest.py`, which are build and test machinery by definition; that is
deliberately not a list of the project's own modules.

**Runtime.** About **5 s** added to a full run on this machine: 3.4 s build,
1.5 s for the imports, the rest negligible. The imports run concurrently in a
`ThreadPoolExecutor` — one process per module, so the wall clock is one import
rather than the sum of nine; sequentially it was 4.7 s and the module took
10.5 s. All four tests carry a `wheel` marker, registered under
`[tool.pytest.ini_options] markers` (`--strict-markers` is on, so it had to
be), and deselect cleanly:

```
$ .venv\Scripts\python.exe -m pytest -m "not wheel"
658 passed, 4 deselected in 11.09s
```

That last line is also the cleanest proof that the brief's 658 baseline is
current and that my change adds four tests and alters none.

### Mutations

Restored from copies in a scratch directory outside the repository, never
`git checkout --` alone, and each patch asserted its target string was present
before replacing it.

| # | Mutation | Result |
| --- | --- | --- |
| **Ma** | `dataset_provenance` removed from `py-modules` again | **both wheel tests red** — `absent from the archive: ['dataset_provenance']` and `export_dataset: ModuleNotFoundError: No module named 'dataset_provenance'`. `2 failed, 2 passed` |
| **Mb** | tenth root module `tenth_module.py` added, `pyproject.toml` untouched | **completeness test red** — `the wheel ships 9 modules and the tree has 10; absent from the archive: ['tenth_module']`. `1 failed, 3 passed`. The list is not hardcoded |
| **Mc** | the import check made in-process, **on top of Ma** | **the import test went green with `py-modules` broken** — `test_every_module_in_the_wheel_imports_from_the_unpacked_wheel` passed while the wheel was genuinely missing `dataset_provenance`, because the in-process interpreter has the checkout on `sys.path` via pytest's `pythonpath = ["."]`. It proves exactly nothing. **The guard caught it**: `test_the_import_child_cannot_reach_the_checkout` failed with *"the child imported the repository's own test package, so it is reading the checkout rather than the unpacked wheel"* |

Mc is the one that justifies the design. An in-process import is not a weaker
version of this test; it is a green light over a broken artifact.

### Gates

Full interpreter path, no `-q` of my own.

| Gate | Result |
| --- | --- |
| `.venv\Scripts\python.exe -m ruff check .` | `All checks passed!` |
| `.venv\Scripts\python.exe -m mypy` | `Success: no issues found in 46 source files` |
| `.venv\Scripts\python.exe -m pytest` | **`662 passed in 15.41s`** |

**658 → 662.** The four are the new module's own tests and nothing else moved;
`-m "not wheel"` gives exactly 658. **45 → 46 files** for mypy: the new test
module, which `files = [..., "tests"]` already covers. `git status` after the
full suite shows only my three files and no `build/` or `dist/`.

### What I refuse to claim

- **That the wheel is installable, or that its dependency metadata is right.**
  I import out of an unpacked archive with `purelib`/`platlib` handed to the
  child by hand. `openai` and `pydantic` came from this environment, not from
  anything the wheel declares. A wrong pin in `dependencies` would not show up
  here.
- **That the test covers anything but importable `.py` modules.** Entry
  points, `package-data`, `*.pyi`, a `py.typed`, console scripts: all outside
  it. The archive is read for `.py` entries only.
- **That it works without `git`.** `shutil.which("git")` returning `None` is a
  `pytest.skip` with a stated reason, not a failure. CI has git; a stripped
  environment would silently lose the coverage.
- **That it holds against `src/omniagent/`.** I designed both sides of the
  comparison to be layout-agnostic and I believe it does, but I did not build
  option B and run it. That claim belongs to whoever does.
- **That the build is offline in any absolute sense.** `--no-index` and
  `--no-build-isolation` forbid the index, and the module passes with a dead
  proxy on `HTTP_PROXY`/`HTTPS_PROXY`. I did not disconnect the network.
- **That the 3.4 s build or the 5 s total hold anywhere but this machine.** CI
  on a cold `setuptools` may differ.
- **That `.github/workflows/ci.yml` is fixed.** It is not, and it is not mine.
  I read line 37 to confirm the `-e` install and touched nothing: CI still
  cannot see this class of defect, because an editable install resolves the
  missing module from the checkout. That is a separate brief and a separate
  chair. The one thing that changed is that `pytest` now catches it, and CI
  runs `pytest`.
- **That option B is done or started.** No module moved, no package created.
  My test is offered as the instrument for proving that move behaviour-free;
  it is not that move.
- **That `tests/test_eval_workspace.py` is now safe from build artifacts.** It
  is not. `.gitignore` does not change what the sandbox walk admits, and a
  hand-run `pip wheel .` still breaks it. Flagged above for the architect, not
  worked around: I did not touch `scripts/eval_workspace.py`.
- **Anything about a model.** No model run was needed and none was done.

### Where it is

Branch `brief-17-wheel-completeness`, cut from `main` at `108708c`, pushed
with `git push origin brief-17-wheel-completeness`. Two commits:
`9b14f6b` (the fix and the test) and this report. Nothing was committed to
`main` and nothing was pushed to `organization`.
