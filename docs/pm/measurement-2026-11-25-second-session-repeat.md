# Result: the ten-file test repeated in a restarted server session, counts only

**From:** AI/ML engineer · **2026-11-25** · branch `aiml/brief34-measure-20261124`. Prediction (not edited):
`docs/pm/prediction-2026-11-25-second-session-repeat.md`, in `75e69b9`, on both remotes before any request. Instruction acted on (PM 01,
relaying the owner's "A: Fix + repeat, parallel"): repeat the reaching files, wording W1, 2 passes, both arms interleaved, in a NEW
server session. **MEASURED** 2026-11-25, 17:24 to 17:37. I stopped the Ollama server process I had started (PID 3848) and started it
again (PID 20812); model files untouched. Version `0.40.16` and `omniagent-v2:latest` digest `05ba6fe701c5cb9d` before and after, both
unchanged. Same runner, same two trees (clean, no `__pycache__`, root listings equal before and after), `--temperature 0`,
`--max-steps 8`, 40 runs = the **same ten files** as session 1 (the PM said the four non-reaching ones only if cheap; they cost four
minutes). Every row: `commit` `1384d63` x20, `45cbd0e` x20, `tree_clean: true`, exit code 0 in all 40, no blank answer. The watcher
saw only `omniagent-v2`. Lock created before the first request, removed on exit (verified gone). **Graded by the fixed `grade()`
(`99a53ba`)**; session 1 is shown both as printed and regraded the same way, from its stored raw outputs.

## Counts per file and arm (2 runs each; S2 = this session, S1 = first session)

`rch` = the oversize error was in the trace, `fi` = `file_info` called, `ok` = correct under the fixed grader.

| File (lines) | Arm | S2 rch · fi · ok | S1 rch · fi · ok (regraded) | Answers and tool sequences equal to S1? |
| --- | --- | --- | --- | --- |
| `config.py` (302) | parent | 2 · 0 · 0 | 2 · 0 · 0 | yes |
| | child | 2 · **2** · **2** | 2 · 2 · 2 | yes |
| `dataset_provenance.py` (200) | parent | **1** · 0 · 0 | 2 · 0 · 0 | **no** |
| | child | **1** · **1** · **1** | 2 · 2 · 2 | **no** |
| `main.py` (370) | parent | 2 · 0 · 0 | 2 · 0 · 0 | **no** (parent only; still wrong) |
| | child | 2 · 2 · 2 | 2 · 2 · 2 | yes |
| `export_dataset.py` (459) | parent | 2 · 0 · 0 | 2 · 0 · 0 | yes |
| | child | 2 · 2 · 2 | 2 · 2 · 2 | yes |
| `sandbox.py` (477) | parent | 2 · 0 · 0 | 2 · 0 · 0 | yes |
| | child | 2 · 2 · 2 | 2 · 2 · 2 | yes |
| `agent.py` (1,330) | parent | 2 · 0 · 0 | 2 · 0 · 0 | yes |
| | child | 2 · 2 · 2 | 2 · 2 · 2 | yes |
| `observability.py` (353) | parent / child | 0 · 0 · 0 / 0 · 0 · 0 | same | yes / yes (first call `observability.py 0 100`, answer "12331") |
| `dataset_limits.py` (97) | parent / child | 0 · 1 · 1 / 0 · 1 · 1 | same | yes / yes |
| `validate_dataset.py` (332) | parent | 0 · **2** · **2** | 0 · 1 · 1 | **no** |
| | child | 0 · 2 · 2 | 0 · 2 · 2 | **no** (a variant of the same answers) |
| `config_inspection.py` (642) | parent | 0 · 0 · 0 | 0 · 0 · 0 | **no** (the same two answers, "25909" once and none once, but not the same passes and sequences) |
| | child | 0 · 0 · 0 | 0 · 0 · 0 | yes |

## Totals on the six files that reached the text in session 1

| | Reached the text | `file_info` called | Correct (fixed grader) | Correct (as printed) |
| --- | --- | --- | --- | --- |
| Parent, S1 | 12 of 12 | 0 | 0 | 0 |
| Child, S1 | 12 of 12 | 12 | **12** (printed 10) | 10 |
| Parent, S2 | **11 of 12** | 0 | 0 | 0 |
| Child, S2 | **11 of 12** | 11 | **11** | 11 |

**On the runs that did reach the text, the child called `file_info` and was correct in 11 of 11; the parent in 0 of 11.**

## Did the restart change anything? Yes, three things, plainly

1. **One run no longer reached the text, in both arms:** for `dataset_provenance.py`, one pass's first call carried an extra argument
   (`dataset_provenance.py -1 -1`) and returned "no such file". Both arms did it (the first call is decided before any arm-specific text
   exists), so it is session nondeterminism at the first step, not the arms. Hence the child's 11 of 12 and the parent's 11 of 12 reaching.
2. **The parent's wrong answers moved:** `main.py` (one run now answers with no number), and `validate_dataset.py`, where the parent now
   called `file_info` and answered 332 in 2 of 2 (1 of 2 in S1) after a malformed first call, a `list_directory` and a second read. So the
   parent can reach `file_info` unaided on a path that never shows the changed text, and that path is not the text's effect.
3. **Nothing moved on the other nine of the twelve (file, arm) pairs of the six, nor on `observability.py` and `dataset_limits.py`.** The arms still
   differ on one non-reaching file (`config_inspection.py`: parent "25909" once, child none), as in S1.

The version, the digest, the trees and the wording were identical; only the server process (and what it carries between requests) was new.

## Scoring my prediction (wrong parts included)

| Prediction | Outcome |
| --- | --- |
| Child, six files: `file_info` in 12 of 12 (80%) | **No: 11 of 12** (one run did not reach the text). |
| Child, six files: correct in 12 of 12 (75%); at least 10 of 12 (90%) | **No for 12 of 12; yes for at least 10:** 11 of 12. |
| Parent, six files: `file_info` in 0 of 12 (85%); correct in 0 of 12 (90%) | Held: 0 and 0. |
| The same six files reach the text in both arms (75%) | **No:** 11 of 12 runs; one `dataset_provenance.py` pass did not. |
| Per file and arm, answers and tools equal S1 (60%) | **No:** `dataset_provenance.py` (both arms), `main.py` (parent), `validate_dataset.py`, `config_inspection.py` (parent) differ. |
| A restart changes nothing about the headline count (75%) | **Half:** parent 0/12 held; child 12/12 became 11/12 (the missing run never saw the text). |
| At least 3 of the 4 first-session non-reaching files still do not reach it (80%) | Held: 4 of 4. |
| On those four, the arms differ somewhere again (55%) | Held, narrowly: one of four (`config_inspection.py`). |
| Digest and version identical before and after (95%) | Held. |

## What this does and does not establish

- **Established (two server sessions, one card, W1 wording, six files, 200 to 1,330 lines):** when the first call is well-formed and
  the oversize error appears, the child calls `file_info` and reports the true count (23 of 23 runs across both sessions) and the parent
  does neither (0 of 23). The effect survived a restart; what did not survive is *whether a given first call is well-formed*: that is
  the stray-argument problem, and it moves between sessions.
- **Not established:** the effect when the first call is malformed (where the parent can also reach `file_info` unaided), a third
  session, other files outside the repository root, other question types. The cause of the remaining arm differences on non-reaching
  files (the root listing's `tools.py` byte size) is still **UNVERIFIED**.
