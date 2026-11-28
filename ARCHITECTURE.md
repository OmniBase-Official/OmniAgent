# Architecture

## Components and flow

- `main.py` parses CLI input, resolves settings, and starts the agent or a direct tool.
- `config.py` merges configuration sources into validated settings.
- `agent.py` owns ReAct orchestration and local endpoint policy for model clients; it re-exports the parser API for compatibility.
- `agent_parser.py` parses raw model replies into structured `Step` values and owns the parsing patterns/helpers.
- `tools.py` owns tool schemas, registry, argument validation, dispatch, and workspace-facing tools; `NO_ARG_INPUTS` remains available there as a compatibility alias.
- `tool_input_values.py` owns the shared set of model phrases that represent empty tool input; both the parser and tool argument handling depend on this small module.
- `calculator.py` evaluates arithmetic expressions from an AST using an explicit node/operator/function allowlist. `tools.py` imports and re-exports its public evaluator names to preserve existing callers.
- `sandbox.py` scopes workspace file access; `observability.py` provides logging and event handling.

## Trust boundaries

- Model-produced tool input is validated against the registered Pydantic argument schema before dispatch.
- Model reply parsing is isolated in `agent_parser.py`; `agent.py` retains compatibility exports for its prior parser names.
- Arithmetic input is parsed as an expression AST; unsupported syntax is rejected and no source is executed.
- Workspace file access goes through the sandbox workspace boundary.
- Static config inspection reports use AST-derived structure, redact source literals, and omit requested file paths from success and error output.
- Model-client endpoints are restricted by the endpoint policy in `agent.py`.

## Decision

The arithmetic evaluator is isolated from the growing tool registry so its parser and limits can be maintained independently. The `tools` module keeps compatibility imports for existing call sites. Model reply parsing is isolated from orchestration in `agent_parser.py`, while `agent.py` preserves the existing `Step` and `_parse` imports. Shared empty-input tokens live in `tool_input_values.py` so the parser does not import the tool registry; all three added modules are declared as flat-layout package modules.
