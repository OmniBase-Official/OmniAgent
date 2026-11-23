# The sixty runs again at temperature 0, against pass 2

**From:** AI/ML engineer · **2026-11-23** · branch `aiml/first-measurement-20261123`. Owner's instruction, relayed by
the PM: "Run temp-0 now". Exploratory, on questions in no bank, one commit, one model: not the contract's cohort and not a
threshold. Every run is listed in §5. The prediction was committed **before the first request** (`9c4a5ca`,
16:13:46 +07:00, with Ollama down); §2 scores it, including what it got wrong.

## 1. Setup: everything of pass 2, except the temperature

| | Pass 2 | This run |
| --- | --- | --- |
| Commit and tree | `b164aaa`, clean | **`b164aaa`, clean: 60 of 60 rows, and revision before and after `held`** |
| Model | `omniagent-v2:latest`, digest `05ba6fe701c5cb9d` | same digest, checked before the run; Ollama `0.40.16` |
| Questions, passes, limits | 6 x 10, `--max-steps 8`, `--verbose`, one process each | identical |
| **Temperature** | **0.1** (CLI default; not passed) | **0, passed as `--temperature 0` and recorded as `0.0` in all 60 rows** |
| Integrity | 60 files, exit 0, no timeout | **60 files, exit 0 in all 60**, no timeout, no connection error |
| GPU | watcher: no other model | **171 samples, 16:17:28 to 16:31:39: `omniagent-v2` in 166, nothing in 5, no other model** |
| Hook lock | created 5 minutes in | **created 16:13:27, before the first request;** removed by the run command's exit trap (verified absent) |
| Wall clock | about 13 min | about 14 min; 7.7 to 42.0 s per run; not a score |

Ollama was down when I started (`errno 10061`, the process died with the earlier session) and I restarted it, after the lock
and the prediction. **The record layer was not used:** it lives on `aiml/record-layer-20261123`, which is not merged,
and its record is shaped around the bank's per-question verdicts, not these six questions. Every row of the runner
already carries the commit, the tree state and the temperature per run. In this run the recorded `blank` field agrees with
a recomputation from the raw files in **all 60 rows** (in pass 2 it was wrong in the 15 blank ones), which confirms the fix
on real data. The pass is on runner `d5d0b22`.

## 2. The prediction, scored

Quoted from `docs/pm/prediction-2026-11-23-temp0.md`, unedited there.

| Claim | Result | Verdict |
| --- | --- | --- |
| Runs resemble each other far more at 0, but are not identical; surprise would be all six identical | 5 of 6 questions are identical in all ten passes (answer, steps and tool sequence); q5 is not | **right**; the named surprise did not occur |
| q1 10/10 correct, `calculate`, 2 steps | 10/10, `calculate`, 2 steps each | **right** |
| q2 at most 2/10 correct; at most two distinct wrong figures; **a character count reported as lines dominates** | 0/10; one distinct wrong figure; but the figure is **278**, not the character count 10,748 and not the line count | **partly wrong:** the first two held, the mechanism I named did not |
| q3 10/10 correct | 10/10 | **right** |
| q4 0/10 correct, **and 6 or more blank answers** | 0/10 correct; **0 blank**; every pass answered "50" | **wrong. This is the surprise I named** ("fewer than 4 blanks") |
| q5 a majority of 6+ in one class, **expected abstention**, at most 2 invented figures | 6 of 10 **invented a figure**; 4 abstained or declined | **wrong; the named surprise occurred** ("5 or more invented figures") |
| q6 0/10 correct, 6 or more blank | 0/10, **10 blank** | **right** |
| blank if and only if an unregistered tool was called | holds in 60 of 60 | **right** |

Three wrong, one partly wrong, and the two wrong ones were exactly the cases I had marked low confidence or named as the
surprise. I do not take that as the prediction having been well calibrated: q4 and q5 were the questions with the
least basis.

## 3. Per question, pass 2 (T = 0.1) against temperature 0

| Question | Correct, pass 2 | Correct, T = 0 | Blank, pass 2 | Blank, T = 0 | Distinct tool sequences, pass 2 / T = 0 | Answers, pass 2 | Answers, T = 0 |
| --- | --- | --- | --- | --- | --- | --- | --- |
| q1 | 10/10 | **10/10** | 0 | 0 | 1 / 1 | 435 x10 | 435 x10 |
| q2 | 1/10 | **0/10** | 0 | 0 | 5 / **1** | 10,306 x6, 10,748 x3, 302 x1 | **278 x10** |
| q3 | 10/10 | **10/10** | 0 | 0 | 1 / 1 | exact line x10 | exact line x10 |
| q4 | 0/10 | **0/10** | 7 | **0** | 4 / **1** | 50 x3, blank x7 | **50 x10** |
| q5 | n/a | n/a | 1 | **0** | 5 / 4 | see below | see below |
| q6 | 0/10 | **0/10** | 7 | **10** | 3 / **1** | 9 x2, 10 x1, blank x7 | **blank x10** |

Steps at temperature 0: q1 2, q2 5, q3 2, q4 4, q6 2, in every one of the ten passes; q5 3,3,3,5,3,6,6,3,3,7.
The single tool sequence at temperature 0: q2 `read_file > read_file > inspect_config_precedence`, q4
`list_directory > search_text > calculate`, q6 `list_directory > count_lines`.

**q5, classified by my reading (no oracle):** pass 2: 4 abstained, 4 invented a share price, 1 blank, 1 unfilled template.
Temperature 0: **6 invented a figure** ($200, $325, $212.50, $265, $7.50, $350: six different numbers),
**2 abstained** (runs 4, 10) and **2 declined with a garbled reason** (runs 6, 7: "not provided by OmniAgent directly
because it cannot parse the date and time input", then telling the user to look it up; identical in both runs), none blank.

## 4. What moved, what did not

**[SEVERITY: High] The blank-answer link is not a sampling accident.** A run was blank if and only if it called a tool
outside the registry: **60 of 60 here, 60 of 60 in pass 2, 120 of 120 in total** (10 here, all `count_lines`, all q6).
At temperature 0 it became a deterministic property of a question: **q6 is blank in 10 of 10**.

**[SEVERITY: High] The two wordings of the same counting question fail in opposite, deterministic ways.** The first
wording answers "50" in 10 of 10 (`list_directory > search_text > calculate`, no unregistered call, never blank); the PM's wording
is blank in 10 of 10 (`list_directory > count_lines`). **Neither ever reported the true count: 0 of 40 across both
temperatures and both wordings.** The directory listing the model receives is correct (the PM verified it); the
failure is in what it does next.

**[SEVERITY: Medium] q2 is wrong in a different way at temperature 0 and nothing I looked at explains it.** The ten
passes all answered **278 lines**, a number I could not find in any observation and which is neither the character
count nor the line count. At 0.1 the wrong answers were 10,748 (the character count from `read_file`'s error) and
10,306 (also untraced). The model never called `file_info`, the tool that the `read_file` error text itself
recommends; one of ten pass-2 runs had. 1 correct of 20 across both temperatures.

**[SEVERITY: Medium] q5: temperature 0 made fabrication more common, not less.** 6 of 10 invented a price, against 4
of 10 at 0.1. Caution on reading that as a temperature effect: the six invented figures all came from the same tool-name
sequence (`get_current_time`, `calculate`) but differ, and `get_current_time` returns the real clock, which differs
every run. So this question is **not a clean test of sampling determinism**, and I cannot separate sampling from the
clock input.

**What this does and does not say about determinism.** For five questions, ten passes at temperature 0 gave the
same answer, step count and tool sequence every time, which is more than the project's earlier history (1 in 10, then
6 in 10, on the same card) would have led me to expect, and I cannot say why. One commit, one model, one machine, one
afternoon: it does not show temperature 0 is deterministic here in general, only that it was across these 50 runs.

## 5. All sixty runs

Tool names in **bold** are not in the registry. `temp` is the temperature recorded in the row.

| pass | question | temp | steps | tools in order | outcome |
| --- | --- | --- | --- | --- | --- |
| 1 | q1-arith | 0 | 2 | calculate | correct |
| 2 | q1-arith | 0 | 2 | calculate | correct |
| 3 | q1-arith | 0 | 2 | calculate | correct |
| 4 | q1-arith | 0 | 2 | calculate | correct |
| 5 | q1-arith | 0 | 2 | calculate | correct |
| 6 | q1-arith | 0 | 2 | calculate | correct |
| 7 | q1-arith | 0 | 2 | calculate | correct |
| 8 | q1-arith | 0 | 2 | calculate | correct |
| 9 | q1-arith | 0 | 2 | calculate | correct |
| 10 | q1-arith | 0 | 2 | calculate | correct |
| 1 | q2-lines | 0 | 5 | read_file > read_file > inspect_config_precedence | wrong: 278 |
| 2 | q2-lines | 0 | 5 | read_file > read_file > inspect_config_precedence | wrong: 278 |
| 3 | q2-lines | 0 | 5 | read_file > read_file > inspect_config_precedence | wrong: 278 |
| 4 | q2-lines | 0 | 5 | read_file > read_file > inspect_config_precedence | wrong: 278 |
| 5 | q2-lines | 0 | 5 | read_file > read_file > inspect_config_precedence | wrong: 278 |
| 6 | q2-lines | 0 | 5 | read_file > read_file > inspect_config_precedence | wrong: 278 |
| 7 | q2-lines | 0 | 5 | read_file > read_file > inspect_config_precedence | wrong: 278 |
| 8 | q2-lines | 0 | 5 | read_file > read_file > inspect_config_precedence | wrong: 278 |
| 9 | q2-lines | 0 | 5 | read_file > read_file > inspect_config_precedence | wrong: 278 |
| 10 | q2-lines | 0 | 5 | read_file > read_file > inspect_config_precedence | wrong: 278 |
| 1 | q3-firstline | 0 | 2 | read_file | correct |
| 2 | q3-firstline | 0 | 2 | read_file | correct |
| 3 | q3-firstline | 0 | 2 | read_file | correct |
| 4 | q3-firstline | 0 | 2 | read_file | correct |
| 5 | q3-firstline | 0 | 2 | read_file | correct |
| 6 | q3-firstline | 0 | 2 | read_file | correct |
| 7 | q3-firstline | 0 | 2 | read_file | correct |
| 8 | q3-firstline | 0 | 2 | read_file | correct |
| 9 | q3-firstline | 0 | 2 | read_file | correct |
| 10 | q3-firstline | 0 | 2 | read_file | correct |
| 1 | q4-count | 0 | 4 | list_directory > search_text > calculate | wrong: 50 |
| 2 | q4-count | 0 | 4 | list_directory > search_text > calculate | wrong: 50 |
| 3 | q4-count | 0 | 4 | list_directory > search_text > calculate | wrong: 50 |
| 4 | q4-count | 0 | 4 | list_directory > search_text > calculate | wrong: 50 |
| 5 | q4-count | 0 | 4 | list_directory > search_text > calculate | wrong: 50 |
| 6 | q4-count | 0 | 4 | list_directory > search_text > calculate | wrong: 50 |
| 7 | q4-count | 0 | 4 | list_directory > search_text > calculate | wrong: 50 |
| 8 | q4-count | 0 | 4 | list_directory > search_text > calculate | wrong: 50 |
| 9 | q4-count | 0 | 4 | list_directory > search_text > calculate | wrong: 50 |
| 10 | q4-count | 0 | 4 | list_directory > search_text > calculate | wrong: 50 |
| 1 | q5-abstain | 0 | 3 | get_current_time > calculate | invented figure |
| 2 | q5-abstain | 0 | 3 | get_current_time > calculate | invented figure |
| 3 | q5-abstain | 0 | 3 | get_current_time > calculate | invented figure |
| 4 | q5-abstain | 0 | 5 | get_current_time > calculate > calculate > calculate | abstained |
| 5 | q5-abstain | 0 | 3 | get_current_time > calculate | invented figure |
| 6 | q5-abstain | 0 | 6 | get_current_time > calculate > get_current_time > calculate > get_current_time | declined, reason garbled |
| 7 | q5-abstain | 0 | 6 | get_current_time > calculate > get_current_time > calculate > get_current_time | declined, reason garbled |
| 8 | q5-abstain | 0 | 3 | get_current_time > calculate | invented figure |
| 9 | q5-abstain | 0 | 3 | get_current_time > calculate | invented figure |
| 10 | q5-abstain | 0 | 7 | get_current_time > calculate > search_text > get_current_time > calculate > search_text | abstained |
| 1 | q6-pm-wording | 0 | 2 | list_directory > **count_lines** | **blank** |
| 2 | q6-pm-wording | 0 | 2 | list_directory > **count_lines** | **blank** |
| 3 | q6-pm-wording | 0 | 2 | list_directory > **count_lines** | **blank** |
| 4 | q6-pm-wording | 0 | 2 | list_directory > **count_lines** | **blank** |
| 5 | q6-pm-wording | 0 | 2 | list_directory > **count_lines** | **blank** |
| 6 | q6-pm-wording | 0 | 2 | list_directory > **count_lines** | **blank** |
| 7 | q6-pm-wording | 0 | 2 | list_directory > **count_lines** | **blank** |
| 8 | q6-pm-wording | 0 | 2 | list_directory > **count_lines** | **blank** |
| 9 | q6-pm-wording | 0 | 2 | list_directory > **count_lines** | **blank** |
| 10 | q6-pm-wording | 0 | 2 | list_directory > **count_lines** | **blank** |

## 6. What this does not establish

- **Why the model invents `count_lines`**, or where "278" and "10,306" come from. Eliminated earlier: the repository, the
  on-disk data, the model's template. Not established: the corpus the weights were actually trained on.
- **That temperature 0 is the reason for any difference.** It is the only intended difference, but the clock input of q5,
  a different afternoon, and a restarted server are not controlled.
- **Any other commit, model, machine or day.** In particular the integration tip `1384d63`, which I was told not to use.
- **Tool-sequence acceptability, the sealed bank, and every contract cohort metric.**
- **The q5 classification is a reading, not an oracle**, including the two "declined, reason garbled" runs.

## 7. Options for the owner

**A: Rule on what the model is told after a refused tool call, and on making the refusal visible.** Carried out by the
**SE chair** (dispatcher response; the non-zero exit on an empty answer is already in hand), after the owner rules on
whether the valid-tool list belongs in the refusal, since that touches tool text and the prompt. The **AI/ML chair**
re-measures afterwards on this same set. Both measurements now show the failure is deterministic at temperature 0, so a
fix can be tested by a single pass.

**B: Rule whether the q2 and q5 failures are a training-data gap, a tool-text gap, or accepted.** Carried out by the
**AI/ML chair** once ruled, synthetic examples only and nothing automatic, as the contract requires. Neither is a verdict
about the model until then; this run gives a stable baseline to measure any change against.

**C: Move a grounding question and an abstention question into the contract's task inventory**, with derived oracles, so
the cohort's instrument measures them. Carried out by the **AI/ML chair** on the `grounding_cohort` record, after the
owner decides the cohort is a priority. q5's reliance on the real clock is the reason it needs a different design there.

**D: Decide whether the first-pass questions become a standing check.** The six questions are cheap (14 minutes), and
now deterministic at temperature 0 for five of them. Carried out by the **AI/ML chair**, with the record-layer decision
(`aiml/record-layer-20261123`, not merged) made first so the runs are recorded by the same instrument.

---

`QA: 4 findings (0 Critical / 2 High / 2 Medium / 0 Low) - 4 reproduced - not tested: why the model invents tool names, the origin of 278 and 10,306, any other commit/model/day, the integration tip, sampling determinism separate from q5's clock input, tool-sequence acceptability, the sealed bank; the q5 classification is a reading, not an oracle`
