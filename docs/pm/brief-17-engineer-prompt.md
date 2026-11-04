# Brief 17 — the paste-ready task

Paste everything below the line. The companion brief is
`docs/pm/brief-17-the-wheel-ships-what-it-claims.md`; `## Result` goes there.

**Who takes it:** the **fullstack engineer** if that chair is free of brief 15,
otherwise a fresh chat. It collides with nothing in flight. **If it is offered
to Codex, the chair must say in its first message whether its sandbox can
build a wheel in a subprocess** — the verification needs that, and a brief
whose verification cannot run is worse than no brief.

---

You are an **engineer** on OmniAgent, `D:\code-project\OmniAgent`. **Branch
from `main` at `05e99e8`, work in your own worktree, commit to your own branch
— never to `main`.** The manager merges. Push with the remote named:
`git push origin <your branch>` — `main` tracks a second remote and a bare
`git push` goes to the wrong repository. Reply to the owner in **Thai**; code,
commits and reports in **English**.

**Read `docs/pm/brief-17-the-wheel-ships-what-it-claims.md` and execute it.**
Three parts, one commit, a second for your report. **No model run is needed.**

## Why this exists

**The wheel this project builds is broken.** Measured and reproduced by the
manager on `05e99e8`:

- the wheel ships **8** modules; the repository root has **9**;
- the missing one is `dataset_provenance.py`, and `export_dataset.py:32` does
  `from dataset_provenance import write_sidecar`;
- unpack the wheel outside the checkout, put the project root off `sys.path`,
  `python -I -c "import export_dataset"` → **`ModuleNotFoundError: No module
  named 'dataset_provenance'`**;
- `pyproject.toml:46` (`py-modules`) and `:166` (ruff `known-first-party`)
  both omit it; `:55` (mypy `files`) includes it. **The only list that knows
  the module exists is the one that cannot ship it** — which is why mypy is
  clean while the artifact is broken;
- `.github/workflows/ci.yml:37` installs with `-e`, so the checkout is on
  `sys.path` and CI cannot see any of this;
- `.gitignore` ignores neither `build/` nor `dist/`.

## Part 1 — ship the module

Add `dataset_provenance` to `py-modules` and to ruff's `known-first-party`.
The mypy list already has it. **Then check all nine root modules against all
three lists and report anything else that is missing** — two of three lists
were wrong about one module, so do not trust the one name I gave you.

## Part 2 — `build/` and `dist/` go in `.gitignore`

**Necessary and not sufficient.** The `tests/test_eval_workspace.py` invariant
walks the tree by the sandbox's rules, which prune hidden and denied paths,
**not gitignored ones** — so a stray `build/` still fails
`test_the_budget_expectation_is_not_unique_to_its_subject` on
`build/lib/agent.py`. The manager reproduced that today.

**Do not fix that by editing `scripts/eval_workspace.py`.** It holds the
answer-key seal and three briefs have had to route around it. Part 3 avoids
creating the directory at all. If you think the seal must learn about build
artifacts, **say so in `## Result` and stop** — that is the architect's call.

## Part 3 — the test that makes this unrepeatable

A test that **builds a wheel and imports every module in it**:

1. **Nothing left in the checkout.** `pip wheel . -w <elsewhere>` still
   created `build/` in the source tree in the manager's run. Direct the build
   elsewhere or clean up what it leaves, and **assert the tree is clean
   afterwards**.
2. **No network** — `--no-build-isolation` or an equivalent. Say which.
3. **Import from the unpacked wheel, project root off `sys.path`, in a
   subprocess, under `-I`.** An in-process import finds the checkout and
   proves nothing.
4. **Every module in the archive, read out of the archive.** A hardcoded list
   is the same defect one level up — a list that goes stale is exactly what
   broke this.
5. **Report the runtime** and, if it is slow, how it can be selected out.

## Must fail first

Run the new tests **before** Part 1 and paste the failures. **If the
completeness test passes before Part 1, it is not testing the wheel** — it
imported the checkout. That is the failure mode to watch for.

## Mutations — restore from a scratchpad copy, never `git checkout --` alone

Ma remove `dataset_provenance` from `py-modules` again → both wheel tests red ·
**Mb drop a tenth module into the root without touching `pyproject.toml`** →
the completeness test must go red; if it stays green you hardcoded the list ·
**Mc make the import check run in-process** → it must stop proving anything;
show that it then passes with `py-modules` broken.

**Mb and Mc are the ones that matter.** Ma proves the fix; Mb and Mc prove the
test is a test.

## Files you may touch

`pyproject.toml` · `.gitignore` · one new test module.

## Files you may not touch

`agent.py`, `config.py` and brief 14's three test modules · `scripts/**`
(**brief 15 is in a new module there**), and `scripts/eval_workspace.py` above
all · `tools.py` · `sandbox.py` · `secure_search.py` and its branches ·
`.github/workflows/**` — **the CI fix is a separate brief and a separate
chair** · `README.md` · `NEXT_CHAT.md` · `docs/` except your `## Result`.

**Do not move any module and do not create a package.** That is option B of
ADR-0002, a separate brief, and it cannot start until brief 14 and the four
`agent.py` defects are merged. **Your test is the instrument that will prove
option B behaviour-free**: the same test, unchanged, must pass against
`src/omniagent/` afterwards. Write it so that is possible — read the names
from the archive and do not assume they are top-level.

## Gates

```
.venv\Scripts\python.exe -m ruff check .
.venv\Scripts\python.exe -m mypy
.venv\Scripts\python.exe -m pytest
```

Full path, **never your own `-q`**. Baseline **658 passed**, mypy clean over
**45** files, ruff clean. Say what the count moved to.

## Commits

```
git add pyproject.toml .gitignore tests/
git commit -m "fix(packaging): the wheel ships every module, and a test proves it"

git add docs/pm/brief-17-the-wheel-ships-what-it-claims.md
git commit -m "docs: brief 17 result -- the artifact is tested now"
```

## The one thing that would make this wrong

**A test that imports the checkout.** Every variant of this defect survives a
test that is accidentally looking at the source tree: the import succeeds, the
test is green, the wheel is still broken. **If your new test passes before you
fix `pyproject.toml`, delete it and start again.**

The second way: **hardcoding the module list in the test.** The defect you are
fixing is a list that went stale; a test carrying its own copy of that list is
the same bug in a different hat.
