# Brief 23 — the graph runtime: decision record and blueprint

**For the solution architect (SAE). Issued 2026-11-22 by the PM.**

**Docs only. No code, no change to `agent.py` or any production file.** Static: no
model run, no test here may contact a model server.

## What the owner asked, and what the owner answered

The owner wants OmniAgent's execution engine to grow from the hand-rolled ReAct
loop into a **bounded state-machine / directed-graph runtime** (Planner,
ContextRetriever, Worker, Verifier, human escalation; an AST dependency graph with
minimal context slices; durable per-transition checkpoints; hybrid model routing;
strict tool contracts and a sandbox), and wants it specified for Codex to implement
in atomic phases. **The owner answered "do both" to the routing question
"local-only, or route to Claude/Codex?".** The PM reads that as: **one routing-policy
layer with two profiles. The shipped default is `local-only`** (Ollama on loopback;
what the contract and the README promise). **A `hybrid` profile is designed now but
stays disabled** until a new owner-approved contract says otherwise, because turning
it on changes a promise of the product ("nothing leaves your machine"), not just a
setting. If you read the owner's answer differently, say so in the ADR and mark it
OWNER'S.

## The conflicts you must resolve or mark OWNER'S (measured by the PM, 2026-11-22)

1. **Contract §1 and the threat model are read-only.** MVP: *"does not run arbitrary
   commands, write or delete files, fetch network resources, load plugins, or
   delegate to other agents"*; six tools only, none new without a security review.
   Threat-model criterion 2's premise is **"the agent has no write tool"**. A
   `WorkerNode` that edits code or runs a shell is a different product and needs a
   new contract. **Phases 1–3 must fit the read-only contract; Phase 4 (edits) is
   gated.**
2. **Contract §2 (endpoint loopback only, amended 2026-11-22 to IP literals) and
   "no delegation to other agents"** forbid cloud nodes at runtime. Hence the
   `hybrid` profile is disabled and would need its own validator and egress policy.
3. **Contract §5/§6: no persistent traces until a retention and deletion path is
   defined; no raw prompts, observations, errors or full endpoint URLs.** A
   checkpoint holding `tool_history` and `error_log` breaks this. **Design it
   content-free by default** (node ids, hashes, counters); raw content only in memory
   unless the user opts in.
4. **Contract §7: no runtime change authorized; the ReAct arm's exploratory cohort
   needs a frozen runtime.** So **build beside it** (a new package), **do not edit
   `agent.py`'s loop**, until the evaluation is done.
5. **The loop is already bounded** (`for iteration in range(1, max_steps + 1)`,
   default 8, max 50, retries capped). The brief's premise of an unbounded `while`
   does not describe `agent.py`; state that plainly in the ADR.
6. **"No frameworks"** is a standing project rule; the graph runtime is hand-rolled.
   **Tree-sitter is a native dependency** and changes the "hand-rolled and small"
   premise (threat-model criterion 5 argued exactly this about a 1,200-line ctypes
   module). Start with the stdlib `ast`; tree-sitter is OWNER'S.
7. **File placement.** `AGENTS.md` and `CLAUDE.md` are now untracked by the owner's
   instruction, so Codex will not receive rules from them. `architecture.md` would
   duplicate `docs/architecture/system-overview.md`. Use **tracked** files named
   below.
8. **Sequencing.** The MVP gates (2–6 on G), `securefs.py`, CI, the package move and
   the model question are still open. Say where this work sits against them; the PM
   decides the order, you say what depends on what.

## Deliverables — in THIS order, so a partial result is still useful

Branch off `origin/pm/verify-brief16` (it carries the amended contract and the
architecture README), in your own worktree, branch e.g. `sae/adr-0005-graph-runtime`.

1. **`docs/architecture/ADR-0005-the-graph-runtime.md`** — one decision, status
   **Proposed**: options (A new package beside the ReAct loop; B rewrite
   `agent.py`; C stay ReAct) with costs and the role that carries each; your
   recommendation; the eight conflicts above, each **resolved or OWNER'S**; the
   two routing profiles; phases 1–4 with **what contract text each phase fits or
   needs amended**. End with *what this document failed to prove*.
2. **`docs/architecture/graph-runtime-spec.md`** — in this order: (a) the Mermaid
   state graph and node-transition diagram; (b) field tables for `AgentState`
   (`task_id`, `goal`, `dependency_graph`, `current_node`, `ast_context_slice`,
   `step_count`, `max_steps`, `tool_history`, `verification_status`, `error_log`),
   `GraphNode`, `GraphEdge` — **no code**, types and invariants only, and which
   fields are content-free; (c) the checkpoint spec (per-transition, append-only
   JSONL first, resume from the last verified node, retention and deletion path as
   an explicit open item for the SE); (d) the routing policy layer and both
   profiles; (e) the AST subgraph extraction algorithm with `CALLS`, `IMPORTS`,
   `MUTATES` edges **and an honest statement of what the stdlib `ast` can and cannot
   know** (`IMPORTS` is exact; `CALLS` and `MUTATES` are name-based
   approximations); (f) the tool-contract validation and sandbox boundary (G's
   `Workspace`, `validate_loopback_url`, the fixed allowlists, brief 20's five
   guards).
3. **`docs/architecture/graph-runtime-engineering-rules.md`** — the strict rules for
   the implementing engineer (Codex): no unbounded loops, a checkpoint on every edge
   transition, strict types, a retry budget `N = 3` then `HumanEscalationNode`,
   no new dependency without the SAE, never edit `agent.py`'s loop, one module per
   brief. **Tracked**, so every worktree receives it.

**Every invariant in the spec carries one more line: the test that must go red if
the invariant is broken, and how to mutation-check it.** That is how this project
avoids the "refused" test that proves nothing. The PM will turn the phases into
`docs/pm/graph-runtime-milestones.md`; **do not write milestones.**

## Reading budget — be economical

Contract §1, §2, §3, §5, §6; threat-model lines 105–128 and 173–192;
`docs/architecture/system-overview.md`; ADR-0003's summary and carry-over
section; G's `agent.py` lines ~800–900 (the loop) and the `Workspace` API in
`sandbox.py`, read from `git show 5005039:<path>`. Do not read the briefs, the
cohort scripts or `securefs.py`.

## What you must not touch

Any `.py` file, any test, any workflow, `docs/pm/` (including the contract), and
**`D:\code-project\OmniAgent`, the main checkout, where Codex is editing.** No
merge, rebase, cherry-pick or push to either `main`; name the remote on a branch
push. Nothing installed on the owner's machine.

## Gates

Docs only, but the three gates run on the branch you commit, full path, never your
own `-q`: `.venv\Scripts\python.exe -m ruff check .` / `-m mypy` / `-m pytest`.
Baseline on `origin/pm/verify-brief16`: ruff clean, mypy clean over 48 files,
**798 passed**. The repository's pre-push hook runs them too.

## Standing rules (end of `~/.claude/CLAUDE.md`)

Rule 1: reproduce before you report; label every figure MEASURED / RECORDED /
REPORTED; end with a `QA:` line. **Rule 2: the weekly meter is per account and
shared by every Claude chair. Today's ceiling is 28% and it read 23% when this was
written, so you have about four points.** The ADR is the priority; **if the meter
reaches 27%, stop at a clean state and tell the PM which deliverable you finished.**
End with a `Budget:` line.

## Done when

- ADR-0005 on your branch, **Proposed**, with all eight conflicts answered;
- the spec's sections (a)–(f) answered, each invariant with its red-test line;
- the engineering rules file;
- three gates green, pushed with the remote named;
- one message to the PM with the owner's open decisions as lettered options, each
  ending by naming the chair that would carry it out.

## The one thing that would make this wrong

**Designing the runtime the prompt describes instead of the one the contract
permits.** The prompt's `WorkerNode` edits code and its routing sends planning to
Claude and patches to Codex; the contract's product reads files and talks only to
loopback. Where they disagree, **write the contract-fitting design and mark the
rest gated**. Do not quietly widen the product.
