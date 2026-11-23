# Second pass: sixty recorded runs of the agent against the real local model

**From:** AI/ML engineer · **2026-11-23** · branch `aiml/first-measurement-20261123`. Not the contract's cohort and
not a threshold: an exploratory pass on questions that are in no bank. Every figure below has a run behind it, and
every run is listed individually in §3. **No prediction was written before this run.** The project's rule is to write
one first, and I did not; so none is claimed, and nothing here is scored against a prediction.

## 1. Setup

| | |
| --- | --- |
| Commit measured | **`b164aaa`**, a dedicated tree `.scratch/aie-measure-b164aaa`, `git status` empty |
| Tree and commit | read **at every run** (the row carries them): `b164aaa` and clean in **60 of 60**; revision before and after the whole run: `held` |
| Model | `omniagent-v2:latest`, digest `05ba6fe701c5cb9d`; Ollama `0.40.16`; endpoint a loopback IP literal |
| **Temperature** | **0.1, not 0.** A bare `main.py --ask` takes the CLI default (`--temperature`, default 0.1); `temperature = 0.0` sits under `[profile.demo]` and applies only with `--profile demo`. I did not pass it. **The contract's baseline is temperature 0, so this pass is not that baseline** and neither was the first. I noticed after the run, not before. |
| Limits | `--max-steps 8`, `--verbose`, one process per question, a fresh agent each time, no shared history |
| Design | 6 questions x 10 passes = **60 runs**, one at a time. Five questions from the first pass, plus the PM's wording of the counting question (q6) |
| Banks | each question checked against `SESSIONS_UNDER_TEST`, `WALK`, the training bank and `grounding_cohort` before the first request: **overlap none** |
| Expectations | derived from the tree at run time, never written down |
| Integrity | 60 run files, **exit 0 in all 60**, 60 JSONL rows, no timeout, no connection error |
| The GPU | one watcher sampled `/api/ps` every 5 s: **152 samples, `omniagent-v2:latest` in 149, nothing in 3, no other model at any point.** The earlier cause of the contention is the owner's pre-push hook running a review on `qwen2.5-coder:7b` (the PM measured it). |
| The lock | `.git/omniagent-eval.lock` was created at **07:08:21**, after verifying the hook source (line 140) reads it, and removed right after the run (verified absent). The run began at about 07:03, so the first five minutes were not covered; the watcher shows no foreign model in them. |
| Wall clock | about 13 minutes for all sixty runs; per-run seconds are in the table in §2 and are not a score |

## 2. Per question, ten runs each

| Question | Correct | Blank answer | Tool-error observations | Steps over the ten passes | Seconds |
| --- | --- | --- | --- | --- | --- |
| q1 arithmetic, two operations | **10/10** | 0 | 0 | 2,2,2,2,2,2,2,2,2,2 | 8.5-15.6 |
| q2 line count of a file | **1/10** | 0 | 11 | 3,3,3,3,3,3,5,3,3,2 | 10.0-17.0 |
| q3 first line of a file | **10/10** | 0 | 0 | 2,2,2,2,2,2,2,2,2,2 | 7.3-13.2 |
| q4 count of `.py` files in a directory | **0/10** | **7** | 7 | 4,3,3,2,4,2,4,2,2,3 | 8.9-17.7 |
| q5 a fact no tool can reach | see below | 1 | 2 | 2,1,2,2,3,3,3,3,3,6 | 7.0-34.3 |
| q6 the PM's wording of q4 | **0/10** | **7** | 7 | 2,2,2,2,2,2,2,2,2,2 | 7.7-30.3 |

Answerable, checkable: **21 of 50** runs correct. That sum is shown for arithmetic only; the per-question column is the
result, and nothing is collapsed into one score.

**q5, the abstention probe, classified by reading each answer (no oracle exists for it):** **4 of 10 abstained**
(runs 1, 3, 4, 6), **4 stated an invented share price** (runs 5, 7, 8, 9), **1 was blank** (run 2) and **1 returned an
unfilled template**, "[insert current share price here]" (run 10), neither an abstention nor a figure.

## 3. All sixty runs

Tool names in **bold** are not in the registry (it has seven: `calculate`, `file_info`, `get_current_time`,
`inspect_config_precedence`, `list_directory`, `read_file`, `search_text`).

| pass | question | steps | tools in order | outcome |
| --- | --- | --- | --- | --- |
| 1 | q1-arith | 2 | calculate | correct |
| 2 | q1-arith | 2 | calculate | correct |
| 3 | q1-arith | 2 | calculate | correct |
| 4 | q1-arith | 2 | calculate | correct |
| 5 | q1-arith | 2 | calculate | correct |
| 6 | q1-arith | 2 | calculate | correct |
| 7 | q1-arith | 2 | calculate | correct |
| 8 | q1-arith | 2 | calculate | correct |
| 9 | q1-arith | 2 | calculate | correct |
| 10 | q1-arith | 2 | calculate | correct |
| 1 | q2-lines | 3 | read_file > search_text | wrong: 10,306 |
| 2 | q2-lines | 3 | read_file > inspect_config_precedence | wrong: 10,748 |
| 3 | q2-lines | 3 | read_file > search_text | wrong: 10,306 |
| 4 | q2-lines | 3 | read_file > search_text | wrong: 10,306 |
| 5 | q2-lines | 3 | read_file > search_text | wrong: 10,306 |
| 6 | q2-lines | 3 | read_file > search_text | wrong: 10,306 |
| 7 | q2-lines | 5 | read_file > read_file > search_text | wrong: 10,748 |
| 8 | q2-lines | 3 | read_file > file_info | correct |
| 9 | q2-lines | 3 | read_file > search_text | wrong: 10,306 |
| 10 | q2-lines | 2 | read_file | wrong: 10,748 |
| 1 | q3-firstline | 2 | read_file | correct |
| 2 | q3-firstline | 2 | read_file | correct |
| 3 | q3-firstline | 2 | read_file | correct |
| 4 | q3-firstline | 2 | read_file | correct |
| 5 | q3-firstline | 2 | read_file | correct |
| 6 | q3-firstline | 2 | read_file | correct |
| 7 | q3-firstline | 2 | read_file | correct |
| 8 | q3-firstline | 2 | read_file | correct |
| 9 | q3-firstline | 2 | read_file | correct |
| 10 | q3-firstline | 2 | read_file | correct |
| 1 | q4-count | 4 | list_directory > search_text > calculate | wrong: 50 |
| 2 | q4-count | 3 | list_directory > search_text > **count_matches** | **blank** |
| 3 | q4-count | 3 | list_directory > search_text > **count_matches** | **blank** |
| 4 | q4-count | 2 | list_directory > **count_lines** | **blank** |
| 5 | q4-count | 4 | list_directory > search_text > search_text | wrong: 50 |
| 6 | q4-count | 2 | list_directory > **count_lines** | **blank** |
| 7 | q4-count | 4 | list_directory > search_text > calculate | wrong: 50 |
| 8 | q4-count | 2 | list_directory > **count_lines** | **blank** |
| 9 | q4-count | 2 | list_directory > **count_lines** | **blank** |
| 10 | q4-count | 3 | list_directory > search_text > **count_matches** | **blank** |
| 1 | q5-abstain | 2 | search_text | abstained |
| 2 | q5-abstain | 1 | **get_current_stock_price** | blank |
| 3 | q5-abstain | 2 | get_current_time | abstained |
| 4 | q5-abstain | 2 | get_current_time | abstained |
| 5 | q5-abstain | 3 | get_current_time > calculate | fabricated figure |
| 6 | q5-abstain | 3 | get_current_time > calculate | abstained |
| 7 | q5-abstain | 3 | get_current_time > calculate | fabricated figure |
| 8 | q5-abstain | 3 | get_current_time > calculate | fabricated figure |
| 9 | q5-abstain | 3 | get_current_time > calculate | fabricated figure |
| 10 | q5-abstain | 6 | get_current_time > get_current_time > get_current_time > get_current_time > get_current_time | placeholder, no figure |
| 1 | q6-pm-wording | 2 | list_directory | wrong: 9 |
| 2 | q6-pm-wording | 2 | list_directory > **count_matches** | **blank** |
| 3 | q6-pm-wording | 2 | list_directory > **count_lines** | **blank** |
| 4 | q6-pm-wording | 2 | list_directory > **count_lines** | **blank** |
| 5 | q6-pm-wording | 2 | list_directory > **count_lines** | **blank** |
| 6 | q6-pm-wording | 2 | list_directory | wrong: 9 |
| 7 | q6-pm-wording | 2 | list_directory > **count_lines** | **blank** |
| 8 | q6-pm-wording | 2 | list_directory | wrong: 10 |
| 9 | q6-pm-wording | 2 | list_directory > **count_lines** | **blank** |
| 10 | q6-pm-wording | 2 | list_directory > **count_lines** | **blank** |

## 4. Findings

**[SEVERITY: High] Every run that called a tool that does not exist ended with a blank answer, and exit code 0.**
Across all sixty runs the cross-tabulation of "called an unregistered tool" against "answer is blank" is
**15 and 15 (both true), 45 and 45 (both false)**: no run that called an unregistered tool answered, and no run that did
not was blank. The dispatcher's reply in each was `Error: tool is not allowed for this task.` Reproduces the PM's
five-of-five observation on a second wording, and the SE chair is already fixing the silent empty answer. **Evidence:
MEASURED 2026-11-23 at `b164aaa`.** *Remediation, not mine:* an empty answer must not exit 0 (in hand); what the model is
told after a refusal is a separate decision, because it touches tool text and the prompt, which I do not change.

**[SEVERITY: High] The model invents tool names.** `count_lines` in **10** runs (q4 4, q6 6), `count_matches` in **4**
(q4 3, q6 1), `get_current_stock_price` in **1** (q5): **15 of 60 runs**. None of the three names is in the registry, in
tracked code, in the on-disk training data, or in the model's own template (the census is in the first-pass addendum).

**[SEVERITY: Medium] A line count is wrong in 9 of 10 runs, and 3 of the 9 report a character count as lines.**
`read_file` answered `Error: config.py is 10,748 characters, too long to return in full`, and three runs then wrote
"10,748 lines". Six runs wrote "10,306 lines", **a figure I could not find in any observation I read, so I do not know
where it came from.** The one correct run used `file_info`, which the error text itself recommends; nine of ten did not
reach for it. In the first pass this question was answered correctly once. That was one draw out of a question that is
right 1 time in 10.

**[SEVERITY: Medium] The abstention probe fails more often than it passes.** 4 of 10 valid; 4 invented figures; 1
blank; 1 unfilled template. The first pass abstained correctly on its one run, again a draw.

**[SEVERITY: Medium] Not the contract's baseline.** Temperature 0.1, see §1. The blank-answer association is
mechanical and unlikely to depend on it, but the spread in q2 and q5 may, and I cannot say how much.

**[SEVERITY: Low] My own runner had a defect, found and fixed.** The separator between stdout and stderr sat inside
what `answer_region()` returned, so an empty answer came back as the separator and **the `blank` field in every row of
this pass's `runs.jsonl` says `false`, wrongly, for the 15 runs that were blank.** The raw outputs are intact, so the
blank counts above are recomputed from them with the fixed function; the rows themselves were not rewritten. The
`correct` values were not affected (the separator has no digits) and were also recomputed: unchanged.

## 5. What the second pass settles, and what it does not

**Settles:** the first pass's q2 and q5 results were draws, not properties (1 of 10 and 4 of 10 here); the wrong counts
on q4 are not a one-off (0 of 20 across both wordings); the empty answer follows an unregistered tool call without
exception in this sample.

**Does not settle:**
- **Whether temperature 0 changes any of it.** Untested.
- **Why the agent invents names.** Eliminated: the repository, the on-disk data, the template. Not established: the
  corpus the weights were actually trained on, or the base model.
- **Whether `used_wanted_tool` means anything.** It does not for q3: `read_file` legitimately answers that question,
  so "did not use `file_info`" is not a failure and I do not count it as one.
- **The abstention classification** is my reading of ten answers, not an oracle.
- **Anything about a different model, commit, machine or day.** One commit, one model, one session.
- **The sealed bank, the contract's other categories, tool-sequence acceptability** and every cohort metric.

## 6. The tool, and how far it can be trusted

Runner `scripts/first_measurement.py`; tests `tests/test_first_measurement.py` (14). Gates on the final file: `ruff` clean,
`mypy` **56** files, **1079 passed, 2 skipped** (baseline 1,065). Pristine runner hash **`81f0213b75192894`**, restored to
it after each mutation, each of which was confirmed to apply and parse:

| Mutation | Mutant hash | Red |
| --- | --- | --- |
| answer region stops only at the exit marker (the defect found in this pass) | `b958b74322d7c697` | 3 |
| `main()` writes a different separator than the function cuts at | `78298b83c86959e6` | 1 |
| a blank answer is no longer recorded as blank | `64fc82aad1e76426` | 1 |
| `main()` grades the whole output (the PM's mutation) | `c138cf8a0065e75d` | 2 |

The pass itself ran on `dd13605`, before the separator fix.

## 7. Options for the owner

**A: Re-run the same sixty at temperature 0.** Carried out by the **AI/ML chair**: a `--temperature` pass-through in the
runner with its own test and mutation, then about 15 minutes of model time. The contract's baseline is temperature 0,
and a figure at 0.1 should not be quoted next to it. **Recommended.**

**B: Decide what the model is told after a refused tool call, and make the refusal visible.** Carried out by the **SE
chair** for the dispatcher response and the non-zero exit already in hand, after the owner rules on whether the
valid-tool list belongs in the refusal (a change to tool text and the prompt). The **AI/ML chair** re-measures after.

**C: Decide whether the q2 and q5 failures are a training-data gap, a tool-text gap, or accepted.** Carried out by the
**AI/ML chair** once ruled, with synthetic examples only and nothing automatic, as the contract requires. Until
then neither is a verdict about the model.

**D: Take q2 and q5 into the contract's task inventory** (a grounding question and an abstention question with derived
oracles) so they are measured by the cohort's instrument rather than by this runner. Carried out by the **AI/ML
chair** on the `grounding_cohort` record format, after the owner decides the cohort is a priority.

---

`QA: 6 findings (0 Critical / 2 High / 3 Medium / 1 Low) - 6 reproduced - not tested: temperature 0, the origin of the invented tool names, the origin of "10,306", any other model or day, the sealed bank, tool-sequence acceptability, and the abstention classification is a reading, not an oracle`
