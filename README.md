# OmniAgent

A local-only **ReAct (Reason + Act)** agent, written from scratch in ~600 lines of Python.

No LangChain. No LlamaIndex. No cloud API. The agent talks to a model running on
your own machine through [Ollama](https://ollama.com), using the `openai` client
library pointed at `http://localhost:11434/v1`. Nothing leaves localhost.

<img src="docs/demo1.svg" alt="Cloning OmniAgent and asking it five questions: it multiplies, carries the result into a follow-up, then is refused by read_file, told to use file_info, and takes the hint." width="860">

That cast is a snapshot of a real session (`main.py --profile demo`, model
`omniagent-v2`), not a mock-up — including the moment `read_file` refuses a
file too long to return, the error names the tool that can answer, and the
agent switches to it. Regenerate it with
`python scripts/make_demo_svg.py`.

---

## Why it exists

Most "agent" tutorials hide the interesting part behind a framework. OmniAgent
keeps the loop in plain sight so you can read it, break it, and change it:

| File | Responsibility |
|---|---|
| [`main.py`](main.py) | CLI entry point: argument parsing, preflight checks, REPL. |
| [`agent.py`](agent.py) | The ReAct engine: system prompt, completion calls, output parsing, tool dispatch, memory. |
| [`tools.py`](tools.py) | Tool implementations, their pydantic argument schemas, and the registry the prompt is generated from. |
| [`sandbox.py`](sandbox.py) | The filesystem boundary the file tools work inside, and its threat model. |
| [`config.py`](config.py) | One settings model, and the documented precedence that fills it. |
| [`observability.py`](observability.py) | Structured JSON-lines logging: session/turn/step context, credential redaction, truncation. |
| [`export_dataset.py`](export_dataset.py) | Replays run logs into a chat-format SFT dataset. |
| [`validate_dataset.py`](validate_dataset.py) | Refuses a malformed dataset, or one containing a credential, before training. |
| [`notebooks/`](notebooks) | The local LoRA fine-tune, merge, GGUF export and Ollama registration. |
| [`scripts/`](scripts) | Dataset collection, the CPU training smoke test, and the notebook generator. |
| [`tests/`](tests) | pytest suite — tools, parser, logger, the loop and the exporter, all without a model. |

---

## How the loop works

```
                 ┌──────────────────────────────────────────┐
                 │  system prompt (tool catalogue + format)  │
                 └────────────────────┬─────────────────────┘
                                      ▼
   user question ──►  ┌───────────────────────────────┐
                      │  LLM generates:               │
                      │    Thought: ...               │
                      │    Action: calculate          │
                      │    Action Input: 2400 * 0.15  │
                      │  (generation STOPS here)      │
                      └───────────────┬───────────────┘
                                      ▼
                      ┌───────────────────────────────┐
                      │  Python parses + runs the tool│
                      │  Observation: ... = 360       │
                      └───────────────┬───────────────┘
                                      ▼
                        appended to the scratchpad,
                        loop repeats (max 8 steps)
                                      │
                                      ▼
                      ┌───────────────────────────────┐
                      │  Thought: ...                 │
                      │  Final Answer: ...  ──► user  │
                      └───────────────────────────────┘
```

Three details do most of the heavy lifting with small open-source models:

1. **A hard stop sequence on `Observation:`.** Without it a 7B model happily
   hallucinates the tool's output and answers from its imagination. Generation
   is cut off the moment it tries.
2. **A forgiving parser.** Small models write ``` ```2 + 2``` ```,
   `calculate(2 + 2)`, `"2 + 2"`, or `(none)`. The parser in
   [`agent.py`](agent.py) normalises all of those instead of failing.
3. **A format-correction nudge.** If a reply contains neither an `Action:` nor a
   `Final Answer:`, the agent replies with the exact expected shape rather than
   crashing or giving up.

**Memory:** only the question/answer pairs are carried between turns. The
Thought/Action/Observation scratchpad is dropped once a question is answered, so
the context window stays clean across a long session.

---

## Tools

| Tool | Description |
|---|---|
| `calculate(expression: str)` | Evaluates arithmetic: `+ - * / // % **`, parentheses, `pi`/`e`/`tau`, and `sqrt`, `log`, `log10`, `exp`, `sin`, `cos`, `tan`, `floor`, `ceil`, `round`, `abs`, `min`, `max`, `factorial`. |
| `get_current_time()` | Current local date/time plus the UTC equivalent and the day of the week. |
| `read_file(path: str)` | Returns a workspace file's text, numbered by line. |
| `list_directory(path: str)` | Lists a workspace directory, folders first, with file sizes. |
| `search_text(query: str, path: str)` | Finds a literal substring under a path and reports `file:line` matches. |

`calculate` does **not** use `eval()`. The expression is parsed into an AST and
walked against an explicit allow-list, so `__import__('os').system(...)` and
friends return an error instead of running. Exponents and factorials are capped
so `9 ** 9 ** 9` cannot exhaust memory.

### Typed arguments

A tool declares its arguments as a pydantic model and receives a validated
instance. One declaration drives three things: validation, the signature printed
into the system prompt, and the error message the model reads when it gets the
call wrong.

The dispatcher accepts the three input shapes small models actually emit:

| Action Input | Becomes |
|---|---|
| `2 + 2` | the bare value, for a tool with exactly one field |
| `{"expression": "2 + 2"}` | a JSON object, for any tool |
| `none` | nothing, for a tool with no fields |

A bad call never reaches the tool. It comes back as an Observation specific
enough to fix:

```
Action Input: {"formula": "2 + 2"}
Observation: Error: invalid arguments for calculate(expression: str) --
             formula: Extra inputs are not permitted. Action Input should be
             the expression itself on one line, e.g. '(1250 * 0.07) + sqrt(144)'.
```

Tools never raise either: a crash is caught, logged with a traceback, and
returned as `Error: ...`.

### Adding your own

Declare a schema and a handler, then register them. The system prompt is
generated from the registry, so the model learns the new tool and its argument
names automatically:

```python
class ReverseTextArgs(ToolArgs):
    text: str = Field(description="The text to reverse.")


def _run_reverse_text(args: ReverseTextArgs) -> str:
    return args.text[::-1]


TOOLS["reverse_text"] = Tool(
    name="reverse_text",
    description="Reverse a string. Use it when the user asks for text backwards.",
    args_model=ReverseTextArgs,
    run=_run_reverse_text,
    example="hello world",
)
```

`mypy` enforces the pairing: giving `run` a handler that does not accept
`ReverseTextArgs` is a type error, not a runtime surprise.

---

## The filesystem boundary

`read_file`, `list_directory` and `search_text` work inside one **workspace**
directory — the current directory by default, or `--workspace PATH`. They are
read-only by construction: nothing in [`sandbox.py`](sandbox.py) writes, renames
or deletes.

This matters more than it looks. Every path a tool receives was chosen by a
language model, and everything a tool returns becomes an Observation — which
goes into the context window, into the log, and from there into the training
dataset. A path the agent should not reach is not just a read it should not
perform; it is a leak that gets written down and then trained on.

| Threat | Mitigation |
|---|---|
| `../../../etc/passwd`, `..\..\Windows\System32` | The path is resolved, then required to sit under the workspace root. |
| Absolute paths outside the root | Same check — an absolute path is allowed only if it lands inside the workspace. |
| Symlinks and junctions pointing out | `Path.resolve()` follows them *before* the containment check, so the target is tested, not the link. |
| Secrets inside the workspace | Dot-files and dot-directories (`.env`, `.git`, `.ssh`) are refused outright, as are credential suffixes (`.pem`, `.key`, `.p12`, …) and names (`id_rsa`, `credentials`). |
| The agent reading its own log back | The active `--log-file` is denied, so earlier conversations cannot re-enter the context and the dataset. |
| Huge files exhausting memory | Size is checked before the read (100 KB), and the returned text is capped (16 000 chars). |
| Binary files flooding the context | A NUL byte in the first 8 KB rejects the file. |
| Devices — `CON`, `NUL`, `COM1`, `\.\PhysicalDrive0` | Only regular files pass. |
| UNC and network paths, NUL bytes in a path | Rejected before resolution. |
| ReDoS via a model-supplied pattern | There is no regex. `search_text` is literal substring matching, so a hostile pattern has nothing to backtrack over. |

Asked directly to exfiltrate, a live model gets nowhere:

```
Action: read_file
Action Input: .env
Observation: Error: hidden files and directories (anything starting with '.') are not readable

Action: read_file
Action Input: ../../Windows/System32/drivers/etc/hosts
Observation: Error: path is outside the workspace (D:\code-project\OmniAgent);
             only files under it can be read
```

Line endings are normalised on read, so the same file produces the same
Observation on Windows and on Linux rather than baking the collection platform
into the dataset.

---

## Setup

### 1. Install and start Ollama

Download from [ollama.com/download](https://ollama.com/download), then:

```bash
ollama serve
```

On Windows the desktop app usually starts the server for you; `ollama serve`
in a terminal works too. Verify it is listening:

```bash
curl http://localhost:11434/api/tags
```

### 2. Pull a model

```bash
ollama pull qwen2.5:7b
```

`qwen2.5:7b` is the default and follows the ReAct format reliably. Any
instruction-tuned model of 7B or larger works — `qwen2.5-coder:7b`,
`llama3.1:8b`, `mistral:7b`, `gemma2:9b`. See which ones you already have with
`ollama list`.

> Avoid pure reasoning models (e.g. `deepseek-r1`) here — they emit their own
> `<think>` blocks, which fight the Thought/Action/Observation format.

### 3. Install the Python dependencies

```bash
python -m venv .venv
```

```bash
.venv\Scripts\activate
```

```bash
pip install -e .
```

On macOS/Linux, activate with `source .venv/bin/activate`.

To work on OmniAgent itself, install the lint/type/test toolchain too:

```bash
pip install -e ".[dev]"
```

The fine-tuning pipeline has its own, much heavier, extras — only needed to
run `scripts/smoke_train.py` locally, not to run the agent:

```bash
pip install -e ".[training]"
```

---

## Usage

Interactive REPL:

```bash
python main.py
```

One-shot question:

```bash
python main.py --ask "What is 15% of 2400 plus the square root of 169?"
```

Pick a different model, hide the reasoning trace:

```bash
python main.py --model qwen2.5-coder:7b --quiet
```

### CLI options

| Flag | Default | Meaning |
|---|---|---|
| `--model` | `qwen2.5:7b` | Ollama model tag (env: `OMNIAGENT_MODEL`). |
| `--base-url` | `http://localhost:11434/v1` | OpenAI-compatible endpoint (env: `OMNIAGENT_BASE_URL`). |
| `--max-steps` | `8` | Maximum ReAct iterations per question. |
| `--temperature` | `0.1` | Sampling temperature. Low values keep the format stable. |
| `--quiet` | off | Hide the Thought/Action/Observation trace. |
| `--ask` | — | Answer one question and exit. |
| `--log-file` | — | Append structured JSON-lines logs here (env: `OMNIAGENT_LOG_FILE`). |
| `--log-level` | `INFO` | `DEBUG`, `INFO`, `WARNING` or `ERROR` (env: `OMNIAGENT_LOG_LEVEL`). |
| `--log-console` | off | Also stream the JSON logs to stderr. |
| `--workspace` | cwd | Directory the file tools may read inside. |
| `--max-retries` | `2` | Retries after a transient model-server failure. |
| `--timeout` | `180` | Per-request timeout in seconds. |
| `--config` | `./omniagent.toml` | Config file to read. |
| `--profile` | — | Named `[profile.NAME]` section to apply. |
| `--print-config` | — | Show every resolved setting and its source, then exit. |

Every setting in the table has a matching `OMNIAGENT_<NAME>` environment
variable; see [Settings](#settings) for the precedence.

### REPL commands

`/help` · `/tools` · `/reset` · `/quit`

---

## Settings

Every setting has one home and one precedence, and the agent will tell you
which layer each value came from:

```
command line  >  environment  >  .env  >  [profile.NAME]  >  [defaults]  >  built-in
```

`omniagent.toml` in the working directory is picked up automatically, or point
at one with `--config`:

```toml
[defaults]
model = "qwen2.5-coder:7b"
log_level = "INFO"

[profile.demo]
max_steps = 12
log_file = "data/demo.jsonl"
temperature = 0.0

[profile.collect]
log_file = "data/collect.jsonl"
log_level = "DEBUG"
verbose = false
```

```bash
python main.py --profile demo --ask "What is 23% of 1800?"
```

Stuck on why a setting is what it is? Ask:

```bash
python main.py --profile demo --print-config
```

```
model                 qwen2.5-coder:7b                    file:defaults
base_url              http://localhost:11434/v1           built-in
api_key               ***redacted***                      built-in
temperature           0.0                                 profile:demo
max_steps             12                                  profile:demo
log_file              data/demo.jsonl                     profile:demo
```

Every setting also has an environment variable, `OMNIAGENT_` plus its name in
upper case — `OMNIAGENT_MODEL`, `OMNIAGENT_MAX_STEPS`, `OMNIAGENT_LOG_FILE`. A
`.env` file beside the config supplies the same names; the real environment
wins over it. That parser is deliberately boring: `KEY=value`, `#` comments,
optional quotes. No substitution, no expansion, nothing executed.

A typo is an error, not a silent default — `modle = "..."` is refused with a
list of the settings that do exist, and so is an unknown `--profile`, an
out-of-range value (naming the layer that supplied it) and an invalid log
level. `api_key` is never printed back.

---

## Example session

```
$ python main.py --model qwen2.5-coder:7b --ask "What is 15% of 2400, then add the
  square root of 169 to it? Also tell me what day of the week it is today."

    endpoint : http://localhost:11434/v1
    model    : qwen2.5-coder:7b

  [step 1]
  Thought      : I need to calculate 15% of 2400 first, then add the square root of 169.
  Action       : calculate
  Action Input : (2400 * 0.15) + sqrt(169)
  Observation  : (2400 * 0.15) + sqrt(169) = 373

  [step 2]
  Thought      : Now I need to find out the current day of the week.
  Action       : get_current_time
  Action Input : (none)
  Observation  : Local time: 2026-09-29 09:08:44 (Tuesday, UTC+0700) | UTC: 2026-09-29 02:08:44

  [step 3]
  Thought      : I have both pieces of information.

OmniAgent: 15% of 2400 plus the square root of 169 is 373, and today is Tuesday,
29 September 2026.
```

---

## When things go wrong

A local model fails in two characteristic ways, and both are handled rather
than left to the user.

**The server is briefly unwell.** The first request after an idle period
routinely times out while Ollama pages the model in. Connection errors,
timeouts and the busy status codes (408, 409, 425, 429, 500, 502, 503, 504) are
retried with exponential backoff; each attempt is logged as `agent.llm.retry`
with its delay. A 404 for a model tag that was never pulled is *not* retried,
because waiting cannot create it. The OpenAI client's own retry is switched off
so the attempt count means what it says.

```
WARNING agent.llm.retry  attempt=1/3 delay=1.0s status=503
WARNING agent.llm.retry  attempt=2/3 delay=2.0s status=503
INFO    agent.llm.response
```

**The model gets stuck.** A small model will resend an Action that cannot work
until the step budget runs out. When the same tool and input fail identically
`max_repeated_actions` times, the agent logs `agent.loop.repeated_action` and
tells the model so directly -- stop sending it, fix the input, use another
tool, or answer -- instead of handing back the same Observation again.

`Ctrl-C` during a step returns to the prompt rather than printing a traceback.

| Setting | Default | Meaning |
|---|---|---|
| `max_retries` | `2` | Extra attempts after a transient failure. |
| `retry_backoff` | `1.0` | Seconds before the first retry, doubled thereafter. |
| `max_repeated_actions` | `2` | Identical failing Actions tolerated before intervening. |
| `timeout` | `180.0` | Per-request timeout in seconds. |

---

## Logging

The console trace is for you; the log stream is for machines:

```bash
python main.py --log-file run.jsonl --ask "What is 18% of 1500?"
```

Every step of the loop becomes one JSON object per line:

```json
{"ts":"2026-10-01T10:16:49.357Z","level":"INFO","logger":"omniagent.agent","event":"agent.llm.response","message":"agent.llm.response","model":"qwen2.5-coder:7b","elapsed_ms":14097.35,"finish_reason":"stop","prompt_tokens":791,"completion_tokens":61,"session_id":"37202807c137","turn":1,"step":1}
```

One answered question produces this sequence, so a log alone explains what the
agent did and how long each part took:

| Event | Carries |
|---|---|
| `agent.connection.ok` | endpoint, whether the requested model is installed |
| `agent.turn.start` | question, step budget, history size |
| `agent.llm.request` / `.response` | model, latency, finish reason, token counts, the raw reply |
| `agent.tool.call` / `.result` | tool, input, observation, `ok`, latency |
| `agent.step.final_answer` | the thought and the answer |
| `agent.turn.end` | answer, steps used, total latency |

Things going wrong get their own events, at `WARNING` or `ERROR` with a
traceback attached: `agent.format.violation`, `agent.budget.exhausted`,
`tool.unknown`, `tool.crashed`, `agent.llm.unreachable`, `agent.llm.error`.

Context is ambient — `session_id`, `turn` and `step` attach themselves through
`observability.bind()` rather than being threaded through every call site.
Fields whose names look like credentials (`api_key`, `token`, `password`, ...)
are masked, including inside nested dicts, and long values such as prompts are
truncated, so a log file stays safe to paste into a bug report.

Logs never go to stdout: that belongs to the human-readable trace. Use a file,
or `console=True` to stream JSON to stderr.

---

## Training data from your own runs

The log already records the exact conversation the model saw: the system
prompt, the question, each raw reply and each Observation. That is a supervised
fine-tuning dataset, so there is no separate collection step — just run the
agent with `--log-file`, then replay:

```bash
python export_dataset.py "data/*.jsonl" -o data/dataset.jsonl --stats
```

```
turns seen : 3
exported   : 3
step counts: 2 steps: 2, 3 steps: 1
tools      : calculate: 2, get_current_time: 2
```

Each line of the output is one turn in the format TRL and transformers consume:

```json
{"messages": [
  {"role": "system",    "content": "You are OmniAgent..."},
  {"role": "user",      "content": "What is 15% of 2400 plus sqrt(169)?"},
  {"role": "assistant", "content": "Thought: ...
Action: calculate
Action Input: (2400 * 0.15) + sqrt(169)"},
  {"role": "user",      "content": "Observation: (2400 * 0.15) + sqrt(169) = 373"},
  {"role": "assistant", "content": "Thought: I have the final result.
Final Answer: ..."}
]}
```

### What is deliberately left out

Training on a turn where the model broke format teaches it to break format, so
the exporter is strict by default:

| Dropped | Why |
|---|---|
| `agent.format.violation`, `agent.loop.repeated_action`, `agent.budget.exhausted` | The turn contains a message the log does not record verbatim, so it cannot be replayed faithfully. Never exported. |
| Any truncated field | A shortened prompt or reply is corrupt training data. |
| Turns with no Final Answer | The conversation never reached one. |
| Turns where a tool returned an error | Pass `--include-tool-errors` to keep them. |
| Identical conversations | De-duplicated by digest. |

Every example is validated before it is written: it must start with a non-empty
system prompt, alternate user/assistant, end on an assistant turn, and contain
no empty message.

Multi-turn sessions are reconstructed with their history, exactly as the agent
sent it — a dropped turn still counts as history for the turns after it.

Because of this, the log schema *is* the training data format. Changing an
event's fields changes the dataset.

---

## Fine-tuning on your own runs

The loop fights small models drifting out of the Thought/Action/Observation
format. A model trained on that exact format drifts less, and the dataset for it
is already being collected every time you pass `--log-file`.

### Collecting enough of it

Four runs is not a training set. [`scripts/collect_dataset.py`](scripts/collect_dataset.py)
walks a bank of ~46 sessions covering every tool — arithmetic, dates, file
reading, searching, and multi-turn conversations that carry history — against a
real local model:

```bash
python scripts/collect_dataset.py --model qwen2.5-coder:7b
```

`--resume` skips questions the log already has an answer for, so an interrupted
run tops itself up rather than starting over. `--dry-run` lists what it would
ask; `--questions FILE` supplies your own bank, one session per line (a plain
question, or a JSON array for a conversation).

```
run the agent  ->  JSONL log  ->  export_dataset.py  ->  validate_dataset.py
                                                              |
                     LoRA (this machine)  <---------------- dataset.jsonl
                             |
                     merge -> GGUF -> ollama create -> python main.py --model omniagent
```

Every arrow stays on one machine. That is not convenience, it is the same rule
the rest of the project follows: the dataset holds your questions, your system
prompt, and the contents of any file the agent read with `read_file` or
`search_text`. Uploading it to a hosted notebook would be the one step that
breaks the rule — and it buys nothing, because Ollama is already here, so there
is no GGUF to download back either.

### Validate before you train

```bash
python validate_dataset.py data/dataset.jsonl
```

```
examples   : 47
messages   : min 5, max 9, mean 5.5
characters : 237,199
tools      : calculate: 33, get_current_time: 8, list_directory: 6, read_file: 5, search_text: 3
verdict    : OK
```

It refuses malformed conversations, and it refuses a dataset containing
anything shaped like a credential — an OpenAI key, an AWS key, a GitHub or
Slack token, a private key block, a bearer token, an `API_KEY=` assignment. A
model trained on a leaked key will reproduce it, so this is an error rather
than a warning. Too few examples, duplicates and a dataset with no tool use are
warnings: your call.

### The notebook

[`notebooks/train_omniagent_lora.ipynb`](notebooks/train_omniagent_lora.ipynb)
runs locally — open it in VS Code, pick this project's `.venv` as the kernel, and
run the cells. It validates the dataset before loading a single weight, trains a
LoRA adapter, merges it, converts to GGUF, writes a checksum manifest, registers
the model with Ollama, and finishes by running `main.py` against it.

```bash
pip install -e ".[training]"
```

**It picks its strategy from your hardware.** With CUDA it loads the base model
in 4-bit (QLoRA), which fits a 4 GB card; without CUDA it falls back to fp32 on
the CPU, which is only sensible for a tiny model. Merging happens on the CPU in
fp16, because a 4-bit model cannot be merged into and a small card has no room
for a full-precision copy anyway. Set `FOUR_BIT = False` if you have VRAM to
spare and want bf16 LoRA instead.

**Licensing matters here.** The default base model is `Qwen/Qwen2.5-1.5B-Instruct`,
which is Apache-2.0. The 3B of the same family is released under a different,
more restrictive licence. Read the model card of whatever you put in
`BASE_MODEL` before you train, not after.

### What is actually verified

Running the notebook needs a GPU, a 3 GB download and a quarter of an hour, so
the test suite checks what it can in milliseconds and the rest was checked by
running it:

- [`tests/test_notebook.py`](tests/test_notebook.py) asserts it is valid
  nbformat, that every code cell parses, that it ships no saved outputs, that it
  still chooses its loading strategy from the hardware, that nothing uploads the
  dataset anywhere, and that the `Modelfile` cell really produces the file
  `ollama create` accepts.
- [`scripts/smoke_train.py`](scripts/smoke_train.py) runs the same steps on a CPU
  with a 135M model in about a minute, so an API change in transformers/trl/peft
  fails there rather than fifteen minutes into a real run.

```bash
python scripts/smoke_train.py
```

### What a real run produced

On an RTX 3050 Laptop (4 GB), 15.8 minutes end to end: 47 examples from real
runs, 3 epochs of QLoRA, final loss 1.0036, a 3.1 GB GGUF, registered as
`omniagent`.

Measured against stock `qwen2.5-coder:7b` on eight questions absent from the
collection bank — checked programmatically, so this is held out rather than a
re-run of the training data:

| | correct | used a tool | total time |
|---|---|---|---|
| `omniagent` (1.5B, fine-tuned) | 5/5 checkable | 7/8 | **55s** |
| `qwen2.5-coder:7b` (stock) | 5/5 checkable | 8/8 | 212s |

Same accuracy, roughly four times faster. Two bugs came out of that run which no
unit test would have found:

- **HTTP 400 on the first question needing a file read.** Ollama defaults to a
  4096-token context whatever the model supports, and this system prompt is
  ~900 tokens before any tool output. The generated `Modelfile` now sets
  `num_ctx`.
- **"How many lines does config.py have?" → "10,306".** That is the file's size
  in bytes, which `list_directory` had shown the model one step earlier; it
  conflated the units. `read_file` now states `278 lines, 10,306 bytes` in its
  header, both labelled. A fact the tool already holds should not be left to the
  model to infer.

If a fine-tune comes out worse than the stock model, say so and keep the stock
one. A fine-tune nobody measured is not an improvement.

---

## Tests

Everything is covered by a pytest suite that needs no model running. A scripted
fake client in [`tests/fakes.py`](tests/fakes.py) stands in for Ollama, so the
loop's behaviour — the messages it sends, what it remembers between turns, how
it handles a model that breaks format, where the step budget bites — is tested
deterministically:

```bash
pytest
```

The same three gates run in development, and all three must be green:

```bash
ruff check . && mypy && pytest
```

`mypy` runs with `strict = true` over every module and the tests — see
[`pyproject.toml`](pyproject.toml).

---

## CI

[`.github/workflows/ci.yml`](.github/workflows/ci.yml) runs the same three gates
on every push and pull request: `ruff check .`, `mypy`, `pytest`, on Python 3.12.

The training extras are deliberately not installed there — torch is gigabytes
and no test needs it. That difference is itself a thing to get wrong, so the
workflow was rehearsed locally in a throwaway virtualenv holding only
`pip install -e ".[dev]"`, where all three gates pass.

---

## Troubleshooting

| Symptom | Fix |
|---|---|
| `Cannot reach a local model server at http://localhost:11434/v1` | Ollama is not running. Start it with `ollama serve`. |
| `Model '...' is not installed on this Ollama server` | `ollama pull <model>`, or pass `--model` with one from `ollama list`. |
| The agent answers maths without calling `calculate` | Lower `--temperature`, or use a larger instruction-tuned model. |
| Replies keep breaking the format | The model is too small or is a reasoning model. Try `qwen2.5:7b` or `llama3.1:8b`. |
| It stops after 8 steps | Raise `--max-steps`. |
| A setting is not what you expected | `python main.py --print-config` names the layer each value came from. |

---

## Requirements

- Python 3.12+
- Ollama, running locally
- `openai` and `pydantic` — see [`pyproject.toml`](pyproject.toml)
  (`requirements.txt` is kept as a mirror for `pip install -r`)

## Coding time

<!--START_SECTION:waka-->

```txt
From: 17 May 2026 - To: 25 October 2026

Python            69 hrs 16 mins        █████████░░░░░░░░░░░░░░░░   35.97 %
Markdown          67 hrs 58 mins        ████████▓░░░░░░░░░░░░░░░░   35.29 %
Other             13 hrs 29 mins        █▓░░░░░░░░░░░░░░░░░░░░░░░   07.00 %
TypeScript        11 hrs 24 mins        █▒░░░░░░░░░░░░░░░░░░░░░░░   05.92 %
Bash              9 hrs 4 mins          █▒░░░░░░░░░░░░░░░░░░░░░░░   04.71 %
Text              4 hrs 36 mins         ▓░░░░░░░░░░░░░░░░░░░░░░░░   02.39 %
YAML              3 hrs 55 mins         ▓░░░░░░░░░░░░░░░░░░░░░░░░   02.04 %
TOML              1 hr 54 mins          ▒░░░░░░░░░░░░░░░░░░░░░░░░   00.99 %
JSON              1 hr 32 mins          ▒░░░░░░░░░░░░░░░░░░░░░░░░   00.80 %
C++               1 hr 26 mins          ▒░░░░░░░░░░░░░░░░░░░░░░░░   00.75 %
```

<!--END_SECTION:waka-->

The [WakaTime workflow](.github/workflows/waka-readme.yml) updates this section
daily at 00:00 UTC (07:00 in Thailand), or when triggered manually from GitHub
Actions. Add your WakaTime API key as the repository Actions secret
`WAKATIME_API_KEY` before running it. It displays account-wide, all-time coding
statistics for up to ten languages.

## License

MIT.
