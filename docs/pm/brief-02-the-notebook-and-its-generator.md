# Brief 02 — the notebook and its generator must be provably the same file

Found while verifying brief 01. `docs/pm/brief-01-task-4-local-only-framing.md`
holds the discovery; this brief holds the fix.

The trap list's first entry says the notebook is generated and that editing it
alone is work that disappears. The repository has a test named for exactly that
failure. The failure happened anyway and the test stayed green.

## What is measured, 2026-10-23, on HEAD `a6cb131`

Running `.venv/Scripts/python.exe scripts/build_notebook.py` on a clean tree
produces `1 insertion(+), 24 deletions(-)` against the committed notebook.

| Difference | Count | What it is |
| --- | --- | --- |
| `"id": "<32 hex>",` removed | 24 | every cell. The committed notebook carries them; the generator emits none. |
| `"import json\n"` added | 1 | into the cell under "## 9. Checksum and manifest" |

### The four defects behind those 25 lines

1. **The generator emits an unused import.** `scripts/build_notebook.py:363`
   puts `import json` in the manifest cell. Nothing in that cell uses `json.`
   — the manifest is written by `run_dir.write_manifest` and the flat copy by
   `flat.write_text(manifest_path.read_text(...))`. `git show
   HEAD:notebooks/train_omniagent_lora.ipynb | grep -c 'json\.'` returns **0**.
   So the import was removed from the notebook alone, which is the trap, and it
   should not be in the generator either.

2. **`ruff` cannot see it.** The generator's own docstring claims writing the
   notebook as a script "lets the cell sources be linted like any other file".
   They are triple-quoted string literals, so no linter reads them. That is how
   an unused import entered and stayed. The docstring overstates what the
   design buys.

3. **The generator declares a schema version it does not satisfy.**
   `scripts/build_notebook.py:487` writes `"nbformat_minor": 5`. nbformat 4.5
   requires an `id` on every cell, and the generator emits none. The committed
   notebook has ids because Jupyter added them when the notebook was executed.
   The committed artifact is more correct than what its generator produces.

4. **`tests/test_notebook.py:264 test_the_notebook_and_its_generator_agree`
   cannot detect any of this, by construction.** It walks the six-entry
   `GENERATED_GUARANTEES` tuple and asserts each snippet appears in both files.
   A line the generator gained and the notebook never received is invisible,
   because no guarantee names that line. It is a substring expectation grading
   characters, not answers — and it is the guard named after this exact failure.
   `test_the_notebook_exists_and_is_valid_nbformat` overstates too: it checks
   `nbformat == 4`, that cells exist, that `cell_type` is in a set and that
   `source` is a list. It never looks at `nbformat_minor` or at `id`, and
   `nbformat` is not a dependency of this project.

## The ruling, with the cost of the alternative

**The generator is the source of truth for cell content. The notebook is a
build artifact that happens to be committed, and it must be byte-reproducible
from the generator.**

That requires the generator to emit cell ids, and **the ids must be
deterministic** — derived from the cell, not random — or every regeneration
churns 24 lines of diff and the comparison test becomes useless.

The alternative considered and rejected: drop `nbformat_minor` to `4`, where
ids are not required, and strip the 24 ids from the committed notebook. It is
the smaller change. **Its cost is that it does not hold.** The moment anyone
opens the notebook in Jupyter it gains ids and the minor version is bumped back
to 5, and the drift is back with a test that was just taught to expect no ids.
Deterministic ids survive that; absent ids do not.

## The blocker you must fix first

`scripts/build_notebook.py` **writes the notebook at import time.** Lines
490–491 are at module level with no `if __name__ == "__main__":` guard, and
`OUT` on line 12 is `Path("notebooks/train_omniagent_lora.ipynb")`, relative to
the current working directory rather than to the file.

So a test that imports the generator **overwrites the real notebook and then
compares the file to itself.** It would pass forever. This is the single way
this brief gets implemented wrongly, and it is also why the fix is a small
refactor and not just a new test.

## Files it may touch

- Modify: `scripts/build_notebook.py`
- Modify: `tests/test_notebook.py`
- Regenerate: `notebooks/train_omniagent_lora.ipynb`, by running the generator

Nothing else. Do not touch `scripts/smoke_train.py`, `tests/test_local_only.py`,
`omniagent.toml`, `README.md`, or anything under `docs/`. Do not add a
dependency — `nbformat` stays out. Standard 2 is no frameworks and the schema
check this needs is two assertions.

## Interfaces it must produce

In `scripts/build_notebook.py`:

```python
def build_notebook() -> dict[str, object]:
    """The notebook as a dict, with a deterministic id on every cell. No I/O."""

def cell_id(index: int, source: list[str]) -> str:
    """First 8 hex characters of sha256 of f"{index}:{''.join(source)}"."""
```

- `build_notebook()` performs **no file I/O** and returns the same dict every
  call. Calling it twice must produce equal dicts.
- `cell_id` takes the index as well as the source so two identical cells cannot
  collide. Eight hex characters satisfies the nbformat id pattern.
- `OUT` is resolved from `__file__`, not from the working directory, so the
  generator writes the same path wherever it is run from.
- The write, the `mkdir` and the `print` move under
  `if __name__ == "__main__":`. **Importing the module must touch no file.**
- Remove `import json` from the manifest cell's source text. Keep the
  generator's own `import json` at line 9 — `json.dumps` still writes the file.
- Correct the module docstring's claim about linting: the cell sources are
  string literals and no linter reads them.

## The tests that must fail first

Two, both in `tests/test_notebook.py`. Write them, run them, and **paste the
failing output** before changing the generator.

```python
def test_the_committed_notebook_is_what_the_generator_produces() -> None:
    """The notebook is a build artifact; drift means one file was edited alone."""

def test_the_generator_is_deterministic() -> None:
    """Two calls must agree, or the comparison above is noise."""
```

The first compares `build_notebook()` against
`json.loads(NOTEBOOK.read_text(encoding="utf-8"))` — **the whole dict, equality,
not a snippet list.** On failure the message must say which cell index differs.

Neither test may write to `notebooks/`, run the generator as a subprocess, or
use a temporary directory. Compare in memory. There is nothing to write.

**Replace `test_the_notebook_and_its_generator_agree` with the first of these.**
Delete it and delete `GENERATED_GUARANTEES`. It is not a weaker version of the
new test, it is a test that cannot fail for the reason it is named, and leaving
both means the next reader trusts the wrong one. If you disagree, argue it in
`## Result` and leave both rather than deleting.

Extend `test_the_notebook_exists_and_is_valid_nbformat` with two assertions:
`nbformat_minor == 5`, and every cell has a non-empty string `id`.

## Mutation checks that must go red

Copy each file to a scratch directory outside the repository before mutating,
restore from that copy, and assert the target string is present before
replacing it. Never `git checkout --` alone.

| # | Mutation | Must go red |
| --- | --- | --- |
| M1 | Change one character in any cell's source text in `scripts/build_notebook.py` | the comparison test |
| M2 | Change one character in a cell's source in `notebooks/train_omniagent_lora.ipynb`, the generator untouched | the comparison test |
| M3 | Make `cell_id` return `uuid4().hex[:8]` instead of the hash | the determinism test |
| M4 | Delete the comparison test's assert | **nothing** — it must go green, which is how you know M1 and M2 were caught by it |
| M5 | Put `import json` back into the manifest cell source and regenerate | the comparison test, because the committed notebook will not have it |

M1 and M2 are not the same check. M1 proves the test notices the generator
moving; M2 proves it notices the notebook moving. A test that only catches one
of them leaves the drift that actually happened undetected — it was the
notebook that was edited alone.

Report every test that turned red for each mutation, by name. If a mutation
turns more than one red, say which is yours.

## The three gates

```
.venv\Scripts\python.exe -m ruff check .
.venv\Scripts\python.exe -m mypy
.venv\Scripts\python.exe -m pytest
```

Full path, and **no `-q` of your own** — `pyproject.toml:168` already sets it
and a second one deletes the summary line. Baseline is **632 passed**. You
remove one test and add two, so expect **633**. Report the actual number.

`mypy` runs in strict mode over 42 files and `build_notebook.py` is one of
them, so `build_notebook()` and `cell_id` need full annotations.

## The one thing that would make this wrong

**A test that regenerates the notebook on disk and then reads it back.** It
compares the file to itself and passes forever, and because the generator
writes at import time, even `import scripts.build_notebook` does it. If at any
point `git status` shows `notebooks/train_omniagent_lora.ipynb` modified while
you are only running tests, stop: the test is writing, and whatever it then
proved, it did not prove this.

The second way: deleting
`test_the_notebook_and_its_generator_agree` and replacing it with something
that also only checks snippets. The new test's value is that it is an equality
check over the whole document. If it has a list of things to look for in it, it
is the old test with a new name.

## Commit

One commit after the gates are green. The regenerated notebook goes in it — the
24 new deterministic ids and the removed import are the point.

```
git add scripts/build_notebook.py tests/test_notebook.py notebooks/train_omniagent_lora.ipynb
git commit -m "fix(notebook): the committed notebook is provably its generator's output"
```

Do not run a bare `git push` — this repository has two remotes and `main`
tracks the one this work does not belong to. Leave it unpushed.

## Result

<!-- Engineer: append here. The two failing outputs from before the fix, every
mutation with the names of the tests that changed colour, the three gate
results, the pytest count, the commit hash, and anything you refuse to claim. -->

### ผลการทำงาน

แก้ `scripts/build_notebook.py` ให้ import ได้โดยไม่เขียนไฟล์, เพิ่ม `cell_id` แบบ SHA-256 deterministic และ `build_notebook()` ที่สร้าง dict ในหน่วยความจำ, ผูก `OUT` กับตำแหน่ง generator, ย้ายการเขียนไว้ใน main guard, เอา `import json` ที่ไม่ใช้จาก manifest cell ออก และแก้คำอธิบายเรื่อง linting เพิ่ม equality test ทั้ง dict และ determinism test พร้อมตรวจ `nbformat_minor` และ IDs; ลบ `GENERATED_GUARANTEES` กับเทสต์เดิมตาม brief

ผล Step 3 หลัง import generator ได้อย่างปลอดภัย แต่ก่อนแก้ drift: comparison test ล้มที่ cell index 0; determinism test ผ่านอยู่แล้ว ผลคำสั่งรันซ้ำโดยกำหนด `--basetemp` เพื่อหลีกเลี่ยง temp setup error ใน sandbox:

```text
============================= test session starts =============================
platform win32 -- Python 3.12.10, pytest-9.1.1, pluggy-1.6.0
rootdir: D:\code-project\OmniAgent
configfile: pyproject.toml
plugins: anyio-4.15.1, platformdirs-4.12.2
collected 25 items

tests\test_notebook.py .F.......................                         [100%]

================================== FAILURES ==================================
_________ test_the_committed_notebook_is_what_the_generator_produces __________

    def test_the_committed_notebook_is_what_the_generator_produces() -> None:
        """The notebook is a build artifact; drift means one file was edited alone."""
        generated = build_notebook()
        committed: dict[str, Any] = json.loads(NOTEBOOK.read_text(encoding="utf-8"))
        generated_cells = generated["cells"]
        committed_cells = committed["cells"]
        assert isinstance(generated_cells, list)
        assert isinstance(committed_cells, list)
    
        difference = "notebook metadata differs"
        for index in range(max(len(generated_cells), len(committed_cells))):
            if (
                index >= len(generated_cells)
                or index >= len(committed_cells)
                or generated_cells[index] != committed_cells[index]
            ):
                difference = f"cell index {index} differs"
                break
    
>       assert generated == committed, difference
E       AssertionError: cell index 0 differs
E       assert {'cells': [{'...mat_minor': 5} == {'cells': [{'...mat_minor': 5}
E         
E         Omitting 3 identical items, use -vv to show
E         Differing items:
E         {'cells': [{'cell_type': 'markdown', 'metadata': {}, 'source': ['# OmniAgent \\u2014 LoRA fine-tune \\u2192 GGUF \\u2192 Ollama\\n', '\\n'...at looks like a credential, because a model trained on a leaked key will\\n', 'reproduce it.'], 'id': '186c7ee3'}, ...]} != {'cells': [{'cell_type': 'markdown', 'id': '7fb27b941602401d91542211134fc71a', 'metadata': {}, 'source': ['# OmniAgent...g anything\\n', 'that looks like a credential, because a model trained on a leaked key will\\n', 'reproduce it.']}, ...]}
E         Use -v to get more diff

tests\test_notebook.py:78: AssertionError
================================ short test summary info =================================
FAILED tests/test_notebook.py::test_the_committed_notebook_is_what_the_generator-produces
======================== 1 failed, 24 passed in 0.96s ========================
```

คำสั่ง Step 3 แบบตรงตาม brief ครั้งแรกมี comparison assertion failure ที่ cell 0 และ error จาก pytest สร้าง `tmp_path` สองกรณีใน temp directory ที่ sandbox จำกัดสิทธิ์ไว้ การรันซ้ำด้วย `--basetemp` ให้ผล failure ที่ต้องการโดยไม่มี setup error

Step 4 สร้าง notebook ด้วย generator ได้ 24 cells; diff:

```text
 notebooks/train_omniagent_lora.ipynb | 96 ++++++++++++++++++------------------
 1 file changed, 48 insertions(+), 48 deletions(-)
```

รัน generator รอบสองแล้ว SHA-256 ไม่เปลี่ยน (`C71C8EA6E405A04EF1B09E31215DF199760B3F36A2D57D22AC5EDCA9FB3C6DE1`) และ diff คงเดิม

ผล mutation checks:

- **M1:** เปลี่ยน `## 1. Settings` ใน generator; ล้มเฉพาะ `test_the_committed_notebook_is_what_the_generator_produces` ที่ cell 1.
- **M2:** เปลี่ยนข้อความใน cell 1 ของ notebook อย่างเดียว; ล้มเฉพาะ `test_the_committed_notebook_is_what_the_generator_produces` ที่ cell 1.
- **M3:** เปลี่ยน `cell_id` ให้ใช้ `uuid4`; ล้มเฉพาะ `test_the_generator_is_deterministic`.
- **M4:** เอา equality assert ออก; `test_the_committed_notebook_is_what_the_generator_produces` ผ่าน (`1 passed`).
- **M5:** ใส่ `import json` ใน manifest cell แล้ว regenerate; คืน notebook จาก scratch copy เดิมก่อนเปรียบเทียบแล้ว ล้มเฉพาะ `test_the_committed_notebook_is_what_the_generator_produces` ที่ cell 18. การลองครั้งแรกที่เปรียบเทียบหลัง regenerate โดยไม่คืนสำเนาผ่าน เพราะ generator เพิ่งเขียน notebook ให้ตรงกับตัวเอง; ไม่นับเป็นผล mutation ที่ยืนยัน

ผล gates หลังปรับ Ruff:

- Ruff: `All checks passed!`
- Mypy: `Success: no issues found in 42 source files`
- Pytest: `633 passed in 13.48s`

Implementation commit: `8b2a80af4ff28f951ed8b3a58c01e54fe4cb12cd`. ไม่ได้ push

สิ่งที่ไม่กล่าวอ้าง: คำสั่ง Step 3 ครั้งแรกมี temp setup errors เพิ่มจาก sandbox; ผล failure ที่อ้างเป็นผลจากการรันซ้ำด้วย `--basetemp` ไม่มีการเพิ่ม dependency หรือแก้ไฟล์นอกขอบเขต brief

---

## PM verification — 2026-10-23, `8b2a80a`

Re-run on the committed state. Every figure below came from a command in this
session.

| Gate | Result |
| --- | --- |
| `ruff check .` | **All checks passed!** |
| `mypy` | **Success: no issues found in 42 source files** |
| `pytest` | **633 passed in 9.82s** — the predicted count |

### The central guarantee, proved rather than read

The brief's one way to get this wrong was a test that writes the notebook and
then compares it to itself. Imported the generator **from `C:/`**, a different
working directory:

```
imported, cells: 24
OUT resolves to: D:\code-project\OmniAgent\notebooks\train_omniagent_lora.ipynb
```

sha256 before and after both `c71c8ea6…`, **mtime unchanged** at `1792735588`,
`git status` empty. The import touches no file, and `OUT` is anchored to
`__file__` rather than the working directory — the old bug would have written
to `C:/notebooks/`, and there is no such directory.

Ran the generator **twice from `C:/`**: the notebook is byte-identical at
`c71c8ea6…`, `git status` clean, no stray `C:/notebooks`. Regeneration is
idempotent, so `cell_id` is genuinely deterministic.

### M2 and M4, re-run independently

M2 is the check that matters — the drift that actually happened was on the
notebook side. Mutated `## 1. Settings` to `## 1. Settingz` **in the notebook
alone**, generator untouched, restored from a scratchpad copy afterwards:

```
1 failed, 632 passed in 9.72s
FAILED tests/test_notebook.py::test_the_committed_notebook_is_what_the_generator_produces
```

Exactly one test red and it is the new one. M4: replaced the equality assert
with `assert True, difference` — `25 passed in 0.63s`. So the red above comes
from that assert and nothing else.

### Also checked

- `import json` is gone from the committed notebook: `grep -c` returns **0**.
- `joined()` is still used five times, so deleting the old test left no dead
  helper behind.
- `scripts/build_notebook.py --help` **still regenerates instead of printing
  help**, because the script takes no arguments. It is now harmless: the
  regeneration is byte-identical and `git status` stays clean, so the
  2026-10-11 accident can no longer take a day's work with it. Recorded in
  `NEXT_CHAT.md`, not fixed, and deliberately not added to this brief's scope.
- The deleted `GENERATED_GUARANTEES` comment carried the 2026-10-11 incident.
  **No history was lost** — `NEXT_CHAT.md` already records it, and that entry
  has now been struck through where it called the deleted test "the guard that
  was missing".

### The lesson this turned up

That 2026-10-11 entry also recorded the old test as mutation-checked both ways.
It was — by reverting one of the six snippets it asserts, which is the one
thing it is built to see. **A mutation drawn from the test's own assumptions
can only confirm what the test already covers.** That is why a test named for
this exact failure sat green over the real drift for twelve days. Added to the
trap list.

### Verdict

**No defects found.** Every interface the brief specified is present and
proved: no I/O on import, `OUT` anchored to `__file__`, a `__main__` guard,
deterministic ids, the unused import gone, the snippet test replaced by an
equality check over the whole document, and `nbformat_minor` plus per-cell
`id` now asserted.

Two things the engineer reported against itself, both correct and both to its
credit: its first M5 attempt passed because it compared after regenerating —
the file against itself — and it discarded that result and redid it; and its
first Step 3 run had `tmp_path` setup errors from the sandbox, so it re-ran
with `--basetemp` and said so rather than quoting the first output.
