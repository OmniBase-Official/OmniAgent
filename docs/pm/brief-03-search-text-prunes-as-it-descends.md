# Brief 03 — `search_text` prunes as it descends

**For the fullstack engineer.**

`NEXT_CHAT.md` item 1 has said since 2026-10-06 that `search_text` is slow
because `sorted(start.rglob("*"))` materialises every path before filtering.
**That diagnosis is wrong, and I measured it today before writing this brief.**
Materialising is 6% of the cost. The prescription in that note — prune as you
descend — is right, for a different reason, and worth about twenty-five seconds
rather than one and a half.

## What is measured, 2026-10-23, on HEAD `f4687e4`

A replay of `tools.py:555-587` against the real workspace, root `.`, needle
`"ReAct"`, with a per-phase clock. Three runs:

| Phase | Run 1 (cold) | Run 2 | Run 3 |
| --- | --- | --- | --- |
| `sorted(rglob("*"))` — 87,482 paths | 1.57 s | 1.67 s | 1.60 s |
| **`workspace.resolve(...)` — 69,186 denied** | **25.32 s** | **25.52 s** | **23.29 s** |
| `stat()` | 0.00 s | 0.00 s | 0.00 s |
| `read_bytes()` — 4,627,772 bytes over 400 files | 3.22 s | 0.03 s | 0.04 s |
| decode and match | 0.04 s | — | — |
| **total** | **34.92 s** | **29.06 s** | **26.62 s** |

Warm, the shape is stable: **`resolve()` is 87–88% of the run, the walk is 6%,
and reading the files is four hundredths of a second.** The 3.22 s read on run 1
is a cold page cache; it does not recur.

That total also matches the 25.7 s this project already recorded for an
unsealed search, which means **that 25.7 s was essentially all `resolve()`**.

### What is actually happening

The loop calls `workspace.resolve(workspace.display(candidate))` once per
candidate **file**, and `sandbox.py:181 _is_hidden` refuses anything with a
dot-prefixed path component. Under `.venv`, `.ci-venv` and `.git` that is
**69,186 files**, each one costing a `display`, a full path resolution and a
raised `SandboxError` that is then discarded. The pruning idiom skips the whole
branch at the directory, so those 69,186 resolutions never happen.

Pruning dot-directories during descent takes the enumeration from 87,482 paths
at 1.6 s to **4,578 paths at 0.06–0.08 s**, measured over three reversed-order
runs — reversed because running the pruned walk after the full one let the full
one warm the cache for it, and the first figure I got that way, 4.58 s, was a
cold-cache artefact.

### Where the 400-file budget goes, and why that is not in this brief

`MAX_SEARCH_FILES` is 400, and of the 400 files scanned from the root:

| Top-level directory | Files scanned |
| --- | --- |
| `models/` | **285** |
| `data/` | 92 |
| `docs/` | 9 |
| `__pycache__/` | 8 |
| the six tracked root `.py` files and `LICENSE` | 6 |

`models/` is not hidden and not denied, so it is legitimately in scope today,
and it takes 71% of the budget. `data/` is the evaluation output directory.
**Changing that is a tool-behaviour change, not an optimisation**, and the
153-example dataset was collected against the current behaviour. It is a
decision for the project owner and it is **deliberately out of this brief.**
Do not touch `sandbox.py`'s denied or listing-only sets.

## Goal

`search_text` produces **byte-identical output** to what it produces today, in
under a second from the workspace root.

## Files you may touch

- Modify: `tools.py` — `search_text` and whatever private helper you add
- Modify or add: the test module that covers `search_text`

Do not touch `sandbox.py`. Do not change `MAX_SEARCH_FILES`,
`MAX_SEARCH_MATCHES`, `max_file_bytes`, or any tool description — a tool
description reaches the model on every turn and is part of every training
example, so changing one invalidates the dataset.

## Interfaces it must produce

A private helper in `tools.py`:

```python
def _searchable_files(workspace: Workspace, start: Path) -> list[Path]:
    """Files under `start` the workspace admits, pruned branch by branch.

    Resolving every path under a hidden directory and discarding it afterwards
    is 87% of a search from the root.
    """
```

- It descends directory by directory and **prunes the whole branch** when
  `workspace.resolve(workspace.display(child))` raises. The project already
  pays for this idiom at `tests/test_eval_workspace.py:113 reachable_files` —
  read it and match it rather than inventing a second shape.
- **It returns `sorted(...)`.** This is the part that is easy to get wrong.
  Today's candidate order is a global sort of full path strings, and
  `MAX_SEARCH_FILES` and `MAX_SEARCH_MATCHES` truncate, so the order decides
  *which* matches the agent sees. An `os.walk` that yields per-directory
  produces a different order and therefore different output. Collect, then sort
  exactly as before.
- `search_text` keeps its own per-candidate `resolve` for the files the helper
  returns, or drops it if the helper already resolved them — either is fine,
  but the output must not change.

## The tests that must fail first

Write them, run them, **paste the failing output**, then change `tools.py`.

1. **Output equivalence against a golden string.** Build a fixture workspace
   containing: a file with two matches, a subdirectory with a match, a
   dot-directory with a match, a file over `max_file_bytes`, and a binary file
   with a null byte in the first bytes. Capture what `search_text` returns
   **today** and assert the new implementation returns exactly that. Run it
   against the current code first so the golden value is measured, not written
   from belief.

2. **Ordering under truncation.** A fixture with more matches than
   `MAX_SEARCH_MATCHES` across several directories, asserting the exact list of
   matches returned. This is the test that catches a reordered walk, and
   without it the change is unverifiable.

3. **No resolution happens under a pruned branch.** Assert that searching a
   tree whose dot-directory holds thousands of entries does not resolve them —
   count the calls by wrapping `workspace.resolve`, or assert the helper's
   returned length. A timing assertion is not acceptable; it will be flaky on
   CI.

## Mutation checks that must go red

Copy each file to a scratch directory outside the repository first and restore
from that copy. Never `git checkout --` alone. Assert the target string is
present before replacing it.

| # | Mutation | Must go red |
| --- | --- | --- |
| M1 | Drop the `sorted()` from `_searchable_files` | the ordering test |
| M2 | Prune on `child.name.startswith(".")` instead of on the workspace's own refusal | the equivalence test — the workspace refuses more than hidden names, and a second copy of its rules in `tools.py` is a rule that will drift |
| M3 | Do not prune: recurse into a branch whose resolve raised | test 3 |
| M4 | Delete test 1's assert | **nothing** — it must go green, so you know M1 and M2 were caught by the tests you think caught them |
| M5 | Return files whose size exceeds `max_file_bytes` | the equivalence test |

Report every test that turned red for each mutation, by name, and say which is
yours when more than one is.

## Measure the result, and report the number

Before and after, from the workspace root, same needle, **three runs each,
warm**:

```
.venv\Scripts\python.exe -c "import time,tools;t=time.perf_counter();tools.search_text('ReAct','.');print(f'{time.perf_counter()-t:.2f} s')"
```

Baseline to beat: **26.6–29.1 s warm.** Report your three numbers, not an
average of one run. If the result is not under a second, say so — the walk is
6% of the cost and the rest is the resolutions this change removes, so
something is still resolving a branch it should have pruned.

## The three gates

```
.venv\Scripts\python.exe -m ruff check .
.venv\Scripts\python.exe -m mypy
.venv\Scripts\python.exe -m pytest
```

Full path, **no `-q` of your own** — `pyproject.toml:168` sets it and a second
one deletes the summary line. Baseline **633 passed**; you add three tests, so
expect **636**. Report the actual number.

`search_text` already carries `# noqa: PLR0912` for its branch count. If your
helper lets you remove that, remove it; if you need a second one, say why in
`## Result` rather than adding it silently.

## The one thing that would make this wrong

**Making the search faster while changing what it returns.** The output order
decides which 50 matches of a truncated search the agent sees, and the 153
training examples in `G:/OmniAgent/datasets/2026-10-10-merged/` were collected
against today's output. A faster `search_text` that returns a different string
for the same query silently invalidates every training example that used it,
and no gate in this repository would notice.

That is why test 1 is a golden string captured from the current code and test 2
asserts an exact truncated list. If you cannot make the new implementation
reproduce them, **stop and report it** — the ordering is the contract, not the
speed.

The second way: copying `sandbox.py`'s rules into `tools.py` to decide what to
prune. The workspace is the only thing that knows what it refuses. Ask it, and
prune on its answer.

## Commit

```
git add tools.py tests/
git commit -m "perf(search_text): prune a refused branch instead of resolving every leaf"
```

Do not run a bare `git push` — this repository has two remotes and `main`
tracks the one this work does not belong to. Leave it unpushed.

## Result

<!-- Engineer: append here. The failing outputs, every mutation with the names
of the tests that changed colour, the three before and three after timings, the
three gate results, the pytest count, the commit hash, and anything you refuse
to claim. -->

**Executed 2026-10-26. Commit `0c04ffa`, on `main`, not pushed.** Gates green,
**636 passed**, output byte-identical on every comparison I could construct.

**The one target I did not hit: the search is 1.31–1.50 s, not under a second.**
The brief says that if it is not under a second then something is still
resolving a branch it should have pruned. That is not what is happening, and the
measurement that says so is under *Why it is not under a second* below. Nothing
refused is descended into — M3 and test 3 are exactly that assertion — and the
remaining 1.3 s *is* the one `workspace.resolve` per admitted entry that
constraint 2 requires. I did not go below it, because the only way left is the
second way this brief says the work goes wrong.

### The tree when I measured

Every timing below, before and after, was taken on this same state. The tree
moved once while I was reading it, so to be exact about which tree: the engineer
prompt names HEAD `0a4f757`, the brief itself is `9e22bd1` (04:42:14), and
`34b65f2` (04:45:05) committed the `.gitignore` change that was still
uncommitted when I opened the repository. **`34b65f2` is the parent of my
commit.** It touched `.gitignore` and nothing else, and `tools.py` is identical
at all three, so every figure below is unaffected by it. Working tree otherwise
clean apart from the test module I added.

| | |
| --- | --- |
| paths from `sorted(rglob("*"))` | **89,568** (brief: 89,550) |
| of those, files | 74,238 |
| files the workspace refuses | **70,075** (brief: 70,032) |
| walk | 1.82 s |
| `resolve()` over the refused paths | 25.38 s |

The untracked `.tmp-omnipatch-release-audit-67a40f9906cc486895f4a4c514569221`
was present throughout and **I did not delete it**: 1,833 entries, 994 KB. At
the 316 µs per refused resolve measured below it is worth **~0.58 s of the old
~27 s run, about 2%**. So it flatters the fix by two percent, not more — the
speed-up is not an artefact of it.

Also in the tree and refused: `.venv`, `.ci-venv`, `.git`, `.github`, `.env`,
`.vscode`, `.kilo`, `.superpowers`, `.mypy_cache`, `.ruff_cache`,
`.pytest_cache`. In the tree and admitted: `models/`, `data/`, `docs/`,
`questions/`, `scripts/`, `tests/`, `notebooks/`, `eval-fixture/`,
`omniagent-core/`, `omniagent.egg-info/`, `__pycache__/`.

### The three tests, and what actually failed first

`tests/test_search_text_pruning.py`, 3 tests. The first run, with the golden
values still placeholders, failed all three:

```
FAILED tests/test_search_text_pruning.py::test_search_text_output_is_byte_identical
FAILED tests/test_search_text_pruning.py::test_truncation_keeps_the_sorted_order
FAILED tests/test_search_text_pruning.py::test_a_refused_branch_is_not_resolved
3 failed, 1 passed in 6.97s
```

```
E       AssertionError: assert ('alpha/f1.tx...neme 06', ...) == ()
E         Left contains 50 more items, first extra item: 'alpha/f1.txt:1: pruneme 01'
```

```
E       AssertionError: 2000 paths resolved under a refused branch
E       assert ['.junk/deep/...005.txt', ...] == []
E         Left contains 2000 more items, first extra item: '.junk/deep/leaf-0000.txt'
```

**I am not going to claim that as three tests failing first, because it is not.**
Tests 1 and 2 are golden captures. Once I filled the goldens in from the current
implementation — which is what the brief asks for, a value measured and not
believed — they pass *against the old code too*, by construction:

```
1 failed, 2 passed in 4.39s
FAILED tests/test_search_text_pruning.py::test_a_refused_branch_is_not_resolved
```

So **test 3 is the only one that is red before the change and green after.**
Tests 1 and 2 are green on both sides and their job is to stay green; the
mutations below are what prove they can still go red. After the change, all
three pass in 1.70 s, down from 4.39 s, because the 2,000 entries under the
fixture's `.junk/` are no longer resolved.

One deviation in the fixture, and it is load-bearing. The brief's list for
test 1 — two matches in a file, a match in a subdirectory, a match in a
dot-directory, a file over `max_file_bytes`, a binary file — **cannot catch M2.**
Every refused thing in it is dot-prefixed, so a `child.name.startswith(".")`
rule reproduces the golden string exactly and M2 goes green. I added a
`secret.key` holding a match: refused for a denied suffix, invisible to any
dot-prefix rule. That is the entry M2 trips over. The oversize file is a real
100,001-byte file, so the fixture runs against the real `MAX_FILE_BYTES` and no
limit was lowered to make the test cheap.

### The change

`_searchable_files(workspace, start)` with the signature and the docstring the
brief specified, matching `tests/test_eval_workspace.py:113 reachable_files`:
a stack, `iterdir()`, `workspace.resolve(workspace.display(child))` on every
entry, and `continue` on `SandboxError` so the whole branch goes. No rule from
`sandbox.py` is restated in `tools.py`.

Two details that are not in the brief and that the ordering contract turns on:

- **It collects `(walked, resolved)` pairs and sorts on the walked path**, then
  returns the resolved ones. Sorting the resolved paths would be a different
  key from `sorted(rglob("*"))` the moment a symlink is involved. This way the
  sort key is byte-for-byte the old one.
- **It does not descend into a symlinked directory**, because `rglob` does not
  either. Following one would both reorder and duplicate.

`search_text` now drops *both* its own per-candidate `resolve` and its own size
check. The brief offers a choice on the resolve, but the choice is only free in
one direction: if `search_text` keeps either guard, it re-filters whatever the
helper returns, and **M2 and M5 both go green** — the mutation is masked by the
caller. The helper has to be the only gate for the mutation table to mean
anything. The single-file case (`path` naming one file) keeps its size check
inline in `search_text`, since the brief's helper is defined over files *under*
`start`.

`# noqa: PLR0912` **stays, and it is the same one, not a second one.** The
helper removed three branches from `search_text` (the `is_file` skip, the
per-candidate try/except, the size check) and the single-file candidate case
added two plus a ternary: ruff reports 13 > 12. Removing it is possible by
folding the single-file case into the helper, which would make the helper's
documented contract ("files under `start`") false for that case. I kept the
brief's interface and the existing suppression.

### M1–M5

Each mutation applied to a file copied to a scratch directory outside the
repository, with the target string asserted present and unique before the
replacement, and restored from that copy with a byte comparison afterwards. No
`git checkout --`. Full suite run per mutation, so a test outside my module
turning red would show up.

| # | Mutation | Result | Red |
| --- | --- | --- | --- |
| M1 | drop the `sorted()` | 2 failed, 634 passed | `test_truncation_keeps_the_sorted_order` (the brief's), **and** `test_search_text_output_is_byte_identical` |
| M2 | prune on `child.name.startswith(".")` | 5 failed, 631 passed | `test_search_text_output_is_byte_identical` (the brief's), `test_a_refused_branch_is_not_resolved`, **and three that were already here** |
| M3 | recurse into a branch whose resolve raised | 1 failed, 635 passed | `test_a_refused_branch_is_not_resolved` (the brief's) |
| M4 | delete test 1's assert | **636 passed** | **nothing** |
| M5 | return files over `max_file_bytes` | 1 failed, 635 passed | `test_search_text_output_is_byte_identical` (the brief's) |

Mine versus the brief's, where more than one went red:

- **M1** also reddens test 1. With the stack walk the `mixed` fixture reorders
  too (`blob.bin`, `top.txt`, `sub/nested.txt`), so the golden string moves.
  Test 2 is still the one that catches it on purpose.
- **M2** reddens three tests that were in the suite before I touched it:
  - `tests/test_eval_workspace.py::test_search_text_no_longer_finds_the_leaked_answer`
  - `tests/test_eval_workspace.py::test_the_transcripts_directory_is_listable_but_not_readable`
  - `tests/test_file_tools.py::test_search_text_reports_no_match_inside_a_denied_directory`

  **This is the brief's "a rule that will drift", already drifted.** A
  dot-prefix copy of the admission rule does not just leak `secret.key`; it
  reopens the transcript leak that `without_own_transcripts` exists to close,
  because `denied_paths` and `listing_only_paths` are not dot-prefixed at all.
  The repository was already defending this and I did not know that until the
  mutation said so.

M4 going green is the result that makes the other four mean something: M1, M2
and M5 were caught by test 1's assert itself, not by something else in the file.

### Six timings, same tree, and then reversed

`.venv\Scripts\python.exe -c "import time,tools;t=time.perf_counter();tools.search_text('ReAct','.');print(...)"`,
from the workspace root, warm. First run of each set discarded as the warm-up,
as instructed.

| | run 1 | run 2 | run 3 | (warm-up) |
| --- | --- | --- | --- | --- |
| **before** — `9e22bd1` | 29.72 s | 28.04 s | 27.41 s | 27.99 s |
| **after** — `0c04ffa` | **1.37 s** | **1.33 s** | **1.31 s** | 1.47 s |

Then reversed, because the brief is right that order warms the cache — new
first, then old again, then new again, all on the same tree:

| | run 1 | run 2 | run 3 |
| --- | --- | --- | --- |
| old code, measured *after* the new | 28.27 s | 26.21 s | 27.99 s |
| new code, measured *after* the old | 1.50 s | 1.36 s | 1.38 s |

**~27–30 s to ~1.3–1.5 s, about 20×.** The order makes no difference to either
side, so neither figure is a page-cache artefact.

My baseline is **26.2–29.7 s**, below the brief's refreshed **29.1–32.6 s**. I
am reporting what I measured rather than reconciling it; the shape matches the
brief exactly (`resolve()` 25.4 s of it, walk 1.8 s).

### Why it is not under a second

Instrumented, on the same tree:

| | |
| --- | --- |
| `_searchable_files` | 1.631 s — **3,971 files admitted, 4,660 `resolve` calls** |
| `read_bytes()` over the 400 scanned files | 0.044 s, 4,639,601 bytes |
| `workspace.resolve` over the 3,971 admitted files *alone* | **1.253 s — 316 µs each** |
| of which `Path.resolve()` alone | 146 µs each |
| `stat()` alone | 10 µs each |
| unpruned `rglob` enumeration alone | 1.265 s / 89,573 paths |

**4,660 × 316 µs ≈ 1.47 s. That is the entire runtime.** The brief's "under a
second" came from the 4,578-paths-at-0.06–0.08 s figure, which is the cost of
*enumerating* a pruned tree. It does not include the one
`workspace.resolve(workspace.display(child))` per admitted entry that
constraint 2 requires, and on this filesystem that call costs 316 µs — about
half of it `Path.resolve()`, which makes a filesystem call per path on Windows,
and the rest the admission checks.

So the floor is ~1.3 s while every admitted entry is asked about individually.
Getting under a second means not asking: caching, or deciding from the parent's
answer, or filtering before the call. All of them are a second copy of
`sandbox.py`'s rules in `tools.py`, which is the other thing this brief says
makes the work wrong. **I stopped at the constraint rather than at the number,
and I am flagging it rather than quietly reporting ~1 s.** If the 25 s was the
point, it is gone; if the sub-second figure was load-bearing, it needs a
decision about `resolve` that is above my line.

### Equivalence, beyond the two fixtures

The fixtures are small, so I built three wider checks.

1. **The real tree.** `search_text('ReAct', '.')` captured before the change and
   compared byte for byte after: **4,606 bytes, identical.**
2. **16 needle/path cases** over the real tree, old implementation versus new —
   including 7 that truncate at the 50-match limit, a no-match case whose
   `(400 files searched)` count has to agree, a refused path, and a path that
   does not exist: **16/16 identical.**
3. **The 153 training examples' own calls.** I extracted every
   `Action: search_text` input the merged dataset actually records — **28
   occurrences, 26 distinct** — and replayed all 26 through `run_tool` under
   both implementations.

   The first pass came back **24 identical, 2 differing**, and the brief says to
   stop and report on exactly that. So I stopped and looked. Both differences
   are **line numbers inside `tools.py` itself** — same files, same match count,
   same order, shifted by the 2 import lines and the 33-line helper I added.
   The confound is the method: `tools.py` is one of the 400 files a search from
   the root reads, so comparing old-code-on-old-tree with new-code-on-new-tree
   compares two different trees.

   I re-ran it with the search space held constant — HEAD's `tools.py` on disk
   for both runs, the new implementation imported from a copy outside the
   workspace: **26/26 identical.** That is the version of the claim I stand
   behind.

   Nothing from the dataset is quoted here or anywhere in the repository: the
   queries and the matched lines are evaluation material and a repo file holding
   them fails the eval-workspace invariant. The captures are in a scratch
   directory outside the tree.

### The gates

```
.venv\Scripts\python.exe -m ruff check .     All checks passed!
.venv\Scripts\python.exe -m mypy             Success: no issues found in 43 source files
.venv\Scripts\python.exe -m pytest           636 passed in 13.59s
```

**636 passed**, exactly the 633 baseline plus three. mypy covers 43 files, up
from 42, because of the new test module. No `-q` of my own.

Untouched, as required: `sandbox.py`, `MAX_SEARCH_FILES`, `MAX_SEARCH_MATCHES`,
`max_file_bytes`, every tool description, and `models/`. Being precise about
what that means, because a careless grep of the diff looks alarming: **no
constant definition and no `description=` line is in the diff at all**, and
`max_file_bytes` appears in it only as reads that moved — out of `search_text`
and into the helper and the single-file case. `git diff 34b65f2 0c04ffa` touches
two files, `tools.py` and the new test module, and `git diff` over `sandbox.py`
and `pyproject.toml` is empty.

The commit is `git add tools.py tests/` only — **this `## Result` is not in
it**, since `docs/` is yours and the brief asked for one commit. Nothing is
pushed; `main` is 30 ahead of and 13 behind `organization/main`, exactly as I
found it.

### What I refuse to claim

1. **That it is under a second.** It is 1.31–1.50 s, and the reason above is
   measured, not inferred.
2. **Byte identity for a tree containing symlinks.** I handled them
   deliberately — sort on the walked path, no descent into a symlinked
   directory, both to match `rglob` — but there is no symlink anywhere in this
   tree, so none of it is exercised. No test covers it. It is reasoning, not
   evidence.
3. **One semantic divergence that is real, mandated, and untested.** A directory
   refused for a reason other than being hidden or denied — one literally named
   `credentials`, or one with a denied suffix like `foo.key` — had its
   *admissible contents* returned by the old code, which never resolved
   directories at all and so never noticed the parent. The pruning walk refuses
   the branch at that directory. Constraint 2 mandates this ("prune the whole
   branch when it raises") and separating the refusal reasons would mean copying
   `sandbox.py`'s rules, so I did not. **I scanned the tree for such a
   directory: there are none**, which is why every comparison above still comes
   out identical. If one is ever created, the output changes. No test covers it,
   because I could not write one that does not also encode the rule I am
   forbidden to copy.
4. **That the dataset's recorded Observations still reproduce.** They do not and
   cannot: the tree has moved since 2026-10-10. What I verified is that the
   change does not alter the output for the queries the dataset used, on today's
   tree. Whether the recorded Observations are still reachable at all is a
   different question and not this brief's.
5. **The 20× figure as a property of the change rather than of this tree.** It
   is a ratio between 70,075 refused resolutions and 4,660 admitted ones. A tree
   without a `.venv` would show almost no gain.

### Four things in the brief that have drifted

1. **`.tmp-omnipatch-release-audit-...` is gitignored.** The brief says "it is
   not gitignored and no brief asked for it". That was true when it was written
   and false **three minutes later**: the brief is commit `9e22bd1` at 04:42:14,
   and `34b65f2`, "chore: ignore the external Bandit audit scratch output",
   landed at 04:45:05 with `.tmp-omnipatch-*/` at `.gitignore:49`. Nothing to
   fix — just do not carry the "not gitignored" line into the next brief. The
   directory is still on disk and I left it there; being ignored does not hide
   it from `search_text`, which walks the filesystem, which is why it is still
   in every number above.
2. **`-q` is set at `pyproject.toml:174`, not `:168`.** The rule is right and I
   followed it; only the line number moved.
3. **The brief's own baseline band.** 26.2–29.7 s measured here against the
   stated 29.1–32.6 s, same day, same tree. Worth knowing before the next brief
   quotes it as the figure to beat.
4. **The engineer prompt's `HEAD 0a4f757` was already one commit stale when it
   became readable**, since the prompt is inside `9e22bd1`, whose parent is
   `0a4f757`. Harmless here — `tools.py` is identical across both — but a brief
   that pins HEAD cannot pin the commit that contains it.

---

## Re-issued 2026-10-26 — the figures are refreshed, the task is not changed

This brief was issued on 2026-10-23 and has not been started. `tools.py` is
untouched: `git log fb8220e..HEAD -- tools.py` is empty. **Nothing about the
diagnosis or the prescription has changed. The numbers in it have.**

Three days of other work moved the tree, so the old baseline would have had the
engineer chasing a figure that no longer exists — the same way
`NEXT_CHAT.md:391` went stale under brief 02. Re-measured today, three runs:

| Phase | 2026-10-23 (warm) | 2026-10-26 (warm) |
| --- | --- | --- |
| paths from `sorted(rglob("*"))` | 87,482 | **89,550** |
| **`resolve()` over refused paths** | 69,186 denied, 23.3–25.5 s | **70,032 denied, 25.4–27.6 s** |
| walk | 1.6 s | 1.6–2.9 s |
| `read_bytes()` | 0.04 s | 0.04–0.06 s |
| **total** | **26.6–29.1 s** | **29.1–32.6 s** |

A cold first run measured 40.9 s with a 7.1 s walk; that is a page-cache
artefact and is not the baseline. **`resolve()` is still 85–87% of a warm run
and the walk is 5–9%.** The shape is unchanged: the prescription in this brief
is still right and still worth about twenty-five seconds.

**Baseline to beat is now 29.1–32.6 s warm, not 26.6–29.1 s.**

### Where the 400-file budget goes now

| Directory | 2026-10-23 | 2026-10-26 |
| --- | --- | --- |
| `models/` | 285 | 255 |
| `data/` | 92 | 102 |
| `docs/` | 9 | 23 |
| `__pycache__/` | 8 | 8 |
| `eval-fixture/` | — | 6 |

`eval-fixture/` is new, from brief 08. `data/` keeps growing because every
evaluation writes there. `docs/` grew because this brief's own siblings were
written into it.

### One thing to be careful about when you measure the improvement

There is currently an untracked directory in the working tree,
`.tmp-omnipatch-release-audit-67a40f9906cc486895f4a4c514569221`, holding about
994 KB of Bandit scan output. **No brief asked for it and it is not
gitignored.** It is dot-prefixed, so the workspace refuses everything inside
it — which means the current `search_text` resolves every leaf under it and
discards them, while a pruning walk skips the whole branch at the top.

**That directory flatters the fix.** Measure before and after **on the same
tree state**, and say in your report what was in the tree when you measured. A
speed-up that depends on how much junk is lying around is not a measurement of
your change.

Do not delete that directory. It is not yours and not mine; it is reported to
the owner separately.

### Everything else in this brief stands

The ordering contract is unchanged and is still the thing that would make this
wrong: `MAX_SEARCH_FILES` is 400 and `MAX_SEARCH_MATCHES` is 50, so the
candidate order decides which matches the agent sees, and the 153 training
examples were collected against today's output. Collect the pruned paths, then
`sorted()` them exactly as before.

The three tests, the five mutations M1–M5, and the forbidden list are all
unchanged. The pytest baseline has moved: it is **633 passed**, not 631, so
expect **636** with your three tests.

---

## PM verification — 2026-10-26, `0c04ffa`

**No defects.** Scope held: `tools.py` and one new test file, nothing else.
`mypy` now covers **43** source files, one more than before, and the suite is
**636 passed** — exactly the predicted 633 plus three.

### The ordering contract, proved rather than argued

This was the one thing that would have made the change wrong, so I checked it
directly instead of reading the diff. I reimplemented the pre-`0c04ffa`
candidate selection verbatim in a scratch harness and compared the **output
strings** of old and new over ten cases:

```
IDENTICAL  'ReAct'              in '.'             old 26.55s  new 1.80s
IDENTICAL  'def '               in '.'             old 27.23s  new 1.85s
IDENTICAL  'workspace'          in '.'             old 27.78s  new 1.85s
IDENTICAL  'budget'             in '.'             old 28.65s  new 1.71s
IDENTICAL  'zzz-no-such-string' in '.'             old 31.22s  new 1.91s
IDENTICAL  'import'             in 'tests'         old  0.02s  new 0.02s
IDENTICAL  'Question'           in 'scripts'       old  0.01s  new 0.01s
IDENTICAL  'cells'              in 'notebooks'     old  0.00s  new 0.00s
IDENTICAL  'fixture'            in 'eval-fixture'  old  0.00s  new 0.00s
IDENTICAL  'MIT'                in 'LICENSE'       old  0.00s  new 0.00s

cases compared: 10 | differing: 0
```

Byte-identical on all ten, including the no-match case — which exercises the
`scanned` counter inside the message text, the easiest thing to get subtly
wrong — a single-file start, and three subdirectory starts.

**M1 re-run independently.** Replacing `sorted(found)` with `found` turns
**two** tests red, not one:

```
FAILED tests/test_search_text_pruning.py::test_search_text_output_is_byte_identical
FAILED tests/test_search_text_pruning.py::test_truncation_keeps_the_sorted_order
2 failed, 634 passed
```

`tools.py` restored from a scratch copy afterwards; `git status` clean.

### The implementation got the subtle part right

`_searchable_files` sorts on the **walked** path and not the resolved one,
with a comment saying why: that is the key `sorted(rglob("*"))` used, and the
truncation limits make the order observable. It also refuses to descend into a
directory symlink, because `rglob` does not follow one either. Neither was
spelled out in the brief.

### The target was missed, and here is exactly where the time goes

The brief asked for **under a second**. It is **~1.3 s** by the engineer's
measurement and **1.71–1.91 s** by mine. That is a real miss and the engineer
reported it rather than rounding it away.

Measured why:

```
_searchable_files: 1.53 s, returned 3,971 files
  resolve() calls : 4,660  costing 1.13 s  (74% of the walk)
  before the fix  : 70,032 refused resolves on top of the admitted ones
```

**The fix cut `resolve()` calls from roughly 74,000 to 4,660 — a 94%
reduction — and `resolve()` is still 74% of what remains.** The remaining
calls are the ones that legitimately have to happen: every directory entry the
walk admits must be checked against the workspace, because that is the rule
the brief insisted on rather than a copied predicate.

So getting under a second is not more pruning. It is making `resolve()`
cheaper, which lives in `sandbox.py` and is out of this brief's scope by its
own forbidden list. **That is a follow-up, not a defect in this work.**

### A note on the measurement conditions

My timings ran the old implementation first in the same process, which warms
the page cache for the new one, so 1.71–1.91 s is the optimistic end. The
`.tmp-omnipatch-*` audit directory was present on disk for both halves of
every comparison, so it cannot have flattered one side over the other — it is
now gitignored (`34b65f2`) but not deleted.

### On committing the report

The engineer asked whether it should commit its own `## Result`. **My brief
did not say, and that is my omission** — briefs 04 through 09 all say "commit
that too" and brief 03 does not. It should not have had to ask.

The answer is yes, the report belongs in the repository with the work, and I
have committed it here together with this verification rather than sending the
question back for another round. A `## Result` left uncommitted is one `git
clean` from gone.
