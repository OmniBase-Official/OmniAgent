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
| [`tools.py`](tools.py) | Tool implementations and the registry the prompt is generated from. |
| [`test_offline.py`](test_offline.py) | Tests for the tools and the parser — runs without a model. |

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

Tools never raise: failures come back as `Error: ...` strings, which the agent
reads as an Observation and can recover from.

### Adding your own

Add an entry to `TOOLS` in [`tools.py`](tools.py) — the system prompt is
generated from that registry, so the model learns about the new tool
automatically:

```python
TOOLS["reverse_text"] = Tool(
    name="reverse_text",
    signature="reverse_text(text: str)",
    description="Reverse a string. Use it when the user asks for text backwards.",
    example="hello world",
    run=lambda text: text[::-1],
)
```

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
pip install -r requirements.txt
```

On macOS/Linux, activate with `source .venv/bin/activate`.

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

## Tests

The tools and the parser are covered by tests that need no model running:

```bash
python test_offline.py
```

`pytest -q test_offline.py` works too, if you have pytest installed.

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

- Python 3.9+ (developed on 3.12)
- Ollama, running locally
- `openai` and `pydantic` — see [`requirements.txt`](requirements.txt)

## License

MIT.
