# Brief 13 — the junction refusal becomes a test

**For the security engineer.** Static throughout, **no model run needed**, and
**no production code changes in this brief at all.** If you find yourself
editing `sandbox.py` or `tools.py`, stop and report it: the guard already
exists and is already correct. What is missing is a test.

## Why this exists

The threat model at `docs/pm/threat-model-2026-11-02-the-search-boundary.md`
names four attacker classes and concludes that the plausible one — after the
model itself — is **a hostile tree already on disk**: a cloned repository or an
unpacked archive containing a junction or symlink aimed outside the workspace.

That class is defended, as of `e159f53`, by the reparse-point check in
`tools.py:_searchable_files`. **Its only test is a manager running `mklink /J`
by hand in a scratchpad.** Measured on 2026-11-02:

| | Result |
| --- | --- |
| guard in place | `No match ... (1 files searched)` — the junction is not walked |
| guard removed | `1 match ... jump/secret.txt:1: marker-outside-...` — **the outside marker leaks** |

So the guard is the only thing standing between a hostile tree and a read
outside the workspace, and **nothing in `tests/` would notice if it were
deleted tomorrow.** The suite would stay green at 656.

## Goal

A permanent fixture that fails if the guard goes away. Nothing more.

## The hazard, and it is the whole brief

**A skipped security test is a green gate that proves nothing.** The obvious
implementation is `pytest.skip` when a link cannot be created, and that turns
this brief into decoration: on a machine without the privilege, the suite
passes while the guard is untested, and nobody reads skip counts.

So:

- **A junction needs no administrator rights** — `mklink /J`, or
  `CreateDirectoryW` plus `DeviceIoControl` with
  `FSCTL_SET_REPARSE_POINT`, or whatever you find cleanest. I created one on
  this machine today in an ordinary shell. **On Windows this test must not be
  skippable. If the junction cannot be created, the test fails and says
  why** — "I could not build the fixture" is a result, not a reason to pass.
- **A symlink usually does need the privilege or Developer Mode.** That test
  may skip, and the skip reason must name the privilege. It is the second
  test, not the first.
- **On POSIX, the symlink test is the unconditional one** and the junction
  test does not apply.

Whatever the platform, **at least one refusal test runs unconditionally and
fails on a leak.**

## What the test asserts

Build the fixture in `tmp_path`, never in the repository:

- a directory **outside** the workspace holding a file with a distinctive
  marker;
- a workspace directory holding one ordinary file **without** the marker, so
  the "searched 1 file" count is itself evidence;
- a junction (and, where possible, a symlink) from inside the workspace to
  the outside directory.

Then assert, through `tools.search_text` with a `Workspace` at the fixture
root — **not by calling the private walk** — that:

1. the marker does **not** appear in the output;
2. the file count in the output is the number of real files, so the branch was
   pruned rather than walked and filtered;
3. a directory **inside** the workspace is still walked normally, so the test
   is not passing because the walk is broken.

Point 3 is not optional. A test that would also pass if `search_text` returned
nothing at all is the defect this project keeps finding in its own
instruments.

## The mutation, and you must run it against the committed test

Remove the reparse-point condition in `tools.py` — in a **scratchpad copy** of
the file, restored by copying back, **never `git checkout --` alone** — and
show the new test going red. Then restore and show it green, with the file's
hash matching before and after.

**If the test stays green with the guard removed, the test is wrong**, and
that is the finding to report rather than something to patch around.

| # | Mutation | Must go red |
| --- | --- | --- |
| Ma | Reparse-point condition removed from the walk | the new junction test |
| Mb | The outside marker also written into the inside file | the test must still distinguish — if it cannot, the assertion is on the wrong thing |

## What to report

- Whether the junction fixture built, and how.
- Whether the symlink fixture built, and if not, the exact privilege missing.
- **How long the new tests add to the suite.** A security fixture that costs
  three seconds every run will be deleted by someone in six months; say what
  it costs.
- Ma and Mb, with the hash of `tools.py` before and after.
- The three gates. Baseline **656 passed**, mypy clean over 44 files, ruff
  clean. Say what the count moved to.

## The three gates

```
.venv\Scripts\python.exe -m ruff check .
.venv\Scripts\python.exe -m mypy
.venv\Scripts\python.exe -m pytest
```

Full path, **never your own `-q`** (`pyproject.toml:168` sets it; a second one
deletes the summary line).

## Files you may touch

- `tests/test_search_text_pruning.py`, or a new `tests/test_link_refusals.py`
  — your call, and say which and why
- nothing else

## Files you may not touch

**`tools.py` and `sandbox.py` above all** — the guard is correct and this
brief adds a test, not a change. Also `agent.py` · `scripts/**` ·
`eval-fixture/**` · `questions/**` · `models/**` · `data/**` ·
`omniagent-core/**` · `.github/workflows/**` · `NEXT_CHAT.md` · `README.md` ·
`docs/` except your `## Result` · anything on the `secure_search.py` branches.

`secure_search.py` is **not being merged** — that is the owner's ruling of
2026-11-02, recorded in the threat model. Do not import it, port from it, or
build toward it here. If you believe a test in this brief is better served by
something in it, say so in `## Result` and leave the code alone.

## The one thing that would make this wrong

**A test that passes for a reason other than the guard.** Three ways it can
happen and all three have happened in this repository: the fixture is refused
by a different rule (hidden, denied, credential name) so the junction is never
reached; the walk returns nothing at all and the absence of the marker proves
nothing; or the test skips on the machine that matters. Ma kills the first
two. The unconditional-junction rule kills the third.

## The split

Nothing here needs a model. The whole brief is yours; the manager re-runs Ma
and the fixture afterwards, as always.

## Commit

```
git add tests/
git commit -m "test: a hostile tree cannot walk out of the workspace"

git add docs/pm/brief-13-the-junction-refusal-becomes-a-test.md
git commit -m "docs: brief 13 result -- the junction refusal has a test now"
```

**Do not run a bare `git push`** — two remotes, and `main` tracks the one this
work does not belong to. Name it: `git push origin main`.

## Result

<!-- Engineer: append here. Whether each fixture built and what was missing if
not; which test file you chose and why; what the new tests add to the suite's
runtime; Ma and Mb with the hash of tools.py before and after; the three gate
results with the count explained; the commit hashes; and anything you refuse
to claim. -->

### Execution record

- The prompt named `af7daa9` as starting HEAD. The actual clean `main` checkout
  was at `4cc404b3a08a4cb901d2c80ab9a15d011085e41f`, a descendant containing the
  intervening PM commits. Work proceeded from that actual HEAD without resetting
  or changing branches. The test commit is based on it.
- Added `tests/test_link_refusals.py`. A separate file keeps platform-specific
  link creation and the refusal assertions together. Both cases call the public
  `tools.search_text` API with `Workspace.at(root)`; neither calls the private
  walk. The fixture is created by pytest in an external scratch location, never
  under the repository. The process `TEMP` was pointed there because the
  default sandbox `AppData` temp location refused pytest's temp-directory
  creation.
- On this Windows run, the mandatory junction was created successfully with
  PowerShell `New-Item -ItemType Junction`; no administrator privilege was
  missing. The external symlink also built successfully, so no symlink
  privilege was missing in this run. The Windows junction test has no skip path.
  On Windows, the symlink test only skips `ERROR_PRIVILEGE_NOT_HELD` (WinError
  1314), naming `SeCreateSymbolicLinkPrivilege` and Developer Mode in the reason.
  POSIX was not run here; there the symlink test is unconditional and fails if
  creation fails.
- The baseline fixture starts with one ordinary in-workspace file that does
  not contain the outside marker. It asserts no match and exactly
  `(1 files searched)`, then positively asserts that `inside/ordinary.txt` is
  searched. This prevents a broken or empty walk from satisfying the refusal
  assertion. The same test then performs Mb by writing the outside marker into
  that inside file: the result must name `inside/ordinary.txt`, never
  `jump/secret.txt`, and an absent query must still report one searched file.
- New-test runtime was approximately **0.63 seconds** of test call time on this
  Windows run: **0.62s** for the junction case and **0.01s** for the symlink
  case. The focused pytest invocation reported 2 passed in 0.84s. No model run
  was performed.

### Mutation checks

- `tools.py` SHA256 before mutation: `B7DB4215E40F171591D723502FFA6C306DE41127BDB736DD9D0E476541B51F9F`.
- **Ma:** Using an external scratch backup, the reparse-point admission condition
  was temporarily forced off. The committed junction test went red and showed
  the leak: `jump/secret.txt:1: outside-marker-...`. `tools.py` was restored by
  copying the saved scratch file back. SHA256 after restoration:
  `B7DB4215E40F171591D723502FFA6C306DE41127BDB736DD9D0E476541B51F9F`.
- **Mb:** The committed test writes the same marker into the inside file and
  verifies its match is attributed to `inside/ordinary.txt`, with no match from
  the external alias and one file searched. This passed for both link fixtures.
  `tools.py` SHA256 before and after Mb remained
  `B7DB4215E40F171591D723502FFA6C306DE41127BDB736DD9D0E476541B51F9F`.
- No production source was changed or committed; `sandbox.py` and `tools.py`
  have no remaining diff. `secure_search.py` was not imported or used.

### Gates

- `.venv\Scripts\python.exe -m ruff check .` — passed, `All checks passed!`.
- `.venv\Scripts\python.exe -m mypy` — passed, `Success: no issues found in 45
  source files` (baseline was 44 before adding the test module).
- `.venv\Scripts\python.exe -m pytest` — **658 passed in 29.43s**. The two
  executed tests are the Windows junction and external-symlink cases; both
  passed without skips. This is 656 baseline tests plus the two new tests.

### Commits

- Test: `ed8e20bed5301e84a8f01a90501ba31e7a988f46` —
  `test: a hostile tree cannot walk out of the workspace`.
- Report: this report commit; its hash is recorded in the delivery summary.

This run verifies the Windows fixtures and gates only; it does not claim a POSIX
run or broader filesystem/threat-model coverage.
