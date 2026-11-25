# Prediction for SE brief 39 (`1125e9c`) against its parent (`b860ead`), written before any request

**From:** AI/ML engineer · **2026-11-25** · branch `aiml/brief34-measure-20261124`. Instruction acted on (PM 01, relaying the owner's
"A: Measure first" for SE brief 39): measure `se/brief-39-stray-args-hint @ 1125e9c6c06bfa0aa6af2845550f823d7e930ccf` against its own
parent `b860ead` as an adjacent pair, one server session, prediction first; my stop line is the owner's 40%. The SHAs under test
pre-exist this file (SE wrote them); I have not run either.

## What changed, as I read it (MEASURED by `git diff b860ead 1125e9c`, `tools.py` +50 lines and one new test file)

When `read_file` or `file_info` fails as "no such file" and the input is `<path>` followed by one or two integers (ASCII digits,
optional leading "-", spaces or tabs), and `<path>` passes the very same sandbox call, the error gains
". Did you mean <path>? Call <tool> again with the path only (Action Input: <path>), no line numbers." Otherwise the message is
unchanged. No tool description, no system prompt.

## Design (the session-2 design, unchanged so the pair is comparable)

- Runner `scripts/second_file_measurement.py`, fixed grader (`99a53ba` and the follow-up test rows), wording **W1** "How many lines are
  in the file {file}?", `--temperature 0`, `--max-steps 8`, ten files x 2 passes x 2 arms = 40 runs, one server session (the one I
  restarted yesterday; no restart now), arms interleaved per file, first arm alternating. Trees `aie-measure-b860ead` (parent) and
  `aie-measure-1125e9c` (child): clean, no `__pycache__`, root listings identical (checked), the ten files byte-identical in both commits.
- Files, same order as before: the six that reached the text before (`config.py`, `dataset_provenance.py`, `main.py`,
  `export_dataset.py`, `sandbox.py`, `agent.py`, the **controls**) and the four whose first call carried stray arguments
  (`observability.py`, `dataset_limits.py`, `validate_dataset.py`, `config_inspection.py`, the **targets**).
- **Hint accounting** from the stored raw outputs by `scripts/count_hints.py` (13 tests; three mutants of its guards each go red):
  *shown* = an observation containing "Did you mean"; *expected* = a `read_file`/`file_info` step whose input is `<path> <int> [<int>]`,
  whose observation starts "Error: no such file:", and whose path is an existing regular file inside the tree; *unexpected* = shown but not
  expected; *missing* = expected but not shown. Row fields are the runner's (first call input, reached, `file_info`, answer, correct).
- Lock before the first request, removed on exit; a watcher logs `/api/ps`.

## Predictions

| Event | Probability |
| --- | --- |
| Parent arm: hint shown in 0 of 40 runs (the parent has no such text) | **99%** |
| Child arm: **unexpected** hints (shown where none was expected) = 0 | **97%** |
| Child arm: **missing** hints (expected, not shown) = 0 | **90%** |
| The child's first call carries stray arguments in at least one run of at least 2 of the 4 targets (it is decided before the arm's text, so the parent's is the same) | **80%** |
| Of child runs whose first call had stray arguments on an existing file: the hint is shown | **93%** |
| ... then the next call is `read_file` with the path only | **70%** |
| ... then the oversize error is reached, `file_info` is called, and the answer is correct | **55%** of the stray-first-call runs (reach 70% x then 80%) |
| Child, targets: correct in at least 1 of 2 runs on **3 or more of the 4** files | **55%**; all 4: **30%**; at most 1 of 4: **15%** |
| Parent, targets: `observability.py` and `config_inspection.py` correct in 0 of 4 runs | **85%** (`dataset_limits.py` and `validate_dataset.py` can be right unaided, as before: parent correct on at least 1 of their 4 runs: 70%) |
| Controls (first call path-only in both arms): parent and child identical in answer and tool sequence | **90%** |
| A control whose first call is stray in this session (as `dataset_provenance.py` once was): the child differs from the parent there, which is the commit's effect and not a regression | **expected, not counted against SE** |
| Within an arm pass 2 differs from pass 1 for at least one file (T=0 nondeterminism, 5 and 6 file-arms in the two earlier sessions) | **80%** |
| The arms are indistinguishable on the four targets (no hint, no gain) | **12%** |

- **Improvement** = more child than parent correct answers on the four targets in the same session, with hints shown in the child's
  observations; **regression** = a control whose first call is path-only getting a different answer in the child, or any hint where
  none was expected.
- **What would surprise me:** a hint on a path that should not be confirmed (it must be 0); a child run that shows the hint and then
  repeats the same stray call; a control with a path-only first call that changes between arms; the parent reaching `file_info` on
  `observability.py` or `config_inspection.py`.
- I will report counts only, per file and arm: first call's input, hint shown, reached, `file_info`, correct, and whether
  nondeterminism across passes changed anything; and I will say plainly if the arms are indistinguishable.
