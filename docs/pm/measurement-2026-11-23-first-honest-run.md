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
