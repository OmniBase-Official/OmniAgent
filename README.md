# OmniAgent

A local-only **ReAct (Reason + Act)** agent, written from scratch in ~600 lines of Python.

No LangChain. No LlamaIndex. No cloud API. The agent talks to a model running on
your own machine through [Ollama](https://ollama.com), using the `openai` client
library pointed at `http://localhost:11434/v1`. Nothing leaves localhost.

---

## Why it exists

Most "agent" tutorials hide the interesting part behind a framework. OmniAgent
keeps the loop in plain sight so you can read it, break it, and change it:

| File | Responsibility |
|---|---|
| [`main.py`](main.py) | CLI entry point: argument parsing, preflight checks, REPL. |
| [`agent.py`](agent.py) | The ReAct engine: system prompt, completion calls, output parsing, tool dispatch, memory. |
| [`tools.py`](tools.py) | Tool implementations, their pydantic argument schemas, and the registry the prompt is generated from. |
| [`observability.py`](observability.py) | Structured JSON-lines logging: session/turn/step context, credential redaction, truncation. |
| [`tests/`](tests) | pytest suite for the tools, the parser and the logger — runs without a model. |

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

### REPL commands

`/help` · `/tools` · `/reset` · `/quit`

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

## Tests

The tools, the parser and the logging core are covered by a pytest suite that
needs no model running:

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

## Troubleshooting

| Symptom | Fix |
|---|---|
| `Cannot reach a local model server at http://localhost:11434/v1` | Ollama is not running. Start it with `ollama serve`. |
| `Model '...' is not installed on this Ollama server` | `ollama pull <model>`, or pass `--model` with one from `ollama list`. |
| The agent answers maths without calling `calculate` | Lower `--temperature`, or use a larger instruction-tuned model. |
| Replies keep breaking the format | The model is too small or is a reasoning model. Try `qwen2.5:7b` or `llama3.1:8b`. |
| It stops after 8 steps | Raise `--max-steps`. |

---

## Requirements

- Python 3.10+ (developed on 3.12)
- Ollama, running locally
- `openai` and `pydantic` — see [`pyproject.toml`](pyproject.toml)
  (`requirements.txt` is kept as a mirror for `pip install -r`)

## License

MIT.
