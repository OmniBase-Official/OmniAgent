# Result — brief 12's run-record layer, ported onto the canonical line (I3)

**From:** AI/ML engineer · **2026-11-23** · owner ruling 23 · branch `aiml/record-layer-20261123`, cut from
**`b164aaa`**. No model was run for this work. Nothing is merged into integration; the PM verifies first.

## 1. What was ported, and what was not

Into the canonical `scripts/holdout_eval.py`, **not** by restoring the legacy file:

| Ported | Note |
| --- | --- |
| `question_record()` | extracted from the legacy tag by script, not retyped |
| `_short_commit()`, `_tree_clean()`, `_append_question_record()` | same |
| `RUNS_PATH` | `data/holdout-runs.jsonl` |
| `_read_run_records`, `_clean_state`, `_question_index`, `_question_sort_key`, `report()`, `_report_question` | same |
| `tests/test_holdout_record.py` | the 7 legacy tests plus 6 new ones (13 in all) |

`evaluate(model, *, runs_path=RUNS_PATH)` now appends one row per question, in both the answered and the
`AgentError` branch. The call site `evaluate(model)` is unchanged on purpose: every existing test mocks it as
`lambda _model: ...`, and none broke.

**Not done, as scoped:** no fixture, no `eval-fixture/` or `questions/`, no file from `data/`, `models/` or `docs/`
other than this document, and the old bank is not restored. The canonical bank's questions are untouched.

## 2. Two deviations from "port it as it was", both forced

**The summary flag is `--runs-report`, not `--report`.** On the canonical line `--report` already exists and means
"destination of the sanitized promotion report" (it errors without `--promotion-run`, and `tests/test_promote_model.py`
calls it that way). The legacy `--report` meant "print the recorded runs". Porting it unchanged would either fail
every promotion run or silently change what the flag means. `--runs-report` cannot be combined with models,
`--promotion-run` or `--report`; a test holds all three refusals and that `--report out.json` still needs a run.

**`report()` now opens with the bank's denominators**, computed from the bank at call time rather than written down
(§4). That is the "own stated denominator" the ruling asks for, placed where a reader of any recorded figure will see it.

## 3. `RUNS_PATH` — how the two evaluations are kept apart

Canonical `scripts/session_eval.py` already defines `RUNS_PATH = data/session-runs.jsonl`. They were never the same
file, but nothing said they must not become one. Separated by **value, with a test**: holdout writes
`data/holdout-runs.jsonl`, session writes `data/session-runs.jsonl`, and
`test_the_two_evaluations_write_different_run_files` asserts they differ and share a directory. Why it matters: a
holdout row has `index` and no `arrangement`; a session row has the reverse, so one file would make each reader
silently misread the other's rows. Mutation Mc5 below sets them equal and the test goes red. Both paths stay
unreadable to the agent: `data/` is listing-only in the seal.

## 4. The canonical bank is a new baseline, with this denominator

Derived by `judge()` against the bank as it stands at `b164aaa`, not counted by eye:

| | Canonical `b164aaa` |
| --- | --- |
| questions / sessions | **19 / 14** |
| answer-checked | **16** |
| tool-checked | 7 |
| honesty-checked | 1 |
| **scored on nothing** | **1** — question index **18** (session 13, position 2) |
| scored on tool choice alone | 1 — question index 7 (session 7, position 0) |

For reference only, the legacy tag had 19 questions with **18** answer-checkable and none scored on nothing. **No
figure recorded before 2026-11-22 is comparable with one from this bank.** The same counts (19 and 14) hide a
different denominator; that is the trap brief 10 already wrote out once, and `report()` now states it on every run.

**[SEVERITY: Medium] A question on the canonical bank is scored on nothing.** Index 18 has no expectation, no
preferred tool and is not an abstention probe, so its verdict is empty on every axis. It still adds to `asked`, so
it enlarges the denominator without being able to move the score — the shape brief 10 titled "no question is scored
on nothing". `tests/test_holdout_questions.py` has `test_only_the_comparisons_are_scored_on_tool_choice_alone`,
which allows index 7 by name but does not cover index 18. **I did not establish whether this was deliberate**, and
did not change the bank (out of scope: the old bank is not restored and this one is not edited here).

## 5. The clean-tree test, mutation-checked

Every mutant was confirmed to apply (pattern found exactly once) and to parse, run, and restored from a saved copy.
Pristine `scripts/holdout_eval.py` hash **`1a843b4196ffb0d2`**; after every restore it was `1a843b4196ffb0d2` again.

| # | Mutation | Mutant hash | Red |
| --- | --- | --- | --- |
| Mc1 | drop the `clean` field from the appended record | `01e8a1f2c9734a9f` | 3: `test_appended_run_record_carries_cleanliness_separately`, `test_evaluate_appends_one_individual_record_per_question`, `test_evaluate_records_a_dirty_or_unknown_tree_as_such` |
| Mc2 | report counts a dirty record as clean | `7f8d45eec3cadc0b` | 2: `test_report_drops_and_counts_dirty_records`, `test_report_names_questions_with_no_surviving_runs_without_zero_over_zero` |
| Mc3 | `evaluate` always records `clean=True` | `e434910c02ab2f3f` | 1: `test_evaluate_records_a_dirty_or_unknown_tree_as_such` |
| Mc4 | unreadable `git status` called clean, not unknown | `de078ac07d2a0c2a` | 1: `test_tree_cleanliness_is_unknown_when_git_status_fails` |
| Mc5 | both evaluations write the same file | `d1738928176d6815` | 1: `test_the_two_evaluations_write_different_run_files` |

Mc3 is the one that justifies the new wiring tests: the legacy tests exercise the builder and the report, so a
version of `evaluate` that threw the tree state away would have passed all seven of them.

## 6. Gates

`.venv\Scripts\python.exe -m ruff check .` — All checks passed. `-m mypy` — Success, **56** source files (55 + the
new test module). `-m pytest` — **1078 passed, 2 skipped** (baseline 1,065 + 13). Inside this tree
`agent.__file__` and `holdout_eval.__file__` both resolve to
`D:\code-project\OmniAgent\.scratch\aie-record-layer\...`.

## 7. What this does not establish

**[SEVERITY: Medium] The tree state is read once, at the start of `evaluate`.** The legacy code did the same, and
it is ported faithfully. A tree that turns dirty, or a HEAD that moves, *during* a run still records
`clean=True` for the later questions — brief 12's failure mode, left half open. The contract asks for the identity to
be rechecked after the run. Remediation, not applied: call `_short_commit()` and `_tree_clean()` per question (about
0.1 s against tens of seconds of model time). The test that must go red: a `_tree_clean` that returns `True` then
`False` must yield rows with both values.

- **No model was run.** The records are exercised on a fake client; nothing here is a measurement of any model.
- **The record layer does not cover the first-pass runner.** `scripts/first_measurement.py` measures different
  questions through `main.py --ask`; it keeps its own per-run files and a before/after revision pair, not rows in
  `data/holdout-runs.jsonl`.
- **Nothing was written to `data/`** by this work; the tests use `tmp_path`.
- **No claim about the other five contract categories** or about `grounding_cohort`'s own record, which is a separate
  and later shape.

## 8. Options for the owner

**A — Record the tree state per question, not once.** Carried out by the **AI/ML chair**: closes the half-open
failure in §7 with the small change and the test named there. Recommended.

**B — Decide index 18.** Carried out by the **AI/ML chair** after the owner rules: give it an expectation, a preferred
tool or an abstention role, or remove it and restate the denominator as 18. Until then every score from this bank has
a question in the denominator that cannot move it.

**C — Give the first-pass runner a per-run JSONL row with commit and tree state**, using the same fields. Carried out
by the **AI/ML chair**; it makes the ten-run counting measurement recorded rather than eyeballed.

---

`QA: 2 findings (0 Critical / 0 High / 2 Medium / 0 Low) - 2 reproduced - not tested: no model run, tree state not rechecked mid-run, whether index 18 is deliberate, the other five categories, a real evaluate() run against a model`
