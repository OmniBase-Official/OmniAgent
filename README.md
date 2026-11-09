# OmniAgent

A local-only **ReAct (Reason + Act)** agent, written from scratch in ~600 lines of Python.

No LangChain. No LlamaIndex. No cloud API. The agent talks to a model running on
your own machine through [Ollama](https://ollama.com), using the `openai` client
library pointed at `http://localhost:11434/v1`. Nothing leaves localhost.

<img src="docs/demo1.svg" alt="Cloning OmniAgent and asking it five questions: it multiplies, carries the result into a follow-up, then is refused by read_file, told to use file_info, and takes the hint." width="860">

That cast is a snapshot of a real session (`main.py --profile demo`, model
`omniagent-v2`), not a mock-up — including the moment `read_file` refuses a
file too long to return, the error names the tool that can answer, and the
agent switches to it.

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
| [`observability.py`](observability.py) | Structured JSON-lines logging with a closed, sanitized telemetry schema. |
| [`export_dataset.py`](export_dataset.py) | Pure conversion helpers remain; the export CLI is disabled pending approval. |
| [`validate_dataset.py`](validate_dataset.py) | Refuses a malformed dataset, or one containing a credential, before training. |

`eval-fixture/` is a small tracked subject directory for stable evaluation listings.
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

Tools return a short `Error: ...` observation when a call fails. Operational
telemetry records only the event status and safe metadata; exception text and
tracebacks are not persisted.

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
| The agent reading its own log back | Persistent operational logs are disabled; transcript paths remain excluded from any file-tool workspace. |
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
| `--verbose` | off | Show the Thought/Action/Observation trace; cannot be combined with `--quiet`. |
| `--ask` | — | Answer one question and exit. |
| `--log-file` | disabled | Persistent operational logs are rejected until retention/deletion rules are approved. |
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
max_steps = 8
temperature = 0.0

[profile.collect]
# Persistent logs are disabled until retention/deletion rules are approved.
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
log_file              None                                built-in
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

Persistent operational logging is disabled until the project owner approves
retention and deletion rules. The shipped profiles do not create log files,
and the CLI rejects `--log-file` from command-line, environment, `.env`, TOML
defaults, or TOML profiles until that policy exists. Direct
`observability.configure(log_file=...)` calls also fail before touching the
target path, including forced reconfiguration.
Sanitized console telemetry can be explicitly enabled with `--log-console`; it
contains only event/status, duration, step count, fixed tool name, model tag or
digest, runtime version, and a fixed `record_type` marker. Prompts, reasoning,
raw model replies, file contents, tool arguments or observations, secrets, raw
errors, stack traces, and final answers are never emitted by this sink.

Each console event is one JSON object written to stderr. Each line contains
only fields from a closed allowlist. New event fields are dropped until they
are explicitly added to the telemetry schema. No context ids, free-form
messages, timestamps, or exception details are emitted.

| Event | Carries |
|---|---|
| `agent.connection.*`, `agent.turn.*`, `agent.llm.*` | status, duration or step count, and model tag when relevant |
| `agent.tool.*` | status, duration, step count, and an allowlisted tool name |

The human-readable console trace is separate from operational logging. The
exporter rejects records marked as operational telemetry as well as legacy
records carrying an OmniAgent logger name, because neither is an approved
trajectory source.

---

## Dataset capture and training policy

Dataset collection, `--resume`, and the dataset-export CLI are disabled until
a separate sink, provenance contract, field preview, and retention/deletion
policy are approved. Operational logs are never dataset inputs. Evaluation
trials use only the synthetic fixture workspace and are tagged with
`record_type = "evaluation_trial"`; user-workspace data is prohibited from
evaluation and training. Existing training artifacts do not authorize new
collection or use of workspace data.

Grounding evaluation stages only the frozen synthetic fixture inventory in a
temporary workspace. Source text is normalized to LF and staged as UTF-8;
the frozen digest covers the staged paths and exact staged bytes. The digest is
checked before model requests and around trials. Concurrent untrusted writers
are outside the current threat model: these checks do not prevent a file swap
between a check and a read. The staging directory must be controlled by the
operator throughout a run.
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
From: 17 May 2026 - To: 10 October 2026

Python        46 hrs 11 mins        █████████░░░░░░░░░░░░░░░░   36.35 %
Markdown      40 hrs 47 mins        ████████░░░░░░░░░░░░░░░░░   32.09 %
Other         10 hrs 31 mins        ██░░░░░░░░░░░░░░░░░░░░░░░   08.28 %
Bash          7 hrs 49 mins         █▓░░░░░░░░░░░░░░░░░░░░░░░   06.16 %
TypeScript    5 hrs 19 mins         █░░░░░░░░░░░░░░░░░░░░░░░░   04.19 %
YAML          3 hrs 50 mins         ▓░░░░░░░░░░░░░░░░░░░░░░░░   03.02 %
Text          3 hrs 14 mins         ▓░░░░░░░░░░░░░░░░░░░░░░░░   02.55 %
TOML          1 hr 50 mins          ▒░░░░░░░░░░░░░░░░░░░░░░░░   01.45 %
PowerShell    1 hr 15 mins          ▒░░░░░░░░░░░░░░░░░░░░░░░░   00.99 %
JSON          1 hr 3 mins           ▒░░░░░░░░░░░░░░░░░░░░░░░░   00.83 %
```

<!--END_SECTION:waka-->

The [WakaTime workflow](.github/workflows/waka-readme.yml) updates this section
daily at 00:00 UTC (07:00 in Thailand), or when triggered manually from GitHub
Actions. Add your WakaTime API key as the repository Actions secret
`WAKATIME_API_KEY` before running it. It displays account-wide, all-time coding
statistics for up to ten languages.

## License

MIT.
