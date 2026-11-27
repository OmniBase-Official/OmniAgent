# Clutter audit, 2026-11-26: folders, worktrees, branches, tracked files, local files

**Report only. Nothing was deleted, moved, renamed, edited, pruned or removed.** Every verdict below is a proposal the owner approves; the PM or the SE carries it out later (Part E).

**MEASURED 2026-11-26** at the integration tip `de0f5c3` (`origin` and `organization` agree), in `.scratch\sae-clutter` with `agent.__file__` printed inside it. Evidence labels: MEASURED (I ran it or read it, with the place), REPORTED (someone else's number, not re-run), UNVERIFIED (what would settle it is named). No model was run and no eval lock was created. Sealed paths (`models/`, `data/`, evaluation scripts, `grounding-cohort/`): names, sizes and hashes only. The local `.env` is named, never opened.

## Counts first

| what | count | verdicts |
| --- | --- | --- |
| Part A rows (`.scratch` entries plus every registered worktree) | **115** | DELETE-SAFE 75, KEEP 12, OWNER-ONLY 25, PRESERVE-THEN-DELETE 3 |
| of which registered worktrees | **45** (45 by `git worktree list`) | |
| of which plain folders / patch and note files | **70** | |
| Part B branch names (local ∪ `origin` ∪ `organization`) | **104** (95 local, 72 `origin`, 61 `organization`) | ASK 41, DELETE-SAFE 39, KEEP 24 |
| tags | `origin` 2, `organization` 1 (the PM's 4 and 2 count peeled `^{}` lines) | KEEP all |
| tracked files at the tip | **133** | byte-identical duplicate groups: **0** |
| tracked files nothing references | **4** (all records in `docs/pm`) | see C2 |
| local ignored entries in the main checkout (Part D) | **25** | |

**Counts the PM gave, re-measured:** `.scratch` 94 entries now (92 at the PM's count; the 94 includes my own `sae-clutter`), registered worktrees 45 (43), local branches 95 (93), `origin` 72 heads, `organization` 61 heads, one stash entry (unchanged, not touched).

## What I found that matters most

1. **[HIGH, MEASURED] The planned fast-forward of the main checkout deletes the private root rule files without a word.** The tip tracks `AGENTS.md` and `CLAUDE.md` (commit `d2f75b1`); the main checkout's commit `3b4bcd6` does not, and holds private copies at those paths (26,975 and 26,522 bytes) hidden by `.git/info/exclude`. In a throwaway repo (git 2.56.1.windows.1, deleted afterwards) `git merge --ff-only` replaced an ignored file `PRIVATE` with the incoming tracked text and printed nothing. I sent the PM this separately before finishing. **Archive the four root private files first (Part D, Batch 0).**
2. **[MEDIUM, MEASURED] Five `brief16-*` folders hold files that are in no ref.** Three hold generated wheel metadata (one of them also `wheel0/source/tests/test_config.py`); two hold the proposed tree's `archive-source` copies (7 and 2 files). The owner's ruling to delete the three snapshot refs covers the same subject, but I marked them KEEP until the owner says the ruling covers the folders.
3. **[LOW, MEASURED] 25 empty `pm-*` / `se-brief4x` folders** are the deregistered leftovers; they hold nothing. **Whether the tools can remove them is UNVERIFIED** (I ran no removal).
4. **[LOW, MEASURED] Living documents still carry facts the register changed:** six tools, `localhost`, the deleted `NEXT_CHAT.md` and demo files. They are my own architecture documents; Part C3 lists the lines.
5. **[LOW, MEASURED; CORRECTED by brief 50] `scripts/make_demo_svg.py`** reads `docs/demo-script.md` and writes `docs/demo1.svg`; both are gone. **It is named as data in the sealed source list `ANSWER_KEY` (`scripts/eval_workspace.py:65`), and deleting it fails `tests/test_eval_workspace.py::test_every_sealed_source_path_exists`. The verdict is ASK, not DELETE-SAFE; see "Correction, brief 50" below.**

## Correction, brief 50 (2026-11-27): the PM's check, and proof instead of search

**Added in a second commit. The text above is kept and corrected in place where it was wrong.** MEASURED 2026-11-27 in `.scratch\sae-proof`, a throwaway tree detached at the integration tip **`4d51b7e`** (the brief expected `97fcae2`; the tip moved, see "The tip moved" below), with `agent.__file__` printed inside it. Baseline at `4d51b7e`: ruff clean, mypy clean (64 files), pytest **1,413 passed, 2 skipped**.

### The error

The audit said `scripts/make_demo_svg.py` is "named only in documents" and DELETE-SAFE. **It is also named as data**: `scripts/eval_workspace.py:65` lists it in `ANSWER_KEY`. My search looked for imports and calls, not for paths held as string lists or sealed inventories. Deleting it, with the full gates, gives **1 failed, 1,412 passed, 2 skipped**; the failure is `tests/test_eval_workspace.py::test_every_sealed_source_path_exists` (MEASURED, reproducing the PM's result). **What would have to change with it:** the entry at `scripts/eval_workspace.py:65`, which is a sealed-list change. **Who decides:** AI/ML or the owner. Until then the file stays. **Verdict: ASK** (was DELETE-SAFE).

### Step 1. Proof per item, in the throwaway tree

Each row applied the change, ran pytest in full (and ruff and mypy for the `.py` change), restored the file from a saved copy, and compared blob hashes (`git hash-object`, first 10 hex). A documentation edit cannot change ruff or mypy results, so those two ran for the script deletion only; that is a stated limit, not a measurement of the documents.

| item | change applied | result | blob before / after | verdict |
| --- | --- | --- | --- | --- |
| `scripts/make_demo_svg.py` | `git rm` | ruff clean, mypy clean (64 files), **1 failed, 1,412 passed, 2 skipped**: `tests/test_eval_workspace.py::test_every_sealed_source_path_exists` | `3500582b9c` / `3500582b9c`, tree clean | **ASK** (was DELETE-SAFE) |
| `docs/superpowers/plans/2026-10-06-train-and-deploy.md` | `git rm` | 1,413 passed, 2 skipped | `c9bc2a162e` / `c9bc2a162e`, tree clean | the suite stays green; **ASK stays** (the owner's call, not a test question; ADR-0003 names it) |
| `docs/architecture/system-overview.md` | six to seven tools (2 lines), `localhost` to `127.0.0.1` (2 lines) | 1,413 passed, 2 skipped | `f674e2d07d` / `f674e2d07d` | **UPDATE**, proved green |
| `docs/architecture/repository-map.md` | drop the demo-generator row (line 28), drop the `NEXT_CHAT.md` entry (line 37) | 1,413 passed, 2 skipped | `d62f007750` / `d62f007750` | **UPDATE**, proved green. The row names `make_demo_svg.py`, so it must change together with that file's verdict |
| `docs/architecture/security-and-ethics.md` | `localhost` to `127.0.0.1` (lines 67, 69), drop the demo row (line 190) | 1,413 passed, 2 skipped | `70842a7948` / `70842a7948` | **UPDATE**, proved green (same caveat) |
| `docs/architecture/ADR-0005-the-graph-runtime.md` | six to seven tools (line 30) | 1,413 passed, 2 skipped | `9916694dba` / `9916694dba` | **UPDATE**, proved green |
| `docs/architecture/graph-runtime-spec.md` | "the six allowed tools" to "the seven allowed tools" | 1,413 passed, 2 skipped | `caa8393e62` / `caa8393e62` | **UPDATE**, proved green |
| `docs/architecture/security/agentic-mvp-contract-2026-11-03.md` | line 23 (the stale default-endpoint sentence) replaced by the draft text | 1,413 passed, 2 skipped | `97cf2edebf` / `97cf2edebf` | **UPDATE**, proved green. **Owner-gated: the contract is frozen and only an approved amendment edits it** |

After each row `git status --short` printed nothing. The contract's six-tools sentence (old line 33) no longer exists: the seventh-tool amendment was applied, so that earlier UPDATE is moot.

### Step 2. Paths held as data (names and line numbers only)

Searched with `git grep -n -F` over **every tracked file outside `docs/`** (code, tests, `scripts/`, `pyproject.toml`, `.github/`, every `*.toml`, `*.yml` and `*.json`, `.gitignore`, the sealed lists) for the path, the basename and the stem, at `4d51b7e`:

| candidate | hits outside `docs/` | hits inside `docs/` |
| --- | --- | --- |
| `make_demo_svg` (path, basename, stem) | `scripts/eval_workspace.py:65` (the `ANSWER_KEY` entry), `scripts/make_demo_svg.py:14` (itself) | `docs/architecture/ADR-0003-the-two-mains.md`, `repository-map.md`, `security-and-ethics.md` |
| `demo1.svg` | `scripts/make_demo_svg.py:22` (itself) | the same three documents |
| `2026-10-06-train-and-deploy` | none | `docs/architecture/ADR-0003-the-two-mains.md` |

`ANSWER_KEY` is defined at `scripts/eval_workspace.py:56`. No other tracked file outside `docs/` names any candidate. Not searched: untracked files.

### The tip moved: items that no longer exist at `4d51b7e`

Commit `0650193` removed the internal process notes (`docs/pm/`) from the public tree and `6d11da3` moved the security documents. Both are older than `4d51b7e`, but this audit's counts were taken at `de0f5c3`. At `4d51b7e` the tracked tree has 109 files and **has no `docs/pm/` files**. Consequences:

- **MOOT (already removed):** the four "unreferenced" records (`audit-2026-11-02-where-the-work-is.md`, `chase-se-2026-11-05.md`, `owner-rulings-2026-11-22.md`, `record-layer-2026-11-23-result.md`), the two files numbered brief 17, and every other `docs/pm/` row in C3. Their ASK and KEEP verdicts no longer apply to the tree. Part C's count of 133 tracked files is the count at `de0f5c3`, not the tip.
- **A finding about this document:** it lives at `docs/pm/clutter-audit-2026-11-26.md`. Merging it into the integration line would put a `docs/pm/` file back into the public tree. **The owner or PM should say where it goes** (kept off the integration line, or moved under `docs/architecture/`). I did not move it.
- The README, `CONTRIBUTING.md`, `SECURITY.md` and the other community files from brief 52 are new at the tip and were not audited here.

### Step 3. Spot-check of my own DELETE-SAFE verdicts

Random sample (seed 50), re-measured by a script that does not reuse the earlier verdict logic. Worktrees: clean tree, and HEAD contained in at least one branch on each remote. Plain folders: every file up to 5 MB hashed and found among the objects reachable from every ref (generated `egg-info` and `.tar` files excluded). Branches: `git merge-base --is-ancestor` against the tip on every ref that exists, and `git branch -r --contains` for local-only pointers.

- **Part A: 10 of 10 held.** Five worktrees (`se-brief29a`, `aie-measure-1384d63`, `aie-tool-text`, `aie-holdout-memo`, `sae-seventh-tool`) and five plain folders (`brief16-targeted-20261107b`, `brief16-baseline-20261107`, `tmp-op13-focused-16dc7395…`, `brief16-targeted-20261107`, `brief16-privacy-target`). Four of the five plain folders hold 0 files, so their "held" is trivial; the one with content, `brief16-baseline-20261107`, had 132 files, all reachable.
- **Part B: 10 of 10 held, with a caveat I should have stated.** Six of the ten (`codex/brief16-operational-telemetry-20261107`, `codex/compare-file-lines-secure-20261102`, `codex/brief16-privacy-fix-20261107`, `codex/sec-search-001-remediation-20261112`, `codex/pre-user-dataset-bounds-20261119`, `codex/brief16-defaults-20261107`) are **not ancestors of the tip**; they held only because the commit is on a remote branch. They are Batch 2b's `git branch -D` pointers, so the word "merged" in the DELETE-SAFE rule does not describe them. **Order still matters:** delete a remote branch that holds such a commit before its local pointer and the commit loses its last name.
- Not done: a second, independent method for the sample (same repository, same git), and a sample larger than ten of each. 20 of 20 is a result for the sample, not for all 75 and 39 rows.

### Step 4. Verdicts and counts changed by the proof

- **Changed:** `scripts/make_demo_svg.py` DELETE-SAFE to **ASK**. **This is the only verdict the proof changed.**
- **Part C counts, corrected** (at the tip): DELETE-SAFE **0** (was 1); ASK **2** (the sealed-list script and the training-era plan); UPDATE **5 files proved green** (`system-overview`, `repository-map`, `security-and-ethics`, `ADR-0005`, `graph-runtime-spec`) plus the contract's line 23 (owner-gated); MOOT **8 documents** removed by `0650193`.
- The Part A and Part B counts are unchanged by this correction (the proof did not touch them). Both were taken at `de0f5c3` and have not been re-taken at `4d51b7e`; the spot-check above is the only re-measurement.
- **Nothing was executed.** No batch was run, no folder was deleted, no branch was deleted.

## Part A. `.scratch\` folders and registered worktrees

Columns: **where** (S = `.scratch`, C = `.claude\worktrees`, X = `~\.codex`, T = `%TEMP%`), size in MB (walk of files, no links), newest file time, state (`worktree <branch> @<head> origin:<n> org:<n> dirty:<n>`: n = remote branches containing HEAD; dirty = `git status --short` lines), **named** (occurrences in `docs/task.md` / tracked documents), **ACTIVE** = a file written in the last 24 hours. A verdict of DELETE-SAFE is a statement about the state at the time of the run; **an ACTIVE tree belongs to a chair who may still be using it, so Part E excludes ACTIVE rows from the first batch.**

| path | where | MB | newest | state | named | verdict and evidence |
| --- | --- | ---: | --- | --- | --- | --- |
| `(main checkout)` | M | 0.0 | - | worktree integration/canonical-20261122 @3b4bcd6 origin:10 org:10 dirty:0 | n/a (generic name) | **KEEP**: the main checkout is not a scratch tree |
| `.scratch/codex-pr10-privacy-redaction-20261125` | S | 50.0 | 11-25 19:33 | worktree codex/pr10-privacy-redaction-20261125 @e7eed11 origin:3 org:3 dirty:2 ACTIVE | task:0 docs:0 | **KEEP**: uncommitted: .github/scripts/gitleaks_report.py, .github/scripts/test_gitleaks_report.py |
| `.scratch/codex-privacy-redaction-20261125` | S | 77.1 | 11-25 19:39 | worktree codex/privacy-redaction-20261125 @5ca8367 origin:1 org:1 dirty:5 ACTIVE | task:0 docs:0 | **KEEP**: uncommitted: .github/scripts/gitleaks_report.py, .github/scripts/test_gitleaks_report.py, .pytest-temp-gitleaks-run-20261125/, .pytest-temp-gitleaks-run-final-20261125/ |
| `.scratch/brief16-baseline-elevated-20261107` | S | 3.2 | 11-07 09:50 | plain folder | task:0 docs:0 | **KEEP**: 160 source files checked, 151 reachable from a ref, 5 generated, 4 other: not in any ref: wheel0\unpacked\omniagent-0.1.0.dist-info\METADATA, wheel0\unpacked\omniagent-0.1.0.dist-info\RECORD, wheel0\unpacked\omniagent-0.1.0.dist-info\top_level.txt |
| `.scratch/brief16-committed-final-20261107` | S | 3.2 | 11-07 10:01 | plain folder | task:0 docs:0 | **KEEP**: 160 source files checked, 151 reachable from a ref, 5 generated, 4 other: not in any ref: wheel0\unpacked\omniagent-0.1.0.dist-info\METADATA, wheel0\unpacked\omniagent-0.1.0.dist-info\RECORD, wheel0\unpacked\omniagent-0.1.0.dist-info\top_level.txt |
| `.scratch/brief16-current-diff-check.patch` | S | 0.4 | 11-09 16:43 | file | task:0 docs:0 | **KEEP**: a patch, not in git; unique file; owner may delete once the brief 16 ruling is confirmed to cover it |
| `.scratch/brief16-final-20261107` | S | 3.2 | 11-07 09:55 | plain folder | task:0 docs:0 | **KEEP**: 160 source files checked, 150 reachable from a ref, 5 generated, 5 other: not in any ref: wheel0\source\tests\test_config.py, wheel0\unpacked\omniagent-0.1.0.dist-info\METADATA, wheel0\unpacked\omniagent-0.1.0.dist-info\RECORD |
| `.scratch/brief16-proposed-tree-20261109-v2.patch` | S | 0.4 | 11-09 16:38 | file | task:0 docs:0 | **KEEP**: a patch, not in git; unique file; owner may delete once the brief 16 ruling is confirmed to cover it |
| `.scratch/brief16-proposed-tree-20261109.patch` | S | 0.4 | 11-09 16:28 | file | task:0 docs:0 | **KEEP**: a patch, not in git; unique file; owner may delete once the brief 16 ruling is confirmed to cover it |
| `.scratch/brief16-proposed-tree-validation-20261109` | S | 5.6 | 11-09 16:37 | plain folder | task:0 docs:0 | **KEEP**: 126 source files checked, 113 reachable from a ref, 6 generated, 7 other: not in any ref: archive-source\.gitignore, archive-source\omniagent.toml, archive-source\README.md |
| `.scratch/brief16-proposed-tree-validation-20261109-v2` | S | 5.5 | 11-09 16:42 | plain folder | task:0 docs:0 | **KEEP**: 124 source files checked, 116 reachable from a ref, 6 generated, 2 other: not in any ref: archive-source\scripts\grounding_cohort.py, archive-source\tests\test_grounding_cohort.py |
| `.scratch/snapshots-manifest-2026-11-22.md` | S | 0.0 | 11-23 06:03 | file | task:1 docs:0 | **KEEP**: the only record of the SHAs of the deleted snapshot refs |
| `~/.codex/worktrees/collect-turns-byte-limits/OmniAgent` | X | 0.9 | 11-16 17:13 | worktree codex/collect-turns-byte-limits @835c208 origin:0 org:1 dirty:0 | n/a (generic name) | **PRESERVE-THEN-DELETE**: HEAD is on organization only: push the branch to the other remote first; outside the project path; Codex-owned or unknown; owner-gated |
| `~/.codex/worktrees/mypy-portability-20261116/OmniAgent` | X | 37.3 | 11-16 07:42 | worktree codex/mypy-portability-20261116 @d787d8a origin:1 org:0 dirty:0 | n/a (generic name) | **PRESERVE-THEN-DELETE**: HEAD is on origin only: push the branch to the other remote first; outside the project path; Codex-owned or unknown; owner-gated |
| `~/.codex/worktrees/provenance-export-bounds-20261116/OmniAgent` | X | 34.7 | 11-16 08:29 | worktree codex/provenance-export-bounds-20261116 @f449cb6 origin:0 org:1 dirty:0 | n/a (generic name) | **PRESERVE-THEN-DELETE**: HEAD is on organization only: push the branch to the other remote first; outside the project path; Codex-owned or unknown; owner-gated |
| `.scratch/pm-agents` | S | 0.0 | - | empty folder | task:0 docs:0 | **OWNER-ONLY**: empty, deregistered; the PM reports the tools could not remove it |
| `.scratch/pm-codex-preserve` | S | 0.0 | - | empty folder | task:0 docs:0 | **OWNER-ONLY**: empty, deregistered; the PM reports the tools could not remove it |
| `.scratch/pm-contract7` | S | 0.0 | - | empty folder | task:0 docs:0 | **OWNER-ONLY**: empty, deregistered; the PM reports the tools could not remove it |
| `.scratch/pm-v-codex` | S | 0.0 | - | empty folder | task:0 docs:0 | **OWNER-ONLY**: empty, deregistered; the PM reports the tools could not remove it |
| `.scratch/pm-v34b` | S | 0.0 | - | empty folder | task:0 docs:0 | **OWNER-ONLY**: empty, deregistered; the PM reports the tools could not remove it |
| `.scratch/pm-v36` | S | 0.0 | - | empty folder | task:0 docs:0 | **OWNER-ONLY**: empty, deregistered; the PM reports the tools could not remove it |
| `.scratch/pm-v37` | S | 0.0 | - | empty folder | task:0 docs:0 | **OWNER-ONLY**: empty, deregistered; the PM reports the tools could not remove it |
| `.scratch/pm-v38` | S | 0.0 | - | empty folder | task:0 docs:0 | **OWNER-ONLY**: empty, deregistered; the PM reports the tools could not remove it |
| `.scratch/pm-v39` | S | 0.0 | - | empty folder | task:0 docs:0 | **OWNER-ONLY**: empty, deregistered; the PM reports the tools could not remove it |
| `.scratch/pm-v39b` | S | 0.0 | - | empty folder | task:0 docs:0 | **OWNER-ONLY**: empty, deregistered; the PM reports the tools could not remove it |
| `.scratch/pm-v43` | S | 0.0 | - | empty folder | task:0 docs:0 | **OWNER-ONLY**: empty, deregistered; the PM reports the tools could not remove it |
| `.scratch/pm-v44` | S | 0.0 | - | empty folder | task:0 docs:0 | **OWNER-ONLY**: empty, deregistered; the PM reports the tools could not remove it |
| `.scratch/pm-v45` | S | 0.0 | - | empty folder | task:0 docs:0 | **OWNER-ONLY**: empty, deregistered; the PM reports the tools could not remove it |
| `.scratch/pm-v46` | S | 0.0 | - | empty folder | task:0 docs:0 | **OWNER-ONLY**: empty, deregistered; the PM reports the tools could not remove it |
| `.scratch/pm-verify-b31` | S | 0.0 | - | empty folder | task:0 docs:0 | **OWNER-ONLY**: empty, deregistered; the PM reports the tools could not remove it |
| `.scratch/pm-verify-b32` | S | 0.0 | - | empty folder | task:0 docs:0 | **OWNER-ONLY**: empty, deregistered; the PM reports the tools could not remove it |
| `.scratch/pm-verify-fm` | S | 0.0 | - | empty folder | task:0 docs:0 | **OWNER-ONLY**: empty, deregistered; the PM reports the tools could not remove it |
| `.scratch/pm-verify-fm3` | S | 0.0 | - | empty folder | task:0 docs:0 | **OWNER-ONLY**: empty, deregistered; the PM reports the tools could not remove it |
| `.scratch/pm-verify-merge2` | S | 0.0 | - | empty folder | task:0 docs:0 | **OWNER-ONLY**: empty, deregistered; the PM reports the tools could not remove it |
| `.scratch/pm-verify-rl` | S | 0.0 | - | empty folder | task:0 docs:0 | **OWNER-ONLY**: empty, deregistered; the PM reports the tools could not remove it |
| `.scratch/pm-verify-s1` | S | 0.0 | - | empty folder | task:0 docs:0 | **OWNER-ONLY**: empty, deregistered; the PM reports the tools could not remove it |
| `.scratch/pm-verify-t0` | S | 0.0 | - | empty folder | task:0 docs:0 | **OWNER-ONLY**: empty, deregistered; the PM reports the tools could not remove it |
| `.scratch/se-brief44` | S | 0.0 | - | empty folder | task:0 docs:0 | **OWNER-ONLY**: empty, deregistered; the PM reports the tools could not remove it |
| `.scratch/se-brief45` | S | 0.0 | - | empty folder | task:0 docs:0 | **OWNER-ONLY**: empty, deregistered; the PM reports the tools could not remove it |
| `.scratch/se-brief46` | S | 0.0 | - | empty folder | task:0 docs:0 | **OWNER-ONLY**: empty, deregistered; the PM reports the tools could not remove it |
| `%TEMP%/OmniAgent-brief11-a097263` | T | 1.0 | 10-31 08:52 | worktree (detached) @a097263 origin:22 org:12 dirty:0 | task:0 docs:0 | **DELETE-SAFE**: clean; HEAD on both remotes; outside the project path; Codex-owned or unknown; owner-gated |
| `.claude/worktrees/se-brief21` | C | 48.3 | 11-22 07:28 | worktree claude/se-brief21-defaults-and-url @6831ba7 origin:30 org:29 dirty:0 | task:0 docs:3 | **DELETE-SAFE**: clean; HEAD on both remotes |
| `.claude/worktrees/se-brief22` | C | 48.3 | 11-22 07:43 | worktree claude/se-brief22-endpoint-corpus @3ac11d7 origin:30 org:29 dirty:0 | task:0 docs:3 | **DELETE-SAFE**: clean; HEAD on both remotes |
| `.claude/worktrees/se-gate2-guard-tests-09c889` | C | 49.1 | 11-22 16:21 | worktree (detached) @adf9025 origin:1 org:1 dirty:0 | task:0 docs:3 | **DELETE-SAFE**: clean; HEAD on both remotes |
| `.scratch/aie-first-measurement` | S | 51.7 | 11-25 19:07 | worktree aiml/first-measurement-20261123 @dc0c78d origin:3 org:3 dirty:0 ACTIVE | task:1 docs:0 | **DELETE-SAFE**: clean; HEAD on both remotes |
| `.scratch/aie-holdout-memo` | S | 49.4 | 11-22 20:11 | worktree aiml/holdout-instrument-memo-20261122 @dc7967f origin:1 org:1 dirty:0 | task:0 docs:0 | **DELETE-SAFE**: clean; HEAD on both remotes |
| `.scratch/aie-measure-1125e9c` | S | 1.6 | 11-25 18:17 | worktree (detached) @1125e9c origin:11 org:11 dirty:0 ACTIVE | task:0 docs:0 | **DELETE-SAFE**: clean; HEAD on both remotes |
| `.scratch/aie-measure-1384d63` | S | 1.6 | 11-24 05:55 | worktree (detached) @1384d63 origin:17 org:17 dirty:0 | task:0 docs:0 | **DELETE-SAFE**: clean; HEAD on both remotes |
| `.scratch/aie-measure-1ce7c81` | S | 2.0 | 11-24 05:50 | worktree (detached) @1ce7c81 origin:1 org:1 dirty:0 | task:0 docs:0 | **DELETE-SAFE**: clean; HEAD on both remotes |
| `.scratch/aie-measure-45cbd0e` | S | 1.6 | 11-24 06:34 | worktree (detached) @45cbd0e origin:14 org:14 dirty:0 | task:0 docs:0 | **DELETE-SAFE**: clean; HEAD on both remotes |
| `.scratch/aie-measure-b164aaa` | S | 2.0 | 11-23 07:22 | worktree (detached) @b164aaa origin:24 org:24 dirty:0 | task:0 docs:0 | **DELETE-SAFE**: clean; HEAD on both remotes |
| `.scratch/aie-measure-b860ead` | S | 1.6 | 11-25 18:17 | worktree (detached) @b860ead origin:12 org:12 dirty:0 ACTIVE | task:0 docs:0 | **DELETE-SAFE**: clean; HEAD on both remotes |
| `.scratch/aie-record-layer` | S | 49.5 | 11-23 06:40 | worktree aiml/record-layer-20261123 @5aba0c2 origin:18 org:18 dirty:0 | task:0 docs:1 | **DELETE-SAFE**: clean; HEAD on both remotes |
| `.scratch/aie-tool-text` | S | 49.4 | 11-25 19:09 | worktree aiml/brief34-measure-20261124 @705eb08 origin:1 org:1 dirty:0 ACTIVE | task:0 docs:0 | **DELETE-SAFE**: clean; HEAD on both remotes |
| `.scratch/brief16-privacy-split-20261109` | S | 50.4 | 11-10 17:02 | worktree codex/brief16-eval-privacy-split-20261109 @b6f884c origin:1 org:1 dirty:0 | task:0 docs:0 | **DELETE-SAFE**: clean; HEAD on both remotes |
| `.scratch/brief16-proposed-tree-20261109-v2` | S | 83.4 | 11-09 19:44 | worktree codex/brief16-record-schema-20261109 @395a110 origin:1 org:1 dirty:0 | task:0 docs:0 | **DELETE-SAFE**: clean; HEAD on both remotes |
| `.scratch/pm-b16` | S | 49.3 | 11-26 08:55 | worktree pm/verify-brief16 @0affaad origin:1 org:1 dirty:0 ACTIVE | task:0 docs:1 | **DELETE-SAFE**: clean; HEAD on both remotes |
| `.scratch/sae-agents-md` | S | 49.3 | 11-25 21:20 | worktree sae/agents-claude-md-review-20261125 @37b2034 origin:1 org:1 dirty:0 ACTIVE | task:0 docs:0 | **DELETE-SAFE**: clean; HEAD on both remotes |
| `.scratch/sae-b26` | S | 49.1 | 11-24 05:24 | worktree sae/snapshot-classification-20261122 @acbda4b origin:1 org:1 dirty:0 | task:0 docs:0 | **DELETE-SAFE**: clean; HEAD on both remotes |
| `.scratch/sae-clutter` | S | 1.7 | 11-26 08:57 | worktree sae/clutter-audit-20261126 @de0f5c3 origin:2 org:2 dirty:0 ACTIVE | task:0 docs:0 | **DELETE-SAFE**: clean; HEAD on both remotes |
| `.scratch/sae-seventh-tool` | S | 49.3 | 11-25 21:14 | worktree sae/seventh-tool-amendment-20261125 @50bb7e3 origin:1 org:1 dirty:0 ACTIVE | task:0 docs:1 | **DELETE-SAFE**: clean; HEAD on both remotes |
| `.scratch/se-brief29a` | S | 0.9 | 11-23 06:08 | worktree se/brief-29a-scan-report-copy @e7eed11 origin:3 org:3 dirty:0 | task:0 docs:0 | **DELETE-SAFE**: clean; HEAD on both remotes |
| `.scratch/se-brief30` | S | 49.2 | 11-23 06:27 | worktree se/brief-30a-empty-answer @682caba origin:18 org:18 dirty:0 | task:0 docs:0 | **DELETE-SAFE**: clean; HEAD on both remotes |
| `.scratch/se-brief33` | S | 49.3 | 11-24 06:16 | worktree se/brief-33-config-error-bound @bbcbe21 origin:11 org:11 dirty:0 | task:0 docs:0 | **DELETE-SAFE**: clean; HEAD on both remotes |
| `.scratch/se-brief34` | S | 49.5 | 11-24 06:24 | worktree se/brief-34-line-count-routing @45cbd0e origin:14 org:14 dirty:0 | task:0 docs:0 | **DELETE-SAFE**: clean; HEAD on both remotes |
| `.scratch/se-brief37` | S | 49.2 | 11-25 07:32 | worktree se/brief-37-no-next-chat @b860ead origin:12 org:12 dirty:0 | task:0 docs:0 | **DELETE-SAFE**: clean; HEAD on both remotes |
| `.scratch/se-brief39` | S | 49.3 | 11-26 06:54 | worktree se/brief-39-stray-args-hint @1125e9c origin:11 org:11 dirty:0 ACTIVE | task:0 docs:0 | **DELETE-SAFE**: clean; HEAD on both remotes |
| `.scratch/se-brief48` | S | 1.7 | 11-26 08:57 | worktree se/brief-48-dataset-readers @de0f5c3 origin:2 org:2 dirty:0 ACTIVE | task:0 docs:0 | **DELETE-SAFE**: clean; HEAD on both remotes |
| `.scratch/swe-gitleaks-tmpfs-20261124` | S | 53.7 | 11-24 11:43 | worktree codex/security-ci-tmpfs-report-fix-20261124 @5ca8367 origin:1 org:1 dirty:0 | task:0 docs:0 | **DELETE-SAFE**: clean; HEAD on both remotes |
| `~/.codex/visualizations/…/option-c-probe-42a5377` | X | 1.2 | 10-31 09:18 | worktree (detached) @42a5377 origin:22 org:12 dirty:0 | task:0 docs:0 | **DELETE-SAFE**: clean; HEAD on both remotes; outside the project path; Codex-owned or unknown; owner-gated |
| `~/.codex/worktrees/agent-instance-run-guard-20261116/OmniAgent` | X | 34.7 | 11-16 16:04 | worktree codex/agent-instance-run-guard-20261116 @d5ea4ab origin:1 org:2 dirty:0 | n/a (generic name) | **DELETE-SAFE**: clean; HEAD on both remotes; outside the project path; Codex-owned or unknown; owner-gated |
| `~/.codex/worktrees/agent-task-deadline/OmniAgent` | X | 0.9 | 11-16 16:44 | worktree codex/agent-task-deadline-20261116 @93ba50c origin:1 org:2 dirty:0 | n/a (generic name) | **DELETE-SAFE**: clean; HEAD on both remotes; outside the project path; Codex-owned or unknown; owner-gated |
| `~/.codex/worktrees/omniagent-scale-security-20261113/OmniAgent` | X | 55.1 | 11-15 07:41 | worktree codex/scale-security-hardening-20261113 @3576aeb origin:4 org:4 dirty:0 | n/a (generic name) | **DELETE-SAFE**: clean; HEAD on both remotes; outside the project path; Codex-owned or unknown; owner-gated |
| `~/.codex/worktrees/omniagent-structure/OmniAgent` | X | 1.1 | 10-31 09:36 | worktree (detached) @2390568 origin:22 org:12 dirty:0 | n/a (generic name) | **DELETE-SAFE**: clean; HEAD on both remotes; outside the project path; Codex-owned or unknown; owner-gated |
| `~/.codex/worktrees/post-merge-main-20261111/OmniAgent` | X | 168.1 | 11-12 06:35 | worktree codex/agentic-task-mode-fast-tools-20261111 @b0b3467 origin:4 org:4 dirty:0 | n/a (generic name) | **DELETE-SAFE**: clean; HEAD on both remotes; outside the project path; Codex-owned or unknown; owner-gated |
| `~/.codex/worktrees/publisher-atomic-no-replace/OmniAgent` | X | 0.8 | 11-16 17:50 | worktree (detached) @5005039 origin:43 org:43 dirty:0 | n/a (generic name) | **DELETE-SAFE**: clean; HEAD on both remotes; outside the project path; Codex-owned or unknown; owner-gated |
| `~/.codex/worktrees/publisher-atomic-staging/OmniAgent` | X | 0.8 | 11-16 16:15 | worktree (detached) @5005039 origin:43 org:43 dirty:0 | n/a (generic name) | **DELETE-SAFE**: clean; HEAD on both remotes; outside the project path; Codex-owned or unknown; owner-gated |
| `~/.codex/worktrees/publisher-collision-guard-20261121/OmniAgent` | X | 36.2 | 11-21 13:29 | worktree codex/publisher-collision-guard-20261121 @a2852d1 origin:1 org:1 dirty:0 | n/a (generic name) | **DELETE-SAFE**: clean; HEAD on both remotes; outside the project path; Codex-owned or unknown; owner-gated |
| `~/.codex/worktrees/windows-root-validation-clean/OmniAgent` | X | 35.2 | 11-21 12:31 | worktree codex/run-guard-deadline-combined-20261121 @0257794 origin:1 org:1 dirty:0 | n/a (generic name) | **DELETE-SAFE**: clean; HEAD on both remotes; outside the project path; Codex-owned or unknown; owner-gated |
| `.scratch/.tmp-b602-preserve-dee5b6d5e99a4a0990b993ef7465d89e` | S | 0.0 | - | empty folder | task:0 docs:0 | **DELETE-SAFE**: empty folder (0 files); removal not tested |
| `.scratch/.tmp-b602-wrapper-focused-075a4c6712a14f2b8c375c79c1d1976e` | S | 0.0 | - | empty folder | task:0 docs:0 | **DELETE-SAFE**: empty folder (0 files); removal not tested |
| `.scratch/.tmp-benchmark-v1-focused-54ac8edbd71d4f35b113dfc99f1299d1` | S | 0.0 | - | empty folder | task:0 docs:0 | **DELETE-SAFE**: empty folder (0 files); removal not tested |
| `.scratch/brief11-stage2-review-20261031-96c6a68a` | S | 49.5 | 11-02 06:53 | deregistered worktree (orphan .git file) | task:0 docs:0 | **DELETE-SAFE**: 99 source files checked, 98 reachable from a ref, 1 generated, 0 other; the rest is pytest or build output |
| `.scratch/brief11-staged-rebuild-20261031` | S | 49.6 | 11-02 06:53 | deregistered worktree (orphan .git file) | task:0 docs:0 | **DELETE-SAFE**: 99 source files checked, 98 reachable from a ref, 1 generated, 0 other; the rest is pytest or build output |
| `.scratch/brief16-baseline-20261107` | S | 2.6 | 11-07 09:48 | plain folder | task:0 docs:0 | **DELETE-SAFE**: 132 source files checked, 132 reachable from a ref, 0 generated, 0 other; the rest is pytest or build output |
| `.scratch/brief16-final-gates-20261109` | S | 2.9 | 11-09 06:42 | plain folder | task:0 docs:0 | **DELETE-SAFE**: 0 source files checked, 0 reachable from a ref, 0 generated, 0 other; the rest is pytest or build output |
| `.scratch/brief16-final-gates-20261109-r2` | S | 3.0 | 11-09 07:25 | plain folder | task:0 docs:0 | **DELETE-SAFE**: 0 source files checked, 0 reachable from a ref, 0 generated, 0 other; the rest is pytest or build output |
| `.scratch/brief16-final-gates-20261109-r3` | S | 3.0 | 11-09 07:28 | plain folder | task:0 docs:0 | **DELETE-SAFE**: 0 source files checked, 0 reachable from a ref, 0 generated, 0 other; the rest is pytest or build output |
| `.scratch/brief16-mutation-mb-provenance-is-always-named` | S | 0.0 | 11-07 09:53 | plain folder | task:0 docs:0 | **DELETE-SAFE**: 0 source files checked, 0 reachable from a ref, 0 generated, 0 other; the rest is pytest or build output |
| `.scratch/brief16-mutation-md-verbose-defaults-on` | S | 0.0 | - | empty folder | task:0 docs:0 | **DELETE-SAFE**: empty folder (0 files); removal not tested |
| `.scratch/brief16-part1-20261107` | S | 0.0 | 11-07 09:58 | plain folder | task:0 docs:0 | **DELETE-SAFE**: 0 source files checked, 0 reachable from a ref, 0 generated, 0 other; the rest is pytest or build output |
| `.scratch/brief16-part2-20261107` | S | 0.1 | 11-07 09:59 | plain folder | task:0 docs:0 | **DELETE-SAFE**: 0 source files checked, 0 reachable from a ref, 0 generated, 0 other; the rest is pytest or build output |
| `.scratch/brief16-part3-20261107` | S | 0.0 | 11-07 09:59 | plain folder | task:0 docs:0 | **DELETE-SAFE**: 0 source files checked, 0 reachable from a ref, 0 generated, 0 other; the rest is pytest or build output |
| `.scratch/brief16-privacy-target` | S | 0.3 | 11-09 06:38 | plain folder | task:0 docs:0 | **DELETE-SAFE**: 0 source files checked, 0 reachable from a ref, 0 generated, 0 other; the rest is pytest or build output |
| `.scratch/brief16-proposed-tree-20261109-tmp` | S | 0.0 | - | empty folder | task:0 docs:0 | **DELETE-SAFE**: empty folder (0 files); removal not tested |
| `.scratch/brief16-record-final-20261109` | S | 2.8 | 11-09 17:17 | plain folder | task:0 docs:0 | **DELETE-SAFE**: 0 source files checked, 0 reachable from a ref, 0 generated, 0 other; the rest is pytest or build output |
| `.scratch/brief16-record-schema-targeted` | S | 0.0 | 11-09 17:11 | plain folder | task:0 docs:0 | **DELETE-SAFE**: 0 source files checked, 0 reachable from a ref, 0 generated, 0 other; the rest is pytest or build output |
| `.scratch/brief16-record-schema-targeted-r2` | S | 0.0 | 11-09 17:12 | plain folder | task:0 docs:0 | **DELETE-SAFE**: 0 source files checked, 0 reachable from a ref, 0 generated, 0 other; the rest is pytest or build output |
| `.scratch/brief16-record-schema-targeted-r3` | S | 0.0 | 11-09 17:13 | plain folder | task:0 docs:0 | **DELETE-SAFE**: 0 source files checked, 0 reachable from a ref, 0 generated, 0 other; the rest is pytest or build output |
| `.scratch/brief16-targeted-20261107` | S | 0.1 | 11-07 09:51 | plain folder | task:0 docs:0 | **DELETE-SAFE**: 0 source files checked, 0 reachable from a ref, 0 generated, 0 other; the rest is pytest or build output |
| `.scratch/brief16-targeted-20261107b` | S | 0.1 | 11-07 09:53 | plain folder | task:0 docs:0 | **DELETE-SAFE**: 0 source files checked, 0 reachable from a ref, 0 generated, 0 other; the rest is pytest or build output |
| `.scratch/gitleaks-scan-93df011` | S | 2.8 | 11-24 11:16 | standalone clone @93df011 | task:0 docs:0 | **DELETE-SAFE**: clone, unpushed:0, HEAD on origin:1 org:1 |
| `.scratch/OmniAgent-test` | S | 41.9 | 11-16 07:22 | standalone clone @d930ee4 | task:0 docs:0 | **DELETE-SAFE**: clone, unpushed:0, HEAD on origin:47 org:48 |
| `.scratch/op7-baseline-temp-f3456cda2d3e410d8dd66f8f1f09d6cc` | S | 0.0 | - | empty folder | task:0 docs:0 | **DELETE-SAFE**: empty folder (0 files); removal not tested |
| `.scratch/op7-system-temp-0728978edda2462b895575839c87e0a8` | S | 0.0 | - | empty folder | task:0 docs:0 | **DELETE-SAFE**: empty folder (0 files); removal not tested |
| `.scratch/op7-system-temp-54eb675bf4da4fb8b88dce953a417396` | S | 0.0 | - | empty folder | task:0 docs:0 | **DELETE-SAFE**: empty folder (0 files); removal not tested |
| `.scratch/op7-system-temp-7cdfb1ff1f764f88a66e28dc8dd118f6` | S | 0.0 | - | empty folder | task:0 docs:0 | **DELETE-SAFE**: empty folder (0 files); removal not tested |
| `.scratch/phase2-main-20261111` | S | 1.2 | 11-11 07:01 | standalone clone @9c60c00 | task:0 docs:0 | **DELETE-SAFE**: clone, unpushed:0, HEAD on origin:48 org:49; 3 modified files, each working blob found in remote history |
| `.scratch/se-acceptance-review-20261107` | S | 0.0 | 11-07 11:16 | plain folder | task:0 docs:0 | **DELETE-SAFE**: 0 source files checked, 0 reachable from a ref, 0 generated, 0 other; the rest is pytest or build output |
| `.scratch/tmp-op11-baseline-attack-20261028` | S | 0.0 | - | empty folder | task:0 docs:0 | **DELETE-SAFE**: empty folder (0 files); removal not tested |
| `.scratch/tmp-op11-focused-20261028-c` | S | 0.0 | - | empty folder | task:0 docs:0 | **DELETE-SAFE**: empty folder (0 files); removal not tested |
| `.scratch/tmp-op11-postpush-20261028` | S | 0.0 | - | empty folder | task:0 docs:0 | **DELETE-SAFE**: empty folder (0 files); removal not tested |
| `.scratch/tmp-op12-break-first-final-3c5bb3cb4d8c4e19b100c70631de4bd3` | S | 0.0 | - | empty folder | task:0 docs:0 | **DELETE-SAFE**: empty folder (0 files); removal not tested |
| `.scratch/tmp-op13-focused-16dc73956536423b9fab05e9717a85b9` | S | 0.0 | - | empty folder | task:0 docs:0 | **DELETE-SAFE**: empty folder (0 files); removal not tested |
| `.scratch/tmp-op13-focused-35e465e36fbc45b7a91771bcacb11740` | S | 0.0 | - | empty folder | task:0 docs:0 | **DELETE-SAFE**: empty folder (0 files); removal not tested |

**How each verdict was reached.** Worktrees: `git worktree list --porcelain`; `git --no-optional-locks status --short` per tree; `git branch -r --contains <HEAD>` counted per remote. Plain folders: every file up to 5 MB was hashed (`git hash-object`) and looked up in the set of objects reachable from **every ref, including the snapshot refs and the stash** (`git rev-list --objects --all`), so a dangling blob does not count as safe. Folders with only pytest or build output (`test_*`, `pytest*`, `wheelhouse`, caches, `egg-info`, `.tar`) hold no source to lose. The three standalone clones were checked with their own `git status`, `git log --branches --not --remotes` and a reachability check of HEAD in this repository.

**Caveats:** removal of any folder was **not tested** (UNVERIFIED), so DELETE-SAFE does not mean the tools can remove it. `%TEMP%\OmniAgent-brief11-a097263` and the 13 Codex trees are outside the project path (ADDENDUM 2); the owner gated their removal. The two `codex-*-privacy-redaction` trees are dirty on purpose and ACTIVE (Codex is working there).

## Part B. Branches

**Counts.** 104 names: ASK 41, DELETE-SAFE 39, KEEP 24. Fully merged into the tip: 29 local, 22 `origin`, 20 `organization` (MEASURED by `git branch --merged`). A branch is merged when it is an ancestor of `origin/integration/canonical-20261122`.

- **On `origin` only (14):** `aiml/brief15-evidence-grounding-20261105`, `brief-17-wheel-completeness`, `claude/se-brief21-defaults-and-url`, `claude/se-brief22-endpoint-corpus`, `claude/se-ci-fix-pr10`, `claude/se-gate2-guard-tests-09c889`, `codex/agentic-mvp-contract-20261103`, `codex/mypy-portability-20261116`, `codex/posix-device-race-20261101`, `codex/remove-ai-handoff-docs-20261116`, `codex/search-text-race-safety-20261101-workspace`, `core-offline-runtime`, `sae/architecture-record-20261104`, `se/brief14-endpoint-loopback-20261105`
- **On `organization` only (3):** `codex/agent-instance-run-guard-20261116`, `codex/agent-task-deadline-20261116`, `codex/provenance-export-bounds-20261116`
- **Local only by name, no remote branch of that name (29; some of their commits are on other remote branches, which the table's verdict accounts for):** `chore/local-ai-delegate`, `claude/serene-maxwell-48ac41`, `codex/brief11-review-20261031-96c6a68a`, `codex/brief16-defaults-20261107`, `codex/brief16-operational-telemetry-20261107`, `codex/brief16-privacy-fix-20261107`, `codex/collect-turns-byte-limits`, `codex/compare-file-line-counts`, `codex/compare-file-lines-secure-20261102`, `codex/dataset-input-bounds-20261116`, `codex/pr10-privacy-redaction-20261125`, `codex/pre-user-dataset-bounds-20261119`, `codex/pre-user-security-logging-20261119`, `codex/privacy-publish-gate-20261112`, `codex/privacy-redaction-20261125`, `codex/promotion-readme-fix-20261112`, `codex/promotion-report-safety-20261112`, `codex/search-text-race-safety-20261101`, `codex/sec-search-001-20261112`, `codex/sec-search-001-remediation-20261112`, `codex/security-bootstrap-20261119`, `codex/weekly-usage-budget-20261118`, `sae/clutter-audit-20261126`, `se/brief-28-merge-tmp`, `se/brief-29a-scan-report-copy`, `se/brief-48-dataset-readers`, `se/brief14-mergecheck-20261105`, `se/gate2-base`, `se/merge2-20261123`
- **Same name, different SHA between remotes:** `main` (`origin` `5e7941b`, `organization` `5005039`; known: owner ruling 1) and `codex/security-ci-release-hardening-20261121` (`origin` `86c215b`, `organization` `e7eed11`).
- **Tags:** `origin`: demo-2026-10-10, legacy/origin-main-2026-11-05; `organization`: demo-2026-10-10. KEEP: `legacy/origin-main-2026-11-05` is the O line's only name.
- **Snapshot and `wip/` refs:** `snapshot/codex-local-ai-delegate-20261122`, its `-index` twin and `wip/salvage-search-text-race-safety-20261122`, on both remotes after the PM's push; KEEP. Twelve local `refs/snapshots/20261122/*` refs exist on no remote and were not touched.

**Near-duplicate families (by name):**

- `claude/se-*` (4): `se-brief21-defaults-and-url`, `se-brief22-endpoint-corpus`, `se-ci-fix-pr10`, `se-gate2-guard-tests-09c889`
- `codex/brief16-*` (5): `brief16-defaults-20261107`, `brief16-eval-privacy-split-20261109`, `brief16-operational-telemetry-20261107`, `brief16-privacy-fix-20261107`, `brief16-record-schema-20261109`
- `codex/security-remediation-*` (4): `security-remediation-batch1-20261112`, `security-remediation-batch2-20261112`, `security-remediation-batch2-22d6932-validation`, `security-remediation-batch2-validation-20261112`
- `pm/docs-*` (3): `docs-cleanup-20261125`, `docs-cleanup-main-org-20261125`, `docs-cleanup-main-origin-20261125`
- `sae/adr-*` (3): `adr-0003-carry-over`, `adr-0003-two-mains`, `adr-0005-graph-runtime`

**Names that point at the same commit (alias pairs).** `main` appears three times because local `main` is `3c76fd2`, `organization/main` is `5005039` and `origin/main` is `5e7941b`.

- `af99092`: `chore/local-ai-delegate`, `codex/brief16-defaults-20261107`, `codex/brief16-operational-telemetry-20261107`, `codex/brief16-privacy-fix-20261107`, `codex/security-remediation-batch2-20261112`, `codex/security-remediation-batch2-validation-20261112`
- `3c76fd2`: `claude/serene-maxwell-48ac41`, `codex/dataset-input-bounds-20261116`, `codex/pre-user-dataset-bounds-20261119`, `codex/pre-user-security-logging-20261119`, `codex/security-bootstrap-20261119`, `main`
- `b0b3467`: `codex/agentic-task-mode-fast-tools-20261111`, `codex/sec-search-001-20261112`, `codex/sec-search-001-remediation-20261112`
- `e7eed11`: `codex/pr10-privacy-redaction-20261125`, `codex/security-ci-release-hardening-20261121`, `se/brief-29a-scan-report-copy`
- `5005039`: `codex/privacy-publish-gate-20261112`, `main`, `se/gate2-base`
- `de0f5c3`: `integration/canonical-20261122`, `sae/clutter-audit-20261126`, `se/brief-46-parser-sites`
- `835c208`: `codex/collect-turns-byte-limits`, `codex/provenance-export-bounds-20261116`
- `2390568`: `codex/compare-file-line-counts`, `codex/search-text-race-safety-20261101`
- `92c6508`: `codex/posix-json-ci-fixes-20261112`, `codex/promotion-readme-fix-20261112`
- `5ca8367`: `codex/privacy-redaction-20261125`, `codex/security-ci-tmpfs-report-fix-20261124`
- `fa6b75c`: `codex/security-remediation-batch2-20261112`, `codex/security-remediation-batch2-22d6932-validation`
- `3b4bcd6`: `integration/canonical-20261122`, `pm/merge-b33-20261125`
- `5e7941b`: `main`, `pm/docs-cleanup-main-origin-20261125`

**Table.** `L/O/G` = local / `origin` / `organization` short SHA (`-` = absent); **ahead** = commits not in the tip; **merged** = ancestor of the tip on every ref that exists; **named** = occurrences in `docs/task.md`.

| branch | L | O | G | ahead | merged | last | named | verdict and why |
| --- | --- | --- | --- | ---: | --- | --- | ---: | --- |
| `aiml/brief15-evidence-grounding-20261105` | - | 1b4e85f | - | 81 | no | 2026-11-05 | 1 | **KEEP**: named in the task register (1x) |
| `aiml/first-measurement-20261123` | dc0c78d | dc0c78d | dc0c78d | 8 | no | 2026-11-23 | 6 | **KEEP**: named in the task register (6x) |
| `aiml/record-layer-20261123` | 5aba0c2 | 5aba0c2 | 5aba0c2 | 0 | yes | 2026-11-23 | 1 | **KEEP**: named in the task register (1x) |
| `aiml/tool-text-measure-20261123` | 2e0dce7 | 2e0dce7 | 2e0dce7 | 14 | no | 2026-11-24 | 6 | **KEEP**: named in the task register (6x) |
| `chore/local-ai-delegate` | af99092 | - | - | 102 | no | 2026-11-07 | 1 | **KEEP**: named in the task register (1x) |
| `codex/brief11-review-20261031-96c6a68a` | 67cbffd | - | - | 54 | no | 2026-10-31 | 0 | **KEEP**: local only, 54 commits past the tip, on no remote: push both before any decision |
| `codex/pr10-privacy-redaction-20261125` | e7eed11 | - | - | 11 | no | 2026-11-22 | 0 | **KEEP**: checked out in an active tree (.scratch/codex-pr10-privacy-redaction-20261125) |
| `codex/privacy-redaction-20261125` | 5ca8367 | - | - | 21 | no | 2026-11-24 | 0 | **KEEP**: checked out in an active tree (.scratch/codex-privacy-redaction-20261125) |
| `codex/security-ci-release-hardening-20261121` | 86c215b | 86c215b | e7eed11 | 3 | no | 2026-11-22 | 2 | **KEEP**: named in the task register (2x); SHAs differ between refs |
| `integration/canonical-20261122` | 3b4bcd6 | de0f5c3 | de0f5c3 | 0 | yes | 2026-11-25 | 4 | **KEEP**: guarded; SHAs differ between refs |
| `main` | 3c76fd2 | 5e7941b | 5005039 | 98 | no | 2026-11-05 | 0 | **KEEP**: guarded; SHAs differ between refs |
| `sae/adr-0003-carry-over` | 513110b | 513110b | 513110b | 102 | no | 2026-11-22 | 1 | **KEEP**: named in the task register (1x) |
| `sae/clutter-audit-20261126` | de0f5c3 | - | - | 0 | yes | 2026-11-26 | 0 | **KEEP**: checked out in an active tree (.scratch/sae-clutter) |
| `sae/snapshot-classification-20261122` | acbda4b | acbda4b | acbda4b | 6 | no | 2026-11-24 | 3 | **KEEP**: named in the task register (3x) |
| `se/brief-29b-gitignore` | 8071f93 | 8071f93 | 8071f93 | 1 | no | 2026-11-22 | 6 | **KEEP**: named in the task register (6x) |
| `se/brief-30a-empty-answer` | 682caba | 682caba | 682caba | 0 | yes | 2026-11-23 | 1 | **KEEP**: named in the task register (1x) |
| `se/brief-31-tool-text` | 1ce7c81 | 1ce7c81 | 1ce7c81 | 1 | no | 2026-11-23 | 4 | **KEEP**: named in the task register (4x) |
| `se/brief-32-config-tool-proof` | 72b3be3 | 72b3be3 | 72b3be3 | 0 | yes | 2026-11-24 | 1 | **KEEP**: named in the task register (1x) |
| `se/brief-39-stray-args-hint` | 1125e9c | 1125e9c | 1125e9c | 0 | yes | 2026-11-25 | 0 | **KEEP**: checked out in an active tree (.scratch/se-brief39) |
| `se/brief-48-dataset-readers` | 4b3cb55 | - | - | 1 | no | 2026-11-26 | 0 | **KEEP**: local only, 1 commits past the tip, on no remote: push both before any decision |
| `se/brief14-mergecheck-20261105` | 0bb8440 | - | - | 89 | no | 2026-11-05 | 0 | **KEEP**: local only, 89 commits past the tip, on no remote: push both before any decision |
| `snapshot/codex-local-ai-delegate-20261122` | 3035da7 | 3035da7 | 3035da7 | 103 | no | 2026-11-22 | 2 | **KEEP**: preserved dirty state; PM-screened |
| `snapshot/codex-local-ai-delegate-20261122-index` | - | 665b1fc | 665b1fc | 103 | no | 2026-11-22 | 0 | **KEEP**: preserved dirty state; PM-screened |
| `wip/salvage-search-text-race-safety-20261122` | 7aa7af9 | 7aa7af9 | 7aa7af9 | 54 | no | 2026-11-22 | 1 | **KEEP**: preserved dirty state; PM-screened |
| `aiml/brief34-measure-20261124` | 705eb08 | 705eb08 | 705eb08 | 29 | no | 2026-11-25 | 0 | **ASK**: 29 commits not in the tip; last commit 2026-11-25 |
| `aiml/holdout-instrument-memo-20261122` | dc7967f | dc7967f | dc7967f | 1 | no | 2026-11-22 | 0 | **ASK**: 1 commits not in the tip; last commit 2026-11-22 |
| `brief-17-wheel-completeness` | - | e38199f | - | 84 | no | 2026-11-05 | 0 | **ASK**: 84 commits not in the tip; last commit 2026-11-05 |
| `claude/se-ci-fix-pr10` | 3fa2f8b | 3fa2f8b | - | 12 | no | 2026-11-22 | 0 | **ASK**: 12 commits not in the tip; last commit 2026-11-22 |
| `codex/agent-instance-run-guard-20261116` | d5ea4ab | - | d5ea4ab | 1 | no | 2026-11-16 | 0 | **ASK**: 1 commits not in the tip; last commit 2026-11-16 |
| `codex/agent-task-deadline-20261116` | 93ba50c | - | 93ba50c | 1 | no | 2026-11-16 | 0 | **ASK**: 1 commits not in the tip; last commit 2026-11-16 |
| `codex/agentic-mvp-contract-20261103` | - | ec7787a | - | 70 | no | 2026-11-04 | 0 | **ASK**: 70 commits not in the tip; last commit 2026-11-04 |
| `codex/agentic-task-mode-fast-tools-20261111` | b0b3467 | b0b3467 | b0b3467 | 5 | no | 2026-11-12 | 0 | **ASK**: 5 commits not in the tip; last commit 2026-11-12 |
| `codex/brief16-eval-privacy-split-20261109` | b6f884c | b6f884c | b6f884c | 2 | no | 2026-11-10 | 0 | **ASK**: 2 commits not in the tip; last commit 2026-11-10 |
| `codex/brief16-record-schema-20261109` | 395a110 | 395a110 | 395a110 | 105 | no | 2026-11-09 | 0 | **ASK**: 105 commits not in the tip; last commit 2026-11-09 |
| `codex/mypy-portability-20261116` | d787d8a | d787d8a | - | 99 | no | 2026-11-16 | 0 | **ASK**: 99 commits not in the tip; last commit 2026-11-16 |
| `codex/phase2-sandbox-hardlink-windows-ci-20261111` | 8d86a17 | 8d86a17 | 8d86a17 | 1 | no | 2026-11-11 | 0 | **ASK**: 1 commits not in the tip; last commit 2026-11-11 |
| `codex/posix-device-race-20261101` | 6a1d2af | 6a1d2af | - | 58 | no | 2026-11-01 | 0 | **ASK**: 58 commits not in the tip; last commit 2026-11-01 |
| `codex/posix-json-ci-fixes-20261112` | d7a12c3 | 92c6508 | 92c6508 | 9 | no | 2026-11-12 | 0 | **ASK**: 9 commits not in the tip; last commit 2026-11-12; SHAs differ between refs |
| `codex/provenance-export-bounds-20261116` | f449cb6 | - | 835c208 | 2 | no | 2026-11-16 | 0 | **ASK**: 2 commits not in the tip; last commit 2026-11-16; SHAs differ between refs |
| `codex/publisher-collision-guard-20261121` | a2852d1 | a2852d1 | a2852d1 | 2 | no | 2026-11-21 | 0 | **ASK**: 2 commits not in the tip; last commit 2026-11-21 |
| `codex/remove-ai-handoff-docs-20261116` | - | 0402ab3 | - | 99 | no | 2026-11-16 | 0 | **ASK**: 99 commits not in the tip; last commit 2026-11-16 |
| `codex/run-guard-deadline-combined-20261121` | 0257794 | 0257794 | 0257794 | 3 | no | 2026-11-21 | 0 | **ASK**: 3 commits not in the tip; last commit 2026-11-21 |
| `codex/scale-security-hardening-20261113` | 3576aeb | 3576aeb | 3576aeb | 1 | no | 2026-11-15 | 0 | **ASK**: 1 commits not in the tip; last commit 2026-11-15 |
| `codex/search-text-race-safety-20261101-workspace` | ae898f6 | ae898f6 | - | 54 | no | 2026-11-01 | 0 | **ASK**: 54 commits not in the tip; last commit 2026-11-01 |
| `codex/security-ci-tmpfs-report-fix-20261124` | 5ca8367 | 5ca8367 | 5ca8367 | 21 | no | 2026-11-24 | 0 | **ASK**: 21 commits not in the tip; last commit 2026-11-24 |
| `codex/security-remediation-batch1-20261112` | 2998a12 | 2998a12 | 2998a12 | 6 | no | 2026-11-12 | 0 | **ASK**: 6 commits not in the tip; last commit 2026-11-12 |
| `codex/security-remediation-batch2-20261112` | fa6b75c | af99092 | af99092 | 8 | no | 2026-11-12 | 0 | **ASK**: 8 commits not in the tip; last commit 2026-11-12; SHAs differ between refs |
| `codex/security-remediation-batch2-22d6932-validation` | - | fa6b75c | fa6b75c | 8 | no | 2026-11-12 | 0 | **ASK**: 8 commits not in the tip; last commit 2026-11-12 |
| `codex/security-remediation-batch2-validation-20261112` | - | af99092 | af99092 | 102 | no | 2026-11-07 | 0 | **ASK**: 102 commits not in the tip; last commit 2026-11-07 |
| `codex/security-runner-fixtures-20261120` | d045397 | 420e9b0 | 420e9b0 | 12 | no | 2026-11-21 | 0 | **ASK**: 12 commits not in the tip; last commit 2026-11-21; SHAs differ between refs |
| `codex/security-scans-validation-20261120` | 0e1e3f0 | 0e1e3f0 | 0e1e3f0 | 7 | no | 2026-11-20 | 0 | **ASK**: 7 commits not in the tip; last commit 2026-11-20 |
| `codex/windows-private-root-validation-20261121` | 870e8fb | 870e8fb | 870e8fb | 22 | no | 2026-11-21 | 0 | **ASK**: 22 commits not in the tip; last commit 2026-11-21 |
| `core-offline-runtime` | fd5176a | fd5176a | - | 12 | no | 2026-10-23 | 0 | **ASK**: 12 commits not in the tip; last commit 2026-10-23 |
| `pm/codex-privacy-redaction-20261125` | 0f6a4ef | 0f6a4ef | 0f6a4ef | 12 | no | 2026-11-25 | 0 | **ASK**: 12 commits not in the tip; last commit 2026-11-25 |
| `pm/docs-cleanup-main-org-20261125` | bdc5814 | bdc5814 | bdc5814 | 1 | no | 2026-11-25 | 0 | **ASK**: 1 commits not in the tip; last commit 2026-11-25 |
| `pm/docs-cleanup-main-origin-20261125` | 5e7941b | 5e7941b | 5e7941b | 100 | no | 2026-11-25 | 0 | **ASK**: 100 commits not in the tip; last commit 2026-11-25 |
| `pm/verify-brief16` | 0affaad | 0affaad | 0affaad | 219 | no | 2026-11-26 | 0 | **ASK**: 219 commits not in the tip; last commit 2026-11-26 |
| `sae/adr-0003-two-mains` | 18d9675 | 18d9675 | 18d9675 | 101 | no | 2026-11-21 | 0 | **ASK**: 101 commits not in the tip; last commit 2026-11-21 |
| `sae/adr-0005-graph-runtime` | b2ac724 | b2ac724 | b2ac724 | 116 | no | 2026-11-22 | 0 | **ASK**: 116 commits not in the tip; last commit 2026-11-22 |
| `sae/agents-claude-md-review-20261125` | 37b2034 | 37b2034 | 37b2034 | 1 | no | 2026-11-25 | 0 | **ASK**: 1 commits not in the tip; last commit 2026-11-25 |
| `sae/architecture-record-20261104` | - | f1f711d | - | 77 | no | 2026-11-04 | 0 | **ASK**: 77 commits not in the tip; last commit 2026-11-04 |
| `sae/seventh-tool-amendment-20261125` | 50bb7e3 | 50bb7e3 | 50bb7e3 | 1 | no | 2026-11-25 | 0 | **ASK**: 1 commits not in the tip; last commit 2026-11-25 |
| `se/brief-27-variant-picks` | adf9025 | adf9025 | adf9025 | 2 | no | 2026-11-22 | 0 | **ASK**: 2 commits not in the tip; last commit 2026-11-22 |
| `se/brief-36-next-chat-removal` | d05c206 | d05c206 | d05c206 | 99 | no | 2026-11-25 | 0 | **ASK**: 99 commits not in the tip; last commit 2026-11-25 |
| `se/brief14-endpoint-loopback-20261105` | - | 8dbf75b | - | 84 | no | 2026-11-05 | 0 | **ASK**: 84 commits not in the tip; last commit 2026-11-05 |
| `claude/se-brief21-defaults-and-url` | 6831ba7 | 6831ba7 | - | 0 | yes | 2026-11-22 | 0 | **DELETE-SAFE**: fully merged into the integration tip; checked out in .claude/worktrees/se-brief21: remove the tree first |
| `claude/se-brief22-endpoint-corpus` | 3ac11d7 | 3ac11d7 | - | 0 | yes | 2026-11-22 | 0 | **DELETE-SAFE**: fully merged into the integration tip; checked out in .claude/worktrees/se-brief22: remove the tree first |
| `claude/se-gate2-guard-tests-09c889` | 01a0938 | 01a0938 | - | 0 | yes | 2026-11-22 | 0 | **DELETE-SAFE**: fully merged into the integration tip |
| `claude/serene-maxwell-48ac41` | 3c76fd2 | - | - | 98 | no | 2026-11-05 | 0 | **DELETE-SAFE**: local pointer; its commit is on a remote branch |
| `codex/brief16-defaults-20261107` | af99092 | - | - | 102 | no | 2026-11-07 | 0 | **DELETE-SAFE**: local pointer; its commit is on a remote branch |
| `codex/brief16-operational-telemetry-20261107` | af99092 | - | - | 102 | no | 2026-11-07 | 0 | **DELETE-SAFE**: local pointer; its commit is on a remote branch |
| `codex/brief16-privacy-fix-20261107` | af99092 | - | - | 102 | no | 2026-11-07 | 0 | **DELETE-SAFE**: local pointer; its commit is on a remote branch |
| `codex/collect-turns-byte-limits` | 835c208 | - | - | 3 | no | 2026-11-16 | 0 | **DELETE-SAFE**: local pointer; its commit is on a remote branch; checked out in ~/.codex/worktrees/collect-turns-byte-limits/OmniAgent: remove the tree first |
| `codex/compare-file-line-counts` | 2390568 | - | - | 53 | no | 2026-10-31 | 0 | **DELETE-SAFE**: local pointer; its commit is on a remote branch |
| `codex/compare-file-lines-secure-20261102` | f37044d | - | - | 66 | no | 2026-11-02 | 0 | **DELETE-SAFE**: local pointer; its commit is on a remote branch |
| `codex/dataset-input-bounds-20261116` | 3c76fd2 | - | - | 98 | no | 2026-11-05 | 0 | **DELETE-SAFE**: local pointer; its commit is on a remote branch |
| `codex/pre-user-dataset-bounds-20261119` | 3c76fd2 | - | - | 98 | no | 2026-11-05 | 0 | **DELETE-SAFE**: local pointer; its commit is on a remote branch |
| `codex/pre-user-security-logging-20261119` | 3c76fd2 | - | - | 98 | no | 2026-11-05 | 0 | **DELETE-SAFE**: local pointer; its commit is on a remote branch |
| `codex/privacy-publish-gate-20261112` | 5005039 | - | - | 0 | yes | 2026-11-12 | 0 | **DELETE-SAFE**: local pointer; its commit is on a remote branch |
| `codex/promotion-readme-fix-20261112` | 92c6508 | - | - | 11 | no | 2026-11-12 | 0 | **DELETE-SAFE**: local pointer; its commit is on a remote branch |
| `codex/promotion-report-safety-20261112` | 1ec9283 | - | - | 10 | no | 2026-11-12 | 0 | **DELETE-SAFE**: local pointer; its commit is on a remote branch |
| `codex/search-text-race-safety-20261101` | 2390568 | - | - | 53 | no | 2026-10-31 | 0 | **DELETE-SAFE**: local pointer; its commit is on a remote branch |
| `codex/sec-search-001-20261112` | b0b3467 | - | - | 5 | no | 2026-11-12 | 0 | **DELETE-SAFE**: local pointer; its commit is on a remote branch |
| `codex/sec-search-001-remediation-20261112` | b0b3467 | - | - | 5 | no | 2026-11-12 | 0 | **DELETE-SAFE**: local pointer; its commit is on a remote branch |
| `codex/security-bootstrap-20261119` | 3c76fd2 | - | - | 98 | no | 2026-11-05 | 0 | **DELETE-SAFE**: local pointer; its commit is on a remote branch |
| `codex/weekly-usage-budget-20261118` | d930ee4 | - | - | 0 | yes | 2026-11-11 | 0 | **DELETE-SAFE**: local pointer; its commit is on a remote branch |
| `pm/contract-seventh-tool-20261126` | 3bc08bb | 3bc08bb | 3bc08bb | 0 | yes | 2026-11-26 | 0 | **DELETE-SAFE**: fully merged into the integration tip |
| `pm/docs-cleanup-20261125` | 146e2e7 | 146e2e7 | 146e2e7 | 0 | yes | 2026-11-25 | 0 | **DELETE-SAFE**: fully merged into the integration tip |
| `pm/merge-b33-20261125` | 3b4bcd6 | 3b4bcd6 | 3b4bcd6 | 0 | yes | 2026-11-25 | 0 | **DELETE-SAFE**: fully merged into the integration tip |
| `pm/track-agents-claude-md-20261126` | d2f75b1 | d2f75b1 | d2f75b1 | 0 | yes | 2026-11-26 | 0 | **DELETE-SAFE**: fully merged into the integration tip |
| `se/brief-28-merge-tmp` | b164aaa | - | - | 0 | yes | 2026-11-22 | 0 | **DELETE-SAFE**: local pointer; its commit is on a remote branch |
| `se/brief-28a-preflight-status-only` | a6e7c38 | a6e7c38 | a6e7c38 | 0 | yes | 2026-11-22 | 0 | **DELETE-SAFE**: fully merged into the integration tip |
| `se/brief-28b-bounded-provenance` | a10a41b | a10a41b | a10a41b | 0 | yes | 2026-11-22 | 0 | **DELETE-SAFE**: fully merged into the integration tip |
| `se/brief-28c-export-read-limits` | ccefadc | ccefadc | ccefadc | 0 | yes | 2026-11-22 | 0 | **DELETE-SAFE**: fully merged into the integration tip |
| `se/brief-29a-scan-report-copy` | e7eed11 | - | - | 11 | no | 2026-11-22 | 0 | **DELETE-SAFE**: local pointer; its commit is on a remote branch; checked out in .scratch/se-brief29a: remove the tree first |
| `se/brief-33-config-error-bound` | bbcbe21 | bbcbe21 | bbcbe21 | 0 | yes | 2026-11-24 | 0 | **DELETE-SAFE**: fully merged into the integration tip; checked out in .scratch/se-brief33: remove the tree first |
| `se/brief-34-line-count-routing` | 45cbd0e | 45cbd0e | 45cbd0e | 0 | yes | 2026-11-24 | 0 | **DELETE-SAFE**: fully merged into the integration tip; checked out in .scratch/se-brief34: remove the tree first |
| `se/brief-37-no-next-chat` | b860ead | b860ead | b860ead | 0 | yes | 2026-11-25 | 0 | **DELETE-SAFE**: fully merged into the integration tip; checked out in .scratch/se-brief37: remove the tree first |
| `se/brief-43-recursion-guard` | a2307ff | a2307ff | a2307ff | 0 | yes | 2026-11-26 | 0 | **DELETE-SAFE**: fully merged into the integration tip |
| `se/brief-44-private-rules-guard` | 7acc15f | 7acc15f | 7acc15f | 0 | yes | 2026-11-26 | 0 | **DELETE-SAFE**: fully merged into the integration tip |
| `se/brief-45-model-cli-recursion` | 867fb6d | 867fb6d | 867fb6d | 0 | yes | 2026-11-26 | 0 | **DELETE-SAFE**: fully merged into the integration tip |
| `se/brief-46-parser-sites` | de0f5c3 | de0f5c3 | de0f5c3 | 0 | yes | 2026-11-26 | 0 | **DELETE-SAFE**: fully merged into the integration tip |
| `se/gate2-base` | 5005039 | - | - | 0 | yes | 2026-11-12 | 0 | **DELETE-SAFE**: local pointer; its commit is on a remote branch |
| `se/merge2-20261123` | 1384d63 | - | - | 0 | yes | 2026-11-23 | 0 | **DELETE-SAFE**: local pointer; its commit is on a remote branch |

**Rule used:** KEEP = `main`, the integration branch, `snapshot/`, `wip/`, anything named in `docs/task.md`, anything checked out in an ACTIVE tree, and local-only branches with commits on no remote (push both first). DELETE-SAFE = merged into the tip on every ref that exists. ASK = unmerged, not named in the register: the owner decides. A branch checked out in a tree cannot be deleted until the tree is removed (the table says which).

### Proposed remote deletions (none run)

Each needs the owner's yes, because a remote deletion is outward-facing. `origin` (17):

```
git push origin --delete claude/se-brief21-defaults-and-url
git push origin --delete claude/se-brief22-endpoint-corpus
git push origin --delete claude/se-gate2-guard-tests-09c889
git push origin --delete pm/contract-seventh-tool-20261126
git push origin --delete pm/docs-cleanup-20261125
git push origin --delete pm/merge-b33-20261125
git push origin --delete pm/track-agents-claude-md-20261126
git push origin --delete se/brief-28a-preflight-status-only
git push origin --delete se/brief-28b-bounded-provenance
git push origin --delete se/brief-28c-export-read-limits
git push origin --delete se/brief-33-config-error-bound
git push origin --delete se/brief-34-line-count-routing
git push origin --delete se/brief-37-no-next-chat
git push origin --delete se/brief-43-recursion-guard
git push origin --delete se/brief-44-private-rules-guard
git push origin --delete se/brief-45-model-cli-recursion
git push origin --delete se/brief-46-parser-sites
```

`organization` (14):

```
git push organization --delete pm/contract-seventh-tool-20261126
git push organization --delete pm/docs-cleanup-20261125
git push organization --delete pm/merge-b33-20261125
git push organization --delete pm/track-agents-claude-md-20261126
git push organization --delete se/brief-28a-preflight-status-only
git push organization --delete se/brief-28b-bounded-provenance
git push organization --delete se/brief-28c-export-read-limits
git push organization --delete se/brief-33-config-error-bound
git push organization --delete se/brief-34-line-count-routing
git push organization --delete se/brief-37-no-next-chat
git push organization --delete se/brief-43-recursion-guard
git push organization --delete se/brief-44-private-rules-guard
git push organization --delete se/brief-45-model-cli-recursion
git push organization --delete se/brief-46-parser-sites
```

## Part C. Tracked files

**C1. Byte-identical duplicates (blob-hash groups over all 133 tracked paths): none.** `git ls-tree -r` at the tip, grouped by blob id: 0 groups. (MEASURED.)

**C2. Tracked files nothing references.** Method: for every tracked file except tests (collected by pytest), the root rule files, `LICENSE`, `.gitignore`, `pyproject.toml`, the briefs and the ADRs (history), search the other tracked non-sealed files for its module name (`git grep -w`, `.py` at the root) or its file name (`git grep -F`). **Not searched:** the sealed evaluation scripts and `grounding-cohort/` were left out of the search corpus (names, sizes and hashes only).

- `docs/pm/audit-2026-11-02-where-the-work-is.md`: **ASK: a point-in-time audit from 2026-11-02, superseded by ADR-0003 and this document**
- `docs/pm/chase-se-2026-11-05.md`: **ASK: a chase note to the SE dated 2026-11-05; the work it chased is merged**
- `docs/pm/owner-rulings-2026-11-22.md`: **KEEP: the record of rulings 1 to 25; the task register carries the later ones**
- `docs/pm/record-layer-2026-11-23-result.md`: **KEEP: a result document; the evidence for the record layer**

**CORRECTED (brief 50).** The sentence "every code file is referenced" below searched imports and calls only, not paths held as data. The orphan-script finding has the wrong verdict: `scripts/make_demo_svg.py` is named in `scripts/eval_workspace.py:65` (the sealed `ANSWER_KEY`), and a throwaway deletion fails one test (see the correction section). **Verdict: ASK** (the sealed list names it; AI/ML or the owner changes the list, or the file stays). The original text said DELETE-SAFE and is superseded.

**C3. Documents that mislead (lines at the tip, MEASURED by `git grep -n`).**

| file:line | says | verdict |
| --- | --- | --- |
| `docs/architecture/system-overview.md:21, 23, 75, 88, 89, 138` | six tools; the default endpoint `http://localhost:11434/v1`; README quoted as "Nothing leaves localhost"; localhost-only egress | **UPDATE** (seven tools after the amendment; the default is `127.0.0.1`; README no longer says it) |
| `docs/architecture/repository-map.md:28` | `scripts/make_demo_svg.py`, `docs/demo1.svg` as live assets | **UPDATE** with C2's deletion |
| `docs/architecture/repository-map.md:37` | `NEXT_CHAT.md` listed as a contributor entry point | **UPDATE** (the file is deleted and must never return) |
| `docs/architecture/security-and-ethics.md:67, 69, 190` | default `localhost:11434`; localhost-only egress "at this baseline"; `docs/demo1.svg` as an asset | **UPDATE** |
| `docs/pm/agentic-mvp-contract-2026-11-03.md` §2 line 33 and §6 line 139 | six tools | **UPDATE after the owner approves the seventh-tool proposal** (brief 40); not before |
| `docs/architecture/ADR-0005-the-graph-runtime.md:30`, `graph-runtime-spec.md:39` | six tools | **UPDATE** with the same amendment (my documents) |
| `docs/pm/proposed-contract-amendment-endpoint-2026-11-22.md` | a proposal; its banner says APPLIED | **KEEP** (the amendment record); it carries 17 `localhost` mentions on purpose |
| `docs/pm/brief-*.md`, `docs/architecture/ADR-0001..0003`, `release-readiness`, `threat-model`, `assignments`, `owner-rulings` | historical mentions of the same facts | **KEEP**: they are the evidence trail; the mentions are dated statements, not claims about the present (UNVERIFIED line by line) |
| `docs/pm/brief-17-pm-verification-2026-11-05.md` and `brief-17-the-wheel-ships-what-it-claims.md` | two files numbered 17 | **ASK**: a reader cannot tell which is the brief |
| `docs/superpowers/plans/2026-10-06-train-and-deploy.md` (13,683 bytes) | an early training-era plan; named only by ADR-0003 and brief 01 | **ASK** (owner) |
| `README.md`, `AGENTS.md`, `CLAUDE.md` | no six-tools or `localhost` claim; `AGENTS.md` names `NEXT_CHAT.md` on purpose (the rule) | **KEEP** |
| `tests/test_no_next_chat.py`, `tests/test_eval_workspace.py` | name `NEXT_CHAT` as a guard and a sealed-path list | **KEEP** |

**C4. Top-level clutter.**

| item | what it is for; who uses it | verdict and evidence |
| --- | --- | --- |
| `grounding-cohort/` (3 files: `README.txt` 894 B `58389611`, `ledger-alpha.txt` 453 B `89d69f1e`, `ledger-beta.txt` 590 B `ead6c445`) | the grounding evaluation's ledgers; sealed, names/sizes/hashes only | **KEEP**: `scripts/grounding_cohort.py` and `tests/test_grounding_cohort.py` use it |
| `notebooks/train_omniagent_lora.ipynb` (20,836 B) | the training notebook, generated by `scripts/build_notebook.py` and tested by `tests/test_notebook.py`; named by README | **KEEP** |
| `omniagent.toml` | the shipped profiles; `config.py` reads it; `tests/test_shipped_config.py` pins it | **KEEP** |
| `requirements.txt` (160 B) | the pip install list; README, CI and the docs name it | **KEEP** |
| `trajectory_utils.py` (391 B) | imported by `export_dataset.py`, `validate_dataset.py`, `pyproject.toml` | **KEEP** |
| `dataset_limits.py`, `dataset_provenance.py`, `export_dataset.py`, `validate_dataset.py` | the dataset readers and exporters; tested | **KEEP** |
| `scripts/smoke_train.py` (6,517 B) | a training smoke script; README and docs name it; no test imports it | **KEEP** (README names it; UNVERIFIED whether anyone runs it) |
| `scripts/make_demo_svg.py` (5,481 B) | demo generator whose input and output are gone; **named in the sealed `ANSWER_KEY` (`scripts/eval_workspace.py:65`)** | **ASK** (corrected from DELETE-SAFE: deleting it fails `test_every_sealed_source_path_exists`) |
| `docs/dataset-bundles.md` (5,027 B) | the dataset publishing note; named by ADR-0003 and brief 19 | **KEEP** |
| sealed evaluation scripts (`scripts/eval_scoring.py` 5,283 B `8a68cd41`, `eval_workspace.py` 6,429 B `0453be72`, `holdout_eval.py` 20,067 B `76d68a60`, `session_eval.py` 15,167 B `6e92a53e`, `grounding_cohort.py` 31,314 B `f25dd207`) | evaluation; not opened | **KEEP**: ten test files name them |

## Part D. Untracked and ignored local files of the main checkout

`git status --short --ignored` in `D:\code-project\OmniAgent` (read-only; the tree was not edited). The checkout is on `integration/canonical-20261122` at `3b4bcd6`, two commits behind the tip. Sizes are walked file sizes; **`.env` is named only, never opened.**

| entry | size | note |
| --- | ---: | --- |
| `models/` | 15,768.09 MB | sealed; model weights |
| `.venv/` | 5,059.43 MB | the shared virtualenv; editable install, every tree uses it (do not delete) |
| `.scratch/` | 1,202.17 MB | all trees in Part A |
| `.mypy_cache/` | 161.50 MB | cache |
| `.claude/` | 145.77 MB | session worktrees (`.claude/worktrees`) |
| `.ci-venv/` | 124.08 MB | a throwaway venv used to rehearse CI locally; recreatable |
| `.pytest_cache/` | 55.88 MB | cache |
| `omniagent-core/` | 37.74 MB | an ignored folder of an older core copy; not referenced by any tracked file (UNVERIFIED who uses it) |
| `data/` | 12.48 MB | sealed |
| `tests/__pycache__/` | 1.25 MB | cache |
| `__pycache__/` | 0.26 MB | cache |
| `scripts/__pycache__/` | 0.14 MB | cache |
| `.ruff_cache/` | 0.09 MB | cache |
| `.superpowers/` | 0.07 MB | tool state |
| `omniagent.egg-info/` | 0.03 MB | editable-install metadata |
| `docs/task.md` | 0.03 MB | the PM's task register; local only |
| `AGENTS.md` | 0.03 MB | PRIVATE root file, ignored; **collides with the tracked file at the tip** |
| `CLAUDE.md` | 0.03 MB | PRIVATE root file, ignored; **collides with the tracked file at the tip** |
| `CODEX.md` | 0.02 MB | private; proposed to drop (brief 42) |
| `docs/pm/handoff-prompt.md` | 0.01 MB | a local-only prompt |
| `CURSOR.md` | 0.01 MB | private |
| `.ai/` | 0.01 MB | the local-AI bridge script (`.ai/delegate.py`) |
| `.vscode/` | 0.00 MB | editor |
| `.kilo/` | 0.00 MB | tool state |
| `.env` | 0.00 MB | present; not opened |

**The rule-bearing files, sizes and SHA-256 prefixes only (never contents):**

| file | bytes | sha256[:12] |
| --- | ---: | --- |
| root AGENTS.md | 26975 | 387d0c5bab75 |
| root CLAUDE.md | 26522 | 1a16f156c0df |
| root CODEX.md | 16183 | 93ff3995e51a |
| root CURSOR.md | 9237 | 0f2d8faab408 |
| ~/.claude/CLAUDE.md | 17010 | 1ca6e1da9704 |
| ~/.codex/AGENTS.md | 17465 | c3459e492581 |
| **tracked** `AGENTS.md` at the tip | 8911 | 50b7e3772f68 |
| **tracked** `CLAUDE.md` at the tip | 2175 | 1b28de3147c0 |

**Drift:** the six local files all differ from each other and from the two tracked files (sizes 9,237 to 26,975 bytes against 8,911 and 2,175). **The tracked `AGENTS.md` (8,911 B) is not the private root `AGENTS.md` (26,975 B): the private file carries rules the tracked one does not.** What is in the private bytes beyond the user-level files is not known to me.

## Part E. A deletion plan (none of it was run)

Every batch runs from a shell that is **not** inside the tree it removes (the trap that left the `pm-*` folders). Each batch ends with the counts in the table.

### Batch 0. Archive before anything (owner; PM carries out)

1. Copy `AGENTS.md`, `CLAUDE.md`, `CODEX.md`, `CURSOR.md` from `D:\code-project\OmniAgent` to a folder **outside** the repository, and compare SHA-256 against Part D. **Nothing else in this plan may touch the main checkout until this is done and the owner confirms**, because the fast-forward to the tip overwrites the two ignored private copies silently (finding 1).
2. Check: the four hashes of the copies equal Part D's. Undo: not needed.

### Batch 1. Deregistered and clean-and-pushed folders (PM; owner approves the list)

- **1a. Registered trees under `.scratch` and `.claude` that are DELETE-SAFE and not ACTIVE: 18** (`git worktree remove <path>`). **ACTIVE and DELETE-SAFE (10): leave until the chair says it is finished**: `.scratch/aie-first-measurement`, `.scratch/aie-measure-1125e9c`, `.scratch/aie-measure-b860ead`, `.scratch/aie-tool-text`, `.scratch/pm-b16`, `.scratch/sae-agents-md`, `.scratch/sae-clutter`, `.scratch/sae-seventh-tool`, `.scratch/se-brief39`, `.scratch/se-brief48`.

```
git worktree remove "D:/code-project/OmniAgent/.claude/worktrees/se-brief21"
git worktree remove "D:/code-project/OmniAgent/.claude/worktrees/se-brief22"
git worktree remove "D:/code-project/OmniAgent/.claude/worktrees/se-gate2-guard-tests-09c889"
git worktree remove "D:/code-project/OmniAgent/.scratch/aie-holdout-memo"
git worktree remove "D:/code-project/OmniAgent/.scratch/aie-measure-1384d63"
git worktree remove "D:/code-project/OmniAgent/.scratch/aie-measure-1ce7c81"
git worktree remove "D:/code-project/OmniAgent/.scratch/aie-measure-45cbd0e"
git worktree remove "D:/code-project/OmniAgent/.scratch/aie-measure-b164aaa"
git worktree remove "D:/code-project/OmniAgent/.scratch/aie-record-layer"
git worktree remove "D:/code-project/OmniAgent/.scratch/brief16-privacy-split-20261109"
git worktree remove "D:/code-project/OmniAgent/.scratch/brief16-proposed-tree-20261109-v2"
git worktree remove "D:/code-project/OmniAgent/.scratch/sae-b26"
git worktree remove "D:/code-project/OmniAgent/.scratch/se-brief29a"
git worktree remove "D:/code-project/OmniAgent/.scratch/se-brief30"
git worktree remove "D:/code-project/OmniAgent/.scratch/se-brief33"
git worktree remove "D:/code-project/OmniAgent/.scratch/se-brief34"
git worktree remove "D:/code-project/OmniAgent/.scratch/se-brief37"
git worktree remove "D:/code-project/OmniAgent/.scratch/swe-gitleaks-tmpfs-20261124"
```

- **1b. Plain folders, DELETE-SAFE (36):** PowerShell `Remove-Item -LiteralPath <path> -Recurse -Force`, one at a time, after the owner has read Part A. Paths: `.tmp-b602-preserve-dee5b6d5e99a4a0990b993ef7465d89e`, `.tmp-b602-wrapper-focused-075a4c6712a14f2b8c375c79c1d1976e`, `.tmp-benchmark-v1-focused-54ac8edbd71d4f35b113dfc99f1299d1`, `brief11-stage2-review-20261031-96c6a68a`, `brief11-staged-rebuild-20261031`, `brief16-baseline-20261107`, `brief16-final-gates-20261109`, `brief16-final-gates-20261109-r2`, `brief16-final-gates-20261109-r3`, `brief16-mutation-mb-provenance-is-always-named`, `brief16-mutation-md-verbose-defaults-on`, `brief16-part1-20261107`, `brief16-part2-20261107`, `brief16-part3-20261107`, `brief16-privacy-target`, `brief16-proposed-tree-20261109-tmp`, `brief16-record-final-20261109`, `brief16-record-schema-targeted`, `brief16-record-schema-targeted-r2`, `brief16-record-schema-targeted-r3`, `brief16-targeted-20261107`, `brief16-targeted-20261107b`, `gitleaks-scan-93df011`, `OmniAgent-test`, `op7-baseline-temp-f3456cda2d3e410d8dd66f8f1f09d6cc`, `op7-system-temp-0728978edda2462b895575839c87e0a8`, `op7-system-temp-54eb675bf4da4fb8b88dce953a417396`, `op7-system-temp-7cdfb1ff1f764f88a66e28dc8dd118f6`, `phase2-main-20261111`, `se-acceptance-review-20261107`, `tmp-op11-baseline-attack-20261028`, `tmp-op11-focused-20261028-c`, `tmp-op11-postpush-20261028`, `tmp-op12-break-first-final-3c5bb3cb4d8c4e19b100c70631de4bd3`, `tmp-op13-focused-16dc73956536423b9fab05e9717a85b9`, `tmp-op13-focused-35e465e36fbc45b7a91771bcacb11740`.
- **1c. OWNER-ONLY, 25 empty folders** (`pm-*`, `se-brief44..46`): the owner closes any shell or editor standing in them, then removes them; if one still refuses, `handle.exe` or a restart settles it. Nothing is in them to lose (0 files each, MEASURED).
- **1d. PRESERVE-THEN-DELETE (3 Codex trees, outside the path, owner-gated):** first `git push origin codex/collect-turns-byte-limits`, `git push origin codex/provenance-export-bounds-20261116` and `git push organization codex/mypy-portability-20261116` (each branch exists on one remote only), then `git ls-remote origin <b>` equals `git ls-remote organization <b>` for each, then `git worktree remove`. The remaining Codex and `%TEMP%` trees (11 DELETE-SAFE) are the owner's decision and Codex's to move.
- **KEEP in Part A:** the `brief16-*` folders with unreachable files, the three patches and the manifest, the two dirty Codex trees, the main checkout.
- **Before:** `git worktree list`, and per tree `git status --short` empty and `git rev-list HEAD --not --remotes` empty. **After:** `git worktree list` shorter by exactly the removed count; `git branch -a` unchanged. **Undo:** `git worktree add <path> <sha>` recreates a tree; a plain-folder removal is not undoable, which is why the content check ran first.

### Batch 2. Local branch pointers (SE or PM)

32 local branches are DELETE-SAFE and not checked out in a tree; branches checked out in a tree wait for Batch 1. **Run from a tree whose HEAD is the integration tip** (for example `.scratch\sae-clutter`): `git branch -d` judges 'merged' against the current HEAD, not against the tip, so from the main checkout (`3b4bcd6`) it would refuse the newest ones. The remote copies are untouched.

**2a. Merged into the tip (17), `git branch -d`:**

```
git branch -d claude/se-gate2-guard-tests-09c889   # was 01a0938
git branch -d codex/privacy-publish-gate-20261112   # was 5005039
git branch -d codex/weekly-usage-budget-20261118   # was d930ee4
git branch -d pm/contract-seventh-tool-20261126   # was 3bc08bb
git branch -d pm/docs-cleanup-20261125   # was 146e2e7
git branch -d pm/merge-b33-20261125   # was 3b4bcd6
git branch -d pm/track-agents-claude-md-20261126   # was d2f75b1
git branch -d se/brief-28-merge-tmp   # was b164aaa
git branch -d se/brief-28a-preflight-status-only   # was a6e7c38
git branch -d se/brief-28b-bounded-provenance   # was a10a41b
git branch -d se/brief-28c-export-read-limits   # was ccefadc
git branch -d se/brief-43-recursion-guard   # was a2307ff
git branch -d se/brief-44-private-rules-guard   # was 7acc15f
git branch -d se/brief-45-model-cli-recursion   # was 867fb6d
git branch -d se/brief-46-parser-sites   # was de0f5c3
git branch -d se/gate2-base   # was 5005039
git branch -d se/merge2-20261123   # was 1384d63
```

**2b. Not merged into the tip, but the commit is on a remote branch (15), `git branch -D` (the pointer only; the commit stays on the remote branch).** These are the O-line and Codex experiment pointers. **Before each:** `git branch -r --contains <sha>` prints at least one branch, and the owner has read that Batch 4 does not delete that branch first. **Order matters:** do Batch 2b before any Batch 4 deletion of the branches that hold these commits, or the commit loses its last name (the tag `legacy/origin-main-2026-11-05` keeps `3c76fd2`).

```
git branch -D claude/serene-maxwell-48ac41   # was 3c76fd2
git branch -D codex/brief16-defaults-20261107   # was af99092
git branch -D codex/brief16-operational-telemetry-20261107   # was af99092
git branch -D codex/brief16-privacy-fix-20261107   # was af99092
git branch -D codex/compare-file-line-counts   # was 2390568
git branch -D codex/compare-file-lines-secure-20261102   # was f37044d
git branch -D codex/dataset-input-bounds-20261116   # was 3c76fd2
git branch -D codex/pre-user-dataset-bounds-20261119   # was 3c76fd2
git branch -D codex/pre-user-security-logging-20261119   # was 3c76fd2
git branch -D codex/promotion-readme-fix-20261112   # was 92c6508
git branch -D codex/promotion-report-safety-20261112   # was 1ec9283
git branch -D codex/search-text-race-safety-20261101   # was 2390568
git branch -D codex/sec-search-001-20261112   # was b0b3467
git branch -D codex/sec-search-001-remediation-20261112   # was b0b3467
git branch -D codex/security-bootstrap-20261119   # was 3c76fd2
```

**After:** the SHA comment is the undo (`git branch <name> <sha>`).

### Batch 3. Tracked files and documents (SE; one commit per batch, on a branch)

1. **NOT `git rm scripts/make_demo_svg.py`** (corrected by brief 50: it fails `tests/test_eval_workspace.py::test_every_sealed_source_path_exists`; ASK). Batch 3 is now only the UPDATE edits in the correction section's proof table, each shown green. 2. **UPDATE** the lines in C3 (my architecture documents: SAE drafts, SE or PM commits). 3. ASK items wait for the owner. **One logical change per commit, staged by path, `git diff --cached --stat` read first.**

**Before and after, all must pass:** `ruff check .`, `mypy`, `pytest`, `tests/test_no_next_chat.py`, `tests/test_no_private_rules_tracked.py` (full venv paths, `agent.__file__` inside the tree). **Undo:** `git revert <commit>`.

### Batch 4. Remote branches (owner approves; PM carries out)

The exact commands are in Part B. **Before each:** `git ls-remote <remote> <branch>` equals the SHA in the table and the branch is merged into the tip. **After:** `git ls-remote <remote> <branch>` prints nothing, the other remote still holds the branch (until its own deletion), and `git ls-remote` for the integration branch is unchanged on both. **Undo:** `git push <remote> <sha>:refs/heads/<branch>` with the SHA from the table. Never `main`, never force.

## The five riskiest items I would NOT delete

1. **The root `AGENTS.md`, `CLAUDE.md`, `CODEX.md`, `CURSOR.md` of the main checkout.** They hold private rules not in the tracked files, and the fast-forward would overwrite two of them silently.
2. **`.scratch\brief16-proposed-tree-validation-20261109` and `-v2`** (and the three `brief16-*` folders with wheel metadata). They hold the proposed tree's files that are in no ref. The owner's snapshot-ref ruling probably covers them; **probably is not measured**.
3. **`.scratch\codex-pr10-privacy-redaction-20261125` and `codex-privacy-redaction-20261125`.** Dirty and ACTIVE: Codex is mid-work on the gitleaks report scripts.
4. **The three `.patch` files and `snapshots-manifest-2026-11-22.md`.** Unique files outside git; the manifest holds the only SHAs of the deleted snapshot refs.
5. **`omniagent-core/` (37 MB, ignored) and `.venv/`.** The first is referenced by nothing tracked but I do not know who uses it; the second is the editable install every tree imports.

## What I could not measure

- Whether the tools can remove any folder (no removal was run); who still uses `omniagent-core/` and `.ci-venv/`; whether Codex or any chair is working in a tree whose newest file is older than 24 hours.
- Which historical mentions in the briefs are stale versus dated (read by counts, not line by line).
- The remotes' rulesets, so I cannot say a deletion command will be accepted.
- The private bytes of the four root files beyond their size and hash.

## The owner's decisions

- **A. Batch 0 now, before anything touches the main checkout** (owner approves; PM archives the four root files). My pick, and the precondition for the fast-forward.
- **B. Batch 1a, 1b and 1c** after the owner reads Part A (PM carries out; owner for the OWNER-ONLY folders).
- **C. The five `brief16-*` folders:** delete them (owner says the snapshot-ref ruling covers them; PM carries out), or keep them.
- **D. Batch 2** (merged local branches) (SE or PM).
- **E. Batch 3 (corrected)**: update the stale lines (SAE drafts, SE commits); `scripts/make_demo_svg.py` stays until AI/ML or the owner decides about the sealed list.
- **F. The 41 ASK branches:** a separate owner pass, family by family, starting with the `codex/brief16-*`, `codex/security-remediation-*` and `pm/docs-cleanup-*` families (owner; PM carries out).
- **G. Batch 4**, remote deletions, one remote first (owner; PM carries out).
- **H. The 13 Codex trees outside the path and the `%TEMP%` tree** (owner-gated; Codex or PM carries out).

## What this document does not establish

That any folder is safe to remove by tool (not run); that an unreachable file is worthless (only that it is in no ref); that ASK branches are abandoned; anything about CI, the stash (one entry, not read), or POSIX.
