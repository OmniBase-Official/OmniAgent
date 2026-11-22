# Brief 12 — a record that refuses to pool

**For the fullstack engineer.** Static throughout — **no model run is needed**
— and the work is disjoint from brief 11, which the security engineer is
executing in `sandbox.py` and `tools.py` at the same time.

Open item 4. Brief 10 Part 3 started recording one line per question into
`data/holdout-runs.jsonl`. Reading that file today found the defect this brief
closes, and nothing has read it since except a throwaway script of mine, twice.

## What is measured, 2026-10-26, HEAD `888623a`

`data/holdout-runs.jsonl` holds **209 records: 190 at `43aba72` and 19 at
`60183b8`.** The 19 are a single run I made while the tree was dirty — brief
10's Part 3 was uncommitted while it ran — and that run is **void**. It is
recorded in this repository as void, at "The P6 run did not happen" in
`docs/pm/brief-10-no-question-is-scored-on-nothing.md`.

Fields today: `index`, `tools`, `steps`, `checkable`, `correct`,
`tool_expected`, `right_tool`, `honest_expected`, `admitted`, `commit`,
`model`.

**Nothing in the file says the tree was dirty.** `scripts/session_eval.py:219
commit()` exists precisely so runs of different code are not pooled, and its
docstring says what happened the day it was written: three runs of yesterday's
agent were mixed with one of today's and reported as a single figure. **Same
commit with a dirty tree defeats it the same way**, and the file already
contains the proof.

## Part 1 — the record says whether the tree was clean

Add a field. `git status --porcelain` empty or not, taken the same way
`commit()` takes the hash: a fixed argv, no shell, a timeout, and
`"unknown"` rather than an exception if git is not there.

**`"unknown"` is not `True`.** A record that cannot establish cleanliness is
not a clean record, and the reader below must treat it as unusable rather
than as fine.

The field is part of the run, not the question, so it belongs wherever
`commit` and `model` already go — do not put it in `question_record()`, which
is pure and tested for carrying nothing but index, tools, steps and the
verdict booleans.

### Tests that must fail first

| Test | Must fail before, pass after |
| --- | --- |
| an appended record carries the cleanliness field | new behaviour |
| `question_record()` still carries **only** index, tools, steps and the six verdict booleans | this one must pass **before and after** — it is the guard that the new field did not leak into the pure function |

## Part 2 — a reader that refuses to pool what should not be pooled

`scripts/session_eval.py:287 report()` reads its runs file and prints each
question's spread across runs, with `Spread.settled` (`:205`) saying whether
every run agreed. `holdout_eval` has no equivalent, so every reading of its
file so far has been a throwaway script — mine, twice, and the second one
found a defect the first had not.

Add `--report` to `scripts/holdout_eval.py`. It reads `RUNS_PATH` and prints,
per question index: how many runs, how many passed each axis, the step range,
and whether it settled.

**What it must refuse:**

1. **Runs where the tree was not clean, and runs where cleanliness is
   `unknown`.** Dropped, not down-weighted, and the output says how many were
   dropped and why. A figure that silently includes a void run is worse than
   no figure.
2. **Pooling across commits.** Group by commit and say so. If someone asks
   for one number over two commits, that is two numbers.
3. **Guessing what a missing field means.** Records written before this brief
   have no cleanliness field at all. They are not clean and not dirty; they
   are **unknown**, and rule 1 applies. The 209 records already in the file
   are all of this kind, so the first run of `--report` will drop every one of
   them and say so. **That is the correct output**, and if it prints a tidy
   table instead, the reader is wrong.

A question with no runs left after the refusals is reported as such. Printing
`0/0` as though it were a result is the defect this project keeps finding in
its own instruments.

### Tests that must fail first

| Test | Must fail before, pass after |
| --- | --- |
| a dirty run is dropped and counted in the "dropped" line | new |
| a record with no cleanliness field is dropped as unknown | new |
| two commits are reported separately, never summed | new |
| a question whose runs were all dropped is named, not printed as `0/0` | new |

Build these over a temporary JSONL file in `tmp_path`, the way
`tests/test_session_eval.py` does. **Do not write into `data/`.**

## Mutations that must go red

Restore from a scratchpad copy, **never `git checkout --` alone**.

| # | Mutation | Must go red |
| --- | --- | --- |
| Ma | Treat `"unknown"` cleanliness as clean | the unknown-is-dropped test |
| Mb | Pool two commits into one tally | the two-commits test |
| Mc | Put the cleanliness field inside `question_record()` | the purity test from Part 1 |
| Md | Report a question with zero surviving runs as `0/0` | the all-dropped test |

**Mc is the one to watch.** The purity test is the only thing standing between
this record and the thing it exists to avoid — a run artifact the agent could
read its own answers out of. It passes today for free; Mc is how you find out
whether it would still catch anything.

## The three gates

```
.venv\Scripts\python.exe -m ruff check .
.venv\Scripts\python.exe -m mypy
.venv\Scripts\python.exe -m pytest
```

Full path, **never your own `-q`** (`pyproject.toml:168` sets it; a second one
deletes the summary). Baseline **642 passed**, mypy clean over **44** files.
Your new tests move the count — say what to.

**Run the gates from a clean tree and say what HEAD you were on.** The
security engineer is committing to `sandbox.py`, `tools.py` and `tests/` on
brief 11 while you work; if the count moves for a reason that is not yours,
that is what happened, and saying so is the report, not an excuse.

## Files you may touch

- `scripts/holdout_eval.py`
- `tests/test_holdout_record.py`
- a new test file if you want one

## Files you may not touch

`sandbox.py` · `tools.py` · `agent.py` · `tests/test_sandbox.py` ·
`tests/test_search_text_pruning.py` · `tests/test_tools.py` —
**all five are brief 11's, in flight right now** · `scripts/eval_scoring.py` ·
`scripts/eval_workspace.py` · `scripts/session_eval.py` ·
`tests/test_eval_workspace.py` · `tests/test_holdout_questions.py` ·
`eval-fixture/**` · `questions/**` · `models/**` · `omniagent-core/**` ·
`.github/workflows/**` · `NEXT_CHAT.md` · `README.md` · `docs/` except your
`## Result`.

`data/**` is **read-only**: read the record file, write nothing into it by
hand. The evaluation appends to it when it runs, which is its job and not
yours. If a file is in neither list, ask rather than decide.

## The one thing that would make this wrong

**A reader that produces a number from the records it has rather than saying
what it could not use.** Every instrument defect this project has found this
week was an instrument reporting something when it should have reported
nothing: a question scored `no check` and read as passing, a run pooled
across a dirty tree, a tally that includes a void run. The first output of
`--report` on the current file should be "209 records, 209 dropped, no
cleanliness recorded" — **if it is anything tidier than that, you have built
the same defect again.**

The second way: **putting the cleanliness into `question_record()`.** It is
pure, it is tested, and it is the thing that keeps question text and
expectations out of a file the agent might one day reach.

## The split

Nothing here needs a model. The whole brief is yours; the manager re-runs it
afterwards, as always.

## Commit

One commit per part, gates green at each:

```
git add scripts/holdout_eval.py tests/
git commit -m "measure: a run record that says whether the tree was clean"

git add scripts/holdout_eval.py tests/
git commit -m "measure: a report that drops what it cannot trust, and says so"
```

Then **commit this brief with your `## Result` appended**:

```
git add docs/pm/brief-12-a-record-that-refuses-to-pool.md
git commit -m "docs: brief 12 result -- the record refuses to pool"
```

**Do not run a bare `git push`** — two remotes, and `main` tracks the one this
work does not belong to. Name it: `git push origin main`.

## Result

<!-- Engineer: append here. The HEAD you worked from; what `--report` prints
on the file as it stands today, verbatim; Ma-Md each with the test that went
red; the three gate results with the test count explained and any movement
you did not cause; the commit hashes; and anything you refuse to claim. -->

### ผลการดำเนินงาน

- เริ่มใน isolated worktree ที่สะอาดจาก `a0972638b798e21f49efe7241a39fa678f7eb017` ซึ่งตรงกับ `main` และ `origin/main` ณ จุดเริ่มต้น; `git status --porcelain` ว่างก่อนแก้ไข Prompt ระบุ `888623a` ซึ่งเป็นบรรพบุรุษก่อนหน้า 3 commits ที่เป็นเอกสาร PM เท่านั้น ไม่มี source หรือ test เปลี่ยนในช่วงนั้น
- เรียก `main(["--report"])` โดยกำหนด `RUNS_PATH` ในหน่วยความจำให้ชี้ไปยัง `data/holdout-runs.jsonl` ของ checkout หลัก แล้วอ่านไฟล์อย่างเดียว ผลที่พิมพ์ออกมาทั้งหมด:

```text
209 records, 209 dropped, no cleanliness recorded
Cleanliness: 0 clean, 0 dirty, 209 unknown (209 missing field).
2 commit groups; each is reported separately.

commit 43aba72: 190 records, 0 clean, 190 dropped
  question 0: no surviving runs
  question 1: no surviving runs
  question 2: no surviving runs
  question 3: no surviving runs
  question 4: no surviving runs
  question 5: no surviving runs
  question 6: no surviving runs
  question 7: no surviving runs
  question 8: no surviving runs
  question 9: no surviving runs
  question 10: no surviving runs
  question 11: no surviving runs
  question 12: no surviving runs
  question 13: no surviving runs
  question 14: no surviving runs
  question 15: no surviving runs
  question 16: no surviving runs
  question 17: no surviving runs
  question 18: no surviving runs

commit 60183b8: 19 records, 0 clean, 19 dropped
  question 0: no surviving runs
  question 1: no surviving runs
  question 2: no surviving runs
  question 3: no surviving runs
  question 4: no surviving runs
  question 5: no surviving runs
  question 6: no surviving runs
  question 7: no surviving runs
  question 8: no surviving runs
  question 9: no surviving runs
  question 10: no surviving runs
  question 11: no surviving runs
  question 12: no surviving runs
  question 13: no surviving runs
  question 14: no surviving runs
  question 15: no surviving runs
  question 16: no surviving runs
  question 17: no surviving runs
  question 18: no surviving runs
Settled means every applicable verdict axis agrees across retained runs.
```

- Mutation checks ทำให้ test ที่ระบุล้มเหลวทุกข้อ แล้วคืน source จาก scratchpad หลังแต่ละ mutation: Ma — `test_report_treats_missing_and_unknown_cleanliness_as_dropped`; Mb — `test_report_keeps_commit_groups_separate`; Mc — `test_question_record_has_only_index_tools_steps_and_verdict_booleans`; Md — `test_report_names_questions_with_no_surviving_runs_without_zero_over_zero`.
- Gates รันด้วย `D:\code-project\OmniAgent\.venv\Scripts\python.exe` โดยไม่มี `-q` บน clean commit แต่ละส่วน: หลัง Part 1 ที่ `fe3238771835963e6b2363e77183904a9651e14d`, Ruff ผ่าน, mypy ผ่าน 44 files, pytest 644 passed; หลัง Part 2 ที่ `2c4657fd795d905b8c620617546a5645ba38f35a`, Ruff ผ่าน, mypy ผ่าน 44 files, pytest 648 passed. จำนวน 642 เดิมเพิ่ม 2 tests ใน Part 1 และอีก 4 ใน Part 2; ไม่พบ test-count movement จากงานอื่นใน worktree นี้
- Commits: `fe3238771835963e6b2363e77183904a9651e14d` (Part 1); `2c4657fd795d905b8c620617546a5645ba38f35a` (Part 2); รายงานนี้อยู่ใน commit ที่สามตามลำดับที่ brief กำหนด
- ไม่ได้รันโมเดลและไม่ได้เขียน `data/**`; จึงไม่อ้างคะแนนหรืออันดับของโมเดล เพราะ report กรองทั้ง 209 records ออกเนื่องจากไม่มีข้อมูล cleanliness
