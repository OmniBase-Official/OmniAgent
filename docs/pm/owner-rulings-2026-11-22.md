# Owner rulings of 2026-11-22

The PM's record of what the owner decided in chat on 2026-11-22, so the next chair
does not rebuild it from a transcript. **A ruling is something the owner said in
words. Anything the PM merely assumed is listed separately and is not a ruling.**

## Rulings (the owner said it)

1. **Option A: `organization/main` (G, `5005039`) is the canonical code line.**
   O (`origin/main`, `3c76fd2`) is preserved as the tag
   `legacy/origin-main-2026-11-05`. O's documents and unique work are carried onto
   G (ADR-0003, Accepted). The *remote* that hosts the canonical line is **not yet
   named**; nothing has been merged into either `main`.
2. **Endpoint: loopback IP literals only** (`127.0.0.1`, `127.0.0.0/8`, `::1`);
   `localhost` is refused. Applied to contract §2 with an amendment record
   (`aca9792`).
3. **Files meant for AI sessions are local-only:** handoff, role and instruction
   markdown is gitignored and untracked (`84410ce`). The briefs themselves stay
   tracked. This also answered the old "is untracking intended?" question: yes.
4. **Standing rules for every AI:** Rule 1 (QA / security red-team review) and
   Rule 2 (weekly pacing), installed at the end of `~/.claude/CLAUDE.md` and
   `~/.codex/AGENTS.md`, plus an OmniAgent addendum to the routing protocol.
   **Claude ceilings, cumulative: 14 / 28 / 42 / 56 / 70 / 84 / 98; the owner
   ruled that 2026-11-22 is day 2 (28%).** Codex remaining floors: 100 / 86 / 72 /
   58 / 42 / 28 / 14. The weekly meter is per account, shared by every Claude chair.
5. **Automatic code review:** git hooks (`pre-commit`, `pre-push`) installed for
   this repository via `core.hooksPath` (`C:\Users\Thanapat Manasom\.omniagent-githooks`).
6. **The graph runtime.** The owner wants OmniAgent's engine to grow from the
   ReAct loop into a bounded graph runtime, and answered the routing question
   **"local only and claude, codex too"**: the runtime must support **both
   local-only and routing to Claude and Codex**. The PM and the SAE had designed
   `hybrid` as a disabled profile (option A of ADR-0005); **the owner's answer is
   option B: hybrid is wanted.** What that requires is in "Consequences" below.
7. **The hybrid profile reaches Claude and Codex through their CLIs
   (`claude -p`, `codex exec`) as a subprocess, not through their APIs.** The owner
   chose this **against the PM's recommendation of APIs.** The PM's dissent is
   recorded here so the decision is made on known ground, and it does not block the
   work: the design proceeds on the owner's choice.

8. **Today's weekly ceiling is 40%, not 28%.** Codex hit its own daily limit and is
   paused, so the owner works on Claude until the weekly meter reads 40% today
   (2026-11-22). It read 27% when the ruling was given.
9. **All work lives under `D:\code-project\OmniAgent`; nothing is built outside it**
   (the location rule, appended to both global instruction files). Isolated trees go
   under `.scratch\`.

## Consequences of ruling 6 that the owner has not yet decided

Turning hybrid on changes a promise of the product ("nothing leaves your machine"),
so it is **not a configuration flag**. Before any hybrid code runs:

- **A new owner-approved contract** (the MVP contract is read-only, loopback-only,
  "does not delegate to other agents"). The SAE drafts; the owner approves.
- **An egress policy and a second validator** for the hybrid profile (allow-listed
  provider hosts only, TLS, no redirects or proxy, keys from the environment only,
  never logged, per-run consent). The SE carries it.
- **Updated threat model:** the new boundary is workspace content reaching a cloud
  provider; prompt injection becomes an exfiltration path. Sealed evaluation paths
  and `.env`/credentials must never leave the machine.
- **Evaluation stays local-only:** the synthetic exploratory cohort is a
  measurement of the local model and must not route to a cloud provider.
- **What the CLI-subprocess choice (ruling 7) changes**, each point **PM-raised and
  UNVERIFIED until the SE tests it**:
  1. **The runtime now runs commands**, which the MVP contract forbids; the new
     contract must say so and bound it (fixed argv, no shell, no user-controlled
     arguments, a timeout and a process-tree kill on Windows).
  2. **The host allow-list cannot see what a CLI connects to.** Egress control moves
     to the subprocess boundary: an isolated config directory, a scrubbed
     environment, a fixed working directory. Whether each CLI can be run with **all
     tool use disabled** and no file or network access beyond the model call is the
     first thing to find out; a cloud agent that can read, edit or run commands in
     the workspace is a larger risk than the one the contract was written to avoid.
  3. **Each CLI loads its owner's global instructions** (`~/.claude/CLAUDE.md`,
     `~/.codex/AGENTS.md`: the routing protocol and the standing rules). Inherited by
     a runtime call, they would make the subprocess delegate to the local AI
     (recursion) and change its output. They must be isolated.
  4. **It spends the owner's subscription meters,** the same per-account meters
     Rule 2 paces. Runtime use competes with the chairs' budget, and a per-run spend
     cap is not available the way it would be with an API key.
  5. **Codex's sandbox cannot reach localhost** (WinError 10013), so a Codex
     subprocess cannot call the local model; it can only be a cloud node.
  6. Output is less deterministic and harder to parse than an API response, and the
     evaluation must never route through it (cohort stays local-only).
  **Next step, SE (a feasibility spike, not a design):** establish, by running them
  on a throwaway directory with no secrets, whether `claude -p` and `codex exec`
  can be run tool-less, config-isolated and instruction-free. The SAE's design waits
  for that result. Still to decide: which providers, the consent model.
- **Phases:** read-only Phases 1–3 can proceed local-only first; the hybrid profile
  is a later phase behind the contract, the egress policy and the updated threat
  model. Phase 4 (write capability) remains gated and undecided.

## PM working assumptions (NOT rulings; the owner may overturn any of them)

- `NEXT_CHAT.md` on `origin/main` is left to disappear with O (deleting it turns
  `test_every_sealed_source_path_exists` red and opens an `ANSWER_KEY` leak while a
  local copy exists). It is already gone on G.
- `securefs.py`: treat as a new proposal needing threat-model criteria 1–5 before
  any of the four branches that carry it merge.
- The holdout instrument and the 19-question bank are not carried onto G (O's
  history is preserved by the tag).
- The parser for the graph's AST slices is the stdlib `ast`, not tree-sitter.
- The graph package waits for the package move (ADR-0002) and for the MVP gates.

## Still open and owner's

The remote that hosts the canonical line; the securefs ruling; the holdout and
question-bank decision; the four graph-runtime decisions in ADR-0005 (as amended by
ruling 6); how Codex learns of all this (`docs/pm/codex-stop-and-snapshot-prompt.md`
is a local file the owner must paste).
