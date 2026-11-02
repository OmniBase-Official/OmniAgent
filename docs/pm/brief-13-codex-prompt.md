# Brief 13 — the paste-ready task for the security engineer

Paste everything below the line. The companion brief is
`docs/pm/brief-13-the-junction-refusal-becomes-a-test.md`; `## Result` goes
there.

---

You are the **security engineer** on OmniAgent, `D:\code-project\OmniAgent`,
branch `main`, HEAD `af7daa9`. Baseline, re-run by the manager today: **656
tests passing**, `ruff` clean, `mypy` strict clean over 44 files, tree clean.

**Read `docs/pm/brief-13-the-junction-refusal-becomes-a-test.md` and execute
it.** One test commit, one report commit. **No model run is needed, and no
production code changes in this brief at all** — if you find yourself editing
`sandbox.py` or `tools.py`, stop and report it.

## Why this exists

Brief 11 is merged. The reparse-point check in `tools.py:_searchable_files` is
now the only thing stopping a hostile tree — a cloned repo or an unpacked
archive containing a junction aimed outside the workspace — from being walked
out of. Measured by the manager on 2026-11-02:

| | Result |
| --- | --- |
| guard in place | `No match ... (1 files searched)` |
| guard removed | `1 match ... jump/secret.txt:1: marker-outside-...` — **the outside marker leaks** |

**Its only test is a manager running `mklink /J` by hand in a scratchpad.** If
the guard were deleted tomorrow the suite would stay green at 656.

## The hazard, and it is the whole brief

**A skipped security test is a green gate that proves nothing.**

- A **junction needs no administrator rights** (`mklink /J` worked in an
  ordinary shell on this machine today). **On Windows this test must not be
  skippable: if the junction cannot be built, the test fails and says why.**
- A **symlink** usually does need the privilege or Developer Mode. That test
  may skip, and the skip reason must name the privilege.
- On POSIX the symlink test is the unconditional one.

Whatever the platform, **at least one refusal test runs unconditionally and
fails on a leak.**

## What the test asserts

Fixture in `tmp_path`, never in the repository: an outside directory holding a
marker file, a workspace holding one ordinary file **without** the marker, and
a junction (and a symlink where possible) from inside to outside. Then, through
`tools.search_text` against a `Workspace` at the fixture root — **not by
calling the private walk** — assert that

1. the marker does not appear in the output,
2. the searched-file count equals the number of real files, so the branch was
   pruned rather than walked and filtered,
3. **a directory inside the workspace is still walked normally.**

Point 3 is not optional. A test that would also pass if `search_text` returned
nothing is the defect this project keeps finding in its own instruments.

## The mutation, run against the committed test

Remove the reparse-point condition in a **scratchpad copy** of `tools.py`,
restore by copying back — **never `git checkout --` alone** — and show the new
test going red, then green again with the file's hash matching before and
after. **If it stays green with the guard removed, the test is wrong, and that
is the finding to report rather than something to patch around.**

Mb: write the marker into the inside file too, and confirm the test still
distinguishes. If it cannot, the assertion is on the wrong thing.

## Report

Whether each fixture built and the exact privilege missing if not; which test
file you chose and why; **how much runtime the new tests add** — a fixture
that costs three seconds every run gets deleted by someone in six months;
Ma and Mb with `tools.py`'s hash before and after; the three gates with the
count explained.

## Files you may touch

`tests/test_search_text_pruning.py`, or a new `tests/test_link_refusals.py` —
your call, say which and why. Nothing else.

## Files you may not touch

**`tools.py` and `sandbox.py` above all.** Also `agent.py` · `scripts/**` ·
`eval-fixture/**` · `questions/**` · `models/**` · `data/**` ·
`omniagent-core/**` · `.github/workflows/**` · `NEXT_CHAT.md` · `README.md` ·
`docs/` except your `## Result`.

**`secure_search.py` is not being merged** — the owner's ruling of
2026-11-02, recorded in
`docs/pm/threat-model-2026-11-02-the-search-boundary.md`. Do not import it,
port from it, or build toward it. If you think a test here is better served by
something in it, say so in `## Result` and leave the code alone.

## Gates

```
.venv\Scripts\python.exe -m ruff check .
.venv\Scripts\python.exe -m mypy
.venv\Scripts\python.exe -m pytest
```

Full path, **never your own `-q`**. Baseline **656 passed**, mypy clean over
**44** files.

## Commits

```
git add tests/
git commit -m "test: a hostile tree cannot walk out of the workspace"

git add docs/pm/brief-13-the-junction-refusal-becomes-a-test.md
git commit -m "docs: brief 13 result -- the junction refusal has a test now"
```

**Do not run a bare `git push`** — two remotes, and `main` tracks the one this
work does not belong to. Name it: `git push origin main`.

## The one thing that would make this wrong

**A test that passes for a reason other than the guard.** Three ways, all of
which have happened here: the fixture is refused by a different rule (hidden,
denied, credential name) so the junction is never reached; the walk returns
nothing at all and the marker's absence proves nothing; or the test skips on
the machine that matters. Ma kills the first two, the unconditional-junction
rule kills the third.
