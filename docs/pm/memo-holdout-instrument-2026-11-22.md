# Memo — the holdout instrument and the question bank, after the canonical ruling

**From:** AI/ML engineer · **2026-11-22** · **No model was run for this memo.**

**Written against** `origin/integration/canonical-20261122` at **`b164aaa`** and the
tag **`legacy/origin-main-2026-11-05`** (annotated `683fcfb`, commit
**`3c76fd2`**). Every claim below was re-derived with `git show` / `git ls-tree`
against those two refs today. Nothing is quoted from the PM's summary without
being checked, and nothing in this memo quotes a question, an expectation, an
answer or a fixture filename.

---

## 1. Where they are — and the premise that needed correcting

**[SEVERITY: Low] — Finding 3, recorded here because it changes the scope of
every option in §6.**

The assignment said the holdout instrument and the question bank "are not on
G". **That is wrong in both directions, and the correction changes what porting
means.**

| Component | legacy tag `3c76fd2` | canonical `b164aaa` |
| --- | --- | --- |
| `scripts/holdout_eval.py` | 427 lines | **282 lines** |
| `scripts/eval_scoring.py` | present | present |
| `scripts/eval_workspace.py` | 102 lines | **139 lines** |
| `scripts/session_eval.py` | present | present |
| `scripts/grounding_cohort.py` | present | present |
| `tests/test_holdout_questions.py` | present | present |
| `tests/test_eval_scoring.py` | present | present |
| `tests/test_eval_workspace.py` | 464 lines | **316 lines** |
| `tests/test_session_eval.py` | present | present |
| `tests/test_grounding_cohort.py` | present | present |
| **`tests/test_holdout_record.py`** | 176 lines | **absent** |
| **`eval-fixture/`** | 7 files | **absent** |
| **`questions/`** | 1 file | **absent** |
| `grounding-cohort/` | present | present, **byte-identical tree** `b4cbca9` |

So: **the instrument's code is on G.** All four evaluation scripts and four of
the five test modules came across. What did not come across is two data
directories, one test module, and — the part that matters most — a layer of
behaviour inside `holdout_eval.py` itself.

Neither `eval-fixture/` nor `questions/` is in `.gitignore` on `b164aaa`, and
neither is in the working tree. They are simply not on the canonical line.

---

## 2. Finding 1 — brief 12's run record is gone from the canonical line

**[SEVERITY: High]**

**Location:** `scripts/holdout_eval.py` on `b164aaa`.

Measured, by counting definitions on each ref:

| Symbol | legacy `3c76fd2` | canonical `b164aaa` |
| --- | --- | --- |
| `def question_record` | 1 | **0** |
| `def _tree_clean` | 1 | **0** |
| `RUNS_PATH` | 3 references | **0** |
| `def report` | 1 | **0** |

Brief 12 existed to add exactly these. Its `## Result` records why: a run
record carried the commit but **not whether the working tree was clean**, so a
void run — dirty tree, same commit — pooled with ten good ones in
`data/holdout-runs.jsonl`, and the defect was found by reading the artifact
afterwards rather than by any test. `question_record()` was built as a pure
function, tested directly, to carry measurements and never the answer key;
`report()` was built to **drop** records whose tree was not clean.

**On the canonical line none of that exists.** There is no record file, so a
holdout run on G produces a console figure and nothing auditable: not the
commit, not the tree state, not one row per question.

**Failure scenario.** 1. Any chair runs the holdout evaluation on `b164aaa`.
2. Another chair is mid-edit in the same checkout, or the runner's own tree is
dirty. 3. The run prints a total. 4. Nothing in the output distinguishes it
from a clean run, and nothing on disk lets anyone check later. The precondition
is ordinary use — the project has a shared checkout and, as of today,
forty-odd worktrees — and this is the third time tree state has cost a
measurement.

**Remediation.** Port `question_record`, `_tree_clean`,
`_append_question_record`, `RUNS_PATH` and `report()` from
`3c76fd2:scripts/holdout_eval.py`, together with
`3c76fd2:tests/test_holdout_record.py` (176 lines), which is the test that goes
red when the clean-tree field is dropped. **Evidence it bites:** brief 15 ran
the equivalent mutation on the newer record and
`test_the_trial_record_carries_every_field_the_contract_lists` failed with
"Right contains 1 more item: `{'tree_clean': True}`".

---

## 3. Finding 2 — figures from the two lines are not comparable, and look as if they are

**[SEVERITY: Medium]**

**Location:** `scripts/holdout_eval.py` — `SESSIONS_UNDER_TEST` on both refs.

Counted, not read:

| Measure | legacy `3c76fd2` | canonical `b164aaa` |
| --- | --- | --- |
| `Question(` in `holdout_eval` | 19 | **19** |
| sessions | 14 | **14** |
| `Question(` in `session_eval` WALK | 8 | **8** |

Identical counts. But the **subjects changed**: on `b164aaa` every repository
path the holdout questions read is a source file under `scripts/` or `tests/` —
four of them, named here only by count, because on the legacy line two of those
same paths are themselves an expectation and this memo does not carry
expectations. **No `eval-fixture/` path appears anywhere in the file**, and the
import-time
derivation that found the fixture-backed subject (`_search_subject`,
`SEARCH_MARKER`, `SEARCH_SUBJECT`) is gone — 0 occurrences. Canonical's
`tests/test_eval_workspace.py` imports only `SESSIONS_UNDER_TEST` from
`holdout_eval`, where the legacy one also imported the marker and the subject.

So two of the bank's questions were removed or re-pointed, and the count stayed
at 19.

**Failure scenario.** A reader compares a canonical total with the recorded
baseline — *"13/18 four times and 14/18 six times, over ten runs,
2026-10-26"* — sees 19 questions and 14 sessions on both sides, and treats the
difference as the model changing. It is the denominator changing. Brief 10
already had to write *"this is **not** comparable with 11/16 … the denominator
is a different denominator"*; the same trap is now set again, and this time the
counts match, which makes it harder to notice.

**Remediation.** Before any figure is quoted from the canonical line, state its
denominator explicitly and do not compare it with any figure recorded before
2026-11-22. If comparability matters, port the fixture (§5) and restore the two
questions; otherwise declare the canonical bank a **new baseline** with its own
first measurement.

---

## 4. What did survive — brief 15, intact

Worth recording because it is the one part that needed no porting.

- `grounding-cohort/` on `b164aaa` is **byte-identical** to what I pushed on
  2026-11-05: tree `b4cbca9` on both `1b4e85f` and `b164aaa`.
- `scripts/grounding_cohort.py` keeps the derived oracle (`accepted_answer`,
  one definition), the endpoint guard (7 `loopback` references) and the
  clean-tree field (5 `tree_clean` references).
- Both files were **extended**, not reduced: `+1206 / -114` lines against my
  commit, almost all of it in `tests/test_grounding_cohort.py`. `CATEGORY` is
  still the single value `"evidence-grounding"`, so the extension deepened one
  category rather than adding the other five.

My brief-15 branch `aiml/brief15-evidence-grounding-20261105` is on `origin` at
`1b4e85f`; nothing was lost when the out-of-path worktree it was built in was
removed.

---

## 5. What porting the bank would actually need

Not one step. Four, in dependency order:

1. **`eval-fixture/` (7 files).** It is the *subject* of a search question and
   its inventory is pinned by a test, so it cannot be partially restored.
   Legacy derives the subject's filename from a marker **at import time**
   rather than storing it, so `holdout_eval` on legacy **raises at import** if
   no fixture file carries the marker. Port the directory first or the module
   will not load.
2. **The two questions and their import-time derivation.** `_search_subject`,
   `SEARCH_MARKER`, `SEARCH_SUBJECT`, plus the listing question. Restoring
   these changes the denominator again, so it must be done before any figure is
   quoted, not after.
3. **The seal.** Canonical's `eval_workspace.py` is **larger** (139 vs 102
   lines), so `ANSWER_KEY` has moved on. Restoring the fixture means re-running
   the seal invariants over it, and the invariant only covers what it reaches —
   brief 15 showed that a check which looks right can be structurally unable to
   fire. Each restored question needs its carrier count asserted, and the
   assertion mutation-checked.
4. **`questions/` (1 file).** Not in legacy's `ANSWER_KEY`, so it was
   **reachable** to the agent on the legacy line. Before it is committed to a
   **public** repository it needs classification: if it holds question or
   expectation material, it belongs behind the seal and possibly out of the
   repository entirely.

**One thing to settle before any of it.** Both GitHub remotes are public. The
legacy tag is already pushed, so whatever is in those 7 + 1 files is already
public — that is a fact to confirm rather than a risk to create, but it should
be confirmed before more is added.

---

## 6. Recommendation

**Port the record layer (§2) now; leave the bank alone and treat the canonical
line as a new baseline.**

The reasoning is a cost split. The record layer is a lift-and-shift of code
that already has its own test, it closes a High finding, and it is needed by
*every* future measurement including the ones the contract still gates. The
bank is the opposite: restoring it buys comparability with figures that brief
10 already described as a different denominator, it drags a fixture and a seal
re-verification with it, and it puts files of uncertain classification into a
public repository. The holdout session queued for day 3 does not need the old
bank — it needs a record that cannot pool a void run.

### Options for the owner

**A — Port brief 12's record layer only.** Carried out by the **AI/ML chair**:
move `question_record`, `_tree_clean`, `_append_question_record`, `RUNS_PATH`
and `report()` plus `tests/test_holdout_record.py` onto the canonical line,
mutation-check the clean-tree test, and declare the canonical bank a new
baseline with its own stated denominator. No fixture, no new public files.
**This is my recommendation.**

**B — Port the record layer and the full bank.** Carried out by the **AI/ML
chair** for the questions and the record, with the **SE chair** re-verifying
the seal over the restored fixture (§5 step 3) and classifying `questions/`
(§5 step 4) before anything is pushed. Buys comparability; costs a fixture, a
seal re-verification and a public-repository decision.

**C — Port nothing; retire the old bank.** Carried out by the **PM chair**:
record the legacy tag as the archive of record, state that no figure before
2026-11-22 is comparable with the canonical line, and have the **AI/ML chair**
build the remaining five contract categories on the `grounding_cohort` record
format, which already carries the commit, the tree state and both hashes.
Cheapest, and loses the old figures permanently.

**D — Decide the public-repository question first.** Carried out by the **SE
chair**: classify the 7 fixture files and the 1 `questions/` file against the
two public remotes, then re-run this decision. Appropriate if the owner is not
certain what is in them; blocks A only trivially, since A adds no data files.

---

## 7. What this memo does not establish

- **No model was run, and no figure here is a measurement of any model.** Every
  number is a line count, a file count or a symbol count from two git refs.
- **The suite figure is confirmed, the skips are not explained.** I re-ran it in
  this worktree at `b164aaa` and got **1,065 passed, 2 skipped** in 33.6 s,
  with `ruff` clean — **MEASURED** today, matching the PM's report. Per Rule 1
  I first confirmed the code under test was this worktree's
  (`agent.__file__` resolves inside `.scratch/aie-holdout-memo`). I did **not**
  identify what the two skips are or why they skip.
- **`docs/` is still sealed on the canonical line** (`eval_workspace.py:57`), so
  this memo is not readable by the agent during a run. That was checked rather
  than assumed, because the memo names question subjects.
- **I did not read the contents** of `eval-fixture/`, `questions/`, or any
  question or expectation. The counts above are deliberately counts.
- **I did not verify that canonical's 19 questions are checkable.** Legacy's
  were 19 with 18 checkable; I did not re-derive that for `b164aaa`.
- **I did not establish why the record layer was dropped.** It may have been
  deliberate during assembly. The finding is that it is absent, not that anyone
  erred.
- **I did not review the ~967 added test lines** in canonical's
  `tests/test_grounding_cohort.py`, so I make no claim about whether the
  extension of my category is sound.

`QA: 3 findings (0 Critical / 1 High / 1 Medium / 1 Low) - 3 reproduced - not tested: no model run, no fixture or question contents read, canonical checkability not re-derived, the two test skips not explained, the ~967 added test lines in canonical's test_grounding_cohort.py not reviewed`
