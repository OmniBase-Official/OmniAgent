# Brief 11 — the walk stops paying for `resolve()`

**For the security engineer.** This changes a security boundary. Everything in
it is static — **no model run is needed anywhere** — and the one thing that
could stop you is named in "Before you start" below.

Open item 3, the largest measurable one left: `Workspace.resolve()` is most of
what a search from the root costs, and every brief so far has forbidden
`sandbox.py`. This one does not.

## What is measured, 2026-10-26, HEAD `6fbdced`

Three passes each, **plain workspace first and sealed second**, because
running one before the other warms the page cache for whichever runs second.
My first attempt had them the other way round and reported 2.92 s where the
real figure is 1.25 s. The numbers below are the reversed, repeated ones.

| | plain workspace | sealed workspace |
| --- | --- | --- |
| wall, `search_text` from `.` | **1.25 s, 1.25 s, 1.44 s** | 0.60 s, 0.60 s, 0.61 s |
| `Workspace.resolve` calls | **4,681** | 685 |
| time in `resolve` | **0.89 s, 0.88 s, 1.01 s** | 0.47 s, 0.48 s, 0.49 s |
| share of wall | **70–71%** | 79–80% |
| output | 7,332 chars, 51 lines | 732 chars, 8 lines |

The note in the open list said 4,660 calls and 1.13 s at 74%. Today it is
4,681 calls and ~0.89 s at 70%. The item is confirmed, the figures have moved,
and **these are the ones to beat**. Timing was taken with a counting wrapper
around `resolve`, which adds a little to its own figure; the call counts are
exact.

## Where it goes

`tools.py:539 _searchable_files` walks with `iterdir()` and, for **every**
entry, calls `workspace.display(child)` and then `workspace.resolve(...)`,
which does `(root / raw).expanduser()` and a full `Path.resolve()`
(`sandbox.py:105-138`). Then `child.is_dir()`, sometimes `child.is_symlink()`,
and `resolved.stat()`. That is four to five syscalls per entry, of which the
`resolve()` is by far the most expensive.

## Goal

The same walk, the same refusals, **byte-identical output**, materially fewer
syscalls. Brief 03 cut this from 26.6 s to 1.7 s by pruning refused branches;
what is left is the per-entry cost itself.

---

# Stage 1 — stop paying for what the directory read already told you

`os.scandir()` returns `DirEntry` objects that already carry `is_dir()`,
`is_file()`, `is_symlink()` and `stat()` from the directory read. `iterdir()`
throws that away and each predicate becomes another syscall.

Replace the `iterdir()` walk with `scandir()` and take those four facts from
the entry. **Do not touch `resolve()` in this stage.**

Then measure and report, in the same shape as the table above: calls, time in
`resolve`, wall, three passes, plain and sealed, **plain first**.

**Stage 2 is gated on this number.** If Stage 1 alone brings the wall under
~0.6 s on the plain workspace, say so and stop — a security boundary is not
worth touching for the remainder. That judgement is yours to report and mine
to make; bring me the figure.

---

# Stage 2 — only resolve what can actually move

A child of a directory that is **already resolved and already inside the
workspace** is inside the workspace too — *unless the child is a link*. So the
full `Path.resolve()` is only needed for entries that can point elsewhere.

The containment check is the only part that can be skipped. **The denied,
hidden, credential-name and size checks all still run on every entry**, and
they are string and stat work, not path resolution.

## The hazard, and it is the whole brief

**On Windows, `is_symlink()` is not the test for "this can point elsewhere".**
A **junction** is a directory reparse point that `Path.resolve()` follows and
that `is_symlink()` reports as `False`. Creating one needs no administrator
rights — `mklink /J` — so it is exactly the thing an attacker, or a careless
tool, can leave in a tree.

**A walk that skips `resolve()` for every non-symlink follows a junction
straight out of the workspace.** That is a sandbox escape introduced by a
performance change, which is the worst way to acquire one.

So the test for "needs a real resolve" must be **reparse point**, not symlink:
`entry.stat(follow_symlinks=False).st_file_attributes` and
`stat.FILE_ATTRIBUTE_REPARSE_POINT` on Windows, with `is_symlink()` as the
POSIX path. `scandir` has already read that attribute, so it is free.

**If you cannot establish, by test rather than by reading, that your check
catches a junction — do not ship Stage 2. Report that instead.** A slow walk
is a correct walk.

## Hard invariant

**Byte-identical output**, on both workspaces, against the current code. Not
"same matches" — the same bytes, including order. `_searchable_files` sorts on
the walked path and the collected training examples were recorded against that
order (`tools.py:567-570`). Compare with a hash, not by eye.

---

# Mutations that must go red

Restore from a scratchpad copy, **never `git checkout --` alone**. Build the
hostile trees in a scratchpad directory and point a `Workspace` at it; **do
not create links inside the repository.**

| # | Mutation | Must go red |
| --- | --- | --- |
| Ma | A **junction** (`mklink /J`) inside the workspace pointing outside it | the walk must not return anything from the far side. Test this against **both** the old and the new code and show the same refusal |
| Mb | A **symlink** to a directory outside the workspace | same |
| Mc | A symlink to a *file* outside the workspace | same |
| Md | Skip the reparse-point check in your new code, keeping everything else | Ma must now **fail**. If Ma still passes, your check is not what is catching it and you have not tested what you think |
| Me | A denied path (`denied_paths`) under the walked root | still refused, old and new |
| Mf | A hidden directory with files under it | still pruned, old and new |
| Mg | A file over `max_file_bytes` | still excluded, old and new |

**Md is the one that matters.** A test asserting "this is refused" proves
nothing if several independent guards would refuse it — and here they might:
containment, denial and hiddenness could each catch a badly built fixture. Md
is how you find out which guard is doing the work.

# Before you start — two questions to answer in your first message

1. **Can you create a junction with `mklink /J` and a symlink in your
   sandbox?** Junctions need no administrator rights; symlinks usually do, or
   Developer Mode. If symlinks are unavailable, say so and do Ma, Md, Me, Mf,
   Mg — **do not quietly skip them.** Brief 05 assumed a WSL build and brief
   07 assumed Ollama; I am asking first this time.
2. **Does `st_file_attributes` exist on your Python build?** It is Windows
   only. If it is missing, stop and report rather than inventing a substitute.

# The three gates

```
.venv\Scripts\python.exe -m ruff check .
.venv\Scripts\python.exe -m mypy
.venv\Scripts\python.exe -m pytest
```

Full path, **never your own `-q`** (`pyproject.toml:168` sets it; a second one
deletes the summary). Baseline **642 passed**, mypy clean over **44** files,
`tree` clean at `6fbdced`. Your new tests move the count — say what to.

# Files you may touch

- `sandbox.py`
- `tools.py` — `_searchable_files` and nothing else in it
- `tests/test_sandbox.py`
- `tests/test_search_text_pruning.py`
- `tests/test_tools.py`

# Files you may not touch

`agent.py` · `scripts/**` · `tests/test_eval_workspace.py` ·
`tests/test_holdout_questions.py` · `tests/test_holdout_record.py` ·
`eval-fixture/**` · `questions/**` · `models/**` · `data/**` ·
`omniagent-core/**` · `.github/workflows/**` · `NEXT_CHAT.md` · `README.md` ·
`docs/` except your `## Result` · anything on `core-offline-runtime`.

`scripts/holdout_eval.py` and `tests/test_holdout_record.py` are **reserved
for brief 12**, the record's clean-tree field, which goes to the fullstack
engineer. They are forbidden here so the two briefs cannot collide. If a file
is in neither list, ask rather than decide.

**Do not change a tool's description or the system prompt.** They reach the
model every turn and are part of every training example; changing one
invalidates the dataset.

# The one thing that would make this wrong

**Buying speed with a hole.** The containment check is the thing standing
between a model-supplied path and the rest of the disk. If the new walk is
fast and Ma is green only because a different guard caught the junction, the
hole is there and the test is lying to you. Md exists for that and it is not
optional.

The second way: **output that is nearly identical.** A different order, one
file more or fewer, and the figures collected against the old order stop being
comparable. Hash it.

# The split

Nothing here needs a model, so there is no split: the whole brief is yours.
The manager re-runs your figures and the mutations afterwards, as always.

# Commit

One commit per stage, gates green at each:

```
git add tools.py tests/
git commit -m "perf(search_text): take what the directory read already knows"

git add sandbox.py tools.py tests/
git commit -m "perf(search_text): resolve only what can point elsewhere"
```

Then **commit this brief with your `## Result` appended**:

```
git add docs/pm/brief-11-the-walk-stops-paying-for-resolve.md
git commit -m "docs: brief 11 result -- the walk's remaining cost, measured"
```

**Do not run a bare `git push`** — two remotes, and `main` tracks the one this
work does not belong to. Name it: `git push origin main`.

## Result

<!-- Engineer: append here. Your answers to the two questions before you
started; Stage 1's figures in the table's shape, plain first, three passes;
your Stage 2 recommendation and whether you shipped it; the byte-identical
hashes for both workspaces; Ma-Mg each with what went red and which guard
caught it; the three gate results with the test count explained; the commit
hashes; and anything you refuse to claim. -->
### Execution and capability

- `stat.FILE_ATTRIBUTE_REPARSE_POINT` is present on this Windows Python build. The junction fixture confirmed the reparse flag is set while `DirEntry.is_symlink()` is false. `mklink /J` was denied in the restricted run; the full Stage 2 suite passed when run with local fixture permissions.
- External directory junction (Ma), external directory symlink (Mb), and external file symlink (Mc) were refused by the baseline and candidate. The Md mutant disabled the reparse-point guard; Ma then exposed the outside marker, as required. Denied path (Me), hidden directory (Mf), and oversized file (Mg) remained refused. Internal file-symlink match behavior and no-recursion into an internal directory symlink were also checked.
- The original 2026-10-26 workload at `6fbdced` cannot be reconstructed from the committed record. The fixture used here is explicitly synthetic: 4,677 files and 3 directories, chosen to reproduce 4,681 plain / 685 sealed resolve calls and 50 / 7 matches. Its output sizes differ from the historic 7,332 / 732 characters, so its timings do not establish the historical `~0.6 s` gate.

### Three-pass synthetic timing

Each implementation ran plain three times first, then sealed three times, on the same fixture and interpreter. Times are seconds. The runs were sequential, so page-cache warmth and machine load affect cross-implementation timing. Treat the timings as synthetic evidence, not a recreation of the historic measurement.

The Stage 1 timing snapshot contains no links (as confirmed by its fixture manifest); its DirEntry calls match ordinary-file behavior in the Stage 1 commit. Link behavior was checked separately by the security regression cases.

| Version | Plain `resolve` seconds (median) | Plain wall seconds (median) | Sealed `resolve` seconds (median) | Sealed wall seconds (median) | Calls plain / sealed |
| --- | --- | --- | --- | --- | --- |
| Baseline | 13.937 / 20.424 / 19.056 (19.056) | 16.201 / 23.758 / 22.160 (22.160) | 2.223 / 2.181 / 2.299 (2.223) | 2.693 / 2.631 / 2.755 (2.693) | 4,681 / 685 |
| Stage 1 | 14.658 / 15.828 / 15.640 (15.640) | 15.064 / 16.261 / 16.071 (16.071) | 2.466 / 2.433 / 2.219 (2.433) | 2.639 / 2.610 / 2.375 (2.610) | 4,681 / 685 |
| Stage 2 | 0.003342 / 0.002632 / 0.002304 (0.002632) | 0.432 / 0.432 / 0.426 (0.432) | 0.002107 / 0.001924 / 0.001910 (0.001924) | 0.171 / 0.166 / 0.164 (0.166) | 1 / 1 |

Output was byte-identical across all three versions: plain SHA-256 `1837a09223bf1634172e6c99584aba1348981c155d9d0b166b3e895b607d15b9` (2,287 bytes, 51 lines); sealed SHA-256 `9779fd8f42fa459fe752f9329b96c8def550e0681859324b784c1009aec9553d` (328 bytes, 8 lines). Stage 1's synthetic plain median remains above `~0.6 s`; Stage 2 was implemented on the synthetic evidence, with no claim that the old workload threshold has been reproduced.

### Gates and commits

- Stage 1: Ruff clean; mypy clean across 44 source files; full suite **648 passed**.
- Stage 2: Ruff clean; mypy clean across 44 source files; full suite **656 passed**. The focused Stage 2 suite had 117 passes; mutation matrix reported 8 passes and 3 deselections.
- Stage 1 commit: `af56ff3` (`perf(search_text): take what the directory read already knows`).
- Stage 2 commit: `3f65e86` (`perf(search_text): resolve only what can point elsewhere`).

Both commits are on local branch `codex/brief11-stages-20261031`; it is not merged or pushed. The historical workload and the historical timing gate remain unverified.

---

## PM verification of brief 11 — 2026-11-02, merged from `codex/brief11-stages-20261031`

**No defects found. Every claim re-derived, and the one the engineer said it
could not establish is now established.** Verified by merging the branch into
`main` at `84f53cf` without committing, with a clean tree before and after.

| Gate | Result |
| --- | --- |
| `ruff` | clean |
| `mypy` | clean over 44 files |
| `pytest` | **656 passed** — exactly the reported figure |

### The real tree, which the Result said could not be reconstructed

It can. The comparison that matters is baseline against candidate **in one
session on one tree**, not against a figure from a week ago. Three passes
each, plain first:

| | baseline `84f53cf` | candidate |
| --- | --- | --- |
| plain wall | 2.729 / 2.675 / 2.539 s | **0.540 / 0.527 / 0.516 s** |
| plain `resolve` calls | **4,690** | **1** |
| plain output | 7,332 chars, sha `442db36f1c10b944` | 7,332 chars, sha **`442db36f1c10b944`** |
| sealed wall | 1.011 / 1.170 / 1.127 s | **0.452 / 0.462 / 0.545 s** |
| sealed `resolve` calls | **688** | **1** |
| sealed output | 732 chars, sha `13cd22e968ddc240` | 732 chars, sha **`13cd22e968ddc240`** |

**Byte-identical by hash on both workspaces, on the repository itself.** About
**5× faster** on the plain workspace, and the `~0.6 s` threshold this brief set
for "stop, Stage 2 is not worth touching a boundary for" is met by Stage 1 and
Stage 2 together at 0.52–0.54 s. Stage 1 alone I did not measure; the engineer
measured it synthetically and reported it above the threshold, which is why
Stage 2 was built.

My own baseline today is about twice my 2026-10-26 figure of 1.25 s, with nine
more `resolve` calls. That is the machine and the tree, not the code — and it
is exactly why the figures above were taken in one session rather than
compared across a week.

### Ma and Md, re-run by the manager

`mklink /J` was **denied in the engineer's restricted run**. It is not denied
here, so the hazard is now tested on this machine by the manager as well.
Fixture built in the scratchpad, never in the repository: a directory outside
the workspace holding a marker, a workspace holding one ordinary file with no
marker in it, and a junction from the workspace to the outside directory.

| | Result |
| --- | --- |
| **Ma**, candidate | `No match ... (1 files searched)` — the junction is not followed, and only the one real file is read |
| **Md**, reparse-point guard removed | `1 match ... jump/secret.txt:1: marker-outside-...` — **the outside marker leaks** |

So the reparse-point check is what does the work. No other guard catches it,
which is what Md exists to establish and what makes Ma's green meaningful
rather than incidental.

`tools.py` was restored from a scratchpad copy, never `git checkout --`:
sha256 `b7db4215e40f171591d7` before the mutation and after the restore, Ma
refused again, 656 passed again.

### The design, read rather than assumed

`sandbox.py:140 admit_resolved_child` carries the contract in its docstring —
the parent must already be resolved and inside, and the name must be proven
not to be a reparse point by the caller — and then re-checks parent
containment itself, rejects `.`, `..` and any name carrying a path, and
applies the denied, hidden and credential-name refusals. The caller resolves
in full whenever the reparse-point attribute is set and uses the cheap path
only otherwise. **The containment guarantee is unchanged; what was removed is
the re-derivation of it.**

That is the right shape, and it is worth saying plainly: this is the design
the brief asked for, done more carefully than the brief specified.

### The prediction for the re-measured baseline, written before the run

Brief 11 changed the walk the agent's `search_text` uses, so the ten-run
baseline of 13–14/18 was measured on different code and has to be taken again.
Written at `858bc81`, clean tree, before any run:

1. **The score distribution does not move.** 13/18 and 14/18 in roughly the
   same proportion, with question 19 the only one that varies. The output is
   byte-identical by hash on both workspaces, so the model sees the same
   observations; if the score moves, byte-identical output was **not** enough
   to hold behaviour fixed, and that is a finding worth more than the baseline.
2. **The step count stays at 54**, identical in every run, for the same reason.
3. **The wall clock barely moves — I expect 185–215 s.** `search_text` is a
   small part of a 200 s run and the saving is under three seconds per call.
   Anyone expecting a 5× faster evaluation out of a 5× faster walk is reading
   the wrong denominator.
