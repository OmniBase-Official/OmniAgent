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

## Result

**Delivered 2026-11-22 by SE 02** on branch `claude/se-brief22-endpoint-corpus`
(`3ac11d7`, one commit on `5005039`; **only `tests/test_endpoint_policy.py`
changed**; no production change). The SE reports 983 passed / 2 skipped (860
baseline + 123 new), ruff and mypy clean, and agreement with the PM's measurement:
**G's validator answers all 31 forms as amended with no code change.** Nothing
merged. Beyond the corpus the SE added 4 forms (192.168.1.10, 8.8.8.8,
`[2001:db8::1]`, port 0) because the frozen corpus never reaches two validator
branches (port 0; "not a loopback address").

Each rejection is asserted by the **exact message of the branch that fired**, not
just "refused" (several corpus forms are refused by two branches). Reported
validator-branch mutations, full suite each: V2 scheme **20 red (0 before: the
scheme branch was untested on G)**; V6 no host **4 red (0 before)**; V7b/V7c
unspecified and IPv4-mapped addresses were also untested on G; V5 port zero and
V7d not-loopback are untested by the corpus itself and pinned only by the SE's
extras.

**Not covered by this table:** `LoopbackOnlyTransport`, a second guard that sends
no request in these tests and is tested only by G's pre-existing transport
tests; uppercase schemes and any form outside the 31 plus the 4 extras.

## PM verification (2026-11-22)

Re-run by the PM in a scratch worktree of `3ac11d7` (the `agent` import resolved
inside it): baseline **983 passed, 2 skipped**; `agent.py` hash `fe1ab9de…` before
and after every run, restored from a saved copy. Reproduced exactly:

| Mutation | Red |
| --- | --- |
| V2 scheme check `if False:` | 20 |
| V6 "names no host" check `if False:` | 4 |
| **whole validator removed** (returns its argument) | **127**, all in the endpoint file |
| **`localhost` accepted again** | **24** = the five `localhost` forms × 4 paths (20) + 4 other tests; nothing else red |

The PM did **not** independently list the 28 rejected forms to prove "no
survivors"; that rests on the arithmetic (127 = 112 + 4 extras + 8 + 3, as the SE
decomposes it) and not on a form-by-form check. V1, V1b, V3, V4, V5, V7a–d were
not re-run by the PM.
