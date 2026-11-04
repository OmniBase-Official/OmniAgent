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
