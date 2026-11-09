# Brief 01 — Task 4: the hosted-notebook framing goes

Plan task: `docs/superpowers/plans/2026-10-06-train-and-deploy.md` §"Task 4: The
Colab framing goes". This is the last open task in that plan.

**Read this brief before the plan's Task 4 section. The plan's own file list and
test are wrong, and this brief narrows both. Measured below.**

## Goal

Nothing in the repository may tell a reader to train on a hosted notebook. The
manifest records an RTX 3050 Laptop GPU and standard 1 is local only.

## What was measured, 2026-10-23, on HEAD `85d137d`

A case-insensitive search for `colab` over the tracked tree (excluding `.venv`,
`.ci-venv`, `models/`, `data/`, `omniagent-core/`) returns exactly five hits in
four files:

| File | Line | Text | Verdict |
| --- | --- | --- | --- |
| `scripts/smoke_train.py` | 3 | "The notebook in ``notebooks/`` is meant for a Colab GPU and a real base model" | **contradicts the manifest — fix** |
| `scripts/smoke_train.py` | 7 | "minutes into someone's Colab session" | **contradicts the manifest — fix** |
| `scripts/build_notebook.py` | 37 | "**Why local rather than Colab.** The whole project runs on one rule: nothing" | **correct as written — keep** |
| `notebooks/train_omniagent_lora.ipynb` | 13 | the same sentence, generated from the line above | **correct as written — keep** |
| `tests/test_notebook.py` | 92 | asserts the notebook imports no `google.colab`, `files.download`, `files.upload`, `drive.mount` | **already guards the real risk — keep** |

`README.md` contains no occurrence of the string at all.

### Two corrections to the plan

1. **The plan lists `README.md` and `scripts/build_notebook.py` as files to
   modify. Neither should change.** `README.md` has nothing to change.
   `build_notebook.py:37` is a sentence that *argues for* local training; the
   generated notebook carries it. Deleting it removes a true statement and
   weakens the document that explains the rule.
2. **The plan's test is `assert "colab" not in path.read_text().lower()`
   parametrized over three paths. That assertion is wrong for two of the three
   and vacuous for one.** It would pass on `README.md` because the string was
   never there, and it would force the deletion of correct prose from
   `build_notebook.py`. A substring expectation grades characters, not answers.

## Files you may touch

- Modify: `scripts/smoke_train.py` (module docstring only)
- **Create**: `tests/test_local_only.py` — measured 2026-10-23, the file does
  not exist. The plan's Task 4 lists it under "Test:" as though it did.
- Regenerate: `notebooks/train_omniagent_lora.ipynb` — **only** via
  `.venv/Scripts/python.exe scripts/build_notebook.py`. Editing the notebook by
  hand is work that disappears on the next regeneration.

Do not touch `README.md`, `scripts/build_notebook.py`, `tests/test_notebook.py`,
or `omniagent.toml`. If you believe one of them must change, append the argument
to `## Result` and stop rather than changing it.

## Interfaces it must produce

No new interfaces. One new test function in `tests/test_local_only.py`:

```python
def test_smoke_train_does_not_point_the_reader_at_a_hosted_notebook() -> None:
    """The manifest records an RTX 3050 Laptop GPU; standard 1 is local only."""
```

It asserts on `scripts/smoke_train.py` alone. If you want the guard to cover
more than one file, each file needs its own mutation check below — a
parametrized case with no mutation behind it is a case that proves nothing.

## The test that must fail first

1. Write the test above.
2. Run `.venv/Scripts/python.exe -m pytest tests/test_local_only.py -v` with
   **no `-q` of your own** (`pyproject.toml:168` already sets it; a second `-q`
   deletes the summary line).
3. Paste the failing output into `## Result`. It must name
   `scripts/smoke_train.py` and the offending text. A failure for any other
   reason — import error, missing file, wrong path — is not this test failing.

Then rewrite the docstring and watch it go green. Keep what the docstring says
about catching a `transformers`/`trl`/`peft` API change before a twenty-minute
run; that is the reason the script exists and it is true.

## Mutation checks that must go red

Copy the file to the scratchpad first and restore from that copy. Never
`git checkout --` alone. Before each replacement, assert the target string is
present — a `sed` pattern containing `\n` matches nothing silently, so a
mutation can "pass" without having mutated anything.

| # | Mutation | Must go red |
| --- | --- | --- |
| M1 | Put `Colab` back into the `scripts/smoke_train.py` docstring | the new test |
| M2 | Delete the new test's assert (replace the body with `pass`) | nothing — record that it goes green, which is how you know M1 is the test and not something else |
| M3 | Hand-edit `notebooks/train_omniagent_lora.ipynb` to insert `import google.colab`, without regenerating | `tests/test_notebook.py` |

M3 exists for one reason: to establish that the notebook is guarded by a test
that is not yours, so you are not claiming coverage you did not add. State in
`## Result` which test caught it, by name.

**A test asserting "this is refused" proves nothing if several independent
guards would refuse it.** If M1 turns more than one test red, name every one of
them in `## Result` and say which of them is yours.

## The three gates, before the commit

```
.venv/Scripts/python.exe -m ruff check .
.venv/Scripts/python.exe -m mypy
.venv/Scripts/python.exe -m pytest
```

Full path every time — a bare `python` picks up `.ci-venv`. Paste the `pytest`
summary line. Baseline to beat: **631 passed**, mypy strict clean over 41 files,
ruff clean. The new test makes it 632. If the count is anything else, say so
rather than rounding it.

## The one thing that would make this wrong

Deleting the word `colab` everywhere it appears. Two of the five occurrences are
the project explaining why it does *not* use a hosted notebook, and one is a
test that keeps `google.colab` out of the generated notebook. A repository that
passes `"colab" not in any file` would have lost its own explanation of the rule
and the guard that enforces it. The target is one docstring in one file.

The second way: editing `notebooks/train_omniagent_lora.ipynb` directly. It is
generated by `scripts/build_notebook.py`. Edit the generator or nothing.

## Commit

One commit, after the gates are green:

```
docs: the notebook trains locally, which is what the manifest records
```

Then check the plan's Task 4 steps off in
`docs/superpowers/plans/2026-10-06-train-and-deploy.md` and note in the plan
that Steps 1 and 3 were narrowed by this brief, with the reason.

## Result

<!-- Engineer: append here. What landed, what was measured, what you refuse to
claim. Quote the failing test output, each mutation's result, and the pytest
summary line. If you changed scope, say what and why. -->

### ผลการทำงาน

เพิ่ม `test_smoke_train_does_not_point_the_reader_at_a_hosted_notebook` ใน
`tests/test_local_only.py` และแก้เฉพาะ module docstring ใน
`scripts/smoke_train.py` ให้กล่าวถึงข้อจำกัดด้าน GPU และการรันฝึกโมเดลจริง
โดยไม่ระบุบริการ hosted notebook

ผลทดสอบครั้งแรกก่อนแก้ docstring (คัดลอกผลลัพธ์ตามที่รันได้):

```text
============================= test session starts =============================
platform win32 -- Python 3.12.10, pytest-9.1.1, pluggy-1.6.0
rootdir: D:\code-project\OmniAgent
configfile: pyproject.toml
plugins: anyio-4.15.1, platformdirs-4.12.2
collected 1 item

tests\test_local_only.py F                                               [100%]

================================== FAILURES ===================================
_______ test_smoke_train_does_not_point_the_reader_at_a_hosted_notebook _______

    def test_smoke_train_does_not_point_the_reader_at_a_hosted_notebook() -> None:
        """The manifest records an RTX 3050 Laptop GPU; standard 1 is local only."""
        source_path = REPO_ROOT / "scripts" / "smoke_train.py"
        source = source_path.read_text(encoding="utf-8")
        offending = next(
            (line.strip() for line in source.splitlines() if "colab" in line.lower()),
            "",
        )
    
>       assert "colab" not in source.lower(), f"{source_path} contains hosted notebook framing: {offending}"
E       AssertionError: D:\code-project\OmniAgent\scripts\smoke_train.py contains hosted notebook framing: The notebook in ``notebooks/`` is meant for a Colab GPU and a real base model,
E       assert 'colab' not in '"""run the ...it(main())\n'
E         
E         'colab' is contained here:
E           ant for a colab gpu and a real base model,
E         ?           +++++
E           which cannot be exercised here. this script runs the same steps -- validate,
E           load, lora-train, merge, generate -- small enough to finish on a laptop, so
E           that an api change in transformers/trl/peft fails here rather than twenty...
E         
E         ...Full output truncated (179 lines hidden), use '-vv' to show
E         
E         ...
E         
E         tests\test_local_only.py:19: AssertionError
=========================== short test summary info ============================
FAILED tests/test_local_only.py::test_smoke_train_does_not_point_the_reader_at_a_hosted_notebook
============================== 1 failed in 0.80s ==============================
```

Mutation checks:

- **M1:** เติม `Colab` กลับใน docstring แล้วมีเพียง
  `test_smoke_train_does_not_point_the_reader_at_a_hosted_notebook` ที่ล้ม
  ผลรวม: `1 failed, 631 passed in 15.59s`.
- **M2:** แทน body ของเทสต์ใหม่ด้วย `pass`; เทสต์ผ่าน (`1 passed in 0.04s`).
- **M3:** แทรก `import google.colab` ใน code cell ของ notebook ชั่วคราว;
  `tests/test_notebook.py::test_nothing_is_uploaded` ล้มเพียงตัวเดียว
  (`1 failed, 23 passed in 0.90s`). คืน notebook จากสำเนา scratch แล้ว
  และตรวจว่าไม่มี `import google.colab` ค้างอยู่

การสร้าง notebook ซ้ำเขียน 24 cells แต่เปลี่ยนไฟล์ที่ commit ไว้:

```text
 notebooks/train_omniagent_lora.ipynb | 25 +------------------------
 1 file changed, 1 insertion(+), 24 deletions(-)
```

diff แสดงว่า generator ลบ `id` ของ cell ทั้งหมดและเพิ่ม `import json` ใน cell
หนึ่ง จึงพบว่า notebook ที่ commit อยู่เดิมไม่ตรงกับ generator ตามเงื่อนไข
หยุดใน brief ผมคืน notebook จากสำเนาเดิมและหยุดก่อน gates กับ commit ตามคำสั่ง
ใน Step 5

ยังไม่ได้รัน gates สุดท้ายหลังการแก้ docstring: ไม่มีผลสุดท้ายของ Ruff หรือ
Mypy และยังไม่มีผล `632 passed` ให้ยืนยัน ไม่มี commit hash เพราะหยุดก่อน commit;
ไม่ได้ push ครับ การรัน M1/M3 ที่ตรวจผลจริงกำหนด `--basetemp` ใต้
`.pytest_cache` เพื่อหลีกเลี่ยงข้อผิดพลาดสร้าง pytest temp directory ใน
environment นี้ ผลจากการลอง M1 ครั้งแรกที่ใช้ temp directory ปริยายไม่นับเป็น
ผล mutation ที่ยืนยันได้

---

## PM verification, 2026-10-23

Re-run by the project manager against the engineer's working tree. `git log`
and the test output are the truth; the report above is a claim. Every figure
below was produced by a command in this session, not read from the report.

### Confirmed

| Claim | How it was checked | Result |
| --- | --- | --- |
| The docstring keeps the five load-bearing facts | read `git diff scripts/smoke_train.py` | **holds.** CPU plus tiny model, the GPU/base-model contrast stated as *hardware*, the five steps, the API-change reason, the smoke-test caveat. The `Usage::` block is untouched, as instructed. |
| The test is not parametrized and is typed | read `tests/test_local_only.py` | **holds.** One function, `REPO_ROOT` built with the `tests/test_shipped_config.py:25` idiom. |
| M1 turns exactly one test red, and it is the new one | asserted `needs a real GPU` present, mutated it to `needs a Colab GPU`, ran the full suite, restored from a scratchpad copy | **`1 failed, 631 passed in 10.39s`** — confirmed |
| M2 goes green | deleted line 19, the assert, ran the file, restored from a scratchpad copy | **`1 passed in 0.02s`** — confirmed, so M1's red came from that assert and nothing else |
| `mypy` is clean | `.venv/Scripts/python.exe -m mypy` | **`Success: no issues found in 42 source files`** — 41 before, so the new file is in scope |
| The suite is 632 | `.venv/Scripts/python.exe -m pytest` | **`632 passed in 9.28s`** — the predicted number, exactly |

### Not confirmed — gate 1 is red

```
.venv/Scripts/python.exe -m ruff check .
  --> tests/test_local_only.py:19:101
Found 1 error.
```

Line 19 is 104 characters against a 100-character limit. The engineer said
plainly that it never ran the gates, so nothing was misreported and nothing was
committed over a red gate. The work is unfinished, not wrong.

### The Step 5 stop was correct, and my instruction was partly wrong

The regeneration diff is `1 insertion(+), 24 deletions(-)`. Taken apart:

- **24 deletions are every one of `"id": <hex>,`** — nbformat cell
  identifiers. The committed notebook carries them, the generator does not emit
  them. Cosmetic, and not drift in any sense this project cares about.
- **The single insertion is real: `"import json\n"`**, into the cell under
  "## 9. Checksum and manifest". It is at `scripts/build_notebook.py:363`,
  so the **generator** holds it and the **committed notebook** does not.
  Neither side uses `json.` anywhere — `git show HEAD:notebooks/... | grep -c
  'json\.'` returns 0 — so what drifted is an unused import, most likely
  removed from the notebook alone. That is the trap this project has written
  down twice: an edit to the notebook and not to its generator.

**My Step 5 instruction, "`git diff` must report no change", was too strict.**
It counts nbformat cell ids as drift. The engineer applied it exactly as
written and stopped, which is the right behaviour for an instruction it was
given; the stop is mine, not its error. A correct version compares cell
*sources*, not the serialised file.

### A finding worth more than this brief

`tests/test_notebook.py:264 test_the_notebook_and_its_generator_agree` cannot
catch this. It walks a fixed `GENERATED_GUARANTEES` list and asserts each
snippet is present in both files. A line the generator gained and the notebook
never received is invisible to it, because no guarantee names that line. It is
a substring expectation grading characters, not answers, guarding the exact
failure mode this repository's trap list calls out first. It has been green
through all of this.

Restoring: the notebook was copied to the scratchpad before regeneration and
restored from that copy. SHA-256 before and after both
`fa3c90ed3e5e314cfffdf7dd97c514811341ed590c7c7711756a4c22a54e2670`.
`git status` shows it unmodified.

### What remains before this can be committed

One line wrapped under 100 characters in `tests/test_local_only.py:19`, then
the three gates re-run. Nothing else. The notebook question is a separate task
and must not be folded into this commit.

---

## PM verification, round 2 — 2026-10-23, `675e0de`

The engineer wrapped line 19 and committed. Re-run on the committed state.

| Gate | Command | Result |
| --- | --- | --- |
| 1 | `.venv/Scripts/python.exe -m ruff check .` | **All checks passed!** |
| 2 | `.venv/Scripts/python.exe -m mypy` | **Success: no issues found in 42 source files** |
| 3 | `.venv/Scripts/python.exe -m pytest` | **632 passed in 10.35s** |

The commit touches `scripts/smoke_train.py` and `tests/test_local_only.py` and
nothing else — 2 files, 26 insertions, 5 deletions. Its message is the one the
brief specified, to the character. The working tree is clean. The notebook,
`README.md` and `scripts/build_notebook.py` were not touched.

### The one thing worth checking about the fix

The rewrap put the failure message inside parentheses:

```python
assert "colab" not in source.lower(), (
    f"{source_path} contains hosted notebook framing: {offending}"
)
```

Written one character differently — the comma inside the parentheses — this
becomes `assert (cond, msg)`, a non-empty tuple, which is true always and can
never fail. Reading it is not proof. **M1 is.** Re-run against the committed
state: the target string asserted present, mutated to `needs a Colab GPU`, full
suite run, file restored from a scratchpad copy.

```
1 failed, 631 passed in 10.25s
FAILED tests/test_local_only.py::test_smoke_train_does_not_point_the_reader_at_a_hosted_notebook
```

Exactly one test red and it is the new one, so the assert still fires and the
rewrap did not hollow it out. Independently, `pyproject.toml:108` selects both
`F` and `B`, so pyflakes `F631` would have caught the tuple form as well — two
separate reasons, one of them measured here.

`git status` is empty after the restore.

### Verdict

**Brief 01 is complete and the plan's Task 4 with it.** The plan file now has
its five steps ticked and carries the three corrections. Nothing in this brief
is left unverified.

The notebook-generator drift found in round 1 is **not** fixed and was
correctly kept out of this commit. It is the candidate for brief 02.
