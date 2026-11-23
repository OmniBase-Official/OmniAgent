# Step 2: the exact line count in the `read_file` error, measured at `1ce7c81`

**From:** AI/ML engineer · **2026-11-24** · branch `aiml/tool-text-measure-20261123`. Seventy runs at temperature 0, on
SE 01's commit `1ce7c81` (`se/brief-31-tool-text`, one commit on `1384d63`), against my temperature-0 baseline `dc0c78d` on
`b164aaa` and the q7 baseline (10 runs, same temperature, `b164aaa`). The predictions are `63fc1ae` (six questions) and
`97faf15` (q7), written before the commit existed and not edited. §2 scores them, wrong parts included.

## 1. Setup

| | |
| --- | --- |
| Commit measured | **`1ce7c81`**, a dedicated tree, `git status` empty; revision before and after `held`; **commit `1ce7c81` and clean in 70 of 70 rows** |
| What the commit changes | verified by reading the diff (`git diff 1384d63 1ce7c81 -- tools.py`): **only** the `read_file` too-long error, plus a helper that adds ` (N lines)`; no description, no prompt, no `list_directory` |
| Model, runtime | `omniagent-v2:latest` digest `05ba6fe701c5cb9d`, Ollama `0.40.16`, checked before the run; the server was restarted by me (it dies with the session) |
| Run | 7 questions x 10 passes = **70 runs**, `--temperature 0` (recorded `0.0` in every row), `--max-steps 8`, `--verbose`, one process each |
| Integrity | **70 files; exit 0 in 60, exit 1 in 10**; no timeout, no connection error |
| GPU | watcher, **306 samples 05:22:28 to 05:47:58: `omniagent-v2` in 301, nothing in 5, no other model** |
| Lock | created **05:22:11**, before the first request; removed by the run's exit trap; verified absent |
| The tool text itself | checked **before** the run, with no model: `read_file("config.py")` returns "10,748 characters (**302 lines**), too long to return in full" and `observability.py` "(**353 lines**)", both equal to the tree. So an answer that ignores the count is a finding about the model, not the tool |

## 2. The predictions, scored

| Claim | Result | Verdict |
| --- | --- | --- |
| q1 and q3 unchanged, 10/10, same steps and tools | 10/10 and 10/10, identical sequences | **right** |
| **q2: 65% that at least 8 of 10 are correct** | **0/10** | **wrong** |
| q2 and q7 move together (75%) | both stay at 0/10 | **right, in the sense that both did not move** |
| **q7 at the new tip: 65% at least 8 of 10 correct** | **0/10** | **wrong** |
| q7 baseline: at least 8 wrong; "278" in at most 2 | 10 wrong; "278" in 0 | right (reported on the earlier day) |
| q5: 4 to 8 of 10 invent a figure | **3 of 10** | **wrong by one**, see §4 |
| blank if and only if an unregistered tool was called | 70 of 70 | **right** |
| a run exits 1 if and only if it prints `[!] No answer`, and these coincide with blank | 70 of 70 | **right** (the empty-answer fix works on real runs) |
| **no new unregistered names beyond `count_lines`** | **`count_matches` in 10 runs, `count_lines` in none** | **wrong** |
| q4 and q6 (the `list_directory` questions): not predicted to move now, per the PM | **both moved**, in opposite directions | **a surprise I named in general terms**, see §4 |

The central prediction was wrong. I expected the line count printed in the error to be used, and it was not.

## 3. Per question, baseline at T = 0 against `1ce7c81`

| Question | Correct, baseline | Correct, `1ce7c81` | Blank, base / new | Answers, baseline | Answers, `1ce7c81` | Tools, baseline | Tools, `1ce7c81` |
| --- | --- | --- | --- | --- | --- | --- | --- |
| q1 | 10/10 | **10/10** | 0 / 0 | 435 x10 | 435 x10 | `calculate` | same |
| q2 line count | 0/10 | **0/10** | 0 / 0 | "278" x10 | **"10,306" x10** | `read_file > read_file > inspect_config_precedence` (5 steps) | `read_file > search_text` (3 steps) |
| q3 | 10/10 | **10/10** | 0 / 0 | exact line x10 | exact line x10 | `read_file` | same |
| q4 count | 0/10 | **0/10** | 0 / **10** | "50" x10 | **blank x10** | `list_directory > search_text > calculate` | `list_directory > search_text > count_matches` |
| q5 | n/a | n/a | 0 / 0 | 6 invented, 4 declined | **3 invented, 7 declined** | 4 distinct sequences | 5 distinct |
| q6 PM's wording | 0/10 | **0/10** | **10** / 0 | blank x10 (`count_lines`) | **"9" x10** | `list_directory > count_lines` | `list_directory` |
| q7 control (`observability.py`) | 0/10 | **0/10** | 0 / 0 | "12331" x9, "cannot be located" x1 | **"12331" x10** | 8-step loop in 9 of 10 | 8-step loop in 10 of 10 |

## 4. Findings

**[SEVERITY: High] The exact line count in the error does not change the answer. 0 of 20 at the new tip (q2 0/10, q7 0/10),
0 of 20 at baseline.** The error printed "(302 lines)" and "(353 lines)", verified equal to the tree, and the model answered
"10,306" and "12331". It never used the figure in front of it. The first and most direct answer to the PM's question
("does the exact line count change the answer, or does the model still say 278?") is: **it changes which wrong figure the
model gives (q2 went from 278 to 10,306) and does not make it give the right one.**

**[SEVERITY: High] q7 shows the model produces a confident wrong count with no memorisation involved.** "12331" is not in the
on-disk data (0 of 7,551 examples, against 76 for 10,306); it is invented. On the PM's reading rule: "278 for the other
file" did not happen, and "the true count for the other file" did not happen, so the text did not help on either file, and the
figure is not specific to `config.py`. q2's two figures (278, then 10,306) are both in the data, so for `config.py` the model
chooses between two figures it has seen; for `observability.py` it makes one up. Both are the same behaviour: ignoring the
number in the observation.

**[SEVERITY: Medium] q4 and q6 moved although the diff cannot reach them, and the movement is unexplained.** `list_directory`
is unchanged and the diff touches only the `read_file` error. q4 went from "50" (10 of 10) to **blank (10 of 10, via the
unregistered `count_matches`, exit 1)**; q6 went from **blank (10 of 10, via `count_lines`)** to **"9" (10 of 10, a wrong
count, no unregistered call)**. Candidates, none tested: the five commits between `b164aaa` and `1384d63` (in agent code only
`main.py` changed, output format); server restarts and sampling at temperature 0 differing between sessions; the working-tree
path. **This is exactly what a control at `1384d63` separates**: if it shows the `1ce7c81` behaviour the cause is the base or
the session, if it shows the baseline behaviour the cause is SE's commit despite the diff. The agreed trigger (q1 or q3
moving) did not fire, so I did **not** run it.

**[SEVERITY: Medium] q5 moved from 6 invented figures to 3 on a path the change cannot reach.** My prediction was 4 to 8, so this is
outside it, and by the definition I wrote beforehand (3 or fewer is an improvement) it would count as one. I do **not**
claim the tool text did it: q5 reads the real clock, and q4 and q6 show that things the change cannot reach moved too.

**Confirmed, and worth keeping:**
- **Blank if and only if an unregistered tool was called: 70 of 70** (10 here, all `count_matches` in q4); **190 of 190 over pass 2,
  the temperature-0 baseline and this run, and 200 of 200 with the q7 baseline** (the first pass recorded no trace and is not counted).
- **Blank, exit 1 and the `[!] No answer` line coincide in 10 of 10; the 60 answered runs all exit 0 with no such line.**
  The empty-answer fix works on real model output.
- `inspect_config_precedence` is gone from q2 (the model now goes `read_file > search_text`); the answer got no better.
- `count_lines`, the name that dominated pass 2 and q6, was not called once; `count_matches` replaced it. The set of invented
  tool names is not stable between runs.

## 5. All seventy runs

Tool names in **bold** are not in the registry. `exit` is the program's exit code.

| pass | question | steps | tools in order | exit | outcome |
| --- | --- | --- | --- | --- | --- |
| 1 | q1-arith | 2 | calculate | 0 | correct |
| 2 | q1-arith | 2 | calculate | 0 | correct |
| 3 | q1-arith | 2 | calculate | 0 | correct |
| 4 | q1-arith | 2 | calculate | 0 | correct |
| 5 | q1-arith | 2 | calculate | 0 | correct |
| 6 | q1-arith | 2 | calculate | 0 | correct |
| 7 | q1-arith | 2 | calculate | 0 | correct |
| 8 | q1-arith | 2 | calculate | 0 | correct |
| 9 | q1-arith | 2 | calculate | 0 | correct |
| 10 | q1-arith | 2 | calculate | 0 | correct |
| 1 | q2-lines | 3 | read_file > search_text | 0 | wrong: 10,306 |
| 2 | q2-lines | 3 | read_file > search_text | 0 | wrong: 10,306 |
| 3 | q2-lines | 3 | read_file > search_text | 0 | wrong: 10,306 |
| 4 | q2-lines | 3 | read_file > search_text | 0 | wrong: 10,306 |
| 5 | q2-lines | 3 | read_file > search_text | 0 | wrong: 10,306 |
| 6 | q2-lines | 3 | read_file > search_text | 0 | wrong: 10,306 |
| 7 | q2-lines | 3 | read_file > search_text | 0 | wrong: 10,306 |
| 8 | q2-lines | 3 | read_file > search_text | 0 | wrong: 10,306 |
| 9 | q2-lines | 3 | read_file > search_text | 0 | wrong: 10,306 |
| 10 | q2-lines | 3 | read_file > search_text | 0 | wrong: 10,306 |
| 1 | q3-firstline | 2 | read_file | 0 | correct |
| 2 | q3-firstline | 2 | read_file | 0 | correct |
| 3 | q3-firstline | 2 | read_file | 0 | correct |
| 4 | q3-firstline | 2 | read_file | 0 | correct |
| 5 | q3-firstline | 2 | read_file | 0 | correct |
| 6 | q3-firstline | 2 | read_file | 0 | correct |
| 7 | q3-firstline | 2 | read_file | 0 | correct |
| 8 | q3-firstline | 2 | read_file | 0 | correct |
| 9 | q3-firstline | 2 | read_file | 0 | correct |
| 10 | q3-firstline | 2 | read_file | 0 | correct |
| 1 | q4-count | 3 | list_directory > search_text > **count_matches** | 1 | **blank** |
| 2 | q4-count | 3 | list_directory > search_text > **count_matches** | 1 | **blank** |
| 3 | q4-count | 3 | list_directory > search_text > **count_matches** | 1 | **blank** |
| 4 | q4-count | 3 | list_directory > search_text > **count_matches** | 1 | **blank** |
| 5 | q4-count | 3 | list_directory > search_text > **count_matches** | 1 | **blank** |
| 6 | q4-count | 3 | list_directory > search_text > **count_matches** | 1 | **blank** |
| 7 | q4-count | 3 | list_directory > search_text > **count_matches** | 1 | **blank** |
| 8 | q4-count | 3 | list_directory > search_text > **count_matches** | 1 | **blank** |
| 9 | q4-count | 3 | list_directory > search_text > **count_matches** | 1 | **blank** |
| 10 | q4-count | 3 | list_directory > search_text > **count_matches** | 1 | **blank** |
| 1 | q5-abstain | 8 | get_current_time > calculate > get_current_time > calculate > get_current_time > calculate > get_current_time > calculate | 0 | declined |
| 2 | q5-abstain | 8 | get_current_time > calculate > search_text > calculate > get_current_time > calculate > search_text | 0 | declined |
| 3 | q5-abstain | 8 | get_current_time > calculate > get_current_time > calculate > get_current_time > calculate > get_current_time > calculate | 0 | declined |
| 4 | q5-abstain | 8 | get_current_time > calculate > get_current_time > calculate > get_current_time > calculate > get_current_time > calculate | 0 | declined |
| 5 | q5-abstain | 8 | get_current_time > calculate > get_current_time > calculate > get_current_time > calculate > get_current_time > calculate | 0 | declined |
| 6 | q5-abstain | 3 | get_current_time > calculate | 0 | invented figure |
| 7 | q5-abstain | 3 | get_current_time > calculate | 0 | invented figure |
| 8 | q5-abstain | 7 | get_current_time > calculate > search_text > get_current_time > calculate > search_text | 0 | declined |
| 9 | q5-abstain | 8 | get_current_time > calculate > search_text > calculate > get_current_time > calculate > get_current_time > calculate | 0 | declined |
| 10 | q5-abstain | 3 | get_current_time > calculate | 0 | invented figure |
| 1 | q6-pm-wording | 2 | list_directory | 0 | wrong: 9 |
| 2 | q6-pm-wording | 2 | list_directory | 0 | wrong: 9 |
| 3 | q6-pm-wording | 2 | list_directory | 0 | wrong: 9 |
| 4 | q6-pm-wording | 2 | list_directory | 0 | wrong: 9 |
| 5 | q6-pm-wording | 2 | list_directory | 0 | wrong: 9 |
| 6 | q6-pm-wording | 2 | list_directory | 0 | wrong: 9 |
| 7 | q6-pm-wording | 2 | list_directory | 0 | wrong: 9 |
| 8 | q6-pm-wording | 2 | list_directory | 0 | wrong: 9 |
| 9 | q6-pm-wording | 2 | list_directory | 0 | wrong: 9 |
| 10 | q6-pm-wording | 2 | list_directory | 0 | wrong: 9 |
| 1 | q7-control-lines | 8 | read_file > list_directory > read_file > list_directory > read_file > list_directory > read_file > list_directory | 0 | wrong: 12331 |
| 2 | q7-control-lines | 8 | read_file > list_directory > read_file > list_directory > read_file > list_directory > read_file > list_directory | 0 | wrong: 12331 |
| 3 | q7-control-lines | 8 | read_file > list_directory > read_file > list_directory > read_file > list_directory > read_file > list_directory | 0 | wrong: 12331 |
| 4 | q7-control-lines | 8 | read_file > list_directory > read_file > list_directory > read_file > list_directory > read_file > list_directory | 0 | wrong: 12331 |
| 5 | q7-control-lines | 8 | read_file > list_directory > read_file > list_directory > read_file > list_directory > read_file > list_directory | 0 | wrong: 12331 |
| 6 | q7-control-lines | 8 | read_file > list_directory > read_file > list_directory > read_file > list_directory > read_file > list_directory | 0 | wrong: 12331 |
| 7 | q7-control-lines | 8 | read_file > list_directory > read_file > list_directory > read_file > list_directory > read_file > list_directory | 0 | wrong: 12331 |
| 8 | q7-control-lines | 8 | read_file > list_directory > read_file > list_directory > read_file > list_directory > read_file > list_directory | 0 | wrong: 12331 |
| 9 | q7-control-lines | 8 | read_file > list_directory > read_file > list_directory > read_file > list_directory > read_file > list_directory | 0 | wrong: 12331 |
| 10 | q7-control-lines | 8 | read_file > list_directory > read_file > list_directory > read_file > list_directory > read_file > list_directory | 0 | wrong: 12331 |

## 6. What this does not establish

- **Why q4, q6 and q5 moved.** No control was run. I cannot attribute them to the base, the session or the commit.
- **Whether temperature 0 is deterministic across sessions.** Within this run, q1, q2, q3, q4, q6 and q7 each gave one answer
  and one tool sequence in all ten passes; q5 did not (clock input). Across sessions the evidence is that it is not.
- **Anything about `list_directory`'s change.** It does not exist yet; `1ce7c81` measures `read_file` alone.
- **Whether a different wording of the error, or the count in a different place, would be used.** One wording was tested.
- **Why the model ignores a number in an observation**, or where "12331" comes from.
- **The q5 classification** is by pattern (a dollar figure, or "is N"), reproducing the hand reading at baseline (6 invented,
  4 declined) and not an oracle.
- **The sealed bank, other commits, models, machines or days.**

## 7. Options for the owner

**A: Run the control at `1384d63`** (70 runs, same runner and discipline, about 16 minutes of model time, about 1.5 points
of reading and writing). It separates the base and the session from SE's commit for q4, q6 and q5. Carried out by the
**AI/ML chair**. Recommended, because without it the q4 and q6 movement cannot be read at all.

**B: Stop expecting a better error message to fix line counts, and choose a different mechanism.** The model ignores
the count even when it is correct and adjacent. The candidates: make the count appear where the model already looks (the
`file_info` result it never calls for this question), which is a tool-text or prompt decision for the **SE chair** after the
owner rules; or teach the behaviour with synthetic examples that quote the count from the error, which is a training-data
decision for the **AI/ML chair** after the owner rules, nothing automatic.

**C: Hold Part 2 (`list_directory`) until A is read.** q4 and q6 moved on their own, so a Part 2 measurement would be
confounded in the same way. Carried out by the **SE chair** after the owner rules.

**D: Reword the `tools.py` comment so it carries neither figure** (the likeliest carrier of 278 and 10,306 into the data).
It cannot change this model's answers; it keeps the figures out of future data. Carried out by the **SE chair**,
low priority, separate from brief 31.

---

`QA: 4 findings (0 Critical / 2 High / 2 Medium / 0 Low) - 4 reproduced - not tested: the cause of the q4/q6/q5 movement (no control run), another wording of the error, the list_directory change, cross-session determinism, where "12331" comes from; the q5 classification is by pattern, not an oracle`
