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

These are the things that actually wasted budget in previous sessions:

- **Never re-read a file you have already read** this session. Trust the earlier
  read and the edit confirmations.
- **Read parts, not wholes.** `sed -n '40,80p'`, `grep -n ... -A 5`, `tail -20`.
  Dumping a 600-line file to change one line is the single biggest waste.
- **Batch independent tool calls into one message.** Lint + types + tests in one
  `&&` chain, not three round trips.
- **Do not spawn subagents.** Each one re-derives context I have already paid
  for. Work inline.
- **Run the targeted test file while iterating**, and the full suite once before
  committing — not after every edit.
- **Long jobs: foreground, inside the 10-minute tool limit.** Background tasks
  are killed when the session ends; two 40-minute runs and a 20-minute
  evaluation have already been lost that way, and every lost minute was paid
  for twice. If a job cannot fit, use `--resume`.
- **Do not re-measure what the handoff already states.** The numbers below are
  real measurements; build on them.
- Keep replies compact. A table beats three paragraphs.

## 3. The 70% context handoff

Watch the length and complexity of this chat. When you estimate we are nearing
**70% of the usable context window**, or when I type `/handoff`:

1. **Stop starting anything new.** Finish only what is already in flight.
2. Rewrite `NEXT_CHAT.md` in the repo so it reflects the new state: what landed
   with commit hashes, the measured numbers, what is still broken, the next
   ten-percent milestone, and any new trap discovered.
3. Commit and push it.
4. Give me the full contents in a code block so I can paste it into a new chat.

Do **not** end the session early for any other reason — not because a milestone
shipped, not because a limit feels close. The handoff happens at ~70%, and
nowhere else.

## 4. Engineering standards that are not negotiable

1. **Local only.** The `openai` client is deliberately pointed at Ollama
   (`base_url="http://localhost:11434/v1"`, `api_key="local-ollama"`). Nothing
   leaves localhost — including the training dataset, which is why fine-tuning
   runs on this machine and not on a hosted notebook.
2. **No frameworks.** The ReAct loop is hand-rolled. No LangChain, no LlamaIndex.
3. **Three gates, all green before every commit.** Use the project venv:
   `.venv/Scripts/python.exe -m ruff check . && .venv/Scripts/python.exe -m mypy && .venv/Scripts/python.exe -m pytest`
4. **Measure, do not assume.** Every round of data collection so far exposed a
   real defect that hundreds of green tests had missed.
5. **Mutation-check anything security- or correctness-critical.** Break the
   control on purpose and confirm a test goes red.
6. **Report faithfully.** If something is wrong, say so with the output.
7. **One prompt-visible change at a time, then measure.** See trap 5 below:
   editing any string that reaches the system prompt reshuffles which questions
   pass, including ones that touch nothing you changed.

---

# PART 2 — Where the project stands

M1–M10 complete, plus a full fine-tuning round, plus a demo rehearsal that
found six real defects. **463 tests pass**, mypy strict clean across 27 files,
ruff clean. Latest commit: `58bb801`.

**Tools:** `calculate`, `get_current_time`, `file_info`, `read_file`,
`list_directory`, `search_text`.

**Models in Ollama:** `omniagent` (current fine-tune, 109 examples, `num_ctx`
16384), `omniagent-v1` (47 examples), `qwen-ctx8k` (stock 7B, `num_ctx` 8192).
Use `omniagent`.

## What landed on 2026-10-02

| commit | what |
|---|---|
| `479317a` | `[profile.demo]` had no `model`, so the demo would have run on the stock 7B at its 4096 default context. Pinned to `omniagent`; 6 tests now cover the shipped `omniagent.toml`, which previously had none |
| `9ef1577` | `cap_observation()` bounds any single observation to `max_observation_tokens` (600); a rejected format-violating reply is no longer kept in the scratchpad verbatim |
| `f52bed1` | the cap note no longer states counts of its own |
| `829ee76` | the console trace shows exactly what the model was given (258 lines of output became 50) |
| `84c805b` | the cap note states what cannot be concluded from a truncated read |
| `58bb801` | `read_file` **refuses** a file it cannot return in full, instead of returning the start of it |

## Measured: held-out eval, `omniagent`, temperature 0, 16 questions

| state | correct | tool pick | follow-ups | honest | steps |
|---|---|---|---|---|---|
| start of session (`f515f20`) | 10/10 | 5/7 | 5/5 | 1/1 | 66 |
| after capping observations | 10/10 | 4/7 | 5/5 | 1/1 | 63 |
| **HEAD `58bb801`** | **9/10** | **6/7** | **5/5** | **1/1** | **59** |
| + restating the question (reverted) | 8/10 | 6/7 | 5/5 | 1/1 | 77 |

`tool pick 6/7` is the best figure ever recorded for this model. The remaining
miss is "what is the very last line of X", already documented. The lost answer
is arithmetic, not a file question — see defect 2.

Run it as `.venv/Scripts/python.exe scripts/holdout_eval.py omniagent > data/holdout-<tag>.txt 2>&1`.
One model per invocation; concurrent runs fight over the 4 GB card. ~300 s.

## Why `read_file` refuses rather than truncates

Three separate fabrications came out of capped reads on the 1.5B:

- a line count copied from the previous turn ("sandbox.py has 689 lines")
- "The word 'budget' is not used anywhere in the file `agent.py`" — about a
  file that uses it on the line computing the context budget
- a quotation attributed to a file that was not in it

An excerpt cannot be told apart from the whole, so whatever the model cannot
see reads as absent. A refusal can only be read one way. `MAX_INTACT_READ_CHARS`
(2,400) is sized to the agent's observation budget; `tools.py` cannot import it
(`agent.py` imports `tools.py`), so a test holds the two together: `read_file`
must never return something `cap_observation` would trim.

## Still broken

1. **The interactive REPL degrades as a session goes on, and the held-out eval
   cannot see it.** `holdout_eval.py` builds a fresh agent per session, so
   history never accumulates. In a 7-question REPL walk, question 4 ("What is
   inside the data directory?") listed the directory correctly at step 1 and
   then said "Now, I need to find out what 'budget' refers to" — question 3's
   topic, still in history — and spent eleven more steps on it. Nothing was
   over budget: 1,562 tokens of a 16,384 window. 463 tests and a 300-second
   eval both missed this.
2. **"How many minutes are in 3 days and 7 hours?" answers 29,520, want 4,740.**
   4,320 plus 7 times 3,600, so it used seconds per hour. It was correct before
   `read_file`'s *description* was edited. Nothing about the question touches a
   file tool; see trap 5.
3. **The rut check detects but does not control.** Six identical
   `read_file ./agent.py` calls in one turn each fired
   `agent.loop.repeated_action`, and the model ignored all six. Only the step
   budget stopped it. A control that fires six times without changing behaviour
   is not a control — it needs to escalate (refuse the action, or force a final
   answer) rather than advise.
4. **The weather question drifts in the REPL** even though it scores ADMITTED in
   the eval: in a long session it answered about the data directory instead of
   saying it cannot know.

## Rejected, with the measurement

**Restating the question after every observation.** Appending
`(the question still being answered: ...)` to each observation fixed defect 1
exactly — the data-directory question went from 12 steps and a wrong answer to
4 steps and a correct one. On the held-out set it cost two arithmetic answers
and 18 extra steps (8/10, 77 steps). Reverted. Do not retry it without a way
to measure interactive sessions, which is the next milestone.

## Next ten-percent milestone, in order

1. **An interactive eval.** A scripted multi-question REPL session, scored the
   way `holdout_eval.py` scores, so that history-accumulation drift becomes a
   number instead of an anecdote. This is the gap that let both the test suite
   and the eval miss the demo's worst failures, and until it exists every REPL
   observation is a single sample that cannot be told apart from noise.
2. Then retry the question restatement against it, and try escalating the rut
   check from advice to refusal.
3. **Rehearse the demo** — 2026-10-10. `main.py --profile demo`.
4. Measure `qwen-ctx8k`: `scripts/holdout_eval.py qwen-ctx8k`.
5. Grow the held-out set to ~50 questions.

## What the demo should and should not ask

Verified working, 2 steps each, on `58bb801`:

- "How many lines does tools.py have?" / "How many lines does sandbox.py have?"
  — asked **in full**, both correct via `file_info`
- "What is 15% of 2480?" then "Now multiply that by 3." — 372, then 1116.
  Arithmetic follow-ups resolve against history correctly
- "What is inside the data directory?" — correct when asked early in a session

Avoid:

- **Elliptical follow-ups on file metadata.** "And sandbox.py?" makes the model
  pick `read_file` and then copy a number out of history. The same question in
  full picks `file_info` and is right. Arithmetic ellipsis is fine; file
  ellipsis is not.
- **Multi-file comparisons** ("which of these two is longer") — unchanged
  capability limit.
- **"What is the last line of X"** — still fails tool pick.
- **A long session before the question you care about.** Ask the questions that
  matter first.

## Traps already paid for once

- **Ollama does not autostart.** `Start-Process "$env:LOCALAPPDATA\Programs\Ollama\ollama.exe" -ArgumentList "serve" -WindowStyle Hidden`, wait ~15 s. `&` from Bash does not work.
- **Background tasks die with the session.**
- **Ollama defaults to 4096 context** and truncates from the *front*, taking the
  system prompt with it.
- **`pip install torch --index-url .../cu126 --upgrade` is a no-op** — pip treats
  `+cpu` and `+cu126` as the same version. Use `--force-reinstall` with the
  explicit local version.
- **A quoted bash heredoc still eats `\n` and `\\` in Python source.** Hit twice
  more this session. Use Write/Edit, or `chr(10)`. There is no quoting that
  makes it safe.
- **Global `pip` fails under the sandbox**; venv pip on `D:` works.
- **`\b` does not match inside `OMNIAGENT_API_KEY`** (`_` is a word character).
- **NEW — a recursive `grep` from Bash scans `.venv` and hangs past the
  120-second limit.** `grep -rn pattern .` at the repo root is not survivable.
  Name the files, or use PowerShell.
- **NEW — `pytest -q | tail` drops the summary line.** So
  `pytest -q | grep passed && git commit` fails the chain silently and nothing
  is committed. Run `pytest` without `-q` for the count, as its own command.
- **NEW — `scripts/holdout_eval.py` prints and keeps nothing.** A 300-second
  measurement left no artifact and had to be run twice because `tail -30` cut
  off the part naming which question failed. Always redirect to `data/`.
- **NEW — editing any tool `description` rewrites the system prompt of every
  question.** At temperature 0 a run is deterministic but not stable against an
  edit anywhere in the prompt: changing `read_file`'s description flipped an
  unrelated arithmetic answer. Expect any prompt-visible edit to reshuffle which
  questions pass, and measure the whole set rather than the question you aimed
  at.
- **NEW — one REPL run is not a measurement.** Three prompt edits each fixed the
  question they targeted and broke a different one. Without the interactive eval
  in milestone 1, treat every single REPL result as an anecdote.

## If the tools or the system prompt change

Re-collect from scratch — both are part of every training example. Note that
`read_file`'s description changed in `58bb801`, so the current dataset no longer
matches the prompt the model is served. The fine-tune still measures its best
tool-pick score, so this is a thing to know rather than a thing to fix first.
