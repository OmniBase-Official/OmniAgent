# Brief 20 — one test per gate-2 guard

**For the security engineer (SE). Issued 2026-11-22 by the PM.**

**Context:** the owner ruled option A on 2026-11-22 — G (`organization/main`,
`5005039`) is the canonical line. ADR-0003's carry-over inventory puts this brief
first: it depends on nothing, adds no production code, and until it exists
"G has contract gate 2" is a claim nobody can check.

Static throughout. **No model run, no localhost, no test here may contact a model
server.**

## The problem, measured

Contract section 5, gate 2: *"dispatcher-enforced fixed and per-task tool
allowlists, including unknown/disallowed-tool stop behavior."* On G the allowlist
is enforced in **five independent places**. The PM removed each in turn, in a
scratch worktree of `5005039`, and ran G's own suite (**860 passed, 2 skipped**
unmutated). **MEASURED 2026-11-22**, file hashes restored; the SAE re-ran the
decisive row independently and got the same result:

| # | Guard | Single-site mutation (exact text) | Result |
| --- | --- | --- | --- |
| G2a | `agent.py:694` — `ReActAgent.__init__` intersects with `FIXED_TOOL_ALLOWLIST` | `) & FIXED_TOOL_ALLOWLIST` → `)` | **860 passed — nothing noticed** |
| G2b | `agent.py:992` — `permitted` in `_invoke_tool` | `permitted = tool_name in self.allowed_tools` → `permitted = True` | **860 passed — nothing noticed** |
| G2c | `tools.py:442` — `run_tool` fixed-allowlist check | `if normalized_name not in FIXED_TOOL_ALLOWLIST:` → `if False:` | 2 failed |
| G2d | `tools.py:458` — `run_tool` per-task check | `if normalized_name not in task_allowlist:` → `if False:` | **860 passed — nothing noticed** |
| G2e | `agent.py:872` — loop stops on a disallowed action | `if step.action not in self.allowed_tools:` → `if False:` | 2 failed |
| G2b + G2d | both per-task guards at dispatch | both of the above at once | **1 failed**: `test_a_disallowed_tool_request_is_rejected_before_dispatch` |

**Three of the five guards can be deleted with the whole suite green, and the
per-task allowlist at dispatch is pinned by exactly one test.** The guards
overlap, and **G2b and G2d answer with the same string**
(`"Error: tool is not allowed for this task."`), so a test that only asserts
"refused" cannot say which guard refused. This is the trap the project already
paid for: **a test asserting "this is refused" proves nothing if several
independent guards would refuse it.**

## What you build

**One new test file: `tests/test_tool_allowlist_guards.py`. No production change.**

For each guard G2a–G2e, a test that is **green on unmutated `5005039` and goes red
when only that guard is removed**, and that asserts **the specific cause**, not
"some refusal". The two guards that share a string must be told apart by
something other than the string. Suggested handles (yours to improve):

- **G2b** — a spy on `tools.run_tool` (or on the tool function) asserting it is
  **never called** for a tool outside `allowed_tools`: the guard is *before*
  dispatch, so the spy catches it when G2b is gone even though G2d would still
  refuse afterwards.
- **G2d** — call `run_tool(name, ..., allowed_tools=<subset>)` directly with a
  real tool outside the subset; assert the refusal **and** that the tool body did
  not run. With G2b irrelevant (you bypass the agent), only G2d can refuse.
- **G2c** — register a throwaway tool in `tools.TOOLS` that is **not** in
  `FIXED_TOOL_ALLOWLIST`, pass an `allowed_tools` that names it, and assert it is
  refused as *unknown* (`"no tool called"`), not as "not allowed for this task".
  Restore `TOOLS` afterwards.
- **G2a** — `ReActAgent(..., allowed_tools={<real>, <invented>})` ends with
  `agent.allowed_tools` containing only the real one.
- **G2e** — drive the loop with a scripted model that asks for a disallowed tool;
  assert the run stops with `""` and **no further Observation reaches the
  scratchpad**.

Also **measure and report** two more guards the PM did not mutate, and add a test
if the same silent-removal property holds: `agent.py:701` (the
`FIXED_INTERNAL_CAPABILITY_ALLOWLIST` intersection) and `agent.py:896` (the
`missing_capabilities` check). Contract gate 2 says "fixed … allowlists"; a second
allowlist is in scope until the SAE says otherwise.

## Mutation evidence — the point of the brief

Take the evidence yourself; do not rely on the table above. **Restore from a
scratchpad copy, never `git checkout --` alone, and report each file's hash
before and after.** For every guard:

1. the new test **passes** on unmutated `5005039`;
2. mutate only that guard (the exact text above) — **your new test goes red**, and
   say which *other* tests go red too;
3. restore; hash back; the suite is green again.

And one check that is the whole reason for the exercise: **after your tests exist,
remove each guard in turn again — the number of red tests must be ≥ 1 for every
one of the five, including G2a, G2b and G2d, which were 0.** Report the full table
(guard × red tests before/after your file).

**If a guard turns out to be dead code** — unreachable, so that no test *can* go
red when it is removed — **do not delete it and do not leave it untested.** Report
it. Whether to remove a redundant guard is a design question for the SAE, and
defence in depth was probably the point.

## Files you may touch

`tests/test_tool_allowlist_guards.py` (new). You may *import* from `tests/fakes.py`
and existing test helpers; do not edit them.

## Files you may not touch

`agent.py`, `tools.py`, `sandbox.py`, `config.py`, `main.py`, `omniagent.toml`,
`scripts/**`, every other test file, `docs/` except the `## Result` section you
append to this brief file, `.github/workflows/**`.

**Do not change the system prompt or any tool description** — they reach the model
every turn and are part of every training example.

## Gates

```
.venv\Scripts\python.exe -m ruff check .
.venv\Scripts\python.exe -m mypy
.venv\Scripts\python.exe -m pytest
```

Full path, **never your own `-q`** (`pyproject.toml` already sets it). Baseline on
`5005039`, measured by the PM: **860 passed, 2 skipped** (pytest); take your own
ruff and mypy baselines from the same commit.

## Where to work

**Branch from `5005039` (`organization/main`) in your own worktree; commit to your
own branch, never to a `main`.** Name the remote on every push (`git push origin
<branch>`). The owner has not yet named which remote hosts the canonical line, so
the PM merges later; do not push to either `main`.

## Traps that already cost this project

- **A worktree can silently test the wrong code.** The shared venv's editable
  install maps at the *dirty main checkout*. Run
  `python -c "import agent; print(agent.__file__)"` from your worktree and confirm
  it prints a path inside it — before you trust any number.
- **A rejection test passes if the connection merely fails.** Prove no socket was
  opened, then delete the validator and see what survives.
- **Never measure a tree someone else is writing to.** `D:\code-project\OmniAgent`
  is Codex's checkout, dirty with 54 changes; **do not read, write or test it.**
  It holds an untracked `tests/test_mvp_security_acceptance.py` whose failing
  test is named `test_disallowed_task_tool_is_stopped_before_dispatch` — the same
  subject, being written there. **You may not read it; the PM will reconcile the
  two if Codex commits it to a branch.**
- Quoted bash heredocs eat backslashes; write files with the Write tool.
- `pytest` handed a Windows 8.3 short path (`THANAP~1`) scans the wrong
  directory; run it from the worktree with a relative path.
- **Standing rules (owner, 2026-11-22), at the end of `~/.claude/CLAUDE.md`:** Rule
  1 (QA/security red-team: reproduce before you report, mutation-check every test
  you call "covered", end your report with a `QA:` line) and Rule 2 (weekly usage
  pacing — **the meter is per account, shared by every Claude chair**, so today's
  ceiling of 28% is divided among all of us; end your report with a `Budget:`
  line, and stop at the ceiling).

## Done when

- `tests/test_tool_allowlist_guards.py` exists with one test per guard (and per
  extra guard you measured), green on `5005039`;
- the before/after table is in your Result: **every guard has ≥ 1 red test when it
  alone is removed**, hashes before and after quoted;
- three gates green, outputs quoted; pushed to your branch;
- one message to the PM ending with `QA:` and `Budget:` lines.

## The one thing that would make this wrong

**A test that goes red for the wrong reason.** If your G2b test goes red because
G2d's refusal string changed, you have not pinned G2b. The only proof is the
single-guard mutation, so run all of them, one at a time, and read which tests
went red.
