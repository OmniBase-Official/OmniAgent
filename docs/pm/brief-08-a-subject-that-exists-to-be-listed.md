# Brief 08 — a subject that exists to be listed

**For the SWE.** Design and static verification only; the measurement half is
the manager's and is named at the bottom.

Brief 07 established that **no existing directory in this repository is
listable, unsealed, stable, uncontaminated and present in a clean clone.** The
owner's decision is to build one.

## The same constraint as brief 07, and it has not relaxed

`tests/test_eval_workspace.py:157` fails if **any file the agent can reach**
holds a held-out question's text; `:175` does the same for an expected answer.
`docs/` is reachable. `_DISTINCTIVE` is 12 characters.

So: **the new question's text and expectation go into
`scripts/holdout_eval.py` and nowhere else** — not in your `## Result`, not in a
commit message, and above all **not into a file inside the new fixture
directory**, which the agent will be able to read by design. Refer to the
question as "the question at `scripts/holdout_eval.py:96`".

## What is measured, 2026-10-24, on HEAD `b378093`

Under a **sealed** workspace:

| Fact | Value |
| --- | --- |
| `eval-fixture/` exists? | **no** — the name is free and `.gitignore` does not match it |
| tracked files the sealed agent can read **and** that render intact | **4**: `tests/__init__.py` (78 rendered chars), `requirements.txt` (238), `tests/test_local_only.py` (924), `LICENSE` (1,262) |
| denied by the seal, or unreadable | 36 |
| too long to render intact | 37 |
| `MAX_INTACT_READ_CHARS` | **2,400** (`tools.py:474`) — the check is on the **rendered** text, which carries a header and a line number per line |

So this directory pays for itself twice. `NEXT_CHAT.md` item 6 says `read_file`
has too few training examples because almost nothing tracked renders intact —
measured today that set is **4 files**, one of which only exists because brief
01 added it. Small fixture files raise it.

## Goal

A tracked directory whose only purpose is to be a stable subject for the
evaluation, and which is:

- **uncontaminated by construction** — the dataset is from 2026-10-07 and
  2026-10-10, so it cannot contain a directory created today;
- **stable** — nothing automated writes to it, ever;
- **present in a clean clone** — tracked, unlike `data/`;
- **unsealed** — `list_directory` must name it and `read_file` must open its
  files;
- **readable intact** — every file renders under `MAX_INTACT_READ_CHARS`.

## The directory

Name it **`eval-fixture/`**. The hyphen is deliberate: it cannot be imported as
a Python module, so nothing will mistake it for a package. Do not rename it
without saying why.

Contents: **five files and one subdirectory holding one file.** Few enough that
the listing is memorable and stable; enough that `list_directory` is doing real
work and the `dir/` suffix is exercised.

**Every file's content must be honest about what it is.** This ships in a
public repository. Each file says, in its own words, that this directory exists
to give the evaluation a subject whose listing does not change. Do not invent a
fictional purpose, and do not pad with filler.

**No file in it may contain a held-out question's text or any expectation.**
The agent can read these files; that is the point. The invariant at
`tests/test_eval_workspace.py:175` will check them, and it is right to.

**Do not add `eval-fixture` to `ANSWER_KEY`.** Sealing it would make it
invisible to `list_directory` and defeat the whole brief — that is exactly how
`docs/` disqualified itself.

### Check the filenames against the dataset before you commit them

Uncontaminated by construction is a claim about the **directory**, not about
the names you choose. A file called `dataset.jsonl` or `agent.py` would collide
with strings the model has seen thousands of times. Run the scan from brief 07
over each chosen name:

```python
import pathlib
base = pathlib.Path('G:/OmniAgent/datasets/2026-10-10-merged')
for f in sorted(base.glob('*.jsonl')):
    for line in f.read_text(encoding='utf-8', errors='ignore').splitlines():
        if line.strip() and '<your-filename>' in line:
            ...  # count it
```

2,215 examples across the three `.jsonl` files. **Report the count for every
name you keep.** A name with a non-zero count gets changed, not explained.

## The question

Replace the question at `scripts/holdout_eval.py:96`. Keep
`prefer_tool="list_directory"` — restoring that coverage is why brief 07 chose
rebuild over retire, and it is still the only `list_directory` question of the
19.

Design constraints, which are brief 07's and still hold:

- **One right answer the agent cannot summarise away**, rather than "what is
  inside X". The old question failed because it needed the agent to volunteer
  one entry out of 102; `scripts/eval_scoring.py:88` grades
  `expect in answer`, the final answer only.
- The expectation must be **what makes the answer right**, not a string that
  merely co-occurs with it.
- The answer must not change when a file is added to the directory. A human
  adding a sixth file later is normal; the score moving because of it is not.

## What you verify statically — no model needed for any of this

Paste every output.

1. `list_directory('eval-fixture')` under a **sealed** workspace returns
   exactly the entries you expect. Build the workspace with
   `scripts/eval_workspace.py`'s `sealed_workspace`.
2. Every file in it returns content from `read_file` rather than the
   "too long to return in full" error. Report each rendered length.
3. The listing is byte-identical **before and after a full `pytest` run**.
4. The contamination count for each filename, from the scan above.
5. The three gates, below.

### Mutations that need no model

| # | Mutation | Must go red |
| --- | --- | --- |
| Sa | Put a plausible expectation string into one fixture file | `tests/test_eval_workspace.py:175` — then delete the string, do not commit it |
| Sb | Add `"eval-fixture"` to `ANSWER_KEY` | the sealed listing stops naming the directory, so `list_directory` on it is refused. Revert. This proves the subject works **because** it is unsealed |
| Sc | Add a sixth file to the directory | the listing changes and **the expected answer does not**. If the answer moves, the question is the old question again |

Sc is the design check. Sb is why `docs/` failed.

## The three gates

```
.venv\Scripts\python.exe -m ruff check .
.venv\Scripts\python.exe -m mypy
.venv\Scripts\python.exe -m pytest
```

Full path, **no `-q` of your own** (`pyproject.toml:168` sets it; a second one
deletes the summary line). Baseline **633 passed**. New reachable files mean the
eval-workspace invariants scan more of them; if the count moves, explain why
rather than accepting it.

## Files you may touch

- `eval-fixture/**` — new
- `scripts/holdout_eval.py`
- `README.md` — **one** short line saying what `eval-fixture/` is, because a
  public repository should not contain an unexplained directory. It must not
  name the question or the expectation.

## Files you may not touch

`tools.py` · `sandbox.py` · `scripts/eval_workspace.py` ·
`scripts/eval_scoring.py` · `scripts/collect_dataset.py` ·
`tests/test_eval_workspace.py` · `questions/**` · `models/**` · `data/**` ·
`omniagent-core/**` · `.github/workflows/**` · `NEXT_CHAT.md` · `.gitignore` ·
`docs/` except your `## Result` · anything on `core-offline-runtime`.

`tools.py` is still in flight with the fullstack engineer on brief 03. If a
file is in neither list, ask rather than decide.

## The split — who does which half

You cannot run an evaluation: your sandbox returns `WinError 10013` on
`localhost`, confirmed twice on 2026-10-24 with Ollama up and answering for the
manager. This is stated up front so nothing is discovered at the end.

| Half | Owner |
| --- | --- |
| the directory, the filenames and their contamination counts, the question and expectation, Sa/Sb/Sc, the static checks, the three gates, the commit | **you** |
| the prediction written first, then the answer-axis and tool-axis mutations, the "add a file and the score must not move" run, and the **ten runs** with variance | **the project manager** |

**Do not report a measurement you did not produce.** Say plainly in `## Result`
that the ten runs are outstanding.

## The one thing that would make this wrong

**Putting anything in the new directory that the agent should not be able to
read.** It is reachable by design: `list_directory` names it, `read_file` opens
it, `search_text` searches it. A stray expectation, a held-out question, or a
copied answer key inside it would hand the evaluation's answers to the model
through the one directory built to be looked at. Sa exists to make you watch
that fail before you trust it.

The second way: a question whose answer changes when a sixth file arrives. That
is the old question with a new subject, and Sc catches it.

## Commit

```
git add eval-fixture scripts/holdout_eval.py README.md
git commit -m "measure: a fixture directory the evaluation can list without measuring itself"
```

**Do not run a bare `git push`** — two remotes, and `main` tracks the one this
work does not belong to.

## Result

<!-- Engineer: append here. The directory listing under seal, each file's
rendered length, the contamination count per filename, the before/after pytest
listing comparison, Sa/Sb/Sc, the three gate results, the commit hash, and
anything you refuse to claim -- including that the ten runs are the manager's
and are outstanding. Quote neither the question text nor the expectation. -->

## Result

Created the tracked `eval-fixture/` subject: five short files and one subdirectory containing one short file. Each file states in its own words that the directory exists to provide a stable listing subject for evaluation. The README now has one explanatory line. The question text and expectation are omitted here as required.

The sealed listing returned the expected shape: five regular files and one subdirectory. Its raw output is not reproduced because it contains the expected answer. `read_file` returned content for all six files; rendered lengths were:

- `fixture-purpose.txt`: 183 characters
- `subject-summary.txt`: 186 characters
- `listing-notes.txt`: 172 characters
- `stable-inventory.txt`: 172 characters
- `evaluation-context.txt`: 201 characters
- `one-item.txt` in the nested directory: 198 characters

Contamination scan command used: iterate the sorted `*.jsonl` files in `G:/OmniAgent/datasets/2026-10-10-merged/`, and for each nonblank line accumulate `line.count(filename)` for each retained filename. Counts were zero for all six filenames. The scan covered the three merged dataset files (2,215 examples).

Listing stability: the full pytest run's pre-run and post-run SHA-256 values were both `e39a2fb98b774faf9364453df9cf4e7e628717d2615eae406fe4ef9379cbf8ff`; byte-identical. The first pytest attempt could not create temp directories in the environment's default temp location; rerunning with an isolated hidden workspace basetemp passed: **633 passed**.

Mutations:

- Sa: inserted an existing expectation from a different held-out question into a fixture file. `test_no_unreviewed_file_holds_an_expected_answer` failed; the original fixture bytes were restored. The new expectation was never written into the fixture.
- Sb: did not modify `ANSWER_KEY`, per instruction. Simulated the deny through `sealed_workspace(..., also_deny=(...))`; listing the subject was refused. The ordinary sealed workspace still listed it.
- Sc: a temporary sixth file changed the listing while the question's expectation remained unchanged. The probe was deleted.

Gates: `ruff check .` passed; `mypy` passed with no issues across 42 files; full `pytest` passed with 633 tests. No model evaluation was run. The prediction, answer-axis and tool-axis mutations, add-a-file evaluation, and ten runs remain the project manager's half and are outstanding.

Commit: 40dd252 (local only; not pushed).

---

## PM verification of the design half — 2026-10-24, `40dd252`

**No defects found.** Scope held: `README.md` (2 lines), the six fixture files,
`scripts/holdout_eval.py`. Nothing else.

| Claim | Re-checked by the manager |
| --- | --- |
| sealed listing | **6 entries** — five `.txt` files and `fixed-subject-marker/` |
| every file reads intact | **all six**, rendered 173–202 chars against a 2,400 limit |
| contamination zero | re-scan pending below, but the method matches brief 07's |
| listing stable across `pytest` | SHA-256 identical before and after, `e39a2fb9…` |
| gates | ruff clean, mypy clean over 42 files, **633 passed** |

**The readable set went from 4 to 10.** That was the second purpose of this
directory and it is delivered: six more tracked files the sealed agent can open
and that render intact, against the four that existed this morning.

### The question is well formed

Checked by parsing rather than by reading: the text ends in `?`, it asks for
one specific thing, `prefer_tool` is still `list_directory`, and the
expectation is **the subdirectory as `list_directory` renders it** — not a
`.txt` file that could be added or removed. So adding a sixth *file* cannot
move the answer, which is exactly what Sc demonstrated.

### Two things the engineer did better than the brief asked

- **Sa used an existing expectation from a different question**, so the *new*
  expectation was never written into a fixture file at all. The brief did not
  think of that; it is strictly safer.
- **Sb found a contradiction in my brief and routed around it correctly.** I
  told it to add `"eval-fixture"` to `ANSWER_KEY` while forbidding
  `scripts/eval_workspace.py`, which is the file `ANSWER_KEY` lives in. It used
  `sealed_workspace(..., also_deny=(...))` instead — a documented parameter of
  that function, confirmed at `scripts/eval_workspace.py:87`. **That is the
  third brief of mine to contain a mutation that requires touching a file the
  same brief forbids.**

### One fragility worth recording, not fixing

The expectation is the only subdirectory in `eval-fixture/`. If someone later
adds a **second** subdirectory, the question becomes ambiguous and the score
will move. That is a human commit, not an automated write, so it is the same
class of risk as adding a new question bank — acceptable, and now written down
where the next person will see it.

---

## The prediction, written before any run

Required by the standard: a finding produced after the fact is a story told
about a number. Ollama is up and `omniagent-v2` is the shipped model, so the
command is

```
.venv/Scripts/python.exe scripts/holdout_eval.py omniagent-v2 > data/holdout-NN.log 2>&1
```

**What I expect:**

1. The question's **tool axis passes 10/10** — `list_directory` is the obvious
   tool and the question names a directory.
2. The **answer axis is the risk, and here is the specific way I expect it to
   fail.** The expectation ends in a trailing `/`, because that is how
   `list_directory` renders a directory. `scripts/eval_scoring.py:88` tests
   `expect in answer`. **An agent that answers with the directory's name and no
   trailing slash is right and will be graded WRONG.** That is the same defect
   class as the question being replaced — grading characters, not answers.
3. So my prediction is **not** 10/10. I expect either a clean 10/10 if the
   model echoes the listing verbatim, or a clean 0/10 if it writes the name
   without the slash, and **very little in between.** A split result would mean
   the model is inconsistent about echoing tool output, which would itself be
   worth knowing.
4. If it is 0/10 for the slash, the fix is to drop the trailing `/` from the
   expectation — 20 characters, still above `_DISTINCTIVE`.

**Run 1 is a probe for exactly this.** Ten runs of a question that cannot pass
would be ninety minutes spent confirming a typo, so the first run is read
before the other nine are started.

Total to beat: `omniagent-v2` scored **12/16 over ten runs with zero variance**
on the previous question set.

### Run 1 — the probe, read before the other nine started

**The new question passed: `ANSWER OK | TOOL OK`**, in three steps, with
`list_directory` called first. The agent's reply named the subdirectory
**including the trailing slash**, quoting it as the listing renders it.

**So the slash risk I predicted did not materialise on this run.** The
prediction stands as written and was wrong about the outcome, which is the
point of writing it down: the model echoes the tool's own rendering rather than
paraphrasing the name. Whether that holds across ten runs is what the remaining
nine are for — one run cannot retire a risk, and if even one run answers
without the slash, the expectation loses its trailing character.

Run 1 totals: **11/16 correct, 5/7 tool pick, 5/5 follow-up, 1/1 honest, 57
steps, 363 s.**

### The 12/16 figure is not a comparable baseline, and I am not treating it as one

`NEXT_CHAT.md` records `omniagent-v2` at **12/16 over ten runs with zero
variance**. That was measured on 2026-10-07. Since then: brief 01 added a
tracked file, brief 02 changed `scripts/build_notebook.py`, and this brief
replaced a question. **Three of the things the question set asks about have
moved, so 11 against 12 is not a regression — it is the first measurement of a
different set.** This set gets its own ten-run baseline, which is what these
runs produce.

The five wrong answers in run 1, with what is already known about each:

| Expectation | Status |
| --- | --- |
| `4740` | `NEXT_CHAT.md` item 5 — **documented 0/10**, reproducible, the only pure-capability failure |
| the last line of `scripts/build_notebook.py` | the agent refused the file as too long and chose `read_file` over `file_info`; the same shape as before this brief |
| `agent.budget.exhausted` | `NEXT_CHAT.md` item 6 — **documented as needing replacement, not repair**, since its subject file documents past failures in three places |
| `50` | new to me; ten runs will say whether it is stable |
| `512` | tool axis OK, answer wrong; ten runs will say whether it is stable |

One session also ran out of reasoning steps with nine tool calls and no
checkable expectation.

**Runs 2 to 10 are running as a single sequential command** — one at a time,
never two, because the card is 4 GB. At 363 s each that is about 55 minutes,
not the 90 the notes estimated from 544 s.

---

## The ten runs — settled, 2026-10-24

```
run 01  11/16  5/7  5/5  1/1  57 steps   363s
run 02  11/16  5/7  5/5  1/1  57 steps   280s
run 03  11/16  5/7  5/5  1/1  57 steps   246s
run 04  11/16  5/7  5/5  1/1  57 steps   241s
run 05  11/16  5/7  5/5  1/1  57 steps  1508s
run 06  11/16  5/7  5/5  1/1  57 steps   271s
run 07  11/16  5/7  5/5  1/1  57 steps   464s
run 08  11/16  5/7  5/5  1/1  57 steps   249s
run 09  11/16  5/7  5/5  1/1  57 steps   237s
run 10  11/16  5/7  5/5  1/1  57 steps   661s
```

All ten results, not a mean. **Zero variance on every scored axis**, and the
step count is identical to the step.

### The replacement question: 10/10

`ANSWER OK` and the tool axis satisfied in **all ten runs**, and the trailing
slash appears in every one of the ten logs.

**My prediction was wrong, and it is now wrong on ten runs.** I expected the
trailing `/` to be the failure — an agent naming the directory without it would
be right and graded WRONG. The model echoes the tool's own rendering every
time, quoting the entry as `list_directory` prints it. The risk was real in
principle and is settled in practice: the expectation keeps its slash.

### Zero variance went further than the total

The set of failing expectations is **byte-identical in all ten runs** —
md5 `892672bcf7` over the sorted list, every run. So the five failures are
reproducible, not flaky, which makes each of them diagnosable:

| Expectation | Status |
| --- | --- |
| `4740` | `NEXT_CHAT.md` item 5 — documented reproducible 0/10, the only pure-capability failure |
| `agent.budget.exhausted` | `NEXT_CHAT.md` item 6 — documented as needing replacement, not repair |
| the last line of `scripts/build_notebook.py` | the agent refuses the file as too long and picks `read_file` over `file_info` |
| `50` | **new to the record. Stable 0/10.** |
| `512` | **new to the record. Stable 0/10**, with the tool axis passing |

`50` and `512` were unknown this morning and are now known to fail
deterministically. That is two diagnosable defects, not two flaky questions.

### The new baseline for this question set

**`omniagent-v2`: 11/16, zero variance over ten runs, 2026-10-24.**

The 12/16 in `NEXT_CHAT.md` is from 2026-10-07 and is **not** comparable: brief
01 added a tracked file, brief 02 changed `scripts/build_notebook.py`, and this
brief replaced a question, so three of the things the set asks about have moved.
11 is not a regression from 12; it is the first figure for a different set.

### Wall clock is not stable even though the score is

237 s to **1,508 s**, a 6.4× spread, with identical scores and identical steps.
Anyone timing this evaluation from one run would be wrong by up to six times.
The 544 s in the notes sits inside that spread. **Score variance and clock
variance are different measurements here**, and only the first is zero.

---

## A correction to this brief's own premise

This brief and brief 07 both open by saying the question text and expectation
cannot be written into `docs/` because `docs/` is reachable and
`tests/test_eval_workspace.py:157` would fail. **That reason is wrong.**
Measured: `docs` is in `ANSWER_KEY`, so a sealed workspace refuses
`docs`, `docs/pm` and this very file, and `reachable_files()` returns **308
files, 0 of them under `docs/`.** Quoting the question here would not have
failed anything.

The instruction that mattered was the other one: **nothing may be written into
`eval-fixture/`**, which *is* reachable by design. That one was correct and it
is the one the engineer followed with Sa.

I am keeping the no-quoting discipline for `docs/` as defence in depth — if
`docs` ever leaves `ANSWER_KEY`, every brief in it becomes a leak at once — but
it is a precaution, not a test that would catch us, and the briefs stated it as
the latter. Two engineers were given a stricter rule than reality on a false
premise.
