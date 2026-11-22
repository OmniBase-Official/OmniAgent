# Graph runtime — rules for the implementing engineer

**Companion to [ADR-0005](ADR-0005-the-graph-runtime.md) and
[the spec](graph-runtime-spec.md). Status: Proposed, 2026-11-22.** Tracked
deliberately: `AGENTS.md` and `CLAUDE.md` are untracked in this repository, so a
fresh worktree would never receive rules written there. **This file is the
contract between the brief and the engineer. If a brief and this file disagree,
stop and ask the PM.**

**None of this authorises building anything.** Phases 1–3 fit the contract;
phase 4 and the `hybrid` profile are gated.

## The ten rules

1. **Never edit `agent.py`'s loop.** The ReAct loop is the shipped runtime and
   the frozen arm of an evaluation. The graph runtime is a new package beside
   it. A diff that touches the loop is rejected without review.
2. **No unbounded loop anywhere.** Every loop is `for … in range(bound)` over a
   bound that is a validated field, or it is not merged. No `while True`, no
   `while not done`. Every transition costs at least one unit of a budget that
   only decreases.
3. **A checkpoint on every edge transition**, written after the node result is
   typed and before the next node runs. Append-only. **Content-free**: ids,
   enums, counters, digests, durations. Never a prompt, an observation, a
   message, a traceback, a path you did not resolve, or a URL.
4. **Retry budget `N = 3`, then `HumanEscalationNode`.** Not 4, not "until it
   works". Escalation is a normal outcome, not a failure path — a bounded
   machine that cannot stop just spends its budget and then lies about why.
5. **Strict types, no exceptions.** `mypy` strict passes or the branch does not
   land. No `Any` in a node signature, no untyped dict as state. Enums for every
   status; a `str` status is how a typo becomes a silent transition.
6. **No new dependency without the SAE.** The stdlib `ast` is the parser.
   tree-sitter is a native dependency and is the **owner's** decision, not an
   implementation detail — the threat model settled how this project treats
   native modules (criterion 5).
7. **Call the existing tool layer; add no guard of your own.** The dispatcher,
   `Workspace`, `validate_loopback_url` and the fixed allowlists already exist.
   On `5005039` the allowlist is enforced in five places and three can be
   deleted with the suite still green — **a sixth overlapping guard makes that
   worse, not better.**
8. **One module per brief, disjoint files.** Two engineers never hold one file.
   If your brief needs a file another brief holds, it is the wrong brief; say
   so before you start.
9. **Every invariant ships with the test that goes red when it breaks, and you
   mutation-check that test before you call it covered.** Remove the guard,
   run the suite, confirm the test goes red **on the specific cause**, restore
   from a saved copy — not `git checkout --` alone — and record the file hash
   before and after in the Result. A test asserting "refused" proves nothing
   while several guards would refuse.
10. **Three gates before every commit**, full path, never your own `-q`:
    `.venv\Scripts\python.exe -m ruff check .`, `-m mypy`, `-m pytest`. The
    pre-push hook runs them again on a clean tree.

## What stops you and sends you back to the PM

- A node that needs to **write a file or run a command** (phase 4: gated; it
  deletes the threat model's "the agent has no write tool" premise).
- Anything that would **reach a non-loopback endpoint** (`hybrid`: gated).
- Anything that would **persist raw content** — including "just for debugging".
- A new top-level module name. The flat namespace is already a release blocker;
  see ADR-0002.
- A figure you cannot reproduce. Report it **UNVERIFIED** and say what would
  settle it.

## Before you report anything

Confirm the code you tested is the code you think it is: print the module's
`__file__` from your worktree and check the path is inside it. The shared venv's
editable install maps at the main checkout, and this project has voided
measurements that way. Then label every figure **MEASURED** (you ran it, dated,
with the commit), **RECORDED** (earlier, dated) or **REPORTED** (someone else's,
not re-run), and end with the `QA:` and `Budget:` lines the standing rules
require.
