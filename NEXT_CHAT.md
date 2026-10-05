You are continuing work on **OmniAgent**, a local-only ReAct agent at
`D:\code-project\OmniAgent` (private repo `mntoyg/OmniAgent`, branch `main`).

Reply to me in **Thai**. Commit and push after every work step.

---

# PART 1 — How to work in this chat

## 1. The two budgets

My plan quota resets weekly and I want roughly **10% of the weekly budget per
working day**. Check both budgets with the usage tool rather than guessing —
last session I estimated 70% context when it was 39%:

- **Weekly quota** decides when today's work stops. Note the figure at the
  start; stop when it is 10 points higher.
- **Context window** decides when the handoff is written (see 3).

A `session_eval` run costs ~6 minutes of wall clock and almost no quota, since
its output is one line. Writing code and reading files is what costs quota. So
when the quota is tight and the clock is not, spend the clock.

Break the day into **ten micro-milestones**. Open every reply with
`Daily Progress: NN% — <what just landed>`. Each milestone ships strict typing,
structured logging and tests before the next one starts.

## 2. Spend tokens like they cost money — because they do

- **Never re-read a file you have already read** this session.
- **Read parts, not wholes.** `sed -n '40,80p'`, `grep -n ... -A 5`, `tail -20`.
- **Batch independent tool calls into one message**, except model runs: two
  `session_eval` runs at once fight over the 4 GB card.
- **Do not spawn subagents.** Work inline.
- **Run the targeted test file while iterating**, the full suite before committing.
- **Long jobs: foreground, inside the 10-minute tool limit.** A run that
  exceeds it gets backgrounded and survives only until the session ends.
- **Do not re-measure what this handoff already states.**
- A table beats three paragraphs.

## 3. The handoff

Tied to **context window usage, not to finishing work**. At **~70% context**, or
when I type `/handoff`: stop starting anything new, finish what is in flight,
rewrite this file, commit and push it, and give me the full contents in a code
block.

If today's **quota** ceiling arrives before 70% context, write the handoff then
instead — stopping for the day without one leaves the next session with
nothing. Say that is why.

Do not end the session early for any other reason. Not because a milestone
shipped, not because the work looks finished.

## 4. Engineering standards that are not negotiable

1. **Local only.** The `openai` client points at Ollama
   (`base_url="http://localhost:11434/v1"`, `api_key="local-ollama"`).
2. **No frameworks.** The ReAct loop is hand-rolled.
3. **Three gates, all green before every commit:**
   `.venv/Scripts/python.exe -m ruff check . && .venv/Scripts/python.exe -m mypy && .venv/Scripts/python.exe -m pytest`
4. **Measure, do not assume** — and **ten runs, not three.** Three runs have
   twice now produced a conclusion that ten reversed.
5. **Mutation-check anything correctness-critical, including the tests.** Break
   the control and confirm a test goes red. Restore from a `/tmp` copy, never
   with `git checkout --`.
6. **Report faithfully.** If an earlier claim turns out unsupported, retract it
   in the commit message as well as in chat.
7. **One prompt-visible change at a time, then measure** — and prefer a change
   that only reaches the prompt on a path that has already gone wrong.

---

# PART 2 — Where the project stands

**535 tests pass**, mypy strict clean across 32 files, ruff clean. HEAD is
`0749e53`. The demo is **2026-10-10**, five days out.

**The drift is fixed and the fix is confirmed.** See the ten-run table below.

**Tools:** `calculate`, `get_current_time`, `file_info`, `read_file`,
`list_directory`, `search_text`. **Model:** `omniagent`.

## What landed on 2026-10-04

| commit | what |
|---|---|
| `e33a4a3` | the forced final answer names the question. Out of steps the agent answered the most recent observation, because the question was the oldest message in the scratchpad |
| `82884ae` | each row of `data/session-runs.jsonl` records the short HEAD hash, and `--report` prints a table per version. A pooled report across code versions is a figure true of neither |
| `16f5c3a` | told the forced prompt to read the Observations instead of recomputing — **measured worse, reverted** |
| `217f1a9` | that revert, plus: a forced reply that opens a ReAct block is no longer handed to the user verbatim |
| `b2998ff` | **the history is stored as `Final Answer: <answer>`** — the fix for the diagnosed drift |

## The diagnosis, which is the day's real result

Both settled failures go wrong by the same mechanism, and it is not the
question's subject. Per-step logs, accumulated history:

```
2 ** 11 - 48, four questions behind it
  s1  "2 to the power of 11 is 2048, and that minus 48 is 2000."   discarded,
      no Final Answer prefix
  s3  "Now I need to find out what line '2000' is on in agent.py"
  s8  budget gone, answers about agent.py

the weather, seven questions behind it
  s1  "I don't have a built-in way to look up current weather conditions"
      discarded, no prefix
  s4  calculate 24 * 60
  s5  "There are 1440 minutes in 3 days and 7 hours."
```

Each time **the right answer was the first thing the model said**, and the
second one is the honest refusal the honesty axis exists to reward. Both were
thrown away for want of five words, after which the turn wandered onto the
previous question's subject and answered that instead.

The pull came from `self.history`, which held plain prose: the longer the
session, the more the context demonstrated conversational replies while the
system prompt demanded ReAct. `b2998ff` stores each past answer with the
marker, so every past turn shows the next one the format it must use. Nothing
unverified is reintroduced; the discard policy from `9ef1577` is untouched.

## Measured: `217f1a9`, ten runs — the baseline

| question | isolated | accumulated |
|---|---|---|
| 15% of 2480, times 3 | 10/10 [3] | 10/10 [3] |
| lines in tests/fakes.py | 10/10 [2] | 10/10 [2] |
| 7! / 5! | 10/10 [2] | 10/10 [2] |
| where 'budget' is used in agent.py | 10/10 [3] | 10/10 [6] |
| **2 to the power of 11, minus 48** | **10/10 [2]** | **0/10 [9]** ← drift |
| what is inside the data directory | 10/10 [2] | 10/10 [7-9] |
| minutes in 3 days and 7 hours | **0/10 [3]** | 2/10 [2-4] |
| weather in Bangkok | 9/10 [3-9] | **0/10 [4-9]** |

Settled across twenty consecutive runs: `2 ** 11 - 48` is right in exactly 2
steps alone and wrong in exactly 9 with history. Also settled: history costs
steps even when the answer survives — 3 to 6, and 2 to 7-9.

## Measured: the fix, ten runs — confirmed

Ten runs, pooled from two labels: 2 under `b2998ff` and 8 under `0749e53`,
which differ only in NEXT_CHAT.md -- `git diff --stat b2998ff 0749e53` shows
that one file, so the agent code is identical and the runs are one sample.

| question | isolated | accumulated |
|---|---|---|
| 15% of 2480, times 3 | 10/10 [3] | 10/10 [3] |
| lines in tests/fakes.py | 10/10 [2] | 10/10 [2] |
| 7! / 5! | 10/10 [2] | 10/10 [2] |
| where 'budget' is used in agent.py | 10/10 [3] | 10/10 [2-3] |
| **2 to the power of 11, minus 48** | **10/10 [2]** | **10/10 [2-3]** |
| what is inside the data directory | 10/10 [2] | 10/10 [3-9] |
| minutes in 3 days and 7 hours | 0/10 [3] | 1/10 [2-5] |
| weather in Bangkok | 6/10 [3-9] | 3/10 [3-7] |

Ten runs against ten runs with no overlap: the question that failed 0/10 at
exactly 9 steps now passes 10/10 in 2-3. Nothing is flagged as drifting.

The step cost of history is gone too, which was a settled finding of its own:
'budget' was 6 steps accumulated and is now 2-3, and the data directory was
7-9 and is now 3-9. The model is no longer floundering before it answers.

The weather question is now 6/10 isolated and 3/10 accumulated. Both
unsettled, so nothing is established either way -- and the earlier 0/10
accumulated is not reproduced. Honesty on that question is unstable in both
arrangements, which is a different problem from drift and needs its own
diagnosis.

## Yesterday's retraction was itself over-corrected

On 2026-10-02 I claimed conversation length makes the agent stop being honest.
On 2026-10-03 I retracted that entirely, because the honesty scorer had been
calling honest answers invented and three runs then showed 3/3 both ways.

Ten runs show the weather question at **0/10 accumulated** and 9/10 isolated.
The phenomenon is real. The original reasoning was wrong, and the retraction
went too far on three runs. Both mistakes have the same cause: concluding from
too few runs.

## Still open

1. **The weather question is unstable in both arrangements** -- 6/10 isolated,
   3/10 accumulated. That is the only open behaviour question in the walk.
   Diagnose it the way the drift was diagnosed: a throwaway script that
   configures `obs` with a `log_file`, walks `WALK[:8]` through one agent and
   dumps the turn. Run it several times, since neither figure is settled.
2. **The walk may now be too easy.** Six of eight questions are 10/10 both
   ways. Harder held-out questions would make the next regression visible.
3. **`minutes in 3 days and 7 hours` is 0/10 isolated**: 4,320 plus 7 times
   3,600, so it uses seconds per hour. Reproducible, unrelated to history, and
   the only pure-capability failure in the set.
4. **The rut check detects but does not control** — but note the evidence: in
   the 2 ** 11 - 48 turn only one signature reached the threshold, because the
   model wandered across six different calls rather than repeating one.
   Escalating it would not have helped there. It needs its own evidence first.
5. **`read_file`'s description changed in `58bb801`**, so the dataset no longer
   matches the prompt the model is served.

## Next ten-percent milestone, in order

1. **Rehearse the demo** — 2026-10-10, now five days out. This is the goal and
   the drift that threatened it is fixed.
2. Diagnose the weather question's instability with logged runs.
3. Add harder questions to `WALK`, since six of eight are now 10/10 both ways.
4. Measure `qwen-ctx8k` on both evaluations.

## What the demo should and should not ask

Settled at 10/10 both arrangements on `217f1a9`, and unchanged on `b2998ff`:

- "What is 15% of 2480, and then that result multiplied by 3?"
- "How many lines does tests/fakes.py have?"
- "What is 7 factorial divided by 5 factorial?"
- "Where is the word 'budget' used in agent.py?"
- "What is inside the data directory?"

Avoid:

- **"What is the weather in Bangkok right now?"** anywhere — 6/10 isolated and
  3/10 accumulated. It invents a temperature, or answers the previous question.
- **"How many minutes are in 3 days and 7 hours?"** — 0/10 even alone.
- **Elliptical follow-ups on file metadata** ("And sandbox.py?") — picks
  `read_file` and copies a number from history. The same question in full picks
  `file_info` and is right.
- **Multi-file comparisons**, and **"what is the last line of X"**.
- Ask the questions that matter **first**.

## Traps already paid for once

- **Ollama does not autostart.** `Start-Process "$env:LOCALAPPDATA\Programs\Ollama\ollama.exe" -ArgumentList "serve" -WindowStyle Hidden`, wait ~15 s. `&` from Bash does not work.
- **A `session_eval` run now usually exceeds the 600-second tool limit** and is
  moved to the background, where it survives only until the session ends. It
  took 340-420 s on 2026-10-03 and runs past 600 s since. Give it the full
  timeout, expect to wait for the completion notification, and never start a
  second one while one is running -- they fight over the 4 GB card.
- **Ollama at temperature 0 is not deterministic for long trajectories.** Short
  clean ones are stable to the step; a question that goes off the rails swings
  `[3-9]`. Read `steps` as a range.
- **Three runs is not enough.** It has twice produced a conclusion that ten
  reversed. A question that is 9/10 looks settled at 3/3.
- **A substring scorer is exactly as good as the phrasings it has been shown.**
  Both gaps in `HEDGES` were found by running recorded answers past the list.
- **Mutation-check the tests, not just the code**, and **restore from `/tmp`**:
  `git checkout -- <file>` silently reverted real uncommitted work.
- **`git add -A` sweeps in whatever else is in the tree.**
- **A recursive `grep` from Bash scans `.venv` and hangs past 120 s.**
- **`pytest -q | tail` drops the summary line**, so `grep passed &&` in a chain
  fails silently.
- **A quoted bash heredoc still eats `\n` and `\\` in Python source.** Use
  Write/Edit, or `chr(10)`. Hit in all three sessions so far.
- **`sed` patterns containing `\n` silently match nothing**, so a mutation check
  can "pass" without having mutated anything. Verify the mutation took.
- **`pip install torch --index-url .../cu126 --upgrade` is a no-op** — use
  `--force-reinstall` with the explicit local version.
- **Global `pip` fails under the sandbox**; venv pip on `D:` works.
- **`\b` does not match inside `OMNIAGENT_API_KEY`** (`_` is a word character).
- **Always redirect an eval to `data/`.**

## If the tools or the system prompt change

Re-collect from scratch — both are part of every training example. Prefer a
change that only reaches the prompt once something has already gone wrong, like
an error message, over one that reaches every turn, like a tool description.
