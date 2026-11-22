# Where the work actually is — a PM audit, 2026-11-02

Written on returning after a week away, by the Claude manager, from `git` and
from re-running the gates. Nothing here is taken from a report.

## What is on `main`

`origin/main` is **`2390568`** (2026-10-31). The local checkout was three
commits behind it, at `a097263`, and dirty; both are fixed, see "Housekeeping".

Re-run on `2390568` today:

| Gate | Result |
| --- | --- |
| `pytest` | **648 passed** |
| `mypy` | clean over **44** files |
| `ruff` | **2 errors — and neither is in `main`'s code.** Both are in `.brief11-worktree/tools.py`, an abandoned worktree sitting inside the repository. The gate is red for anyone who runs it here |

**Brief 12 landed and is verified.** `--report` on the record file as it stands
prints exactly what the brief demanded as its hardest test:

```
209 records, 209 dropped, no cleanliness recorded
Cleanliness: 0 clean, 0 dirty, 209 unknown (209 missing field).
2 commit groups; each is reported separately.
```

Per-question lines read "no surviving runs" rather than `0/0`. That is the
defect class this project keeps finding in its own instruments, and this
instrument refuses it.

## What is **not** on main, and where it is

| Line of work | Where | Size vs `main` | Result section |
| --- | --- | --- | --- |
| **Brief 11 as written** | `codex/brief11-stages-20261031` (`a36a1d8`), **local only, never pushed** | +286 / −19 over `sandbox.py`, `tools.py`, `tests/test_search_text_pruning.py` | **yes, and it is an honest one** |
| Brief 11 Stage 2, a review copy | `codex/brief11-review-20261031-96c6a68a` (`67cbffd`) | the same change without the docs | no |
| **`secure_search.py`** | `origin/codex/search-text-race-safety-20261101-workspace` (`ae898f6`) | **+1,833 / −73**, a new 1,016-line module | **no** |
| **`secure_search.py` plus Linux work** | `origin/codex/posix-device-race-20261101` (`6a1d2af`, 5 commits) | **+2,455 / −84**, the module at 1,199 lines, 1,120 lines of tests, plus `.github/workflows/ci.yml` and `README.md` | **no** |

`codex/compare-file-line-counts` and
`codex/search-text-race-safety-20261101` both point at `2390568`, which is
`main`; they carry nothing of their own.

### Brief 11's Result is the model of how to report

It states what it could **not** establish, unprompted: the 2026-10-26
workload cannot be reconstructed from the committed record, so its fixture is
synthetic and its timings do not recreate the historical figure. It says the
`~0.6 s` Stage 1 gate was not reproduced and that Stage 2 was therefore
implemented on synthetic evidence. On that fixture Stage 2 takes
`Workspace.resolve` calls from **4,681 to 1** with byte-identical output
(plain SHA-256 `1837a092…`, sealed `9779fd8f…`), and the junction mutation
Md behaved as the brief required: with the reparse-point guard removed, the
junction exposed the outside marker.

It also records that `mklink /J` was denied in the restricted run and the
suite passed only with local fixture permissions. **Verifying it is mine and
is not done.**

### `secure_search.py` is a different kind of change and has no brief

From its own docstring: it refuses **all** symlinks and Windows reparse
points, "including links whose current targets are inside the workspace";
Windows support is "limited to 64-bit AMD64 on a local fixed NTFS volume",
pinning directories from the volume root without delete sharing; Linux
requires "procfs and a validated ext4 workspace"; anything else "fail[s]
closed".

That is a race-resistant enumerator built on raw `ctypes` Win32 handles and
Linux `O_PATH` with `/proc/self/fd` identity checks. It is the largest change
in this repository's history, it replaces 86 lines of `tools.py`, it changes
the portability contract, and **no brief was ever written for it.** I am not
judging it here. I am recording that it exists, that it is unreviewed, and
that it cannot be merged on a report nobody has checked.

## Housekeeping done today

- Local `main` fast-forwarded `a097263` → `2390568`.
- Two uncommitted edits stashed rather than discarded, as
  `stash@{0}`: an abandoned first attempt at brief 11 Stage 1 in `tools.py`
  (superseded by `af56ff3` on the branch), and **a stray whitespace edit to
  `scripts/smoke_train.py`** — one trailing space and the final newline
  removed, dated 2026-10-27, in a file no brief authorised. That is open item
  7 again, in a new place.
- Two prunable worktrees pruned. **`.brief11-worktree/` (1.3 MB) and
  `.scratch/` (96 MB) are still in the tree**, untracked and un-ignored.
  `.brief11-worktree/tools.py` is what makes `ruff` red.
- `.scratch/` holds `op7-*` directories from 2026-10-28 and `.tmp-b602-*`
  from 2026-10-27, so open item 7 was investigated while I was away and the
  result is not in `docs/`.

## The record was left stale

`docs/pm/handoff-prompt.md` still says HEAD `43aba72`, **642 tests** and ten
briefs. It is `2390568`, **648 tests** and eleven briefs' worth of work, one
of them unmerged. The standing rule is that the state is kept in step with
the prompt; this is the first thing the next session would have read.
