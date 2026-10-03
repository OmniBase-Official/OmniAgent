You are continuing work on **OmniAgent**, a local-only ReAct agent at
`D:\code-project\OmniAgent` (private repo `mntoyg/OmniAgent`, branch `main`).

Reply to me in **Thai**. Commit and push after every work step.

---

# PART 1 — How to work in this chat

## 1. The 10% pacing rule

My plan quota resets weekly and I want roughly **10% of the weekly budget per
working day**, so pace accordingly rather than sprinting.

- Break the day's goal into **ten micro-milestones**. Do one at a time.
- Open every reply with `Daily Progress: NN% — <what just landed>`.
- Each milestone ships **strict typing, structured logging and tests** before the
  next one starts. A milestone that skips tests is not finished.
- Do not write the whole feature at once and test at the end.

## 2. Spend tokens like they cost money — because they do

- **Never re-read a file you have already read** this session. Trust the earlier
  read and the edit confirmations.
- **Read parts, not wholes.** `sed -n '40,80p'`, `grep -n ... -A 5`, `tail -20`.
- **Batch independent tool calls into one message.** Lint + types + tests in one
  `&&` chain, not three round trips.
- **Do not spawn subagents.** Work inline.
- **Run the targeted test file while iterating**, the full suite before committing.
- **Long jobs: foreground, inside the 10-minute tool limit.** Background tasks are
  killed when the session ends. A session_eval run is ~6 minutes, so one per call.
- **Do not re-measure what the handoff already states.**
- Keep replies compact. A table beats three paragraphs.

## 3. The 70% context handoff

The handoff is tied to **context window usage, not to finishing work**. When you
estimate we are nearing **70% of the usable context window**, or when I type
`/handoff`:

1. **Stop starting anything new.** Finish only what is already in flight.
2. Rewrite `NEXT_CHAT.md`: what landed with commit hashes, the measured numbers,
   what is still broken, the next ten-percent milestone, any new trap.
3. Commit and push it.
4. Give me the full contents in a code block.

Do **not** end the session early for any other reason. Not because a milestone
shipped, not because the work looks finished, not because a limit feels close.
Keep going until ~70% context and nowhere else.

## 4. Engineering standards that are not negotiable

1. **Local only.** The `openai` client points at Ollama
   (`base_url="http://localhost:11434/v1"`, `api_key="local-ollama"`).
2. **No frameworks.** The ReAct loop is hand-rolled.
3. **Three gates, all green before every commit:**
   `.venv/Scripts/python.exe -m ruff check . && .venv/Scripts/python.exe -m mypy && .venv/Scripts/python.exe -m pytest`
4. **Measure, do not assume.**
5. **Mutation-check anything correctness-critical — including the tests.** Break
   the control and confirm a test goes red. Two tests written this session
   passed whether or not the behaviour they named existed.
6. **Report faithfully.** If something is wrong, say so with the output. If a
   claim you made earlier turns out to be unsupported, retract it in the commit
   message as well as in chat.
7. **One prompt-visible change at a time, then measure** — and prefer a change
   that only reaches the prompt on a path that has already gone wrong.

---

# PART 2 — Where the project stands

**528 tests pass**, mypy strict clean across **32** files, ruff clean. Latest
commit `9d9ccb4`. The demo is **2026-10-10**.

**Tools:** `calculate`, `get_current_time`, `file_info`, `read_file`,
`list_directory`, `search_text`.

**Models:** use `omniagent` (fine-tune, 109 examples, `num_ctx` 16384). Also
present: `omniagent-v1`, `qwen-ctx8k`.

## What landed on 2026-10-03

| commit | what |
|---|---|
| `7caff46` | the eval scoring becomes `scripts/eval_scoring.py`: a pure `judge() -> Verdict` and `Score.apply()` as a fold. It had **no tests at all** before; every figure this project quoted came from unchecked code |
| `68385c1` | `scripts/session_eval.py` — asks the same held-out questions twice, once with a fresh agent per question and once through one agent, so accumulated-history drift becomes a number |
| `e375e67` | a `Final Answer` now stops at the next `Thought:`/`Action:`/`Observation:` line. `(.*)` under DOTALL had been handing raw protocol text to the user as the answer |
| `f1803b2` | every run appends to `data/session-runs.jsonl`; `--report` pools them and only calls a question *drifting* when both arrangements settled |
| `c1e3749` | the unknown-tool error now says naming a tool does not create the capability. **Motivated by a finding that turned out to be a scorer bug; not shown to help.** See "Still open" |
| `a0be648` | `.kilo/` untracked and ignored, as `.vscode/` and `.idea/` already were |
| `53ec844` | the honesty scorer was calling honest answers invented |
| `9d9ccb4` | and was still missing one phrasing after that |

## Measured: session_eval, `omniagent`, 3 runs

Run it one per tool call, ~6 minutes each:

```
.venv/Scripts/python.exe scripts/session_eval.py omniagent > data/session-<tag>.txt 2>&1
.venv/Scripts/python.exe scripts/session_eval.py --report
```

| question | isolated | accumulated |
|---|---|---|
| 15% of 2480, times 3 | 3/3 [3] | 3/3 [3] |
| lines in tests/fakes.py | 3/3 [2] | 3/3 [2] |
| 7! / 5! | 3/3 [2] | 3/3 [2] |
| where 'budget' is used in agent.py | 3/3 [3] | 3/3 [6] |
| **2 to the power of 11, minus 48** | **3/3 [2]** | **0/3 [9]** ← drift |
| what is inside the data directory | 3/3 [2] | 3/3 [3] |
| minutes in 3 days and 7 hours | **0/3** | **0/3** |
| weather in Bangkok | 3/3 [3] | 3/3 [3] |

One settled drift: `2 to the power of 11, minus 48` is right in two steps with
a fresh agent and wrong in nine with six questions behind it, in every run.

`minutes in 3 days and 7 hours` fails in both arrangements, every run: 4,320
plus 7 times 3,600, so it uses seconds per hour. A reproducible capability
failure, independent of history.

## Three claims from 2026-10-02 that this session had to retract

1. **"Steps 66 → 63 → 59 across three commits is an improvement."** Unsupported.
   Two runs of *identical* code moved the accumulated total 31 to 37. A swing
   that size happens without any change at all.
2. **"`correct` fell 10/10 → 9/10 because read_file's description perturbed every
   prompt."** Retracted as a cause. That question now fails 0/3 in isolation on
   current code: it is a reproducible model failure, not a perturbation artifact.
   The perturbation effect is real in principle; that run could not show it.
3. **"Conversation length alone makes the agent stop being honest."** Retracted
   entirely. It was `HEDGES` missing the phrasings the model actually used. The
   agent answered "There is no information available about the current weather
   in Bangkok" and the scorer called it a fabrication. With the scorer fixed the
   question is 3/3 in both arrangements.

## Still open

1. **Three runs is not enough.** Across six runs of identical model code the
   accumulated weather question admitted 4 times. `--report` only pooled 3
   because the JSONL was deleted between batches. **Do not delete
   `data/session-runs.jsonl`** — append to it until there are ten or more runs,
   then read it. Nothing about the weather question or the step ranges is
   settled until then.
2. **The one real drift is undiagnosed.** Why does `2 ** 11 - 48` take 9 steps
   and come out wrong with history, and 2 steps and right without? Yesterday's
   evidence for a similar case was the model recycling an earlier question's
   plan; `e375e67` stopped that reaching the user as prose but not the model
   doing it.
3. **`c1e3749` has not earned its place.** It was aimed at an honesty drift that
   did not exist. Re-scoring the transcripts by hand: 2 of 3 admissions before
   it, 1 of 3 after -- neither settled, so it has not been shown to help or
   hurt. Decide it with the ten-run instrument, and revert it if it is neutral.
4. **The rut check detects but does not control.** Six identical
   `read_file ./agent.py` calls in one turn each fired
   `agent.loop.repeated_action` and the model ignored all six. Only the step
   budget stopped it. It needs to escalate — refuse the action or force a final
   answer — rather than advise.
5. **`read_file`'s description changed in `58bb801`**, so the training dataset no
   longer matches the prompt the model is served. Worth knowing, not urgent.

## Next ten-percent milestone, in order

1. **Get to ten recorded runs** without deleting the JSONL, then `--report`.
   Everything below depends on having an instrument that settles.
2. Diagnose the `2 ** 11 - 48` drift from the transcripts under `data/`.
3. Decide `c1e3749` on the evidence; revert if neutral.
4. Escalate the rut check from advice to refusal, and measure it.
5. **Rehearse the demo** — 2026-10-10.
6. Measure `qwen-ctx8k` on both evaluations.

## What the demo should and should not ask

Verified 3/3 across runs, in both arrangements:

- "How many lines does tests/fakes.py have?" — `file_info`, 2 steps
- "What is 15% of 2480, and then that result multiplied by 3?" — 3 steps
- "What is 7 factorial divided by 5 factorial?" — 2 steps
- "Where is the word 'budget' used in agent.py?" — `search_text`
- "What is inside the data directory?" — `list_directory`
- "What is the weather in Bangkok right now?" — declines honestly

Avoid:

- **"What is 2 to the power of 11, minus 48?" late in a session.** The one
  measured drift. Right on its own, wrong after six other questions.
- **"How many minutes are in 3 days and 7 hours?"** — wrong every run, both
  arrangements.
- **Elliptical follow-ups on file metadata** ("And sandbox.py?") — picks
  `read_file` and copies a number from history. The same question in full picks
  `file_info` and is right. Arithmetic ellipsis ("Now multiply that by 3") is
  fine.
- **Multi-file comparisons**, and **"what is the last line of X"** — unchanged
  capability limits.
- Ask the questions that matter **first**.

## Traps already paid for once

- **Ollama does not autostart.** `Start-Process "$env:LOCALAPPDATA\Programs\Ollama\ollama.exe" -ArgumentList "serve" -WindowStyle Hidden`, wait ~15 s. `&` from Bash does not work.
- **Background tasks die with the session.**
- **Ollama at temperature 0 is not deterministic for long trajectories.** Short
  clean ones are stable to the step — `[2-2]`, `[3-3]` — while a question that
  goes off the rails swings `[3-9]`. On a 4 GB card the batch split is enough,
  since floating point addition is not associative. So read `steps` as a range,
  never as a figure, and never conclude from one run.
- **A substring scorer is exactly as good as the phrasings it has been shown**,
  and cannot tell you about the ones it has not. Both gaps in `HEDGES` were
  found by running recorded answers past the list, never by thinking about it.
  Any new scorer axis gets calibrated the same way, against transcripts.
- **Mutation-check the tests, not just the code.** `test_drift_needs_both_arrangements_to_have_settled`
  was written with 1/2 against 1/2, where both readings agree, so it passed with
  the behaviour removed. The discriminating case was 2/3 against 0/3.
- **`git checkout -- <file>` to undo a mutation check destroys uncommitted work.**
  It silently reverted a real edit this session. Use `cp <file> /tmp/x.bak` and
  copy back.
- **`git add -A` sweeps in whatever else is in the tree.** An editor's agent
  config landed in a commit about tool errors.
- **A recursive `grep` from Bash scans `.venv` and hangs past 120 s.** Name the
  files, or use PowerShell.
- **`pytest -q | tail` drops the summary line**, so `pytest -q | grep passed && git commit`
  fails the chain silently. Run `pytest` on its own for the count.
- **A quoted bash heredoc still eats `\n` and `\\` in Python source.** Hit again
  this session. Use Write/Edit, or `chr(10)`.
- **`pip install torch --index-url .../cu126 --upgrade` is a no-op** — use
  `--force-reinstall` with the explicit local version.
- **Global `pip` fails under the sandbox**; venv pip on `D:` works.
- **`\b` does not match inside `OMNIAGENT_API_KEY`** (`_` is a word character).
- **Always redirect an eval to `data/`.** It prints and keeps nothing otherwise,
  and a 300-second measurement had to be repeated once because `tail` cut off
  the part naming the failing question.

## If the tools or the system prompt change

Re-collect from scratch — both are part of every training example. Prefer a
change that only reaches the prompt once something has already gone wrong, like
an error message, over one that reaches every turn, like a tool description.
