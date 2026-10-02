# Next-chat prompt — OmniAgent

Paste everything below the line into a **new** Claude Code chat as the first
message. It is written to be self-contained; nothing from the previous
conversation is needed.

Keep this file updated at the end of each session.

---

Continue work on **OmniAgent**, a local-only ReAct agent at
`D:\code-project\OmniAgent` (private repo `mntoyg/OmniAgent`, branch `main`).
Reply to me in Thai. Commit and push after every work step.

## The rules this project is built on — do not break them

1. **Local only.** The `openai` client is deliberately pointed at Ollama
   (`base_url="http://localhost:11434/v1"`, `api_key="local-ollama"`). Nothing
   leaves localhost — including the training dataset, which is why fine-tuning
   happens on this machine and not on Colab.
2. **No frameworks.** The ReAct loop is hand-rolled. No LangChain, no
   LlamaIndex.
3. **Three gates, all green before every commit.** Run them with the project
   venv, never bare `python`:
   ```
   .venv/Scripts/python.exe -m ruff check .
   .venv/Scripts/python.exe -m mypy
   .venv/Scripts/python.exe -m pytest
   ```
4. **Measure, don't assume.** Every single round of data collection so far
   exposed a real defect that 440 green tests had missed. When you change
   behaviour, verify it against a live model, and when you claim an improvement,
   show the number.
5. **Mutation-check security- and correctness-critical code.** Break the control
   deliberately and confirm a test goes red. Five rounds of this have been done
   so far (49/49, then 10/10 on the context budget); it has caught several tests
   that were passing for the wrong reason.

## Where things stand

The ten-milestone hardening roadmap is complete (M1–M10, commits `d5212f5`
through `7570162`), and so is a full fine-tuning round. 444 tests pass, mypy
strict is clean across 26 files, CI is green on every push.

**Modules:** `main.py` (CLI/REPL), `agent.py` (the loop, context budget),
`tools.py` (6 tools + pydantic arg schemas), `sandbox.py` (filesystem boundary),
`observability.py` (JSONL logging), `config.py` (settings precedence),
`export_dataset.py` (logs → SFT dataset), `validate_dataset.py` (refuses bad
data), `scripts/collect_dataset.py`, `scripts/build_notebook.py`,
`scripts/smoke_train.py`, `notebooks/train_omniagent_lora.ipynb`.

**Tools:** `calculate`, `get_current_time`, `file_info`, `read_file`,
`list_directory`, `search_text`.

**Models in Ollama:** `omniagent` (the current fine-tune, 109 examples),
`omniagent-v1` (the earlier one, 47 examples), `qwen-ctx8k` (stock
qwen2.5-coder:7b with `num_ctx 8192`), plus the stock pulls.

### The last measured state, at temperature 0, on 16 held-out questions

| model | correct | tool pick | follow-ups | honest | steps |
|---|---|---|---|---|---|
| `omniagent` (after the latest fixes) | **10/10** | 5/7 | 5/5 | 1/1 | **66** |
| `omniagent-v1` | 10/10 | 5/7 | 5/5 | 0/1 | 74 |

`omniagent` is the one to use. More training data (47 → 109 examples) did **not**
measurably improve accuracy — the two models trade one question each way, which
is inside the noise of a 16-question set. What did improve things was fixing the
agent, not growing the dataset.

## Known, reproducible weaknesses

- **Tool choice, 5/7, on the same two questions in every run of both models:**
  "which of two files has more lines" and "what is the last line of X".
  `file_info` returns exactly those facts, clearly labelled, and the 1.5B model
  still answers from the file body or gets them wrong (it said `test_sandbox.py`
  — 351 lines — was longer than `test_config.py` — 354). This is a capability
  limit, not a missing tool. **Do not demo multi-file comparisons on the 1.5B.**
  Worth measuring whether `qwen-ctx8k` handles them, which has not been done.
- The held-out set is only 16 questions, so it cannot resolve small differences.
  Growing it is the cheapest way to make model comparisons meaningful.

## What to do next, roughly in order

1. **Rehearse the demo** — 2026-10-10 is the date. Run
   `python main.py --profile demo` and walk through the questions you would
   actually show. Fix whatever looks clumsy. This matters more than any
   remaining feature.
2. **Measure `qwen-ctx8k` on the held-out set** so the demo-model choice is
   evidence-based rather than assumed:
   ```
   .venv/Scripts/python.exe scripts/holdout_eval.py qwen-ctx8k
   ```
   That script refuses to run if any of its questions appear in the collection
   bank, so it stays genuinely held out. It pins temperature to 0, because an
   earlier pair of runs disagreed on one question and the difference turned out
   to be variance rather than the model. Run one model per invocation: two
   concurrent runs fight over the 4 GB card and every timing becomes
   meaningless.
3. **Grow the held-out set to ~50 questions** so a model comparison can mean
   something.
4. Optional, after the demo: streaming output, session persistence — both were
   dropped from the original ten to make room.

## Traps that have already cost time — do not rediscover them

- **Ollama does not autostart.** Launch it with PowerShell
  `Start-Process "$env:LOCALAPPDATA\Programs\Ollama\ollama.exe" -ArgumentList "serve" -WindowStyle Hidden`
  and allow ~15 s. Backgrounding it from the Bash tool with `&` does not work.
- **Background tasks do not survive the end of a session.** A 40-minute
  collection run and a 20-minute eval were both killed mid-way. For anything
  long, either run it in the foreground within the 10-minute tool limit, or use
  `--resume`, which `collect_dataset.py` supports for exactly this reason.
- **Ollama defaults to a 4096-token context** whatever the model's own limit is,
  and it truncates from the *front* — taking the system prompt with it. A 7B
  model asked how many lines a file had once replied "The current date and time
  is Friday, 2 October 2026", because it had never seen the question. The agent
  now trims the conversation itself, and generated Modelfiles set `num_ctx`.
- **`pip install torch --index-url .../cu126 --upgrade` is a no-op** when a CPU
  build of the same version is installed: pip treats `2.14.1+cpu` and
  `2.14.1+cu126` as the same version. Use `--force-reinstall` with the explicit
  local version.
- **A quoted bash heredoc still eats `\n` and `\\` in Python source.** Four
  separate `SyntaxError: unterminated string literal` incidents came from this.
  Use the Write/Edit tools, or build the escape with `chr(10)`.
- **Global `pip` fails under the sandbox** ("Unexpected condition testing for
  writable directory"). `pip` inside the project venv on `D:` works fine.
- **`\b` does not match inside `OMNIAGENT_API_KEY`**, because `_` is a word
  character. That one cost the secret scanner every prefixed environment
  variable for two milestones.

## If the dataset or the tools change

Re-collect from scratch. The system prompt and the tool catalogue are part of
every training example, so mixing versions teaches the model two formats.
Archive the old log rather than appending to it.

```
.venv/Scripts/python.exe scripts/collect_dataset.py --model qwen-ctx8k --log-file data/collect.jsonl
.venv/Scripts/python.exe export_dataset.py "data/collect.jsonl" -o data/dataset.jsonl --stats
.venv/Scripts/python.exe validate_dataset.py data/dataset.jsonl
```

Then open `notebooks/train_omniagent_lora.ipynb` in VS Code, select the
project's `.venv` as the kernel, and run it. It picks QLoRA 4-bit on CUDA by
itself (the card is an RTX 3050 Laptop, 4 GB), merges on the CPU, converts to
GGUF, registers the model with Ollama and finishes by running the agent against
it. About 30 minutes on this machine.
