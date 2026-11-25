# Prediction for the repeat of the brief 39 pair in a restarted server session, written before any request

**From:** AI/ML engineer · **2026-11-25** · branch `aiml/brief34-measure-20261124`. Instruction acted on (PM 01, relaying the owner's
"A: FF, then repeat"): "repeat the brief 39 pair in a NEW server session. Restart only the Ollama server process again ... Same design:
ten files x 2 passes x 2 arms, W1, T=0, fixed grader, interleaved per file, clean trees ... Prediction first, pushed to BOTH remotes".
My stop line is the owner's 40% (meter 37% at the start). The first session's result is `2491b4a`; this file is not edited afterwards.

## Design (identical to the first pair, apart from the server process)

Runner `scripts/second_file_measurement.py`, hint counter `scripts/count_hints.py`, trees `aie-measure-b860ead` (parent, now the old integration
tip) and `aie-measure-1125e9c` (child, now the integration tip), W1 "How many lines are in the file {file}?", `--temperature 0`,
`--max-steps 8`, the same ten files in the same order (four targets: `observability.py`, `dataset_limits.py`, `validate_dataset.py`,
`config_inspection.py`; six controls), 2 passes, 40 runs. Before the run: `__pycache__` removed, both trees clean (the runner aborts
otherwise), root listings identical (the runner aborts otherwise). The Ollama server process I started is stopped and started again;
version `0.40.16` and digest `05ba6fe701c5cb9d` read before and after. Lock before the first request, removed on exit.
Per arm there are 20 runs (10 files x 2 passes): I state totals per arm, not out of 40.

## Predictions

| Event | Probability |
| --- | --- |
| Parent: hint shown in 0 of 20 runs | **99%** |
| Child: 0 unexpected hints (including 0 where the first call is the bare file name) and 0 missing | **93%** |
| The set of stray first calls differs from the first session's (the first call is nondeterministic across sessions) | **85%** |
| Stray first calls (on an existing file) per arm in this session: median 8, range 3 to 13; pooled with session 1's 11 per arm | 8 |
| At least 3 of the 4 targets see the hint in the child in at least one run | **75%**; all 4: **50%** |
| At least 3 of the 4 targets reach the oversize text in the child in at least one run (hint, then the exact path) | **55%** |
| `dataset_limits.py`: the stem failure (`read_file` with `dataset_limits`, no extension, after the hint) repeats in at least one run | **40%** (it needs a stray first call AND the same slip; it was 2 of 2 last time) |
| `dataset_limits.py` is correct in at least 1 of 2 child runs | **60%** (including the case of a bare first call) |
| Controls whose first call is the bare file name: identical answers and tool sequences in both arms | **90%** |
| Controls correct in both arms on every run where the first call is the bare name | **90%** |
| Child correct overall at least 17 of 20 | **60%**; at least as many as the parent: **80%** |
| Pooled over both sessions, correct on stray first calls: child at least 70% | **70%**; parent at most 60%: **75%** |
| Digest and version identical before and after the restart | **95%** |

- **What would surprise me:** a hint where none belongs; a child run that shows the hint and then fails on a target it passed last time
  for a reason other than the stem slip; the parent beating the child overall by 2 or more.
- **How I will read it:** the pooled stray-first-call table (both sessions) is the headline; a single session's counts are a direction. If
  the stem failure repeats on `dataset_limits.py` I say so and it goes to SE as a separate brief, not as a change to the hint here.
- Counts only, in one result file; per file and arm: first call, hint (runs and occurrences), reached, `file_info`, correct, the stem
  failure if it shows, and the pooled table with the number of stray first calls in each session.
