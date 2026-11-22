# Brief 22 — the endpoint corpus becomes G's acceptance test

**For the security engineer (SE). Issued 2026-11-22 by the PM. QUEUED behind brief
21 for the same engineer — one task per engineer; do not start before the PM says
brief 21 is verified.**

The owner **approved option A on 2026-11-22** and the PM applied it to the
contract: **§2 now permits loopback IP literals only; `localhost` is refused.**
G's `validate_loopback_url` already answers brief 14's frozen corpus correctly
*as amended*; what G lacks is the **test**. G's endpoint test file is 166 lines to
O's 307 and does not contain the corpus. Test-only. Size S.

Static throughout. **No test here may open a socket or contact a model server.**

## The corpus, as amended

Source: `tests/test_endpoint_policy.py` at `3c76fd2` (`git show 3c76fd2:tests/test_endpoint_policy.py`,
lines 46–84). **31 forms: 8 accepted + 23 rejected, and each tree's own default.**
Amended expectations (contract §2, amendment record of 2026-11-22):

- **Accepted (3 + the default):** `http://127.0.0.1:11434/v1`, `http://[::1]:11434/v1`,
  `http://127.0.0.2:11434/v1`, and G's `DEFAULT_BASE_URL`
  (`http://127.0.0.1:11434/v1`).
- **Rejected (28):** the original 23 **plus the five `localhost` spellings that O
  accepted**: `http://localhost:11434/v1`, `http://localhost:1/v1`,
  `http://localhost/v1`, `http://localhost:11434/`, `http://LOCALHOST:11434/v1`.
  Give those five their own reason: *"a hostname, including localhost"*.

**MEASURED by the PM 2026-11-22 on `5005039`** (a script, every socket forbidden):
under the *old* expectations G gave exactly 5 wrong answers, all of them the
`localhost` forms; under the amended ones it gives **0**. So **no production
change is expected.** If your run disagrees, stop and tell the PM.

## What you build

Extend **`tests/test_endpoint_policy.py`** (G's file, do not duplicate its
helpers) with the corpus as parametrized tests: every accepted form constructs
through `validate_loopback_url`, `AgentConfig` and `Settings`; every rejected form
is refused with `EndpointPolicyError`, **with the reason as the test id**.

**Every rejection test must prove the refusal came from the validator and not
from a failed connection.** A socket shim that raises on any connect or
`handle_request` (O's `_forbid_every_socket` fixture does this, lines 90–105)
turns "the refusal arrived too late" into a failure. Reuse G's equivalent if it
has one; add the shim if it does not.

## Mutation evidence — the part that matters

**A rejection test passes if several independent guards would refuse the form.**
Brief 14 learned this: of 74 rejection tests, deleting the validator turned 73
red; the survivor was an independent transport guard. Do the same here, with the
rigour:

1. Delete / neutralise **each validator branch in turn** (scheme, host
   classification, hostname refusal, user-info, query/fragment, port, malformed
   IPv6, empty string) and report **which corpus forms go red**. A branch whose
   removal turns nothing red is untested: say so.
2. Remove the **whole validator** (`validate_loopback_url` returns its argument)
   and report how many of the 28 rejected forms survive (should be none except
   where an independent guard — e.g. the transport — also refuses; name each one).
3. **The five `localhost` forms are the new part:** put the old behaviour back
   (accept `localhost`) and show **all five** go red and nothing else does.

Restore from a scratchpad copy every time; **hash before and after.**

## Files you may touch

`tests/test_endpoint_policy.py` only.

## Files you may not touch

Every production file (`agent.py`, `config.py`, `tools.py`, `sandbox.py`,
`main.py`, `omniagent.toml`), **the validator and `DEFAULT_BASE_URL`**, every other
test file, `docs/` except your `## Result` appended here. If a form is answered
wrongly by G's validator, **report it; do not fix it.**

## Gates

```
.venv\Scripts\python.exe -m ruff check .
.venv\Scripts\python.exe -m mypy
.venv\Scripts\python.exe -m pytest
```

Full path, never your own `-q`. Baseline on `5005039`: **860 passed, 2 skipped**.
Brief 21 will have moved that on its own branch; **branch from `5005039`**, not
from brief 20 or 21, so the three merge independently.

## Traps

- `python -c "import agent; print(agent.__file__)"` from your worktree must print
  a path inside it.
- **Never read, write or test `D:\code-project\OmniAgent`** (Codex is editing it).
- Windows 8.3 short paths make `pytest` scan the wrong directory.
- **Standing rules** (end of `~/.claude/CLAUDE.md`): Rule 1 — reproduce, and
  mutation-check every test you call covered; Rule 2 — the weekly meter is
  **per account, shared by every Claude chair**, today's ceiling 28%.

## Done when

- the 31-form corpus is in G's endpoint test file, green on `5005039`;
- the mutation table (branch × forms red, validator-removed survivors, the five
  `localhost` forms) with hashes before and after;
- three gates green; pushed to your own branch with the remote named; never to a
  `main`;
- one message to the PM ending with `QA:` and `Budget:` lines.

## The one thing that would make this wrong

**Reporting 31 green rejection tests as proof.** They prove the validator only if
removing the validator turns them red. Run the removal, and name every survivor.
