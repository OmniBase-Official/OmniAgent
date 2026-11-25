# Result: the next-call sentence on ten files (brief 34, second-file test), counts only

**From:** AI/ML engineer · **2026-11-25** · branch `aiml/brief34-measure-20261124`. Prediction (not edited):
`docs/pm/prediction-2026-11-24-second-file-test.md`, in `a77e798`, on both remotes before any request. Instruction acted on: the
owner, typing in the AIE chat, set the weekly stop line at 40% and said to run the second-file test as the PM sent it. **MEASURED** by me
on 2026-11-25, 16:52 to 17:09, one Ollama 0.40.16 session, `omniagent-v2:latest` digest `05ba6fe701c5cb9d`; runner tip `d2bd673`.
40 runs: 10 files x 2 passes x 2 arms, `--temperature 0`, `--max-steps 8`; every row has `commit` (`1384d63` x20, `45cbd0e` x20),
`tree_clean: true`, temperature 0.0. Both trees had their ignored `__pycache__/` removed beforehand; the runner checked the two root
listings equal before and after. The `/api/ps` watcher saw only `omniagent-v2`; lock created before the probe and again before the run,
removed each time (verified gone). Raw outputs are local and uncommitted.

## The wording probe (unscored, untimed, not a measurement)

One step in the parent tree on the two held-out files `pyproject.toml` and `README.md`. **W0** ("How many lines does {file} have?") was
refused by the runner's bank check on the probe files (a banked question matched), so **W0 was not run and there is no data for it**; it
is therefore not the first candidate with data. **W1, W2 and W3 each gave a path-only first call on both files.** By the registered
rule I took the first candidate with data, **W1: "How many lines are in the file {file}?"**, for every file and both arms. That departs from the
rule's letter only in that W0 could not be tried.

## Counts per file and arm (2 runs each; `fi` = `file_info` called; `rch` = the oversize error was reached)

| File (true lines) | First call's input (both arms) | rch parent / child | `fi` parent / child | Answers parent | Answers child | Correct parent / child |
| --- | --- | --- | --- | --- | --- | --- |
| `config.py` (302) | `config.py` | 2/2 · 2/2 | 0 · **2** | none (no number) | "302" x2 | 0/2 · **2/2** |
| `dataset_provenance.py` (200) | `dataset_provenance.py` | 2/2 · 2/2 | 0 · **2** | none | "200" x2 | 0/2 · **2/2** |
| `main.py` (370) | `main.py` | 2/2 · 2/2 | 0 · **2** | "1", "20" (a line range) x2 | "370" x2 | 0/2 · **2/2** |
| `export_dataset.py` (459) | `export_dataset.py 1` | 2/2 · 2/2 | 0 · **2** | "20" x2 | "459" x2 | 0/2 · **2/2** |
| `sandbox.py` (477) | `sandbox.py` | 2/2 · 2/2 | 0 · **2** | "100" x2 | "477" x2 | 0/2 · **2/2** |
| `agent.py` (1,330) | `agent.py` | 2/2 · 2/2 | 0 · **2** | none | "1,330" x2 | 0/2 · **2/2** (runner printed 0/2, see below) |
| `observability.py` (353) | `observability.py 0 100` | **0/2** · 0/2 | 0 · 0 | "12331" x2 | "12331" x2 | 0/2 · 0/2 |
| `dataset_limits.py` (97) | `dataset_limits.py -1` or `... 0 100` | **0/2** · 0/2 | 1 · 1 | "97" once, none once | "97" once, none once | 1/2 · 1/2 |
| `validate_dataset.py` (332) | `validate_dataset.py -1 -1` or `-1` | **0/2** · 0/2 | 1 · 2 | "13363" and "332" | "332" x2 | 1/2 · 2/2 |
| `config_inspection.py` (642) | `config_inspection.py -1 -1` | **0/2** · 0/2 | 0 · 0 | "25909" once, none once | none x2 | 0/2 · 0/2 |

(`expected` came from `git show HEAD:<file>` in each tree, identical at both commits. Exit code 0 in all 40 rows; no blank answer.)

## What the counts say

1. **Six of the ten files reached the changed text** (the oversize error was in the trace): `config.py`, `dataset_provenance.py`, `main.py`,
   `export_dataset.py`, `sandbox.py`, `agent.py`, in both arms and both passes. **The other four reached nothing** (the first call carried an
   extra invented argument, `-1`, `0 100`, `-1 -1`, and returned "no such file"), plus the earlier `observability.py`; those four say
   nothing about the text.
2. **On the six that reached it:** parent `file_info` called in **0 of 12** runs, child in **12 of 12**; parent correct in **0 of 12**, child
   correct in **12 of 12**. Sizes 200 to 1,330 lines; no file where the child did not follow the call. No run called `file_info` and
   then answered wrongly.
3. **Runner artefact, disclosed:** the as-run grade has `agent.py` child at 0/2 because the model wrote "1,330" and `grade()` requires the
   bare token; I recounted from the stored answer numbers (the answer line reads "There are 1,330 lines in the file agent.py." in
   both child runs). The as-run total for the child on the six files is 10 of 12; the recounted one is 12 of 12. I did not change the grader
   and a thousands-separator tolerance is a tests-first change for later.
4. **Files that did not reach the text still differ between arms in two places** (`validate_dataset.py`: parent `file_info` 1/2 and answers
   "13363" and "332", child 2/2 and "332"; `config_inspection.py`: parent "25909" once). The text cannot cause these (it was never shown).
   What I can say: the listing of the tree root shown by `list_directory` differs in the byte size of `tools.py` between the arms,
   and "13363", "25909" are those files' on-disk byte sizes as a listing prints them (13,031 bytes in git plus 332 carriage returns; 25,267 plus 642): the model again read a size as a line count. That the listing difference is the cause of the arm split is **UNVERIFIED**.
5. **Within an arm the second pass repeated the first on the six reaching files** (same tools, same answers); it did **not** on
   `dataset_limits.py` (both arms), `validate_dataset.py` (both arms) and `config_inspection.py` (parent): temperature 0 gave different
   first-call inputs on different passes there. These are all files where the text was not reached.

## Scoring my prediction (wrong parts included)

| Prediction | Outcome |
| --- | --- |
| At least one of W0 to W3 path-only on both probe files: 75% | Held (W1, W2, W3). W0 (35%) could not be run (bank refusal). |
| Files reaching the text: median 7, range 4 to 10 | **6 of 10**, in range. |
| `config.py` reaches in every run of both arms: 90% | Held (4 of 4). |
| Parent calls `file_info` in any run on any file: 10% | **Wrong as stated:** 2 of 40 parent runs (`dataset_limits.py`, `validate_dataset.py`), both on files that never reached the text. On the files that did: 0 of 12, which is what I meant. |
| Parent correct on 2 or more reaching files: 10% | Held: 0. |
| Child `file_info` in at least 80% of reaching files: 55% | Held (12 of 12). I was too cautious. |
| Child correct on at least 80% of reaching files: 45% | Held (12 of 12 recounted; 10 of 12 as printed). |
| A child run calls `file_info` and answers wrongly: 25% | Did not happen (the one apparent case is the grader). |
| Second pass repeats the first, for every file: 80% | **Wrong:** 5 file-arms differed, all on files that never reached the text. |
| Root listings of the two trees stay identical, no q7-style divergence: 85% | Listings were identical (checked); `observability.py` arms agreed. But two non-reaching files still differ between arms (item 4), so the divergence did not fully disappear. |
| Improvement = child correct more than parent on at least 3 reaching files | **Met: 6 of 6 files.** |

## What this does and does not establish

- **Established (one session, two passes, six files that reached the text, 200 to 1,330 lines):** the closing sentence of the oversize
  error, with the exact `Action: file_info, Action Input: <path>`, makes the model call `file_info` and report the true count; the same
  session's parent arm did neither on any of those files. The effect is not confined to `config.py`.
- **Not established:** behaviour when the first call is malformed (4 of 10 files with this wording, and `observability.py`: those never see
  the text and mostly answer wrongly in both arms), a second server session, files outside the repository root, and other question
  types. Whether the stray numeric arguments (`-1`, `0 100`) are a property of the tool's input handling or of the wording is not tested.
