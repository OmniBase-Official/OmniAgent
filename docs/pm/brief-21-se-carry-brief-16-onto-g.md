# Brief 21 — carry brief 16's three defaults onto G, and take the endpoint URL out of messages and logs

**For the security engineer (SE). Issued 2026-11-22 by the PM.**

The owner ruled option A on 2026-11-22: **G (`organization/main`, `5005039`) is
canonical.** ADR-0003's carry-over inventory (`origin/sae/adr-0003-carry-over`)
found that **G has none of brief 16's three defaults and puts the full endpoint
URL into error messages.** This brief closes four contract gaps at once. Size S.
Depends on nothing; **disjoint from brief 20** (which only adds a test file).

Static throughout. **No model run, and no test here may contact a model server.**

## What is measured on G (`5005039`), by the PM and the SAE, 2026-11-22

| Gap | Where on G | Contract |
| --- | --- | --- |
| model named three ways | `agent.py:59` `DEFAULT_MODEL = "qwen2.5:7b"`; `omniagent.toml` `[defaults]` `model = "qwen2.5-coder:7b"`; `[profile.demo]` `omniagent-v2` | §2: "relying on an implicit default is not acceptable" |
| two retry layers, one named | the OpenAI client's own retries vs the agent's `max_retries` (default 2) | §3/§5: no automatic retries; both layers recorded |
| `verbose` defaults to **True** | `agent.py:479` **and** `config.py:75` (two sites) | §6: logs quiet by default |
| full endpoint URL in messages | `agent.py:770` and `:1220` (error strings), and a log event at ~`:766` with `base_url=self.config.base_url`; **README line 715 documents the message** | §2: "Do not log the full endpoint URL" |

## What you do

**Port brief 16, do not blindly cherry-pick.** Read brief 16
(`git show origin/pm/verify-brief16:docs/pm/brief-16-three-defaults-and-the-one-brief-14-took.md`,
including its `## Result`) and its three commits on `origin/pm/verify-brief16`:
`959df13` (shipped model default), `312408b` (the two retry layers), `8a35c5f`
(`--verbose`, quiet by default). G's `agent.py`, `config.py` and their tests
differ from O's, so expect to port by hand. The PM verified brief 16 on its own
tree (798 passed, mutations Ma–Me red).

1. **One answer to "which model is this".** Make `--help`, the TOML and the code
   agree (brief 16 kept `qwen2.5:7b` and changed only `[defaults].model`).
   Provenance must stay available through `config.resolve()`'s existing source
   map — **do not build a second mechanism.** `[profile.demo]`'s `omniagent-v2`
   and `max_steps = 8` do not change; that is the contract's approved baseline.
2. **Two retry knobs, named as two,** documented in one place, with a test that
   both are discoverable from a resolved config and that setting one leaves the
   other alone. The evaluation-facing path sets the agent's `max_retries` to 0
   explicitly.
3. **Quiet by default.** `verbose` is `False` at **both** sites. `--verbose` turns
   it on; `--quiet` keeps working; both together is an error, not a guess.
   **A lesson from verifying brief 16:** its test read `AgentConfig`'s default
   only through `Settings.agent_config()`, so flipping `AgentConfig.verbose` back
   to `True` left the whole suite green. **Your test must assert
   `AgentConfig().verbose is False` directly,** not via `Settings`.
4. **The endpoint URL out of every message and log.** Find **every** site that
   puts the configured URL into a user-visible string, an exception message, a
   log record or a trace event (start with the three above; `grep -n base_url`
   `agent.py` `main.py` `observability.py`, and say what you found). Replace with
   the endpoint *classification* (`loopback`), never the URL. Update README line
   715 and the `--verbose` option row, **two README lines only.** The CLI
   preflight display in `main.py` is the terminal, not a log: leave it, but
   **say in your Result** whether it prints the URL.

## Tests that must fail first

| Test | Part |
| --- | --- |
| `--help` model string equals the default that wins | 1 |
| the shipped TOML `[defaults]` model equals the code default | 1 |
| a resolved config reports the model **and** the layer it came from | 1 |
| the demo profile still resolves to `omniagent-v2` — passes **before and after** | 1 |
| both retry values discoverable; setting one leaves the other | 2 |
| the evaluation path resolves the agent's `max_retries` to 0 | 2 |
| `AgentConfig().verbose is False` **and** `Settings` default `verbose` is False | 3 |
| `--verbose` on, `--quiet` off, both together is an error | 3 |
| a fake transport raises `APIConnectionError` with a distinctive port (e.g. `65500`) in the URL; **neither the raised message nor any captured log record contains the URL or the port** | 4 |

For part 4, capture logs the way the repository's other tests do
(`tests/log_capture.py` if G has it, else the existing helper) and **prove no
socket was opened**.

## Mutations that must go red (restore from a scratchpad copy; hashes before and after)

| # | Mutation | Must go red |
| --- | --- | --- |
| Ma | change the code model default without the TOML | the agreement test |
| Mb | make provenance always report one layer | the provenance test (if nothing goes red you built a second mechanism) |
| Mc | demo profile's model set to the base tag | the regression guard |
| Md-cfg | `config.py:75` `verbose` default back to `True` | the quiet test |
| **Md-agent** | `agent.py:479` `verbose` default back to `True` | **the direct `AgentConfig()` test** |
| Me | `--verbose` and `--quiet` together resolve silently | the conflict test |
| **Mu1–Mu3** | put the URL back into each of the three message/log sites **one at a time** | **a test per site** — report which |

**A test asserting "this is refused" proves nothing if several independent guards
would refuse it.** Mu is the live example: if putting the URL back at one site is
caught only because another site's test also fires, say so.

## Files you may touch

`agent.py`, `config.py`, `main.py`, `omniagent.toml`, `tests/test_config.py`,
`tests/test_shipped_config.py`, **a new** `tests/test_endpoint_not_in_messages.py`,
and **two lines of `README.md`**.

## Files you may not touch

- **`validate_loopback_url`, `DEFAULT_BASE_URL`, `LoopbackOnlyTransport` and the
  rest of the endpoint validator.** Whether `localhost` should be accepted is an
  **open owner decision** (the contract permits it, G refuses it); do not change
  what is accepted or the default URL.
- `tools.py`, `sandbox.py`, `scripts/**`, `tests/test_tool_allowlist_guards.py`
  (brief 20's, on another branch), `[profile.demo]`'s model or `max_steps`,
  anything under `docs/` except your `## Result` appended to this file.
- **Do not change the system prompt or any tool description.**

## Gates

```
.venv\Scripts\python.exe -m ruff check .
.venv\Scripts\python.exe -m mypy
.venv\Scripts\python.exe -m pytest
```

Full path, **never your own `-q`.** Baseline on `5005039`: **860 passed, 2 skipped**
(MEASURED by the PM 2026-11-22); take your own ruff and mypy baselines from it.

## Where to work

**Branch from `5005039` — not from your brief-20 branch — in your own worktree;
commit to your own branch, never to a `main`.** Name the remote on every push.
The owner has not named which remote hosts the canonical line; do not push to
either `main`. The PM merges both briefs independently.

## Traps that already cost this project

- Run `python -c "import agent; print(agent.__file__)"` from your worktree and
  confirm it prints a path **inside it** (the shared venv's editable install
  points at the dirty main checkout).
- **Never read, write or test `D:\code-project\OmniAgent`;** Codex is editing it.
- `pytest` given a Windows 8.3 short path scans the wrong directory.
- **Standing rules (end of `~/.claude/CLAUDE.md`):** Rule 1 (reproduce before you
  report, mutation-check every test you call covered, end with a `QA:` line) and
  Rule 2 (**the weekly meter is per account and shared by every Claude chair;
  today's ceiling is 28%** — read it before each long run and stop at it).

## Done when

- every row of both tables is shown with its result;
- three gates green, outputs quoted; pushed to your own branch;
- one message to the PM ending with `QA:` and `Budget:` lines.

## The one thing that would make this wrong

**Fixing the message strings and missing a log field.** The URL reached users
through three paths on G, one of them a structured log event rather than a string.
Search for the *value*, not the three line numbers.
