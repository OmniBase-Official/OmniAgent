# First honest measurement of the agent with the real local model — PARTIAL

**From:** AI/ML engineer · **2026-11-23** · **Marked partial on purpose.** The
outcomes and the wall clock are measured; the step counts and the tool calls
are not, and §6 says exactly why.

| | |
| --- | --- |
| Branch | `aiml/first-measurement-20261123` |
| Commit measured | **`b164aaa`** (`integration/canonical-20261122`) |
| Tree | `git status --porcelain` empty **before and after**; HEAD `b164aaa` both times — the run is not void |
| Worktree | `D:\code-project\OmniAgent\.scratch\aie-first-measurement` (inside the project path, per the location rule) |
| Model | `omniagent-v2:latest`, digest `05ba6fe701c5cb9d`, 2,950 MB |
| Runtime | Ollama **0.40.16**, started by me after the socket answered `errno 10061` |
| Endpoint | `http://127.0.0.1:11434/v1` — loopback IP literal |
| Limits | `--max-steps 8`, shipped defaults otherwise, one question per process |
| GPU | RTX 3050 Laptop, 4,096 MiB; 0 MiB used and 0 % utilisation before the run, no other `ollama.exe` process |

One model run at a time. No other chair was measuring — verified, not assumed.

## 1. The questions, and the proof they are not from a sealed bank

Five questions, written for this run. Before the first request the runner
checked each against every bank it could import and **aborted the whole run** on
any match:

| Bank | Entries checked | Overlap |
| --- | --- | --- |
| `holdout_eval.SESSIONS_UNDER_TEST` | 19 | none |
| `session_eval.WALK` | 8 | none |
| `collect_dataset.SESSIONS` (training) | 126 | none |
| `grounding_cohort.TASKS` | 2 | none |

No bank failed to import, so all four were really checked. No sealed question
text, expectation or answer key was read or is quoted here.

**Every expectation was derived from the tree at run time** — the line count,
the first line and the file count are computed, never written down.

## 2. The five runs, individually

| # | Question (paraphrased by subject) | Tool it calls for | Answer | Correct | Seconds |
| --- | --- | --- | --- | --- | --- |
| q1 | arithmetic, two operations | `calculate` | 435 | **yes** | 41.8 |
| q2 | line count of `config.py` | `file_info` | 302 | **yes** | 23.9 |
| q3 | first line of `requirements.txt` | `file_info` | exact line, verbatim | **yes** | 11.7 |
| q4 | count of `.py` files in `scripts/` | `list_directory` | **50** | **NO** — the tree holds **12** | 19.2 |
| q5 | a fact no tool can reach | none | declined, said it needs an external lookup | **valid abstention** | 13.9 |

**Score, stated with its denominator: 3 of 4 checkable questions correct, 1
wrong, plus 1 valid abstention out of 1.** Five runs, reported individually,
not averaged. `returncode` 0 on all five; no tool error, no step exhaustion and
no connection error appeared in any output.

**The 41.8 s on q1 is not a property of q1.** It is the first run, so it carries
the cold model load. The four that follow span 11.7–23.9 s, a 2.0× spread. Wall
clock and score are different measurements and this clock figure should be
expected to move on a busy machine.

## 3. The finding that matters — my own grader reported 4 of 4

**[SEVERITY: High] A substring expectation graded the startup banner, not the answer.**

**Location:** the runner's check, `expected.casefold() in whole_output.casefold()`.

The run first reported **`expected_present: true` for all four** checkable
questions, including q4, whose answer is wrong. The mechanism, reproduced:

```
expectation was      : 12
agent answered       : 50
"12" in whole blob   : True
"12" in answer line  : False
  carrier line -> 'endpoint : http://127.0.0.1:11434/v1'
```

**`127.0.0.1` contains `12`.** The expectation matched the loopback literal that
`main.py` prints in its own banner, four lines above the answer.

**Failure scenario.** 1. A chair measures with a short numeric expectation.
2. The grader searches the captured output rather than the answer. 3. The
endpoint banner, the workspace path or a step number supplies the digits.
4. The run reports a pass. The actor is whoever writes the grader; the
precondition is ordinary use, and **a two- or three-character expectation makes
it near-certain** rather than unlucky.

This is the defect the project already recorded twice — *"a substring
expectation grades characters, not answers"* — and it reappeared in the first
measurement taken after the canonical ruling, in a new carrier nobody had
looked at: the program's own banner. The old bank's expectations include bare
line counts, so this is not hypothetical for the instrument either.

**Remediation, and what must go red.** Grade the **answer line only** (the text
after `OmniAgent:`), and refuse an expectation shorter than a stated
distinctiveness threshold instead of scoring it. The test that must fail when
the fix is removed: feed the q4 output with expectation `12` and assert the
verdict is **wrong**; today that assertion fails on the whole-blob grader and
passes on an answer-anchored one. Note that `grounding_cohort.grade()` on the
canonical line is **not** affected — it grades the agent's returned answer
string, with a distractor axis, and never sees a banner.

## 4. What this evidence shows

- The agent at `b164aaa` **runs end to end against the real local model** and
  returns a final answer for all five questions, with no crash, no tool error
  and no step exhaustion.
- It gets **arithmetic and two file-metadata facts right**, including an exact
  verbatim line.
- It **abstained correctly** on the one question no tool can answer, in its own
  words, without inventing a figure.
- It **got a counting question wrong by a wide margin** (50 against 12), which
  is a grounding failure rather than a refusal: it produced a confident number
  that no tool output supports.

## 5. What this evidence does not show

- **Nothing about tool use.** Zero tool names appear in the captured output
  because the Thought/Action/Observation trace is off by default; `--verbose`
  turns it on and I did not get to that pass. So I cannot say whether q1 used
  `calculate` or did the arithmetic in-model, nor whether q4's wrong number came
  from a tool it misread or from no tool at all. **That distinction is the whole
  diagnosis of q4** and it is the first thing the next pass must get.
- **Nothing about step counts.** Same cause.
- **Nothing statistical.** One run per question. The project has measured the
  same question answered correctly 1 time in 10 on one day and 6 in 10 two days
  later with unchanged text, so a single run per question cannot distinguish a
  wrong answer from an unlucky one. **q4 needs ten runs before anyone calls it a
  property of the model.**
- **Nothing comparable to any earlier figure.** Five new questions, a different
  commit and a different bank: a different denominator.
- **Nothing about the sealed bank**, which was not read, not run and not quoted.
- **No record was persisted.** Brief 12's run-record layer is absent from the
  canonical line (see `docs/pm/memo-holdout-instrument-2026-11-22.md`), so this
  run has no JSONL row, no commit field and no clean-tree field on disk. The
  commit and tree state above were captured by my runner, not by the
  instrument. **That is the gap the memo's option A closes, and this run is the
  first evidence it bites.**

## 6. Why this is partial, and what the second pass is

I stopped at the reporting step with the weekly meter at 51 % against the 53 %
stop line the PM asked me to leave. The second pass is small and already
specified:

1. Re-run the same five questions with `--verbose` to capture
   Thought/Action/Observation, giving step counts and tool names per question.
2. Fix the grader to read the answer line only, and keep the q4 output as the
   regression case that proves it.
3. Ten runs of q4 alone, to settle whether 50 is a property or a draw — asked
   **inside** the five-question set rather than alone, because a single-question
   probe does not reproduce the run's conditions.

## 7. Options for the owner

**A — Port brief 12's record layer first, then re-measure.** Carried out by the
**AI/ML chair**. This run produced no auditable record because the layer is
gone; every further measurement has the same hole. Small, no model needed.
**Recommended, and unchanged from the memo.**

**B — Second pass now: `--verbose`, the grader fix, and ten runs of q4.**
Carried out by the **AI/ML chair**. Turns q4 from a sighting into a result and
gives the step and tool figures this report is missing.

**C — Both, in that order, in one session.** Carried out by the **AI/ML chair**.
Costs more meter than either alone; it is the order that produces a recorded,
auditable ten-run figure.

**D — Have the grader defect reviewed against the live instrument.** Carried out
by the **SE chair**: check `eval_scoring.judge()` and the old bank's short
numeric expectations for the same whole-output carrier, since the old bank's
expectations include bare line counts. No model run needed.

---

`QA: 1 finding (0 Critical / 1 High / 0 Medium / 0 Low) - 1 reproduced - not tested: tool calls and step counts not captured, q4 run once only, no ten-run repeat, sealed bank not touched, eval_scoring.judge() not inspected, no run record persisted`

`Budget: week 51% used (owner confirmed 46-56% in the AI/ML session; PM stop line 53%), 5-hour 59%`

---

## Addendum, 2026-11-23, second session — I1 done, I2 half done, the model pass NOT run

### I1 — done (`fe48786`)

`scripts/first_measurement.py` and `tests/test_first_measurement.py` are committed. The runner measures a tree
other than its own (`--project`), so the agent cannot read it and the measured commit is exactly that tree; one
process per question, one file per run, a finished run is never repeated, and it aborts before any request if a
question appears in a bank. Gates: ruff clean, mypy 56 files, **1072 passed, 2 skipped** (1065 + 7).

Raw outputs of the first pass are **not committed**: they hold model replies and live under `data/`
(gitignored). The PM can read them at
`D:\code-project\OmniAgent\.scratch\aie-first-measurement\data\first-measurement\pass1\` (6 files).

**Mutation check, hashes recorded** (runner pristine `9c38154ca9871292`, restored to it after each):

| Mutation | Red |
| --- | --- |
| grade the whole output again (`33895ed…` is M2; M1 `09d8e55700fe8257`) | 3 tests, including the new banner-token test |
| bare substring instead of a whole token (`33895ed10f0f681c`) | 1 test: expectation inside a longer number |

**Two of my own mistakes, kept because they change how far the test can be trusted:**
1. The first version of the q4 regression test did **not** isolate the fix. With the answer-region guard removed
   it stayed green, because the whole-token rule independently rejects `12` inside `127`. Two guards agreed, so
   the test proved neither. A second test now puts the expectation in the banner as a whole token (the port), so
   only the answer-region guard can reject it.
2. My first attempt at that mutation never applied (an assertion failed, hash unchanged) and a second produced a
   `SyntaxError` from a `\1` in a replacement string. Neither counts as a red test. The reported results are
   from a mutant that parses and has a different hash.

### I2 part 1 — where `count_lines` comes from: nowhere in the repository, the training data, or the model's own template

All counts, no content. The registry has 7 tools and `count_lines` is not one of them.

| Place searched | Result |
| --- | --- |
| tracked files, `b164aaa` | **0** files |
| tracked files, legacy tag `3c76fd2` | **0** files |
| `TOOLS[...]` registrations, both refs | **0** |
| training and run files on disk (`data/*.jsonl`, **18 files, ~7,500 examples**) | **0** examples mention it |
| action names outside the registry in those files | only in `demo.jsonl` (3,074 examples): 13 occurrences across `none`, `activate`, `finalize`, `get_weather`, `sum`, `final_answer`, `Final`; plus 1 `Final` in each of three collect/dataset files |
| `omniagent-v2:latest` baked-in Modelfile/template (read-only `/api/show`) | **0** mentions; no system prompt; no tool names baked in |
| git history, `-S count_lines` over all refs | 3 commits, **all on new branches** (this one, the SE empty-answer branch, the PM task doc); none in the product |

**What this supports:** nothing in this repository or in the model's own prompt teaches `count_lines`; the model
invented a plausible name for "count" when its question was about counting. **What it does not establish:**
that the fine-tuning corpus is the on-disk `data/` set (the weights' corpus is not recorded where I looked, and
`models/` is sealed), nor that the base model is the source. By elimination it is the model's prior, not proven.
`demo.jsonl` is the only file that *does* contain invented action names (e.g. `get_weather`), so unregistered
names are not unknown to the training data; they are just not this one.

### I2 part 2 — the `--verbose` second pass was NOT run, and why

Before starting I checked the shared model server. `qwen2.5-coder:7b` was resident on the GPU and its
`expires_at` advanced from `06:29:28` to `06:32:35` Thai time over a 330 s watch, i.e. **someone else was using it
and renewing it**. It is not my model (I only use `omniagent-v2:latest`). The project rule is one model run at a
time on a 4 GB card, and the addendum forbids starting a run while another chair's local-AI delegation is in
flight. I cannot tell from here whose it is, so I did not start. No partial measurement exists; the worktree
`.scratch/aie-measure-b164aaa` (HEAD `b164aaa`, clean) is ready. The run is one command:

```
python scripts/first_measurement.py --project D:\code-project\OmniAgent\.scratch\aie-measure-b164aaa --out <dir under data/> --passes 10
```

That is 6 questions x 10 passes = 60 runs, each a fresh process, so the counting question runs ten times inside
the set and the PM's wording runs ten times beside it.

### Meter anomaly

My last read showed **weekly 0 %, 5-hour 4 %**, against **52 %** minutes earlier, with the 5-hour `resetsAt` also
moved (03:50Z to 04:20Z). I do not trust it and did not treat it as new headroom. Nothing in this session relied on it.
