# Prediction for the second-file test of brief 34, written before any request

**From:** AI/ML engineer · **2026-11-24** · branch `aiml/brief34-measure-20261124`. Instruction acted on (PM 01, relaying the
owner's choice of option A): "run the second-file test ... several other oversize files ... 1 to 2 passes each per arm, the parent
arm now 1384d63 and the child 45cbd0e, interleaved in ONE session"; probe wording "WITHOUT scoring (a few untimed runs, say so)".
Nothing is requested from the model until this file is on both remotes. The SHAs under test (`1384d63`, `45cbd0e`) pre-exist it.

## What this test is for

The pair at `d227107` showed the next-call sentence working on `config.py` only (0/10 to 10/10), and q7 never reached the text, so
"works beyond one file" is untested. At temperature 0 ten passes of one file are one observation; this spends the runs on files.

## Fixed in advance (so I cannot tune them to the result)

- **Measured files (10, all at the repository root, none sealed, none in a bank):** `config.py` (302 lines, the known positive),
  `observability.py` (353; failed with a malformed first call before), `dataset_limits.py` (97), `dataset_provenance.py` (200),
  `validate_dataset.py` (332), `main.py` (370), `export_dataset.py` (459), `sandbox.py` (477), `config_inspection.py` (642),
  `agent.py` (1,330). All are identical at both commits (`git diff 1384d63 45cbd0e` touches `tools.py` and one new test only) and all
  trigger the oversize error (checked by calling `read_file` on each in the parent tree: 10 of 10 over the 2,400-character render limit).
  True line counts come from `git show <commit>:<file>`, not from the model. `tools.py` is excluded (it differs between the arms).
- **Probe files, not measured:** `pyproject.toml` and `README.md`. The probe runs ONE step in the parent tree (the first call is
  decided before any error text exists, so it cannot depend on the arm) and prints only the first call's input. **Unscored, untimed,
  not a measurement.**
- **Wording candidates, tried in this order, one run per probe file, temperature 0:**
  W0 "How many lines does {file} have?" (the q2/q7 wording) · W1 "How many lines are in the file {file}?" ·
  W2 "Count the lines in {file}." · W3 "What is the line count of the file {file}?"
  **Selection rule:** the first wording whose first call is exactly the path alone on both probe files. If none is, the one with fewest
  malformed first calls (ties: the earlier one). One wording is used for every file and both arms.
- **Design:** 10 files x 2 passes x 2 arms = 40 runs, `--max-steps 8`, temperature 0, one server session, `PYTHONDONTWRITEBYTECODE=1`,
  arms interleaved per file and per pass with the first arm alternating. Both trees had their ignored `__pycache__/` removed (the
  q7-style divergence in the pair was probably a stale one) and the runner aborts unless the two root listings are identical.
  Lock before the first request (probe included), removed on exit.
- **Row:** arm, commit, tree_clean, pass, file, steps, tools, first call's input, **reached** (an `Observation` line that is the
  oversize error), `file_info` called, answer numbers, expected, correct, exit code. No question, no reply.

## Predictions

| Event | Probability |
| --- | --- |
| At least one wording W0 to W3 gives a path-only first call on both probe files | **75%** |
| W0 does | **35%** (it did not for `observability.py`) |
| Of the 10 measured files, the number whose first call is well-formed so the error is **reached** (per arm; the first call is arm-independent): median 7, range 4 to 10 | 7 |
| `config.py` reaches the text in every run, in both arms | **90%** |
| Parent arm: `file_info` called in any run on any file | **10%** |
| Parent arm: correct on 2 or more files that reach the text | **10%** (a small file can be right by luck) |
| Child arm, among the files that reach the text: `file_info` called in at least 80% of them | **55%** |
| Child arm, among the files that reach the text: correct on at least 80% of them | **45%** |
| A child run calls `file_info` and then answers wrongly | **25%** (that would mean the model ignores even a correct count it fetched itself) |
| Within an arm the second pass repeats the first pass's answer and tool sequence, for every file | **80%** |
| The root listings of the two trees stay identical, so the q7-style divergence does not recur | **85%** |

- **Improvement** = among files that reach the text, the child is correct more often than the parent, in the same session, on
  at least 3 files. **A file that does not reach the text says nothing** and is reported as such, not as success or failure.
  **No effect beyond `config.py`** = the child's gain over the parent is confined to `config.py`.
- **What would surprise me:** the child calling `file_info` on a file where the first call was malformed (then the text was not the
  cause); large files (`agent.py`, 1,330 lines) failing while small ones succeed; parent and child differing on a file that
  never reaches the text (a harness artefact again).
- I will report counts only, per file and arm, and say plainly how many of the 10 reached the text.
