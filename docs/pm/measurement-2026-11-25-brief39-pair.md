# Result: SE brief 39 (`1125e9c`) against its parent (`b860ead`), one session, counts only

**Correction, 2026-11-25 (found by the PM's recount):** the first version of this file gave per-arm correct totals as "38 of 40" and "34 of 40" and a parent hint count "of 40"; each arm has 20 runs, so the totals are **child 18 of 20, parent 14 of 20** and the parent hint count is 0 of 20. The per-file counts were right. Fixed below.

**From:** AI/ML engineer · **2026-11-25** · branch `aiml/brief34-measure-20261124`. Prediction (not edited):
`docs/pm/prediction-2026-11-25-brief39-pair.md`, in `c995dd8`, on both remotes before any request. Instruction acted on (PM 01, relaying the
owner's "A: Measure first" for SE brief 39): an adjacent pair, one server session, prediction first; my stop line is the owner's 40%.
**MEASURED** 2026-11-25, 18:26 to 18:40, the Ollama session started yesterday at 17:24 (not restarted for this run), `omniagent-v2:latest`
digest `05ba6fe701c5cb9d`, version 0.40.16, both unchanged at the end. 40 runs = the session-2 design: ten files x 2 passes x 2 arms,
wording W1 "How many lines are in the file {file}?", `--temperature 0`, `--max-steps 8`, arms interleaved per file, first arm alternating,
fixed grader. Every row: `commit` `b860ead` x20, `1125e9c` x20, `tree_clean: true`, exit 0 in 40 of 40, no blank answer. Trees clean with no
`__pycache__`, root listings identical before and after, the ten files byte-identical in both commits. The `/api/ps` watcher saw only
`omniagent-v2` (the hook's qwen had expired first, 18:26:45). Lock created before the first request, removed on exit (verified gone).

**Read this first: `b860ead` already contains brief 34's next-call sentence** (`45cbd0e` is in its history), so the parent arm is the
earlier "child". The six controls are right in both arms for that reason, not because nothing changed.

## Counts per file and arm (2 passes each; `rch` = oversize error reached, `fi` = `file_info` called, `ok` = correct)

First call = the first tool call's input, pass 1 / pass 2. Hint = "Did you mean" in an observation. Hint counts are per run, from the raw outputs
(`scripts/count_hints.py`); "shown/exp" = shown / expected.

| File (lines) | Arm | First call (p1 / p2) | Hint shown/exp | rch | fi | ok |
| --- | --- | --- | --- | --- | --- | --- |
| **`observability.py` (353)** target | parent | `... 0 100` / `... 0 100` | 0/2 | 0 | 0 | **0/2** ("12331") |
| | child | `... 0 100` / `... 0 100` | **2/2** | 2 | 2 | **2/2** ("353", and "12,331 bytes" in the same sentence) |
| **`dataset_limits.py` (97)** target | parent | `... 0 100` / `... -1` | 0/3 | 0 | 1 | **1/2** |
| | child | `... -1` / `... -1` | **2/2** | **0** | **0** | **0/2** ("does not exist": the model dropped the extension, `dataset_limits`) |
| **`validate_dataset.py` (332)** target | parent | `... -1` / `... -1` | 0/4 | 0 | 2 | 2/2 (unaided, as before) |
| | child | `... -1` / `... -1` | **4/4** | 0 | 2 | 2/2 |
| **`config_inspection.py` (642)** target | parent | `... -1 -1` / `... -1 -1` | 0/5 | 0 | 0 | **0/2** (8-step loops) |
| | child | `... -1 -1` / `... -1 -1` | **2/2** | 2 | 2 | **2/2** ("642") |
| `config.py` (302) control | parent / child | `config.py` both passes | 0/0 · 0/0 | 2 · 2 | 2 · 2 | 2/2 · 2/2 |
| `main.py` (370) control | parent / child | `main.py` both passes | 0/0 · 0/0 | 2 · 2 | 2 · 2 | 2/2 · 2/2 |
| `sandbox.py` (477) control | parent / child | `sandbox.py` both passes | 0/0 · 0/0 | 2 · 2 | 2 · 2 | 2/2 · 2/2 |
| `agent.py` (1,330) control | parent / child | `agent.py` both passes | 0/0 · 0/0 | 2 · 2 | 2 · 2 | 2/2 · 2/2 |
| `export_dataset.py` (459) control | parent | `... 1` / `... 1` | 0/2 | 2 | 2 | 2/2 (unaided) |
| | child | `... 1` / `... 1` | **2/2** | 2 | 2 | 2/2 |
| `dataset_provenance.py` (200) control | parent | `... -1 -1` / `dataset_provenance.py` | 0/1 | 1 | 1 | **1/2** |
| | child | `dataset_provenance.py` / `... -1 -1` | **1/1** | 2 | 2 | **2/2** |

(For the two controls with a stray first call, `export_dataset.py` and `dataset_provenance.py`, the stray call is not the target of the
brief but the commit applies to it.)

## Totals

- **Hints:** parent **0 shown** in 40 runs. Child **13 shown, 13 expected, 0 unexpected, 0 missing.** **Hint shown where it should not be: 0.**
- **Runs whose first call had stray arguments (on an existing file):** parent 11, child 11. Correct among them: parent **5 of 11**, child **9 of 11**.
- **After a hint (13 hints in the child):** the very next call was `read_file`/`file_info` with the exact candidate path in **5**; an exact-path
  call came later in the same run in **11 of 13**; the 2 that never did are both `dataset_limits.py` (the model wrote `dataset_limits`, no extension,
  then gave up with "does not exist").
- **All 20 runs per arm:** child correct 18 of 20 (misses: `dataset_limits.py` x2), parent correct 14 of 20 (misses: `observability.py` x2,
  `dataset_limits.py` x1, `dataset_provenance.py` x1, `config_inspection.py` x2).
- **The four path-only controls (`config.py`, `main.py`, `sandbox.py`, `agent.py`):** identical answers and tool sequences in both arms and passes.
- **Nondeterminism across passes changed things:** the first call differs between passes in the same arm for `dataset_limits.py` (parent: `0 100`,
  then `-1`) and `dataset_provenance.py` (parent stray in pass 1, child stray in pass 2), so the arms' stray-call sets are not paired pass by pass;
  with that, 11 and 11 stray runs. Pass 2 differs from pass 1 in an arm for at least those two files and for the parent's `config_inspection.py` tool sequences.

## What the counts say

1. **The hint works where the model follows it:** on three of the four targets the child reaches the oversize text or `file_info` and is correct in
   both passes (`observability.py`, `validate_dataset.py` already right unaided, `config_inspection.py`), against 0/2, 2/2 and 0/2 in the parent.
   The only target the child fails is `dataset_limits.py` (0/2, parent 1/2 on the strength of one run whose first call was different).
2. **No leak and no miss in this session:** 0 unexpected, 0 missing hints.
3. **The arms are distinguishable** (9 of 11 against 5 of 11 on stray first calls; 18 against 14 of 20 per arm), on 40 runs in one session, so read the
   counts as a direction with one real exception, not as a rate.
4. **One failure mode the hint does not cover:** after "Did you mean dataset_limits.py?" the model typed `dataset_limits` (the stem), in
   both passes. That is a model behaviour, not the tool; whether other files do this is not tested.

## Scoring my prediction (wrong parts included)

| Prediction | Outcome |
| --- | --- |
| Parent hint shown in 0 runs (99%; the prediction wrote "0 of 40", the parent has 20 runs) | Held (0 of 20). |
| Child unexpected hints = 0 (97%); missing = 0 (90%) | Held (0 and 0). |
| Stray first call in at least one run of at least 2 of the 4 targets (80%) | Held (all 4). |
| Hint shown in at least 93% of child stray first-call runs | Held (11 of 11). |
| ... then the next call is `read_file` with the path only (70%) | **Wrong as an immediate step:** 5 of 13 hints; 11 of 13 within the run. |
| ... then reach, `file_info`, correct: 55% of stray runs | Close: 9 of 11 correct (82%), higher than I said. |
| Child correct on 3 or more of 4 targets (55%); all 4 (30%); at most 1 (15%) | 3 of 4: **yes**; all 4: no. |
| Parent: `observability.py` and `config_inspection.py` 0 of 4 (85%) | Held (0 of 4). `dataset_limits.py` and `validate_dataset.py` right at least once (70%): held. |
| Controls with a path-only first call identical between arms (90%) | Held (4 of 4 files). |
| Pass 2 differs from pass 1 somewhere (80%) | Held. |
| The arms are indistinguishable on the four targets (12%) | Not the case. |
| What would surprise me: a child run showing the hint and then repeating the same stray call | **It happened once:** `validate_dataset.py`, both passes, the first hint was followed by `read_file validate_dataset.py -1` again and the second hint by `file_info validate_dataset.py`. |

## What this does and does not establish

- **Established (one session, 40 runs):** the hint text appears exactly where SE's rule says (13 of 13), never where it should not (0 of 20 parent runs,
  0 unexpected in the child), and in this session the child answers 18 of 20 correctly against 14 of 20, with the gain on the stray first calls
  (9 of 11 against 5 of 11).
- **Not established:** a second server session (the first call is nondeterministic across sessions, so the set of stray runs will differ), files outside the
  repository root, a hint for a path that should be refused (the sandbox cases are SE's tests, not exercised by these ten files), and the `dataset_limits`
  stem failure on other files.
