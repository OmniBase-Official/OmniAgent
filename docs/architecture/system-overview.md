# OmniAgent system overview

**Baseline:** `ae5cd95` on `main`, 2026-11-04. Adopted from a Codex draft
written at `f37044d` under ADR-0001; **`git diff --name-only f37044d..HEAD`
changes no source file**, so the source claims below carry over unchanged.
Gates re-run at this baseline: `ruff` clean, `mypy` clean over 45 source
files, 658 tests passed in 16.48 s.

This page describes **checked-in source**. It is not a statement of approved
policy — where the two differ,
[the agentic MVP contract](../pm/agentic-mvp-contract-2026-11-03.md) governs,
and each difference is marked below. It does not claim that the complete
workflow is offline or that the process is an operating-system security
boundary.

## Product shape

OmniAgent is a local-first, hand-written ReAct assistant. The CLI resolves
configuration, establishes logging and a workspace, checks the model server,
and starts a one-shot or interactive turn. `agent.py` constructs a prompt from
a fixed system prompt and a typed registry of six tools, then sends
OpenAI-compatible chat completions to a configurable endpoint whose default is
`http://localhost:11434/v1` (`agent.py:34`).

The model proposes at most one action per reply. Application code parses the
response, validates tool arguments, dispatches only registered tools, and
returns a real observation to the model. Naming an unregistered tool does not
create that capability.

**Contract delta.** The contract requires loopback to be *enforced*, not
defaulted, and requires a per-task tool allowlist the dispatcher honours.
Neither exists in this source. Gate 1 is brief 14, in flight; gate 2 is
unassigned.

## Runtime and data flow

```mermaid
sequenceDiagram
    actor Operator
    participant CLI as main.py / config.py
    participant Log as observability.py
    participant Loop as agent.py ReActAgent
    participant Endpoint as Configured OpenAI-compatible endpoint
    participant Registry as tools.py typed registry
    participant Boundary as sandbox.py Workspace
    participant Files as Configured workspace
    participant Pipeline as Dataset and evaluation scripts
    participant Train as Local training workflow

    Operator->>CLI: question and settings
    CLI->>CLI: resolve and validate layered configuration
    CLI->>Log: configure JSONL file and/or stderr
    CLI->>Boundary: establish workspace and deny transcript paths
    CLI->>Loop: construct agent and rendered tool catalogue
    Loop->>Endpoint: model-list preflight and chat completion
    Endpoint-->>Loop: Thought / Action / Final Answer text
    Loop->>Registry: parse action and validate typed arguments
    Registry->>Boundary: read/list/search/inspect, or calculate/time
    Boundary->>Files: bounded read-only operation
    Files-->>Boundary: content, listing, matches, facts, or refusal
    Boundary-->>Registry: observation text
    Registry-->>Loop: observation
    Loop->>Log: question, prompt, reply, tool input, observation, events
    Loop->>Endpoint: next completion with scratchpad and bounded history
    Loop-->>CLI: final answer or error/step-limit outcome
    Log-->>Pipeline: operator-selected run log
    Pipeline->>Pipeline: collect/export, validate, fingerprint, evaluate
    Pipeline-->>Train: operator-selected dataset and sidecar
    Train->>Train: load, train, merge, convert, register with Ollama
```

The endpoint is a trust boundary. The default is loopback, but `base_url` is
configurable. Questions, prompt context, tool inputs, and observations go to
that configured endpoint. A non-local endpoint therefore receives user and
workspace content. **The README's "Nothing leaves localhost"
(`README.md:7`) is too broad** for a configurable endpoint and for the full
repository workflow, which downloads packages and model weights and clones
`llama.cpp` from GitHub. Brief 14 narrows the first half of that gap by
enforcing loopback; it does not touch the training workflow, and the README
sentence stays wrong until someone rewrites it.

## Components

| Component | Responsibility and evidence |
|---|---|
| CLI/configuration | `main.py` handles command parsing, config resolution, logging, workspace setup, model preflight, one-shot answers and the REPL. `config.py` defines precedence: CLI, environment, `.env`, profile, defaults, built-in. |
| ReAct loop | `agent.py` owns prompt generation, model calls, response parsing, retry handling, bounded steps, per-turn scratchpad, and cross-turn user-question/final-answer history. |
| Model transport | `agent.py` constructs the OpenAI-compatible client with `AgentConfig.base_url`; default is `http://localhost:11434/v1`. Local routing is a default, not enforced egress control. **Two retry layers exist** — the client at `max_retries=0` (`agent.py:443`) and the agent's own default of 2 (`agent.py:261`); the contract requires both recorded. |
| Tool registry | `tools.py` defines typed schemas and six tools. Verified at this baseline: `python -c "import tools; print(list(tools.TOOLS))"` returns `calculate`, `get_current_time`, `file_info`, `read_file`, `list_directory`, `search_text`. The catalogue in the system prompt is rendered from the registry. |
| Workspace boundary | `sandbox.py` admits model-selected paths within the configured workspace, applies hidden/credential/transcript denials and read-size/binary checks, and provides bounded file facts. **It is a model-read leash, not process isolation**, and the approved threat model says so in its own words. |
| Logging | `observability.py` emits JSON Lines to a configured file and/or stderr. It applies field-name credential redaction and length limits, but deliberately records content used by dataset export. **Contract delta: the approved policy is quiet and sanitized by default; `verbose` defaults to `True` (`agent.py:260`) and `agent.py:493` and `:869` print the full `base_url`, which the contract forbids.** Readiness block B. |
| Dataset/evaluation | Root dataset utilities and `scripts/` collect logs, export/validate examples, fingerprint prompt provenance, publish bundles, and run evaluations. They are operator-run, not model-facing tools. **`dataset_provenance.py` is a ninth root module that the wheel does not ship — see ADR-0002.** |
| Training | `scripts/build_notebook.py` generates `notebooks/train_omniagent_lora.ipynb`. The workflow downloads/loads model assets, trains and merges locally, clones `llama.cpp` from GitHub if missing, converts to GGUF, and registers through local Ollama. Network use is part of training. |
| Packaging | `pyproject.toml:46` ships eight flat `py-modules` into the installing user's top-level namespace, with no `[project.scripts]` entry point. **Both are release blockers and neither is a code-quality problem.** ADR-0002. |

## Model-facing capabilities

- `calculate` evaluates an allowlisted arithmetic AST; it does not call Python
  `eval()`.
- `get_current_time` returns local and UTC time.
- `read_file`, `list_directory`, `search_text`, and `file_info` inspect files
  through `Workspace`.

At this baseline the ReAct registry has no arbitrary shell, file-write,
network-fetch, plugin, or multi-agent tool. This does not describe
operator-run scripts: training and maintenance workflows can invoke
subprocesses and external package/model/repository sources.

**Whoever adds a tool that writes must read the threat model first.** Criteria
1 and 2 of
[the search-boundary threat model](../pm/threat-model-2026-11-02-the-search-boundary.md)
name a write tool as one of the two conditions that reverse its ruling, and
the contract names a new owner decision as the price.

## The served model

Recorded here because the contract requires the digest frozen before any
completion request, and because every figure this project owns was measured on
a model the repository does not contain. Measured on this machine, 2026-11-04:

| | |
| --- | --- |
| tag | `omniagent-v2:latest` |
| manifest id | `05ba6fe701c5` |
| weights blob | `sha256-40995d3b1f3547aa6007f5ceb605dcd0cecb52f62c12531c2ce08e10c8ae39c7` |
| served by | Ollama **0.34.4** |
| in the repository | **no.** `git ls-tree HEAD` has no `models/` and no `data/` |
| what the README tells a reader to pull | `ollama pull qwen2.5:7b` (`README.md:227`) |

The Ollama installer reports a deferred pending update to 0.40.14. **A version
the contract calls frozen can move the next time the service restarts**, so
the preflight record has to read it, not assume it.

## Trust boundaries and failure modes

1. **Configuration to endpoint:** invalid settings fail configuration;
   changing `base_url` changes where content is sent. The application does not
   enforce localhost-only egress at this baseline.
2. **Model to dispatcher:** malformed output, unknown tools, invalid inputs,
   repeated actions, and step exhaustion can cause errors or stop a turn. A
   syntactically valid final answer can still be wrong.
3. **Workspace to prompt:** repository files are untrusted. Prompt injection
   in a file is not neutralized by path validation; the small tool set limits
   available actions but cannot make the model obey instructions.
4. **Observation to log/training:** workspace text may enter prompt context,
   local logs, exported examples, and a later model. It can contain personal,
   confidential, or third-party data.
5. **Training supply chain:** weights, tokenizers, Python packages,
   conversion code, and datasets have distinct provenance and license terms.
   The notebook clones `llama.cpp` from mutable `master`.
6. **Operational failures:** endpoint unavailability, missing model tags,
   timeouts/status failures, exhausted retries, malformed config, or
   inaccessible workspace/log paths can prevent a turn. No availability
   guarantee is implied.
7. **The built artifact:** the wheel is not the checkout. Measured at this
   baseline, `import export_dataset` from the wheel raises
   `ModuleNotFoundError`. ADR-0002.

## Source and test pointers

Start with `main.py`, `config.py`, `agent.py`, `tools.py`, `sandbox.py`, and
`observability.py`. Relevant tests include `tests/test_react_loop.py`,
`tests/test_parser.py`, `tests/test_tool_args.py`, `tests/test_tools.py`,
`tests/test_sandbox.py`, `tests/test_local_only.py`,
`tests/test_link_refusals.py`, `tests/test_observability.py`,
`tests/test_export_dataset.py`, and `tests/test_notebook.py`.

The suite passes at this baseline — 658 tests, 16.48 s — and **that is not
proof of the properties above.** The project's own standard says it: a test
asserting that something is refused proves nothing until the guard is removed
and the test goes red. Brief 13 did that for the Windows junction case. The
POSIX case of the same guard has no such test, and the `omniagent-core` gate
runs on `ubuntu-24.04`.
