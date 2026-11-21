# Brief 19 — what of O has to move onto G

**For the solution architect (SAE). Issued 2026-11-22 by the PM.**

**The owner ruled option A on 2026-11-22: G is the canonical line.** The code
history that stays is `organization/main` (`5005039`); O's documents and O's
unique work are carried onto it. This brief **measures what has to be carried.
It does not carry anything.** No branch surgery, no merge, no push to either
`main`, until the PM has the inventory and the owner has seen it.

Static throughout. **No model run, no localhost, no test here may contact a
model server.**

## What is ruled, and what is not

**Ruled (owner, 2026-11-22):** A — G canonical, "carry O's documents onto it".

**Not ruled, and not yours to rule:**

- **`securefs.py` / `publisher_root.py`.** Your ADR is right that A is about the
  two pinned commits and does not endorse what is stacked behind G. The owner
  has **not** yet answered whether those modules are the parked
  `secure_search.py` work resumed. **Treat every `origin/codex/*` branch that
  carries them (`scale-security-hardening-20261113`,
  `security-scans-validation-20261120`, `security-runner-fixtures-20261120`,
  `windows-private-root-validation-20261121`) as NOT a candidate base.** Nothing
  in this inventory may assume they land.
- **`NEXT_CHAT.md`.** G deleted it, O still edits it. Whether handoff and role
  prompts are tracked at all is **owner decision 2, still open.** Mark it
  OWNER'S in the inventory; do not pick.
- **Where the canonical line lives** (which remote, what happens to O's
  `origin/main`). Not yet asked. **Do not propose a push, a force-push or a
  rename.** You may list the facts the owner will need.

## Pinned refs

| Name | Ref | Commit |
| --- | --- | --- |
| **G — canonical** | `organization/main` | `5005039` |
| **O — carried from** | `origin/main` | `3c76fd2` |
| O-line, not on `origin/main` | brief 16 | `af99092` (branch `chore/local-ai-delegate`; **its commits are ancestors of the pushed `origin/pm/verify-brief16`**, so you can read them from there) |
| base | merge-base | `85d137d` |

**Brief 16 is the thing the O line has that `3c76fd2` does not.** The PM
verified it on `af99092`: ruff clean, mypy clean over 48 files, 798 passed, and
mutations Ma–Me red as the brief required (RECORDED 2026-11-21, by the PM).
**Its three defaults — one model default that `--help`, the TOML and the code
agree on, two retry layers named as two, `verbose` off by default — are
"carry unless G already has them".** Measure which of the three G has.

`git fetch origin` and `git fetch organization`; confirm those SHAs before you
believe any number here.

## The deliverable

**Amend `docs/architecture/ADR-0003-the-two-mains.md` — that file only — on a
new branch off `origin/sae/adr-0003-two-mains` (`18d9675`)**, suggested
`sae/adr-0003-carry-over`. Two changes:

1. **Status** becomes *Accepted — option A, owner ruling 2026-11-22*, carrying
   your own condition (A is a verdict on two pinned commits and endorses nothing
   stacked behind G) and naming the two open owner questions above.
2. A new section, **`## Carry-over inventory`**, answering 1–6 below.

## 1. Documents

Every tracked document on O that G lacks, grouped by kind — contract, threat
model, ADRs, briefs 1–19, assignments, release readiness, audits. Every
document on **G that O lacks** (e.g. `docs/dataset-bundles.md`,
`docs/demo-script.md`, `docs/video-script.md`). The files both sides changed.
For each group: **carries mechanically** (a copy onto G, no code involved) or
needs a decision. `NEXT_CHAT.md` is OWNER'S.

Then, **separately: which of O's documents describe a state that G changes.**
The readiness plan of 2026-11-04 says CI is unassigned and gate 2 is
unassigned; G has changed `ci.yml` since the base (both sides have the file) and
has a gate 2. List the claims in O's documents that
carrying them onto G would make **stale**, so the PM amends them rather than
publishing something false.

## 2. Code that is O's own

For each behaviour O added since the base, one disposition:

- **ON G** — identical or equivalent (name which),
- **CARRY** — G lacks it; say what, where, how large,
- **DESIGN** — both exist and differ; **one implementation survives and you say
  which and why**, or you mark it OWNER'S/AI-ML'S,
- **DROP** — G supersedes it; say why dropping loses nothing the contract needs.

**At minimum**, one row each for: brief 11's walk (`_searchable_files`,
`Workspace.admit_resolved_child`) against G's traversal bound; brief 13's
junction refusal (gate 5, Windows); **brief 14's endpoint** (`ENDPOINT_DESCRIPTION`
and its policy prefix) against G's `validate_openai_client_endpoint` — **the
eleven same-named symbols mean one validator must go, so say which**; brief 15's
`SEALED_FROM_TRIALS` and anything else in O's trial record that G lacks (your ADR
says it is O's one unique symbol — confirm); brief 16's three defaults; brief
17's wheel tests; `holdout_eval.py`'s 15 symbols (`SEARCH_MARKER`,
`_append_question_record`, …); `collect_dataset.already_answered`;
`build_notebook.build_notebook`; `tests/test_eval_workspace.py`'s sealed
inventory. **Add every row the cross-run matrix implies that I did not name.**

## 3. O's tests on G — which red is which

The matrix says O's tests on G are **39 failed and 34 errors** (re-measured by the
PM 2026-11-21, same figures). Do it **per module, not wholesale**, and classify
every failing or erroring test module into exactly one of:

- **LOST BEHAVIOUR** — G lacks the behaviour; the code must be carried and the
  test comes with it as the acceptance test,
- **RENAMED INTERFACE** — the behaviour exists on G under another name; the test
  is rewritten, the behaviour is not,
- **OBSOLETE** — it tests an O-specific design that §2 drops.

Count per category. **A test that errors on import is a different finding from
one that fails on behaviour; keep them apart.** The PM will re-run your
classification — say the command.

## 4. Order, size, chairs

Per carried item: size **S / M / L** (files touched, tests), what it depends on,
and **which chair carries it** (SE / AI-ML / FSE / SWE). Propose the grouping
into briefs: **one chair per brief, disjoint files**, in an order. **Do not write
the briefs.** Name the first one the PM should issue and why.

## 5. A finding the PM measured on G that the inventory must carry

**Contract gate 2 on G is implemented, and its tests are thin.** G enforces the
tool allowlist in five independent places. The PM removed each in turn, in a
scratch worktree of `5005039`, running G's own suite (**860 passed, 2 skipped**
unmutated; MEASURED 2026-11-22, file hashes restored):

| # | Guard removed | Result |
| --- | --- | --- |
| G2a | `agent.py:694` — init intersects with `FIXED_TOOL_ALLOWLIST` | **860 passed — nothing noticed** |
| G2b | `agent.py:992` — `permitted` in `_invoke_tool` | **860 passed — nothing noticed** |
| G2c | `tools.py:442` — `run_tool` fixed-allowlist check | 2 failed (`test_run_tool_dispatch`, `test_an_invented_tool_is_told_that_inventing_it_changed_nothing`) |
| G2d | `tools.py:458` — `run_tool` per-task check | **860 passed — nothing noticed** |
| G2e | `agent.py:872` — loop stops on a disallowed action | 2 failed (both in `test_grounding_cohort.py`) |
| G2b + G2d | both per-task guards at dispatch | **1 failed**: `test_a_disallowed_tool_request_is_rejected_before_dispatch` |

Read it carefully: **the per-task allowlist is pinned before dispatch by exactly
one test, and no single guard of the five has its own.** The guards overlap, and
two of them even answer with the same string, so a test that asserts "refused"
cannot say which guard refused. That is not a reason against A — it is work to
add to the inventory as **an SE brief that gives each guard a test that goes red
when only that guard is removed**. Size it. (The dirty main checkout has an
untracked `tests/test_mvp_security_acceptance.py` whose failing test is named
`test_disallowed_task_tool_is_stopped_before_dispatch`; **you may not read it**,
but note that the same subject is already being written there.)

## 6. The stack

Which `origin/codex/*` branches could be the next base *if* the owner later
rules on `securefs`, and which cannot? **Paths and imports only.** Do not verify
their other work. A branch that imports `securefs` is **blocked pending the
owner**, not rejected.

## What you must not touch

- `docs/` apart from the one ADR file. **No source, no test, no workflow.**
- **`D:\code-project\OmniAgent` — the main checkout. Codex is editing it; 54
  uncommitted changes.** Never read, write or test it. If Codex commits it to a
  named branch the PM will name it to you and it joins as a third tree.
- No `git merge`, `rebase`, `cherry-pick`, `push` to either `main`. Cross-runs
  are `git checkout <ref> -- tests` in throwaway worktrees you delete after.
- **Nothing installed on the owner's machine.** POSIX stays UNMEASURED.

## Traps that already cost this project

- **A worktree can silently test the wrong code** — the shared venv's editable
  install maps at the dirty main checkout. Run
  `python -c "import agent; print(agent.__file__)"` from each worktree and
  confirm it prints a path inside it.
- **A test asserting "refused" proves nothing if several independent guards
  would refuse it.** §5 is the live example; apply it to anything you call
  "covered".
- **A report is a claim.** Label every figure MEASURED / RECORDED / REPORTED;
  strike superseded numbers **in place** and retract errors in the commit
  message too. You wrote one retraction this week and did it properly; do the
  same again.
- Quoted bash heredocs eat backslashes; use the Write tool. `pytest` given a
  Windows 8.3 short path (`THANAP~1`) scans the wrong directory — copy test files
  into the worktree instead.

## Gates

Docs only, but the three gates still run on the branch you commit, full path,
never your own `-q`:

```
.venv\Scripts\python.exe -m ruff check .
.venv\Scripts\python.exe -m mypy
.venv\Scripts\python.exe -m pytest
```

Baseline on `origin/sae/adr-0003-two-mains`: ruff clean, mypy clean over 48
files, **791 passed** (your own, 2026-11-21).

## Done when

- the ADR on your branch is *Accepted*, with §1–6 answered **measured or
  UNKNOWN**;
- every row of §3 has exactly one classification and a count per class;
- a proposed brief list with chairs, sizes and a first brief;
- three gates green, outputs quoted; pushed with the remote named
  (`git push origin sae/adr-0003-carry-over`);
- one message to the PM with **the decisions the owner has to make next**, as
  lettered options, each ending by naming the chair that would carry it out.

## The one thing that would make this wrong

**Counting O's commits instead of O's behaviours.** 98 commits is a number; what
matters is which of them put a behaviour on O that the contract needs and G
lacks. **And the mirror image: "carrying" wholesale a file G rewrote
deliberately** (`observability.py`, `sandbox.py`'s `workspace_scope`). Under A,
G wins every collision unless O's side is a requirement the contract states.
