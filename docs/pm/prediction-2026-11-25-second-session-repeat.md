# Prediction for the repeat of the ten-file test in a restarted server session, written before any request

**From:** AI/ML engineer · **2026-11-25** · branch `aiml/brief34-measure-20261124`. Instruction acted on (PM 01, relaying the owner's
"A: Fix + repeat, parallel"): "C: repeat the six reaching files ... same wording W1, 2 passes, both arms interleaved, in a NEW server
session: restart only the Ollama server process ... prediction first, pushed to BOTH remotes, then the run." My own stop line is 40%
(owner, in this chat). The first session's result is `0f67918`; the grader fix is a separate commit before this file, so this run is graded
by the fixed `grade()` and the first result stays readable as printed.

## Design

- Same runner (`scripts/second_file_measurement.py`), same trees (`aie-measure-1384d63` parent, `aie-measure-45cbd0e` child, both
  clean, no `__pycache__`, identical root listings), same wording **W1** "How many lines are in the file {file}?", `--temperature 0`,
  `--max-steps 8`, 2 passes, arms interleaved per file with the first arm alternating, `PYTHONDONTWRITEBYTECODE=1`.
- **Files: the same ten as the first session, in the same order** (the six that reached the text first, then the four that did not).
  PM asked for the six and "the four only if cheap": 16 more runs is about four minutes, so I run all ten (40 runs). The six are the
  primary result.
- **What is new:** the Ollama server process is stopped and started again (the process I started; model files untouched). I read the
  version and the `omniagent-v2:latest` digest before and after (expected 0.40.16 and `05ba6fe701c5cb9d`; a different digest voids the
  comparison). Nothing else loads a model; the lock is created before the first request and removed on exit.
- Row fields as before. Correctness is graded by the fixed grader and I will also state the first session's numbers recomputed with it.

## Predictions

| Event | Probability |
| --- | --- |
| Child arm, six first-session reaching files: `file_info` called in 12 of 12 | **80%** |
| Child arm, same six: correct in 12 of 12 (fixed grader) | **75%** |
| Child arm, same six: correct in at least 10 of 12 | **90%** |
| Parent arm, same six: `file_info` called in 0 of 12 | **85%** |
| Parent arm, same six: correct in 0 of 12 | **90%** |
| The same six files reach the oversize text in both arms (first call is path-only or a path the tool accepts) | **75%** |
| For each of the six files and each arm, the answers and the tool sequence equal the first session's | **60%** (the parent's wrong answers, "1"/"20" and "100", are the likeliest to move) |
| A restart changes nothing about the headline count (parent 0/12 `file_info`, child 12/12) | **75%** |
| Of the four first-session non-reaching files, at least 3 still do not reach the text | **80%** |
| On the four, the arms differ somewhere again | **55%** (the root listing still differs in `tools.py`'s byte size) |
| The digest and version are identical before and after the restart | **95%** |

- **What would surprise me:** a child run on one of the six that reaches the text but does not call `file_info`; a file that
  reached the text in session 1 and does not now (the first call is decided by the wording, not by the arms, so that would be session
  nondeterminism at the first step); the parent calling `file_info` on a reaching file.
- **How I will read the result:** child 12/12 and parent 0/12 again means the effect survived a restart (one more server session,
  still the same card, trees and wording). Anything else is reported with the file and arm, and a restart that changed a count is said
  plainly, not averaged away.
- Counts only, in one result file; per file and arm: reached, `file_info`, correct, and whether the answers match the first session's.
