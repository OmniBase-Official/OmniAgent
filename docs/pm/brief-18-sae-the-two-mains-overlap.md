# Brief 18 — the two `main`s: measure the overlap, decide nothing

**For the solution architect (SAE). Issued 2026-11-21 by the PM.**

The owner chose **option C** on 2026-11-21: *measure the overlap first, merge
nothing.* This brief is that measurement. Its deliverable is one ADR, status
**Proposed**. **The owner decides which line is canonical; the ADR informs the
decision and does not make it.**

Static throughout. **No model run, no localhost, no test here may contact a
model server.**

## The problem

`origin/main` and `organization/main` share a merge-base and have no common
tip since. Neither contains the other. Early in this project a bare `git push`
went to the wrong remote; nobody knows today whether the two sides are
**redundant** (they did the same work twice), **complementary** (disjoint work
that merges), or **contradictory** (incompatible designs for the same thing).
Every other plan — the Codex security stack, the release blocks, the package
move — rests on that answer.

## Pinned refs — measure these and nothing else

| Name | Ref | Commit | Date |
| --- | --- | --- | --- |
| base | merge-base | `85d137d` | 2026-10-12 |
| **O** | `origin/main` (`mntoyg/OmniAgent`) | `3c76fd2` | 2026-11-05 |
| **G** | `organization/main` (`OmniBase-Official/OmniAgent`) | `5005039` | 2026-11-12 |

`git fetch origin` and `git fetch organization` first, then confirm those
three SHAs before you believe any number below. **Record them in the ADR.** If
a ref has moved, say so and re-measure.

**G's non-bot history is exactly three squashed PRs:** `9c60c00` #2 *Privacy:
isolate evaluation trial groundwork*, `d930ee4` #3 *fix: block hard-link
workspace escapes*, `5005039` #4 *Security remediation: POSIX filename and JSON
validation*. The rest of G's 23 commits are `waka-readme` bot commits.
**You have three diffs and three titles. You do not have their authors'
reasoning** — a squashed PR carries intent only as far as its message and its
tests do. Mark anything you infer as inferred.

## What the PM measured on 2026-11-21 — a starting point, not a result

All read-only, from refs. **MEASURED 2026-11-21** unless marked.

- O is **98** commits past base; G is **23**.
- Files changed since base: **88** on O's side, **53** on G's side. **16**
  were touched by both: `NEXT_CHAT.md`, `README.md`, `agent.py`, `config.py`,
  `pyproject.toml`, `sandbox.py`, `tools.py`, `grounding-cohort/README.txt`,
  `grounding-cohort/ledger-alpha.txt`, `grounding-cohort/ledger-beta.txt`,
  `scripts/grounding_cohort.py`, `scripts/holdout_eval.py`,
  `tests/test_endpoint_policy.py`, `tests/test_eval_workspace.py`,
  `tests/test_grounding_cohort.py`, `tests/test_holdout_questions.py`.
- `git merge-tree --write-tree --name-only origin/main organization/main`
  reports **12 conflicts**: **8 content** in `agent.py`, `config.py`,
  `pyproject.toml`, `sandbox.py`, `tools.py`, `scripts/holdout_eval.py`,
  `tests/test_eval_workspace.py`, `tests/test_holdout_questions.py`; **3
  add/add** in
  `scripts/grounding_cohort.py`, `tests/test_endpoint_policy.py`,
  `tests/test_grounding_cohort.py`; **1 modify/delete** `NEXT_CHAT.md`. `README.md`
  and the three `grounding-cohort/` files auto-merge. **Re-run it; do not copy
  my count.**
- **An add/add means both sides independently created the same path after the
  base.** That is a signal of parallel work in the same area. It is **not yet
  proof of redundancy** — two files can share a name and a purpose and still
  disagree on every interface.
- PR sizes (diff against each PR's parent): #2 **28 files, +3456/−1560**;
  #3 **3 files, +61**; #4 **34 files, +4346/−771**.
- **G-only files** (O never touched them) include `.github/workflows/ci.yml`,
  `config_inspection.py`, `observability.py`, `export_dataset.py`, `main.py`,
  `omniagent.toml`, `scripts/promote_model.py`, `scripts/publish_dataset.py`,
  `scripts/collect_dataset.py`, `tests/log_capture.py`, and a dozen test files.
  **Do not read "G-only" as "complementary".** O's files of the same names may
  have been *rewritten* since base by edits that the file-level diff shows
  differently. Check by content, not by filename.

### One more thing, reported, not measured by you

The main checkout `D:\code-project\OmniAgent` is **dirty with 54 uncommitted
changes and Codex is editing it.** The PM compared a few of those files, read
only, against G's blobs: `tests/log_capture.py` on disk is **byte-identical to
G's**, and the deletion of `questions/bank-2026-10-10.txt` matches G's own
deletion. That *suggests* an unreviewed port of G's content onto O's line is in
flight there — an answer to this very question that nobody asked for.
**Inference, not fact.** **Do not read, copy from or measure that checkout:**
it is being written to, and a measurement of a moving tree is the failure this
project has paid for three times. The PM is asking the owner to have Codex
commit that work to a named branch; **if a branch appears, the PM will name it
to you and it joins the measurement as a third tree. Until then it does not
exist for this brief.**

## What the ADR must establish

Each answer **measured, or marked UNKNOWN with what would settle it.**

### 1. Per PR: what it is for, and where it stands on O

For each of #2, #3, #4: the intent in one short paragraph, then a table of its
behaviours, each classified exactly one of —

- **PRESENT-IDENTICAL** on O (same behaviour, same interface),
- **PRESENT-EQUIVALENT** on O (same behaviour, different interface — say how),
- **ABSENT** on O,
- **CONTRADICTS** O (the two cannot both hold — say why).

**The evidence is a test, not a reading.** Method, in **scratch worktrees you
create off the pinned commits**: take the test files each PR added or changed
and run them against O's tree; then the reverse — O's tests for the same
modules against G's tree. A red test has two possible causes and the ADR must
say which for every red one: **the behaviour is missing**, or **the test depends
on an interface that drifted**. A matrix of "which tree's tests pass on which
tree" is the single most useful table you can hand the owner.

### 2. The hard-link escape — report this one early

PR #3 (`d930ee4`, 61 lines in 3 files) blocks a hard-link workspace escape.
**Is that escape reachable on O's tree?** Write the reproduction as a test and
run it on both trees. NTFS supports hard links, so this is measurable here.

- If it is **reachable on O**, that is an **open workspace-escape defect on the
  line that carries the contract's read-only-tools promise** (say which of the
  six gates it touches; the PM has not mapped it). **Message the PM the moment
  you know — do not wait for the ADR.** Fixing it is the SE's; you measure.
- **A test asserting "this is refused" proves nothing if several independent
  guards would refuse it.** Prove the PR #3 test goes red with the fix removed
  on G (a mutation, restored from a scratchpad copy, file hash before and
  after). Otherwise "G blocks it" is a claim.

### 3. The conflicts, classified

For each of the dry-run conflicts: **textual only** (both sides edit adjacent
lines, intents compatible) or **semantic** (the intents collide). For
`agent.py`, `tools.py`, `sandbox.py`, `config.py`: two or three lines on what
each side changed *architecturally*, and whether both can hold at once.

### 4. The trial-record area

Both sides created `scripts/grounding_cohort.py` and its test. O's version is
**brief 15** (one evidence-grounding category, a derived oracle, a sealed
trial record); G's is PR #2's "trial groundwork". **Compare at the interface
level:** what a trial record contains, what seals it, what the oracle is
derived from. Same design, compatible designs, or different designs?
**This is contract section 3, the AI/ML chair's area.** If they conflict, flag
it for the AI/ML chair and the owner; do not resolve it.

### 5. The cost of each way out

Three ways, none of them recommended until you have the numbers above:

- **A.** bring O's line into G,
- **B.** port G's intent onto O,
- **a reconciling merge** (what the dry-run is a first look at).

For each: how many files, how many conflicts are semantic, what cannot be done
mechanically, and **which of the repository's tests would have to be rewritten
rather than just re-run.** Then your recommendation, status Proposed.

### 6. The Codex branches that stack on O

`origin/codex/*` branches since 2026-11-07 are stacked on O (and on brief 16,
`af99092`, which the PM verified separately). One table: each branch by name,
its changed paths intersected with G's three PRs' paths. **Paths only** — you
are not verifying those branches, only showing where they might duplicate or
collide with G. The branch names the PM saw, newest first:
`windows-private-root-validation-20261121`, `security-runner-fixtures-20261120`,
`security-scans-validation-20261120`, `mypy-portability-20261116`,
`remove-ai-handoff-docs-20261116`, `provenance-export-bounds-20261116`,
`agent-instance-run-guard-20261116`, `agent-task-deadline-20261116`,
`scale-security-hardening-20261113`, `security-remediation-batch2-20261112`.
Take the list from `git for-each-ref`, not from this paragraph.

### 7. What this brief cannot measure

PR #4 is about **POSIX** filenames. That is a Linux behaviour. **Do not assume
a WSL/Linux build is available to you** — say in the ADR what you could and
could not run, and **tell the PM before the ADR depends on a Linux run.** Mark
the POSIX behaviours **UNMEASURED** if you cannot run them. Do not infer them
from reading.

## The numbering of the ADR

**Name it `ADR-0003-the-two-mains.md`.** The PM's 2026-11-04 assignment reserved
"ADR-0003" for the model question (readiness block D3); that document exists on
no ref. **The model question becomes ADR-0004.** The PM will correct the two
`docs/pm/` references; you do not touch `docs/pm/`.

## Files you may touch

`docs/architecture/ADR-0003-the-two-mains.md` only. Scratch outputs (matrices,
logs) stay in your scratchpad or under a gitignored `.scratch/`. **No source
file, no test file, no workflow, nothing under `docs/pm/`.**

## Files and trees you may not touch

- **`D:\code-project\OmniAgent` — the main checkout. Codex is editing it.** Run
  nothing there that rewrites state or reads a file that is being written.
  `git` against committed refs from *your own* worktree is fine.
- No `git merge`, `rebase`, `cherry-pick` or `push` to either `main`, **even
  in a scratch worktree you intend to throw away** — a cherry-pick of a PR's
  tests into a scratch worktree is a `git checkout <ref> -- <path>` of those
  files, not a merge, and the worktree is deleted afterwards.
- `git merge-tree --write-tree` is read-only and is how the dry-run was taken.

## Gates

The ADR is docs only, but a scratch worktree is where tests are run, so the
three gates still run **on the branch you commit**, full path, **never your own
`-q`**:

```
.venv\Scripts\python.exe -m ruff check .
.venv\Scripts\python.exe -m mypy
.venv\Scripts\python.exe -m pytest
```

Baseline the PM measured on `af99092`: ruff clean, mypy clean over **48**
files, **798 passed**. **On O (`3c76fd2`) the last recorded figure is 791
passed** (RECORDED 2026-11-05). Take any figure for G from your own run.

## Traps that already cost this project

- **A worktree can silently test the wrong code.** The venv at
  `D:\code-project\OmniAgent\.venv` has an editable install that maps module
  names at the *main checkout*, which is dirty. Before you trust any number from
  a worktree, run `python -c "import agent; print(agent.__file__)"` from that
  worktree and **confirm it prints a path inside the worktree.** The PM did this
  for `af99092`; every scratch worktree you create needs its own check.
- **A test green in its author's worktree can be red on `main`.** Run where the
  code has to live.
- **A rejection test passes if the connection merely fails.** Prove no socket
  was opened, then delete the validator and see what survives.
- **`build/` and `dist/` poison the sandbox invariant** if a wheel is built in
  the checkout.
- Quoted bash heredocs eat backslashes. Write files with the Write tool.
- Claude chairs can reach `localhost`; Codex cannot. Nothing here needs it.

## Branch and report

Work in **your own worktree and branch** (`sae/adr-0003-two-mains`), commit to
that branch, **never to `main`**; the PM merges. Name the remote on every push
(`git push origin sae/adr-0003-two-mains`).

**Every number in the ADR carries one of three labels:** MEASURED (date and
commit), RECORDED (earlier, dated), REPORTED (someone else's claim). Strike
superseded numbers in place. **Do not report a measurement you did not produce.**

## Done when

- the ADR exists on your branch, with the three pinned SHAs at the top;
- sections 1–7 each answered **measured or UNKNOWN**;
- the PR #3 reachability question is answered on both trees, with the mutation
  evidence;
- the matrix of tests-on-trees is in the ADR;
- three gates green on your branch, outputs quoted;
- you have told the PM, in one message, the **three things the owner must
  decide next** in the form of lettered options, each ending by naming the chair
  that would carry it out.

## The one thing that would make this wrong

**Choosing a winner by diff size.** G is smaller; O is bigger; neither fact says
which is right. The decision turns on which side holds the *security
behaviour the contract needs* and which side's *tests would survive the move*,
and only the cross-run matrix tells you either.

The second way: **measuring a tree someone else is writing to.** Pinned
commits, your own worktrees, and the main checkout left alone.
