# Result: SE brief 34 (`45cbd0e`) against its parent (`1384d63`), one session, counts only

**From:** AI/ML engineer · **2026-11-24** · branch `aiml/brief34-measure-20261124`. Prediction (not edited):
`docs/pm/prediction-2026-11-24-brief34-pair.md` at `15c89d4`, on both remotes before the first request. **MEASURED** by me, 140
runs, 06:36 to 07:14, one Ollama session, `omniagent-v2:latest` digest `05ba6fe701c5cb9d`, `--temperature 0`, `--max-steps 8`,
`--control-file observability.py`, 10 passes, the arms alternating order every pass (pass 1 parent first). Every row records
`commit` (`1384d63` in 70, `45cbd0e` in 70), `tree_clean: true` in all 140, `temperature: 0.0`. Lock created before the first
request and removed at exit (verified gone). The `/api/ps` watcher logged only `omniagent-v2` (408 samples) or nothing (4): no
other model touched the GPU. Raw outputs are local and uncommitted.

## Counts per question and arm (distinct answers / distinct tool sequences, exit codes)

| Question | Parent `1384d63` | Child `45cbd0e` |
| --- | --- | --- |
| q1 arithmetic | 10/10 correct; 1 answer; `calculate`; exit 0 | identical |
| q2 lines of `config.py` (302) | **0/10**; "278" x10; `read_file, read_file, inspect_config_precedence` (5 steps); `file_info` called 0/10; exit 0 | **10/10 "302"**; `read_file, file_info` (3 steps); **`file_info` called 10/10**; exit 0 |
| q3 first line of `requirements.txt` | 10/10; `read_file`; exit 0 | identical |
| q4 count in `scripts/` | blank x10; `list_directory, search_text, count_matches`; exit 1 | identical |
| q5 share price (no expectation) | 5 x 3 steps; 5 longer loops (7 or 8 steps) | 9 x 3 steps; 1 x 7 steps |
| q6 same count, other wording | "9" x10 (wrong); `list_directory`; exit 0 | identical |
| q7 lines of `observability.py` (353) | **0/10**; "12331" x10; an 8-step `read_file`/`list_directory` loop; `file_info` 0/10 | **0/10**; "does not exist" x10; `read_file, list_directory, read_file, read_file` (4 steps); `file_info` 0/10 |

Every question except q5 gave exactly one answer and one tool sequence across its ten passes in each arm (q5 reads the clock).
Blank if and only if an unregistered tool was called: **140 of 140** (checked against `tools.TOOLS` of the child tree, where
`count_matches` is absent; `inspect_config_precedence` is registered). Blank, exit 1 and the `[!] No answer` line coincide in
140 of 140. Every answered run exits 0.

## What the pair shows

1. **q2 moved, and only q2 moved because of the text.** The same session, the same question, the only reachable difference being the
   last sentence of the `read_file` error: parent "278" in 10 of 10, child "302" in 10 of 10, with `file_info` called in 10 of 10 child runs
   and 0 of 10 parent runs. Interleaving cannot explain a 0/10 to 10/10 split with no run crossing over. All 20 q2 runs saw the changed
   error (the "too long" text appears in 20 of 20).
2. **q1, q3, q4, q6 are indistinguishable between arms**, down to the tool sequence: what I predicted for questions the text cannot reach.
3. **q5: not distinguishable from noise at n=10** (5 against 9 three-step runs; q5 varies inside one arm too). I did not re-score
   invented against declined figures.
4. **q7 differs between arms (8-step loop to "12331" against 4 steps to "does not exist"), and this is NOT the effect of the changed
   text.** In all 20 q7 runs of this session the first call is `read_file` with the input `observability.py 1` (a malformed input), which
   returns `Error: no such file`; the oversize error is **never** reached (0 of 20, both arms). What differs is the next observation, the
   `list_directory` listing of the tree root, which is not the same in the two trees: the parent tree lists a stale `__pycache__/`
   directory (left by earlier runs; 10 of 10 parent listings) and the child tree did not (0 of 10), and `tools.py` has a different byte
   size (48,294 against 48,349). That the listings differ is MEASURED; that this is why the model goes down a different path is **UNVERIFIED**
   (the settling test is two trees with identical listings, or a q7 that does not list the root).

## Corrections to my earlier reports (MEASURED on the stored raw files)

- **q7 never tested the error text.** In all 50 q7 runs I hold (`b164aaa`, `1ce7c81`, `1384d63`, and this session) the oversize
  error was reached 0 times: the first input is always the malformed `observability.py 1`. My earlier statements "q2 and q7 are 0/10 ... 0
  of 30" and "the model does not use a correct adjacent line count" rest on **q2 alone** (10 runs at `1ce7c81`). The q7 movement between
  `1384d63` and `1ce7c81` was not the text either.
- **"12331" is not invented.** It is the byte size of `observability.py` that `list_directory` prints (`observability.py (12331 bytes)`);
  the model reads a number from the listing and reports it as a line count, a unit error on a real observation. My earlier line "12331
  is in none of the 7,551 examples: invented" was true of the examples and misleading about the cause.
- `inspect_config_precedence` (q2 parent) is a registered tool, not an invented one.
- After the run I imported `tools` from the child tree to read its registry; that wrote a `__pycache__/` there (git-ignored, after the
  last run, `tree_clean` unaffected). Do not reuse the child tree for a q7 comparison without removing it.

## Scoring my prediction (wrong parts included)

| Prediction | Outcome |
| --- | --- |
| `file_info` called in q2 at least once: 50%; in 8 of 10 or more: 35% | **Yes, 10 of 10.** Too cautious. |
| q2 correct in at least 1: 40%; in at least 8: 30%; stays 0/10: 50% | **10/10 correct.** The upper tail I gave 30% happened. |
| q7 behaves like q2 (`file_info` in both or neither): 80% | **Wrong.** `file_info` 0 of 20 on q7; the premise that q7 reaches the oversize error was false. |
| q7 correct in at least 1: 40% | **No, 0 of 20.** |
| Parent: `file_info` ever on q2 or q7: 5%; parent correct: 5% | Held: 0 and 0. |
| Parent reproduces its control (q2 "278", q7 "does not exist", all ten): 55% | **Half.** q2 yes (same sequence); q7 no (the parent gave the 8-step loop, as `1ce7c81` did; the child gave the control's 4-step sequence). |
| q1, q3 10/10 in both arms: 95% | Held. |
| q4 and q6 identical between arms: 80% | Held. |
| q5 within the earlier spread between arms: 75% | Borderline: 5 against 9 short runs; not rescored. |
| One answer and one sequence per question per arm (q5 aside): 75% | Held. |
| Links hold in 140 of 140: 90% | Held. |

## What this does and does not establish

- **Established (one session, 10 runs per arm):** replacing the closing sentence of the oversize error with a copy-ready
  `Action: file_info, Action Input: <path>` made the model call `file_info` and answer correctly in 10 of 10 on `config.py`, where the
  general wording and the earlier printed line count had produced 0 of 10 and 0 of 10.
- **Not established:** that this generalises to another file (q7 never reached the text, so it says nothing), to other tools, or
  across server sessions. Whether `config.py` memorisation ("278") is beaten or simply bypassed is not shown; one file is one file.
- **Not tested:** a second oversize file whose first call is well-formed, the effect on `list_directory`, a different session.
