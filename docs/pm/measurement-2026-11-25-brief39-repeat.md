# Result: the brief 39 pair repeated in a restarted server session, counts only

**From:** AI/ML engineer · **2026-11-25** · branch `aiml/brief34-measure-20261124`. Prediction (not edited):
`docs/pm/prediction-2026-11-25-brief39-repeat.md`, in `f7c5b49`, on both remotes before any request. Instruction acted on (PM 01, relaying the
owner's "A: FF, then repeat"): repeat the brief 39 pair in a NEW server session, same design. **MEASURED** 2026-11-25, 18:53 to 19:07. I stopped and
started the Ollama server process I had started (PID 20812 to 10824), model files untouched; version `0.40.16` and `omniagent-v2:latest` digest
`05ba6fe701c5cb9d` before and after, unchanged. Same runner, hint counter, trees (`b860ead` parent, `1125e9c` child; `__pycache__` removed, clean,
root listings identical before and after), W1 wording, `--temperature 0`, `--max-steps 8`, the same ten files in the same order, 2 passes,
fixed grader. 40 runs: 20 per arm; every row `commit` `b860ead` x20 / `1125e9c` x20, `tree_clean: true`, exit 0 in 40 of 40, no blank. The
watcher saw only `omniagent-v2`; lock before the first request, removed on exit (verified gone).

## The headline: the restarted session reproduced the first session exactly

I compared the two sessions' rows field by field (arm, commit, pass, file, exit code, steps, tool sequence, first call's input, reached,
`file_info`, blank, answer numbers, expected, correct): **0 of 40 rows differ.** The 40 raw output files are **byte-identical**, 40 of 40.
They are two real runs (different clock times, different per-run seconds: median 18.2 and 22.2), not a re-read of the old files.

So the first-call nondeterminism seen between sessions earlier (the ten-file test and its restart) did **not** occur here. **The repeat is
therefore not an independent sample of the stray-call set:** the stray first calls are the same 11 per arm as in the first session, and
pooling the two sessions would count the same 11 runs twice. The pooled table below says so rather than doubling the numbers.

## Counts per file and arm (identical in both sessions; 2 passes each)

First call = pass 1 / pass 2. Hint = runs with a hint / occurrences (a run can show it twice). `rch` = the oversize error reached, `fi` = `file_info` called.

| File (lines) | Arm | First call | Hint runs / occurrences | rch | fi | Correct |
| --- | --- | --- | --- | --- | --- | --- |
| `observability.py` (353) target | parent | `... 0 100` / `... 0 100` | 0 / 0 | 0 | 0 | 0/2 |
| | child | same | **2 / 2** | 2 | 2 | **2/2** |
| `dataset_limits.py` (97) target | parent | `... 0 100` / `... -1` | 0 / 0 | 0 | 1 | 1/2 |
| | child | `... -1` / `... -1` | **2 / 2** | **0** | **0** | **0/2, stem failure in 2 of 2** |
| `validate_dataset.py` (332) target | parent | `... -1` / `... -1` | 0 / 0 | 0 | 2 | 2/2 |
| | child | same | **2 / 4** | 0 | 2 | 2/2 |
| `config_inspection.py` (642) target | parent | `... -1 -1` / `... -1 -1` | 0 / 0 | 0 | 0 | 0/2 |
| | child | same | **2 / 2** | 2 | 2 | **2/2** |
| `export_dataset.py` (459) control | parent | `... 1` / `... 1` | 0 / 0 | 2 | 2 | 2/2 |
| | child | same | 2 / 2 | 2 | 2 | 2/2 |
| `dataset_provenance.py` (200) control | parent | `... -1 -1` / bare | 0 / 0 | 1 | 1 | 1/2 |
| | child | bare / `... -1 -1` | 1 / 1 | 2 | 2 | 2/2 |
| `config.py`, `main.py`, `sandbox.py`, `agent.py` controls | parent / child | bare name, both passes | 0 / 0 · 0 / 0 | 2 · 2 | 2 · 2 | 2/2 · 2/2 each |

**Stem failure** (after "Did you mean dataset_limits.py?" the model calls `read_file` with `dataset_limits`, no extension, then two empty-path
calls, and answers that the file does not exist): **2 of 2 child runs on `dataset_limits.py`, as in the first session.** It is the only miss in
the child's 20 runs.

## Totals and the pooled table

- **Hints:** parent 0 shown in 20 runs. Child 11 runs show a hint, 13 occurrences, **0 unexpected, 0 missing**, and **0 where the first call is the bare name.**
- **Per arm, all 20 runs:** child correct 18, parent correct 14 (same as the first session, because the runs are the same).
- **Stray first calls on an existing file:** 11 per arm; correct on them: child 9 of 11, parent 5 of 11.

| Pool | Independent stray first-call runs per arm | Child correct | Parent correct |
| --- | --- | --- | --- |
| First session (`2491b4a`) | 11 | 9 | 5 |
| This session (identical to it) | 0 new | 0 new | 0 new |
| **Pooled, de-duplicated** | **11** | **9 (82%)** | **5 (45%)** |

## Scoring my prediction (wrong parts included)

| Prediction | Outcome |
| --- | --- |
| Parent hint shown in 0 of 20 (99%); child 0 unexpected, 0 missing (93%) | Held. |
| The stray first-call set differs from the first session's (85%) | **Wrong: identical.** I expected cross-session nondeterminism and this restart gave none. |
| Stray first calls per arm: median 8, range 3 to 13 | 11, inside the range. |
| At least 3 of 4 targets see the hint in the child (75%); all 4 (50%) | 4 of 4. |
| At least 3 of 4 targets reach the oversize text in the child (55%) | **Wrong: 2 of 4** (`observability.py`, `config_inspection.py`). A third, `validate_dataset.py`, reached `file_info` with the exact path without the oversize error. |
| `dataset_limits.py` stem failure repeats in at least one run (40%) | **Yes, 2 of 2.** |
| `dataset_limits.py` correct in at least 1 of 2 child runs (60%) | **No, 0 of 2.** |
| Controls with a bare first call identical between arms (90%); correct in both (90%) | Held. |
| Child correct at least 17 of 20 (60%); at least the parent (80%) | Held (18 against 14). |
| Pooled, correct on stray calls: child at least 70% (70%); parent at most 60% (75%) | Held (82%; 45%), on 11 runs, not 22. |
| Digest and version identical before and after (95%) | Held. |

## What this does and does not establish

- **Established:** the result of the first pair is reproducible after a server restart on this card, exactly (40 of 40 raw files byte-identical). The hint
  counts (13 of 13, none unexpected) and the `dataset_limits.py` stem failure reproduce.
- **Not established:** independence. Two identical sessions are one observation of the stray-call set; whether a different card, a different Ollama
  version, a different wording or another day gives a different set is untested, and the earlier ten-file test showed a restart can change it. Files
  outside the repository root and the refused-candidate branch of the hint remain untested.
- **For SE (a separate brief, not a change to the hint here):** the model drops the extension after the hint on `dataset_limits.py`; that is where
  the remaining child miss is.
