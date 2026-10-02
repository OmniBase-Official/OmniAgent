# Next-chat prompt — OmniAgent

Paste **everything below the line** into a new Claude Code chat as the first
message. It is self-contained; nothing from the previous conversation is needed.

Update this file at the end of every session, before the handoff.

---

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
2. Rewrite `NEXT_CHAT.md` in the repo — this very file — so it reflects the new
   state: what landed with commit hashes, the measured numbers, what is still
   broken, the next ten-percent milestone, and any new trap discovered.
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
2. **No frameworks.** The ReAct loop is hand-rolled. No LangChain, no
   LlamaIndex.
3. **Three gates, all green before every commit.** Use the project venv, never
   bare `python`:
   ```
   .venv/Scripts/python.exe -m ruff check . && .venv/Scripts/python.exe -m mypy && .venv/Scripts/python.exe -m pytest
   ```
4. **Measure, do not assume.** Every round of data collection so far exposed a
   real defect that 440 green tests had missed. Verify behaviour against a live
   model, and when you claim an improvement, show the number.
5. **Mutation-check anything security- or correctness-critical.** Break the
   control on purpose and confirm a test goes red. Six rounds so far; it has
   repeatedly caught tests that were passing for the wrong reason.
6. **Report faithfully.** If something is wrong, say so with the output. Correct
   your own earlier claims when you find them wrong — in this project that has
   mattered more than once.

---

# PART 2 — Where the project stands

The ten-milestone hardening roadmap is complete (M1–M10) and so is a full
fine-tuning round. **444 tests pass**, mypy strict is clean across 26 files, CI
is green on every push. Latest commit: `d192360`.

**Modules:** `main.py` (CLI/REPL), `agent.py` (loop + context budget),
`tools.py` (6 tools, pydantic arg schemas), `sandbox.py` (filesystem boundary),
`observability.py` (JSONL logging), `config.py` (settings precedence),
`export_dataset.py` (logs → SFT dataset), `validate_dataset.py`,
`scripts/collect_dataset.py`, `scripts/holdout_eval.py`,
`scripts/build_notebook.py`, `scripts/smoke_train.py`,
`notebooks/train_omniagent_lora.ipynb`.

**Tools:** `calculate`, `get_current_time`, `file_info`, `read_file`,
`list_directory`, `search_text`.

**Models in Ollama:** `omniagent` (current fine-tune, 109 examples),
`omniagent-v1` (earlier, 47 examples), `qwen-ctx8k` (stock qwen2.5-coder:7b with
`num_ctx 8192`), plus the stock pulls.

## Last measured state — temperature 0, 16 held-out questions

| model | correct | tool pick | follow-ups | honest | steps |
|---|---|---|---|---|---|
| `omniagent` | **10/10** | 5/7 | 5/5 | 1/1 | **66** |
| `omniagent-v1` | 10/10 | 5/7 | 5/5 | 0/1 | 74 |

Use `omniagent`. Growing the dataset from 47 to 109 examples did **not**
measurably improve accuracy — the two models trade one question each way, inside
the noise of a 16-question set. What improved results was fixing the agent
(catching repeated succeeding actions: one more correct answer, six fewer steps),
not adding data.

## Known, reproducible weaknesses

- **Tool choice, 5/7, failing the same two questions in every run of both
  models:** "which of two files has more lines" and "what is the last line of X".
  `file_info` returns exactly those facts, clearly labelled, and the 1.5B model
  still gets them wrong — it reported `test_sandbox.py` (351 lines) as longer
  than `test_config.py` (354). A capability limit, not a missing tool.
  **Do not demo multi-file comparisons on the 1.5B.**
- The held-out set is only 16 questions, so it cannot resolve small differences.

## The next ten-percent milestones, in order

1. **Rehearse the demo.** 2026-10-10 is the date. Run
   `.venv/Scripts/python.exe main.py --profile demo` and walk the questions you
   would actually show. Fix what looks clumsy. This matters more than any
   remaining feature.
2. **Measure `qwen-ctx8k`:**
   `.venv/Scripts/python.exe scripts/holdout_eval.py qwen-ctx8k` — so the
   demo-model choice has evidence behind it. That script refuses to run if any
   question appears in the training bank, and pins temperature to 0 because an
   earlier pair of runs disagreed on one question and the difference turned out
   to be variance. One model per invocation: concurrent runs fight over the 4 GB
   card and every timing becomes meaningless.
3. **Grow the held-out set to ~50 questions** so comparisons can mean something.
4. After the demo, optionally: streaming output, session persistence — both were
   dropped from the original ten to make room.

## Traps already paid for once — do not rediscover them

- **Ollama does not autostart.** `Start-Process
  "$env:LOCALAPPDATA\Programs\Ollama\ollama.exe" -ArgumentList "serve"
  -WindowStyle Hidden`, then allow ~15 s. Backgrounding it from the Bash tool
  with `&` does not work.
- **Background tasks die with the session.** See the pacing rules above.
- **Ollama defaults to a 4096-token context** whatever the model supports, and
  truncates from the *front*, taking the system prompt with it. A 7B model asked
  how many lines a file had once replied "The current date and time is Friday, 2
  October 2026" — it had never seen the question. The agent now trims the
  conversation itself; generated Modelfiles set `num_ctx`.
- **`pip install torch --index-url .../cu126 --upgrade` is a no-op** when a CPU
  build of the same version is present: pip treats `2.14.1+cpu` and
  `2.14.1+cu126` as the same version. Use `--force-reinstall` with the explicit
  local version.
- **A quoted bash heredoc still eats `\n` and `\\` in Python source.** Five
  `SyntaxError: unterminated string literal` incidents came from this, including
  one from a Windows path containing `\U`. Use the Write/Edit tools, or build the
  escape with `chr(10)`.
- **Global `pip` fails under the sandbox** ("Unexpected condition testing for
  writable directory"). `pip` inside the project venv on `D:` works fine.
- **`\b` does not match inside `OMNIAGENT_API_KEY`**, because `_` is a word
  character — that cost the secret scanner every prefixed environment variable
  for two milestones.

## If the tools or the system prompt change

Re-collect the dataset from scratch. Both are part of every training example, so
mixing versions teaches the model two formats. Archive the old log rather than
appending.

```
.venv/Scripts/python.exe scripts/collect_dataset.py --model qwen-ctx8k --log-file data/collect.jsonl
.venv/Scripts/python.exe export_dataset.py "data/collect.jsonl" -o data/dataset.jsonl --stats
.venv/Scripts/python.exe validate_dataset.py data/dataset.jsonl
```

Then open `notebooks/train_omniagent_lora.ipynb` in VS Code, select the project's
`.venv` as the kernel and run it. It chooses QLoRA 4-bit on CUDA by itself (the
card is an RTX 3050 Laptop, 4 GB), merges on the CPU, converts to GGUF,
registers the model with Ollama and finishes by running the agent against it.
About 30 minutes on this machine.

---

**Start by confirming the three gates are green and Ollama is up, then tell me
the first 10% milestone you are taking and get on with it.**
