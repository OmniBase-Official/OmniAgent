# Brief 10 — no question is scored on nothing

> **Part 1 was rewritten on 2026-10-26 and the hold is lifted.** The first
> version demanded a new answer format and graded it with a `none_of` list.
> A probe settled it: **the reworded question derails the agent in three runs
> out of three, where the original answers correctly in three out of three in
> the same harness.** The rule is now a plain expectation on the longer file's
> name and the question text does not change. The evidence, the control, and
> what it cost the prediction are at the end of this file. Parts 2 and 3 were
> never affected.

**For the SWE.** Design and static verification only; the measurement half is
the manager's and is named at the bottom. **No model run is needed for any
part of this brief** — including the retro-scoring in Part 1, which reads logs
that are already on disk.

Two items on the open list are the same defect seen twice: **a question whose
right answer is not a substring is graded on a weaker axis, and a weaker axis
reads as "not wrong".** They live in the same three files and they both move
the denominator, so they are one brief and one re-measure rather than two.

## What is measured, 2026-10-26, on HEAD `dbfc39e`

Gates re-run by the manager before writing this: ruff clean, mypy clean over
**43** files, **636 passed**. Working tree clean.

The bank at `scripts/holdout_eval.py:52`:

| Fact | Value |
| --- | --- |
| questions | **19** |
| scored on an answer (`expect` set) | **16** — this is the 11/16 denominator |
| scored on tool choice | 7 |
| scored on honesty | 1 |
| **scored on tool choice alone** | **1** — `scripts/holdout_eval.py:77` |
| **scored on nothing at all** | **1** — `scripts/holdout_eval.py:122`, which prints `no check` |
| reachable files under the seal | **309** (308 in the notes plus `tests/test_search_text_pruning.py`, added in `0c04ffa`) |

### What those two questions actually did, in all ten recorded runs

Read out of `data/holdout-run01.log` … `run10.log` — the ten runs behind the
current baseline. **This is the evidence the brief rests on; do not re-derive
it, but do not trust it either: the logs are on your disk and you can check
any line of it.**

The comparison at `:77` — **answered correctly in 10 runs out of 10**, every
time in the same words, and every time in **7 steps with 6 tool calls**
including three `read_file`s and a `search_text` it had no use for. Scored
`TOOL OK`. The answer axis never saw it.

The follow-up at `:122` — **answered correctly in 0 runs out of 10**, and
scored `no check` in all ten:

| What it answered | Runs |
| --- | --- |
| "I ran out of reasoning steps before reaching an answer." | 6 |
| "I am unable to answer this question as it requires a tool that cannot locate the files mentioned in the question." — a false hedge; both files exist and it had already read one of them | 3 |
| the right file, by the wrong arithmetic: it reported a difference of 391 where the two counts differ by 390 | 1 |

**8 or 9 steps in every one of the ten runs.** This is the derailment the open
list calls a defect in the instrument, and it is worse than "hidden": three of
the ten runs are the agent inventing a tool failure, which is the exact
behaviour the honesty axis exists to catch, landing on a question that has no
honesty axis.

So the instrument currently reports 11/16 while **one question it does not
score is failing deterministically and another is passing for the wrong
reason.**

### Why the second item is the same defect

`agent.budget.exhausted` is the expectation at `scripts/holdout_eval.py:91`
and `scripts/session_eval.py:84`. Measured:

- the string occurs in **five** reachable files, recorded in
  `EXPECTATION_CARRIERS` at `tests/test_eval_workspace.py:60` and asserted by
  `test_the_budget_expectation_is_not_unique_to_its_subject`. A `search_text`
  over `.` returns four files that are not the question's subject.
- the subject itself argues against the answer. `agent.py:194-195` records, in
  prose, that the model "answered that the word 'budget' is not used anywhere
  in the file". `agent.py:370` contains a quoted sentence beginning "I have
  found where 'budget' is used in agent.py". `agent.py:612-618` records both
  fine-tunes reading one file nine times on a comparison question.

A question whose subject file contains both a denial of the answer and a
transcript of a previous wrong attempt is not measuring retrieval. It is the
same class as brief 07's listing subject: **the subject has to be replaced,
not the expectation repaired.**

## Goal

Three changes to the instrument, after which **no question in either
evaluation is scored on tool choice alone or on nothing**, and every
expectation is uniquely located in the file the question is about.

---

# Part 1 — give the two comparisons an expectation

**Rewritten 2026-10-26 after the probe at the end of this file.** The first
version of this part asked for an `Expectation(all_of, none_of)` type and a
question text demanding "the filename only". Measured: that rewording derails
the agent in **3 runs out of 3**, while the original wording answers correctly
in **3 out of 3** in the same harness. The new type is not needed and the
question texts do not change.

## What changes

The two comparison questions get an ordinary `expect`: **the name of the
longer file**.

- `scripts/holdout_eval.py:77` — `expect` is the longer of
  `tests/test_config.py` and `tests/test_sandbox.py`. Keep
  `prefer_tool="file_info"`.
- `scripts/holdout_eval.py:122` — `expect` is the longer of `tests/fakes.py`
  and `scripts/build_notebook.py`, the two files its chain has just asked
  about.

**Computed at import time from `_lines()`, never written down.**
`scripts/holdout_eval.py:39` exists for this and its docstring says why: a
hardcoded count is wrong the moment the file is edited, and the figure then
falls for a reason that is not the model. If someone adds 200 lines to the
shorter file, the expectation must flip by itself. A test must prove it does —
not by reading the constant back, but by asserting the expectation equals the
name of whichever file `_lines()` says is longer.

Measured today, so you can check your computation against it:

| File | Lines |
| --- | --- |
| `tests/test_config.py` | 354 |
| `tests/test_sandbox.py` | 539 |
| `tests/fakes.py` | 122 |
| `scripts/build_notebook.py` | 512 |

And measured under the seal, so you know these are clean expectations:
`tests/test_sandbox.py` and `scripts/build_notebook.py` each occur in **0**
reachable files. (`tests/fakes.py` occurs in `README.md`, which is why the
loser's name is not used for anything.) Both are over `_DISTINCTIVE`, so the
leak invariant covers them. **Check this yourself rather than taking it from
me; it is the kind of fact that moves.**

## The hole this leaves, which is recorded rather than closed

`tests/test_holdout_questions.py:20-24` says a substring cannot score a
comparison, because "fakes.py is longer than build_notebook.py" contains every
word a right answer would. **That reasoning is correct and the hole stays
open: an answer that names the two files the wrong way round scores right.**

It stays open because every way of closing it is worse:

- forbidding the loser's name grades a **correct** answer wrong — measured,
  all ten recorded answers name both files;
- demanding a bare filename **destroys the question** — measured, 3 runs of 3;
- matching phrases like "is longer than" grades characters, which is the
  defect this whole brief exists to remove.

So write the hole down where the next person will find it. Add a test in the
style of `test_the_budget_expectation_is_not_unique_to_its_subject` — a
measured weakness, asserted so that it cannot be forgotten and so that it
fails loudly if someone later changes the rule. It should assert that the
reversed answer **would** be graded correct. A test that documents a known
hole is worth more than a comment: the comment goes stale, the test does not.

**Report it in the figures too.** A question with a known false-positive mode
is not the same as one without. Say so wherever the new baseline is quoted.

## Retro-score the ten recorded runs

Before anything is run again, score the **recorded answers** in
`data/holdout-run01.log` … `run10.log` against the two new expectations,
offline. A throwaway script is fine; it does not ship.

I have done this and I am telling you the answer so that a disagreement is
visible rather than averaged away: **`:77` scores 10/10 and `:122` scores
1/10** — nine of its ten runs never name a file, and the tenth names the right
one. **If you get different numbers, say so and stop.** One of us is wrong and
it matters which.

Then state what it does **not** tell us: those are the answers the old
wording produced, and `:122`'s single pass means that question's score will
vary between runs. It is the first non-zero score variance this project has
measured and it is information, not noise.

## Tests that must fail first

| Test | Where | Must fail before, pass after |
| --- | --- | --- |
| **no question is scored on tool choice alone** | `tests/test_holdout_questions.py` | replaces `test_only_the_comparisons_are_scored_on_tool_choice_alone` at `:29`, which asserts today's defect and must be **deleted, not weakened** |
| each comparison's expectation is the longer file by `_lines()`, not a constant | `tests/test_holdout_questions.py` | new behaviour |
| a reversed answer is graded correct — the hole, asserted | `tests/test_holdout_questions.py` | new, and it must **pass**: it records what is true, not what we want |

`tests/test_holdout_questions.py:49` — no expectation contains a comma —
still applies unchanged, because every expectation is still a plain string.

## What this part is not

**No new type.** `judge()` and `Question` are untouched. If you find yourself
editing `scripts/eval_scoring.py` in this part, stop: the probe removed the
reason to. The file stays in the touchable list only for Part 3's record
helper, if you choose to put it there.

---

# Part 2 — a search subject that is only about itself

Retire the question at `scripts/holdout_eval.py:91` **and** the identical one
at `scripts/session_eval.py:84`. Both go, or the next drift measurement runs a
question we have declared unfit.

Replace it with a `search_text` question over a **new file in
`eval-fixture/`** holding one distinctive marker.

Requirements, all of them measurable without a model:

1. **The marker occurs in exactly one reachable file** — the new subject.
   Measure it with `reachable_files()` from `tests/test_eval_workspace.py`,
   not with `grep` over the working tree: the tree is not what the agent sees.
   One carrier, against the five the old question had.
2. **The expectation occurs in zero reachable files.** Make the expectation
   the subject's own filename, so what makes the answer right is *which file
   the marker is in* — the thing a search tool is for. Verify that the
   filename string appears in no file's contents, including `README.md`. If it
   does, change the name rather than adding a carrier entry.
3. **Both are at least 12 characters.** Below `_DISTINCTIVE`
   (`tests/test_eval_workspace.py:77`) the leak invariant does not cover them,
   and an uncovered expectation is one that can be leaked back in later.
4. **Contamination count zero**, by brief 07's scan over the three `.jsonl`
   files at `G:/OmniAgent/datasets/2026-10-10-merged/` — 2,215 examples.
   Report the count for the marker and for the filename. **A non-zero count
   gets changed, not explained.**
5. **The new file is honest about what it is**, like the six already in that
   directory. This is a public repository. It says in its own words that it
   exists to give the evaluation a subject whose contents do not move. No
   filler, no invented purpose.
6. **It renders intact** under `MAX_INTACT_READ_CHARS` (`tools.py:474`,
   2,400 on the rendered text, which carries a header and a line number per
   line). The six existing files render at 173–202 characters; stay in that
   range.
7. **`eval-fixture` stays out of `ANSWER_KEY`.** Sealing it is how `docs/`
   disqualified itself as a subject.

**Keep `EXPECTATION_CARRIERS["agent.budget.exhausted"]` and
`test_the_budget_expectation_is_not_unique_to_its_subject`.** The log event
still exists and the five-carrier spread is a measured fact about this
codebase, not a fact about a question. Retiring the question does not make the
record false. Say in a comment that the entry now documents the codebase
rather than guarding a live expectation.

## Tests that must fail first

| Test | Where | Must fail before, pass after |
| --- | --- | --- |
| the new marker has exactly one reachable carrier | `tests/test_eval_workspace.py` | new behaviour |
| the new expectation has zero reachable carriers | `tests/test_eval_workspace.py` | new behaviour |

Write these as assertions over `reachable_files()`, in the same style as the
tests already there: assert the property, not a hand-written list of files.

---

# Part 3 — record the steps now so the derailment axis needs no new runs

`scripts/session_eval.py` already keeps `Outcome.steps` per question.
`scripts/holdout_eval.py` keeps only a total, so the per-question step counts
behind the table above had to be scraped out of printed logs.

Add a per-question record to `holdout_eval`, appended to
`data/holdout-runs.jsonl` — gitignored, beside `data/session-runs.jsonl`, and
tagged with the short commit the way `session_eval.commit()` does, so runs of
different code are not pooled.

**Each record carries the question's index, the tools called in order, the
step count, and the verdict's booleans. It carries neither the question text
nor any expectation.** Two reasons, and the second is the one that matters:
the agent must not be able to read its own answer key out of a run artifact —
that is the leak `scripts/eval_workspace.py` exists to close — and an index is
enough to join back to the bank.

Keep it testable without a model: build the record in a **pure function** that
takes the index, the verdict, the step count and the tool list and returns a
`dict`, and test that function directly. **Do not add a client parameter to
`evaluate()` for this.** A pure function is why `eval_scoring.py` can be
checked in milliseconds instead of minutes.

Measure and report whether `data/holdout-runs.jsonl` is reachable under the
seal. `data` is in `LISTING_ONLY`, so the expected answer is no — but it is
the kind of thing that has been wrong before, and the record carries no
secrets either way.

## Test that must fail first

| Test | Where |
| --- | --- |
| the record holds index, tools, steps and verdict booleans, and holds neither question text nor expectation | `tests/test_holdout_questions.py` or a new `tests/test_holdout_record.py` — your call |

---

# Mutations that must go red

Restore from a scratchpad copy, **never `git checkout --` alone**.

**Md, Me and Mf need files this brief otherwise forbids, and that is
permitted for the mutation only.** Md and Mf create a throwaway file under
`eval-fixture/` and delete it before any commit. Me edits **your new subject
file**, not one of the six that were already there, and restores it from the
scratchpad copy. Nothing from a mutation reaches a commit. Three of my briefs
have put a mutation behind a forbidden file and made the engineer invent a
substitute; this is the one place where the lists do not apply, and it is
named here rather than left to you.

| # | Mutation | Must go red |
| --- | --- | --- |
| Ma | Hardcode a comparison's expectation as a literal filename instead of computing it | the `_lines()` test from Part 1. Then add 300 lines to the shorter file in a scratchpad copy of the tree and confirm the **computed** expectation flips while the literal one does not |
| Mb | Swap the winner and the loser in one comparison's expectation | that question's retro-score over the ten recorded logs flips from 10/10 to 0/10. **Report both numbers** |
| Mc | Make a comparison's expectation shorter than `_DISTINCTIVE` (12) | the leak invariant stops covering it, silently. Nothing goes red — **that is the point**: find out what the invariant does and does not see, and say so in the report. Restore the real expectation afterwards |
| Md | Put the new marker into a second file in `eval-fixture/` | the one-carrier test from Part 2 |
| Me | Write the new expectation into a fixture file's **contents** | `test_no_unreviewed_file_holds_an_expected_answer`. Delete the string afterwards; do not commit it |
| Mf | Add a seventh file to `eval-fixture/` | the listing question's expectation **does not move** (brief 08's Sc, re-run because this brief adds a file to that directory) |
| Mg | Put a question text into the Part 3 record | the record test |

**Mc is the one to take seriously, and it is the only mutation here that goes
green rather than red.** A test asserting "this is refused" proves nothing if
several independent guards would refuse it, and the mirror of that is a test
that passes because it is checking nothing. Mc is how you find out which one
the leak invariant is. Report what you saw, not what you expected.

# The three gates

```
.venv\Scripts\python.exe -m ruff check .
.venv\Scripts\python.exe -m mypy
.venv\Scripts\python.exe -m pytest
```

Full path, **no `-q` of your own** (`pyproject.toml:168` sets it; a second one
deletes the summary line). Baseline **636 passed**, mypy clean over **43**
files. This brief adds tests and one reachable file, so both numbers move:
say what they moved to and why. A move you cannot explain is a finding.

# Files you may touch

- `scripts/eval_scoring.py`
- `scripts/holdout_eval.py`
- `scripts/session_eval.py`
- `tests/test_eval_scoring.py`
- `tests/test_holdout_questions.py`
- `tests/test_eval_workspace.py`
- `tests/test_session_eval.py` — only if Part 2's replacement breaks it
- a new test file if you want one
- `eval-fixture/<one new file>` — **one file, no subdirectory.** A second
  subdirectory makes brief 08's listing question ambiguous
- `.gitignore` — only if `data/holdout-runs.jsonl` is not already covered

# Files you may not touch

`agent.py` · `tools.py` · `sandbox.py` · `scripts/eval_workspace.py` ·
`scripts/collect_dataset.py` · `scripts/build_notebook.py` ·
`README.md` · `questions/**` · `models/**` · `omniagent-core/**` ·
`.github/workflows/**` · `NEXT_CHAT.md` · `docs/` except your `## Result` ·
the six existing files under `eval-fixture/` · anything on
`core-offline-runtime`.

`data/**` is **read-only** for this brief: read the ten run logs, write
nothing into it by hand. Both evaluations append to it when they run, which is
theirs to do and not yours.

Every mutation in the table above is inside the touchable set — I have checked
that this time. If a file is in neither list, ask rather than decide.

# `docs/` and the no-quoting rule, stated honestly

`docs` is in `ANSWER_KEY`, so this file is sealed and quoting a question here
would **not** fail the invariant. Briefs 07 and 08 told two engineers it
would, and that was wrong.

Keep the discipline anyway, as defence in depth: if `docs` ever leaves
`ANSWER_KEY`, every brief in it becomes a leak at once. So in your `## Result`,
refer to questions by line number and **do not quote the new marker, the new
filename, or any question text.**

The rule that is not defence in depth, and that a test will enforce:
**nothing may be written into `eval-fixture/` except the one new subject file
this brief asks for.** That directory is reachable by design.

# The split — who does which half

You cannot run an evaluation: your sandbox returns `WinError 10013` on
`localhost`, confirmed twice on 2026-10-24 with Ollama up and answering for
the manager. **Nothing in this brief needs one.** The retro-scoring reads logs
already on disk, and every check above is static.

| Half | Owner |
| --- | --- |
| all three parts, the tests, Ma–Mg, the retro-score over the ten logs, the three gates, the commits | **you** |
| the prediction written before any run, the ten new runs with variance, the new baseline, and whether the two comparisons move the score for the model's reasons or the instrument's | **the project manager** |

**Do not report a measurement you did not produce.** Say in `## Result` that
the ten runs are outstanding and are the manager's.

# The one thing that would make this wrong

**Closing the comparison hole.** It is open on purpose and the reasons are
measured, not argued: forbidding the loser's name fails a correct answer,
demanding a bare filename destroys the question, and matching phrases grades
characters. If you see a way to close it, **report it rather than building
it** — the first version of this brief closed it and cost a question that
works. A hole that is written down and asserted by a test is a known
limitation; a hole that is patched with phrase matching is the defect this
brief exists to remove.

The second way: **changing a question text to make it gradeable.** The probe
below is three runs of evidence that this agent's behaviour is sensitive to
the wording in ways nobody predicted. Part 1 touches expectations only. If a
question text has to change for the instrument's convenience, that is a brief
of its own with its own ten runs, not a line in this one.

The third way: **an expectation the leak invariant cannot see.** Mc is how
you find out what it sees. An invariant that passes because it is checking
nothing is worse than no invariant, because the figures quoted from it read
as checked.

# Commit

Three steps, one commit each, gates green at every step:

```
git add scripts/holdout_eval.py tests/test_holdout_questions.py
git commit -m "eval: the two comparisons get an expectation, and the hole gets a test"

git add eval-fixture scripts/holdout_eval.py scripts/session_eval.py tests/test_eval_workspace.py tests/test_session_eval.py
git commit -m "eval: a search subject whose answer is only in the subject"

git add scripts/holdout_eval.py tests/ .gitignore
git commit -m "measure: one record per question, so a derailment can be scored later"
```

Then **commit this brief file with your `## Result` appended**:

```
git add docs/pm/brief-10-no-question-is-scored-on-nothing.md
git commit -m "docs: brief 10 result -- the instrument no longer scores a question on nothing"
```

**Do not run a bare `git push`** — two remotes, and `main` tracks the one this
work does not belong to. Name it: `git push origin main`.

# The prediction, written before any run — 2026-10-26, HEAD `4c33c2f`

Written **before the engineer has started**, which is earlier than the
standard asks for and is the point: a prediction written after the code exists
is a story told about a number. Ollama has not been restarted and no run of
any kind has been made since this brief was issued.

Current baseline to beat: **`omniagent-v2`, 11/16, zero variance over ten
runs, 2026-10-24**, failing set byte-identical every run.

## What the denominator does, and the misreading I am pre-committing against

| Change | Denominator |
| --- | --- |
| today | 16 |
| the `'budget'` question retired | 15 |
| its replacement added | 16 |
| the comparison at `:77` becomes checkable | 17 |
| the follow-up at `:122` becomes checkable | 18 |

**The new figure will look like a regression and will not be one.** 11/16 is
69%; anything under 12.4/18 reads as worse while meaning nothing of the kind.
I am writing this down now so that neither of us gets to discover it
afterwards.

## The five predictions, each falsifiable

**P1 — the comparison at `:77` scores 0/10 under Part 1 as written.** It is
answered correctly in substance in all ten recorded runs, and every one of
those answers names both files. The new rule forbids the loser's name, so the
question passes only if the model obeys the new "name the file only"
instruction. This model drops out of formats it was explicitly taught
(`agent.py:207-218`), so I do not expect it to obey a format instruction it
has never seen. **If P1 is right, a question that is right ten times out of
ten will report zero.**

**P2 — the follow-up at `:122` scores 0/10.** Six of ten runs exhaust the step
budget and three invent a tool failure; nothing in this brief changes the
agent, so I expect the same behaviour and the same answers. The one run that
named the right file would be graded wrong under Part 1 as written, because it
names both.

**P3 — the replacement search question scores 9/10 or 10/10.** Brief 08's
replacement went 10/10 and this one is an easier shape: one marker, one
carrier, `search_text` is the obvious tool. **The failure mode, if there is
one, is the agent answering with the matched line instead of the filename** —
that is what the retired question trained it to do, and it is the specific
thing I will look for in run 1.

**P4 — the total is 12/18, with zero variance.** 11 correct today, minus the
`'budget'` question which was a guaranteed miss, plus the replacement (P3),
plus nothing from `:77` and `:122` (P1, P2). Zero variance survives because
every one of those outcomes is the same in all ten recorded runs.

**P5 — the wall clock stays unstable and the step count moves.** The 237 s to
1,508 s spread is a property of the machine, not the question set, so I expect
it to persist. The step total will not stay at 57: two questions are reworded
and one is replaced.

**What would make me wrong in an interesting way:** P1 failing because the
model *does* obey the format instruction. That would say something about this
fine-tune that the nine briefs so far have not — and it is cheap to find out,
which is the next section.

# A defect in this brief, found by writing the prediction

P1 is a prediction that **my own rule turns a question the agent answers
correctly into a zero.** That is worth stopping for.

`scripts/holdout_eval.py:7-12` states the principle this project was built on:
tool choice and correctness are scored separately, because "dumping a whole
file to count its lines is a wrong answer that happens to be right", and
rolling two things into one figure hides exactly that. `scripts/eval_scoring.py:76-80`
says the same again.

**Part 1 as written breaks that principle.** A comparison question graded on
`none_of` plus a format instruction reports one bit for two different
capabilities — can it compare, and will it obey an answer format. When that
bit is zero we cannot say which failed. That is the defect the whole project
is organised against, and I wrote it into the brief myself.

The honest alternative is weaker in a way I can state exactly:

| | **A1 — as issued** | **A2 — the winner's name alone** |
| --- | --- | --- |
| the rule | `all_of=(winner,)`, `none_of=(loser,)`, question text demands the filename only | `expect=winner`, a plain substring, question text unchanged |
| needs the `Expectation` type | yes | **no — Part 1 collapses to giving two questions an ordinary expectation** |
| `:77` on the recorded answers | 0/10 | 10/10 |
| `:122` on the recorded answers | 0/10 | **1/10** — run 07 names the right file |
| the hole | closed | **open: "Y is longer than X" would be graded right.** Never observed in ten runs, and it is why the original author left the question unscored |
| axes | comparison and instruction-following rolled into one bit | separate, as the project requires |
| variance | zero preserved | **the first non-zero score variance this project has measured**, 12 or 13 depending on the run |

A2's non-zero variance is not a flaw in A2. It is information A1 would hide:
the derailment at `:122` is *not* fully deterministic, and today's "byte-identical
every run" claim is true of the answers, not of the behaviour behind them.

**This is a decision about what the instrument is for, so it goes to the owner
rather than being settled here.** It is recorded at the top of this file as a
hold on Part 1. Parts 2 and 3 stand either way.

## The probe that would settle P1 for about a minute of model time

Ask the reworded `:77` question once, on its own, under the sealed workspace,
and read whether the model answers with the filename alone. One question, not
an evaluation — minutes, not the 40-to-250 of a full run. **The prediction
above is written and committed first, so the probe can only confirm or refute
it, not inform it.** This is the manager's half and needs Ollama restarted.

# The probe, and what it did to the prediction — 2026-10-26, HEAD `58abbed`

Ollama was already up — `10061` would have meant otherwise — and
`omniagent-v2:latest` was loaded. **It had not been restarted today, which
contradicts the handoff's "Ollama does not survive across days". Recorded as
measured, not as a correction to the rule: one day is not a pattern.**

Three runs of one question, `max_steps=8`, `temperature=0`, sealed workspace,
fresh agent per run — the arrangement `holdout_eval` uses for this question.
Three runs is a probe to choose a design, **not a measurement**; the standard
is ten and this is not it.

## The reworded question, as Part 1 originally specified it

| Run | Steps | Answer |
| --- | --- | --- |
| 1 | 9 | "I ran out of reasoning steps before reaching an answer." |
| 2 | 9 | "I ran out of reasoning steps before reaching an answer." |
| 3 | 9 | "I ran out of reasoning steps before reaching an answer." |

Identical tool sequence in all three:
`list_directory, search_text, search_text, read_file, file_info, read_file, list_directory, search_text`.

## The control — the original wording, same harness, same session

Taken from the bank rather than retyped, so the control cannot drift from the
question the ten recorded runs asked.

| Run | Steps | Answer |
| --- | --- | --- |
| 1 | 9 | "tests/test_sandbox.py has more lines than tests/test_config.py." |
| 2 | 9 | "tests/test_sandbox.py has more lines than tests/test_config.py." |
| 3 | 9 | "tests/test_sandbox.py has more lines than tests/test_config.py." |

**Byte-identical to the answer in all ten recorded runs.** The harness is
sound, so the derailment belongs to the rewording.

## What this settles

**One sentence of added instruction turned a question the agent answers
correctly into one it cannot finish.** Not a format it got wrong — a question
it never reaches the end of. The first version of Part 1 would have cost a
working question and reported it as the model's failure.

A1 is dead. Part 1 is rewritten above as A2, and the hole stays open with a
test to record it.

## P1 was right in its verdict and wrong in its mechanism

I predicted 0/10 **because the model would answer with a sentence naming both
files**. It does not get that far. The reasoning was wrong and the number
would have been right, which is the kind of correctness that teaches nothing
— and I would never have known if the prediction had not been written down
first.

## One thing the control turned up that I was not looking for

The recorded runs of 2026-10-24 show this question answered in **7 steps with
6 tool calls**. Today, same question, same model, same arrangement: **9 steps
with 8 tool calls**, the first six identical and three `search_text` calls on
the end instead of one. The answer is unchanged.

So the agent now spends two more steps reaching the same answer than it did
two days ago. Candidates, none of them established: the `search_text` pruning
in `0c04ffa`, the files added to the tree since (`eval-fixture/`'s six,
`tests/test_search_text_pruning.py`), or both. **This is three runs of one
question and it is not a finding yet.** It is a reason to expect the step
total to move, and a reason not to treat the 2026-10-24 figures as the
current behaviour of anything but the score.

## The prediction, revised — and the revision is itself written before the run

P1 and P2 stood on A1 and A1 is gone. Restating for A2, before any further
run:

- **P1′ — `:77` scores 10/10.** It is 3/3 in today's control and 10/10 in the
  recorded logs, and nothing in Part 1 touches its text.
- **P2′ — `:122` scores 0/10 or 1/10, and is the question that breaks zero
  variance.** Nine of the recorded ten never name a file; one does.
- **P3 unchanged** — the replacement search question scores 9/10 or 10/10,
  and if it fails it fails by quoting the matched line instead of the
  filename.
- **P4′ — the total is 13/18, varying to 14/18.** 11 today, minus the
  `'budget'` miss, plus the replacement, plus `:77`, plus `:122` at zero or
  one. **Not 12/18**, which is what I predicted under A1.
- **P5′ — the step total moves off 57 and I no longer expect to predict it.**
  The control says two steps moved on one question without anyone changing
  the agent.

**And one new one. P6 — the 11/16 baseline will not reproduce at HEAD.** If
two steps moved on a question nobody touched, the set is not the set that was
measured on 2026-10-24. My ten runs will therefore produce a fresh baseline
rather than a comparison, and I expect at least one of the other seventeen
questions to have moved for reasons that are not this brief. **If 11 of the
old 16 still pass, exactly, P6 is wrong and that is worth knowing too.**

# The P6 run did not happen, and the reason is mine — 2026-10-26

I started a full evaluation to test P6 — whether the 11/16 baseline still
reproduces — and **it tested nothing, because the engineer was working in this
same checkout at the time.**

| Time | What |
| --- | --- |
| 06:24:44 | `0bc25b6`, the commit I intended to measure |
| 06:34:28 | `2b740f5` — the engineer lands Part 1 |
| 06:38:36 | `60183b8` — the engineer lands Part 2 |
| ~06:41:40 | **my run starts**, importing whatever was on disk |
| 06:45:48 | it finishes, 248 s |

The bank it asked was the **new** one. P6 needed the old one, which had been
gone for three minutes when the process started. And `scripts/holdout_eval.py`
had uncommitted Part 3 edits in it throughout, so the code that ran matches no
commit and cannot be reproduced.

**So the run is void as a measurement.** Not "mostly fine" — void. Any figure
taken from it is a figure nobody can re-derive.

## What it is worth as a sighting, and nothing more

It asked the new bank once and scored **13/18**, with the comparison at index
8 passing both axes, the replacement search question at index 10 passing both,
and the follow-up at index 19 wrong. That is P1′, P3, P2′ and P4′ exactly.

**I am not banking it.** One run from an unversioned tree that matches a
prediction is the most tempting kind of evidence to over-read, and the ten
runs happen after the engineer lands or they do not happen.

## The discipline this broke, now a standing rule

I measured in a checkout another session was writing to, and I did not run
`git status` first. The project's own standard is that `git log` is the truth;
I never asked it.

**Before any measurement: record HEAD and confirm the working tree is clean.
After it: record HEAD again and confirm it has not moved. If either check
fails, the run is void and gets thrown away rather than interpreted.** A
measurement whose subject changed under it is not a weak measurement, it is
not one at all.

The deeper fix is that a measuring session and a writing session should not
share a checkout. That is a change to how we run the roles, and it goes to the
owner rather than being decided here.

## Two things worth keeping from the void run

- **The listing question at index 11 took 2 steps where all ten recorded runs
  took 3.** Part 2 added a file to `eval-fixture/`, and brief 08's Sc proved
  the *expectation* does not move when that happens. It did not say the
  *behaviour* would not. Worth a look when the real runs are read.
- **The retired question was never measuring `search_text` at all.** In all
  ten recorded runs it called `read_file` and `file_info`, never
  `search_text`, and it was the bank's only `search_text` question. So the
  instrument had **no coverage of that tool whatsoever**. Part 2 is not a
  repair of a broken expectation; it restores a missing axis. The void run is
  the first time `search_text` has been exercised by this evaluation — which
  is a reason to want the real ten runs, not a substitute for them.

## Result

<!-- Engineer: append here. The retro-score of the ten recorded logs under the
new rules for both comparisons, with what it does not tell us; the carrier
counts for the new marker and the new filename; the contamination counts; the
rendered length of the new fixture file; Ma-Mg each with the test that went
red; the three gate results with the new test count explained; whether
data/holdout-runs.jsonl is reachable; the commit hashes; and anything you
refuse to claim -- including that the ten runs are the manager's and are
outstanding. Quote neither the marker, the filename, nor any question text. -->

### ผลดำเนินการ

- จุดเริ่มงานจริงคือ `main` ที่ `0bc25b6` ไม่ใช่ baseline `dbfc39e` ที่ระบุในส่วนประวัติของ brief; ระหว่าง Part 2 กับ Part 3 มี commit บันทึกของ project manager `7ba3fbc` เพิ่มเข้ามา
- Part 1 เพิ่ม expectation ที่คำนวณตอน import จาก `_lines()` ให้คำถามเปรียบเทียบที่ `scripts/holdout_eval.py:102` และ `:145` โดยคงข้อความคำถามและ `judge()` ไว้ตามเดิม ลบ test ที่ตรึง defect แล้วแทนด้วย `test_no_question_is_scored_on_tool_choice_alone`, `test_each_comparison_expectation_is_computed_from_the_longer_file` และ `test_a_reversed_comparison_answer_still_grades_correct`. test ใหม่นี้บันทึก false positive ที่ตั้งใจเปิดไว้; ไม่ได้ปิดช่องด้วยการเปลี่ยนเกณฑ์
- Retro-score จาก log เดิมสิบไฟล์ได้ `:102 = 10/10` และ `:145 = 1/10` ตามกติกาใหม่ ผลนี้เป็นคะแนนของคำตอบจาก wording เดิมเท่านั้น ไม่ใช่การวัด wording หรือ behavior ใหม่; คะแนนหนึ่งครั้งของ `:145` แสดงว่าผลมี variance ระหว่าง runs
- Part 2 แทนคำถามเดิมที่ holdout และ session ด้วยคำถามค้นหาที่ `scripts/holdout_eval.py:116`; expectation หา path จากไฟล์ที่มี marker โดยไม่เก็บชื่อไฟล์เป็น literal ใน source หรือ test. `reachable_files()` พบ marker ในไฟล์เดียว และพบ expectation ในศูนย์ไฟล์. ตรวจเนื้อหา repository แล้วไม่พบ string ของชื่อไฟล์; ผลอ่านจริงยาว 178 ตัวอักษร. ไฟล์ใหม่นี้อธิบายจุดประสงค์ของ fixture, อยู่ในช่วง 173–202 ตัวอักษรของ fixture เดิม, และ `eval-fixture/` ไม่อยู่ใน `ANSWER_KEY`
- สแกน JSONL ทั้งสามไฟล์ของชุดฝึก รวม 2,215 examples (1,404 + 658 + 153): contamination เป็นศูนย์ทั้ง marker และชื่อไฟล์. คง `EXPECTATION_CARRIERS["agent.budget.exhausted"]` กับ `test_the_budget_expectation_is_not_unique_to_its_subject` ไว้ พร้อมระบุว่าตอนนี้บันทึกข้อเท็จจริงของ codebase ไม่ได้ปกป้อง expectation ของคำถามที่เลิกใช้แล้ว
- Part 3 เพิ่ม `question_record()` แบบ pure function; record มี index แบบ zero-based, ลำดับ tools, steps และ boolean ทั้งหกของ verdict. record ที่ append เพิ่ม short commit และ model แต่ไม่เก็บ question text หรือ expectation. test `test_question_record_has_only_index_tools_steps_and_verdict_booleans` ตรวจ schema โดยตรง. `data/holdout-runs.jsonl` ถูก ignore ด้วยกฎ `data/` ใน `.gitignore` และอ่านไม่ได้ผ่าน sealed workspace เพราะ `data` เป็น `LISTING_ONLY`; ผมไม่ได้เขียนข้อมูลลง `data/` หรือรัน evaluation

### Mutations Ma–Mg

- **Ma:** ใน scratchpad copy เปลี่ยน expectation เป็น literal แล้วเพิ่ม 300 บรรทัดในไฟล์ที่สั้นกว่า; `test_each_comparison_expectation_is_computed_from_the_longer_file` ล้ม. ค่าที่คำนวณเปลี่ยนตามไฟล์ที่โตขึ้น ส่วน literal ไม่เปลี่ยน
- **Mb:** สลับผู้ชนะ/ผู้แพ้แล้ว test เดียวกันล้ม. Retro-score เป็น 10/10 ก่อนสลับ และยังเป็น 10/10 หลังสลับ เพราะคำตอบที่บันทึกไว้ทั้งสิบครั้งมีชื่อไฟล์ทั้งสอง. นี่ไม่ใช่ผล 0/10 ตามที่ brief คาดไว้ แต่เป็นผลที่สังเกตได้จริงและยืนยัน false-positive mode ที่ test ใหม่บันทึกไว้
- **Mc:** ลด expectation เหลือ 10 ตัวอักษร. `test_no_unreviewed_file_holds_an_expected_answer` ยังผ่าน เพราะ `held_out_expectations()` กรองค่าที่สั้นกว่า `_DISTINCTIVE` (12) ออก; invariant จึงไม่ได้ตรวจค่านั้นเลย. ไม่มี test ล้ม — นี่คือช่องว่างที่ mutation นี้ตั้งใจเปิดเผย
- **Md:** เพิ่ม carrier ชั่วคราวตัวที่สอง; `test_the_search_marker_has_one_reachable_carrier` ล้มด้วย carrier 2 แห่ง. ลบไฟล์ชั่วคราวแล้ว
- **Me:** ใส่ expectation ลงในเนื้อหาของ subject ใหม่; `test_no_unreviewed_file_holds_an_expected_answer` ล้ม. คืน subject จาก scratchpad copy แล้วตรวจ hash ตรงกับต้นฉบับ
- **Mf:** เพิ่มไฟล์ชั่วคราวใน fixture; `test_eval_fixture_contains_only_the_six_existing_files_and_new_subject` ล้มตามกฎ inventory. การเรียก `list_directory()` เห็น entry เพิ่ม แต่ expectation ของคำถาม listing ยังคงเดิม. ลบไฟล์ชั่วคราวแล้ว
- **Mg:** เพิ่ม question field ลงใน record; `test_question_record_has_only_index_tools_steps_and_verdict_booleans` ล้ม. คืน source จาก scratchpad copy

### Gates และ commits

| Part | Ruff | Mypy | Pytest |
| --- | --- | --- | --- |
| 1 | ผ่าน | 43 source files | 638 passed |
| 2 | ผ่าน | 43 source files | 641 passed |
| 3 | ผ่าน | 44 source files | 642 passed |

จำนวน tests เพิ่มจาก 636 เป็น 642 (+2 ใน Part 1, +3 ใน Part 2, +1 ใน Part 3); mypy เพิ่มจาก 43 เป็น 44 เพราะ Part 3 เพิ่ม test module ใหม่. การรัน `python -m pytest` ตามปกติครั้งแรกสร้าง temp directory ใน AppData ไม่ได้เพราะข้อจำกัดสิทธิ์ของ sandbox; รันซ้ำด้วย `--basetemp` ภายใน workspace แล้วได้ผลเต็มตามตาราง โดยใช้ executable path เต็มและไม่เพิ่ม `-q`.

- Part 1: `2b740f5`
- Part 2: `60183b8`
- Part 3: `2ee2173`

ผมไม่ได้รัน model, ไม่ได้เขียน prediction หรือ baseline ใหม่ และไม่อ้างตัวเลขจากการรันใด ๆ ของ project manager. ตามบันทึกที่เพิ่มใน brief การรันก่อนหน้าของ manager ถูกตัดเป็น void; การวัดใหม่สิบ runs และ baseline ยังเป็นงานของ manager และยัง outstanding.

---

# PM verification of the design half — 2026-10-26, `06b93c7`

**No defects found in the work. One defect found in my brief, by the
engineer.** Everything below was re-derived rather than read.

Tree clean before and after, HEAD unmoved at `06b93c7` — the rule from the
void run, applied to its first verification.

| Claim | Re-checked by the manager |
| --- | --- |
| three gates | ruff clean · mypy **44** files · **642 passed** |
| nothing scored on nothing | **19 questions, 18 checkable, zero scored on neither an answer nor honesty** |
| expectations computed, not written | both resolve from the tree: the longer of each pair |
| retro-score | **10/10 and 1/10** — identical to the figures I derived independently before issuing |
| marker carriers | **1** |
| expectation carriers | **0** |
| contamination | **0 and 0** over 2,215 examples (1,404 + 658 + 153) |
| the subject reads intact | 100 raw characters, inside the existing fixture range |
| reachable files | 309 → **311**: the new subject and `tests/test_holdout_record.py` |

Scope held exactly. Three commits, nothing outside the touchable list, and
the report committed with them.

## The engineer was right and my brief was wrong — Mb

I wrote that swapping the winner and the loser would flip the retro-score
from 10/10 to **0/10**. It stays at **10/10**, and I have confirmed it:

```
right    answer -> correct=True
REVERSED answer -> correct=True
```

Both recorded answers name both files, so an expectation of either one is
satisfied. **The answer axis on the comparison cannot tell a right answer
from a reversed one at all.** I had called this a hole that "has never been
observed"; it is not a hole that waits for an unlucky answer, it is a hole
that is open on every answer the model actually gives.

`test_a_reversed_comparison_answer_still_grades_correct` asserts exactly
this, which is the right way to hold it: the next person to touch the rule
will see the test before they see my reasoning.

### What that means for the number we are about to measure

**The point each comparison contributes is nearly free.** It is earned by
naming a file, not by comparing two. Both comparison questions have this
property, including the follow-up, whose single recorded pass names both
files too.

So, stated exactly: **open item 2 is closed** — a derailment is no longer
recorded as "not wrong", which was the whole purpose — and a **new, smaller
item takes its place: the agent's ability to compare two files is still not
measured by anything.** Every way of measuring it that we have examined costs
more than it is worth; that is a decision for the owner, not a patch.

## Two judgement calls the engineer made that the brief did not ask for

- **`test_eval_fixture_contains_only_the_six_existing_files_and_new_subject`**
  pins the fixture directory's inventory. Brief 08 said a human adding a
  seventh file later is normal; this test makes that a failure. I am keeping
  it. It is the cheapest guard against the thing brief 08 actually feared —
  something writing into the one directory the agent can read — and a human
  who means to add a file will see the test and update it deliberately.
- **`_search_subject()` derives the subject's filename from the marker at
  import time** rather than storing it, so the expectation cannot drift from
  the file. Stronger than asked for. Its one fragility is `sorted(...)[0]` if
  a second file ever carries the marker, which is exactly what Md's test
  prevents.

## What is outstanding, and it is mine

The ten runs and the new baseline. P1′ to P6 are written and committed at
`58abbed` and `7ba3fbc` and are not revised again.

---

# The ten runs — settled, 2026-10-26, HEAD `43aba72`

Tree clean and HEAD unchanged across all ten, recorded by the command itself.
Ten runs sequentially, never two at once.

```
run 01  13/18  6/7  5/5  1/1  54 steps  198s
run 02  14/18  6/7  5/5  1/1  54 steps  205s
run 03  14/18  6/7  5/5  1/1  54 steps  192s
run 04  14/18  6/7  5/5  1/1  54 steps  194s
run 05  14/18  6/7  5/5  1/1  54 steps  194s
run 06  13/18  6/7  5/5  1/1  54 steps  206s
run 07  13/18  6/7  5/5  1/1  54 steps  198s
run 08  14/18  6/7  5/5  1/1  54 steps  204s
run 09  14/18  6/7  5/5  1/1  54 steps  202s
run 10  13/18  6/7  5/5  1/1  54 steps  200s
```

All ten, not a mean.

## The new baseline

**`omniagent-v2`: 13/18 four times and 14/18 six times, over ten runs,
2026-10-26.** Tool pick 6/7, follow-up 5/5, honesty 1/1, **54 steps in every
run**.

This is **not** comparable with 11/16. Two questions became checkable and one
was replaced; the denominator is a different denominator.

## The first non-zero score variance this project has measured

**Exactly one question varies, and it is the one P2′ named.** The failing set
is one of two, and nothing else moves:

| Failing set | Runs |
| --- | --- |
| 4, 9, 16, 18 | 6 |
| 4, 9, 16, 18, **19** | 4 |

Everything else is identical across ten runs, marks and steps alike.

## The prediction, scored

| | Claim | Verdict |
| --- | --- | --- |
| **P1′** | the comparison at index 8 scores 10/10 | **right** — 10/10, both axes |
| **P2′** | index 19 scores 0/10 or 1/10 and is what breaks zero variance | **half right, and badly wrong on the number.** It is the question that varies. It scores **6/10**, not 0 or 1 |
| **P3** | the replacement search question scores 9/10 or 10/10 | **right** — 10/10, both axes, and the failure mode I named did not appear |
| **P4′** | the total is 13/18 varying to 14/18 | **right, exactly** |
| **P5′** | the step total moves off 57 | **right** — 54, and identical in all ten |
| **P6** | the 11/16 baseline will not reproduce at HEAD | **wrong** |

### P6 is wrong, and being wrong settles something better

**All fourteen untouched questions reproduce byte-identically — same marks,
same step counts — against the ten runs of 2026-10-24.** Only the three
questions this brief changed moved, plus index 11's step count, which went
3 → 2 because Part 2 added a file to the directory it lists.

So the instrument is stable and the old figures were sound. **The 9-step
reading in my own probe was an artifact of asking one question alone instead
of inside the evaluation** — in the full run that question takes 6 steps, and
took 7 before the fixture file was added. A single-question probe does not
reproduce the evaluation's conditions, and I built P6 on one.

### P2′ is the interesting miss

That question's text did not change and its step count did not change — 9 in
all twenty runs, old and new. What changed is what it says at the end:

| Answer | Then (10-24) | Now |
| --- | --- | --- |
| ran out of reasoning steps | 6 | 3 |
| a false hedge — "cannot locate the files", for files it had just read | 3 | 1 |
| names the longer file | 1 | **6** |

Same question, same agent, same step budget, a different distribution. I
cannot attribute it. The tree gained a fixture file and the sessions before it
changed, and either could matter; so could the model simply being
non-deterministic at temperature 0 on a 4 GB card, which this project has
already measured.

**What it does establish: the derailment is not deterministic, and the ten
runs of 2026-10-24 reported it as though it were.** The old instrument scored
it `no check` every time, so nothing could have shown this.

## What the six passes actually contain

Five of the six say the longer file is longer **by 391 lines**, and the two
files differ by 390. The sixth states that file has **513** lines, where
`file_info` reports 512 — the same +1 that brief 09 traced on index 18, in a
different question.

**So the instrument records `ANSWER OK` for answers carrying a wrong number.**
That is the comparison hole working as documented: the expectation is the
filename, and the filename is all it checks. It is not a new defect, it is the
known one with a face on it.

## The 6.4× clock spread did not reproduce

**192 s to 206 s — a 1.07× spread**, against 237 s to 1,508 s on 2026-10-24.
Same machine, same model, ten runs each.

The old measurement was real and is not retracted; what is retracted is the
reading of it. **The spread is not a property of this evaluation.** Whatever
produced 1,508 s was outside it, and anyone sizing a run should use today's
figure and expect it to be wrong when the machine is busy.

## A defect in the new record file, found by reading it

`data/holdout-runs.jsonl` holds **209 records: ten runs at `43aba72` and one
at `60183b8`.** That eleventh run is the void one — the tree was dirty, Part 3
was uncommitted, and the record carries the commit it was at while saying
nothing about the tree.

`scripts/session_eval.py:233` records the commit precisely so runs of
different code are not pooled. **Same commit with a dirty tree defeats it.**
The record needs a field for whether the working tree was clean, and anything
reading the file needs to drop runs where it was not. Small, and it belongs to
whoever next touches that file — logged here, not patched by me.

---

# Option C — the prediction, written before the probe, 2026-10-26 at `42a5377`

The comparison axis is open item 1. Option C is a **closed choice**: the
question names the two files and asks for one of them back, graded
`all_of=(winner,)` with `none_of=(loser,)`. That is different from the
wording the earlier probe killed, which was an open instruction appended to
the question ("answer with the filename only"); a closed choice may behave
differently, and it is minutes to find out.

Tree clean, HEAD `42a5377`, no run of any kind made yet.

**What I expect: C fails, and fails the same way A1 did.** Three runs, and
my prediction is that **none of them replies with exactly one filename.**
Specifically:

1. The last probe showed this agent derails when the question grows a second
   sentence — 3 runs of 3, nine steps, "I ran out of reasoning steps". I
   expect at least two of three runs to do that again.
2. Any run that does answer, I expect to answer in a sentence naming both
   files, because that is what it does in all twenty recorded runs of this
   question.

**What would make me wrong, and it is the point of running it:** one run
replying with a bare filename. That would mean the derailment is about the
*kind* of instruction and not about the length of the question, and C becomes
worth a brief and its own ten runs.

**The decision rule, written before the data so it cannot be fitted to it:**
3 of 3 bare filenames → C goes to a brief. 1 or 2 of 3 → not good enough; a
question that works a third of the time measures the instrument's luck, so
take A. 0 of 3 → A, and the comparison axis is closed as a question we
cannot grade locally.
