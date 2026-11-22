# ADR-0005: the graph runtime — a bounded state machine beside the ReAct loop

- **Status: Proposed, 2026-11-22.** The owner decides. Nothing here authorises a
  runtime change, a cohort, a new dependency or a cloud call.
- **Deliverable of brief 23.** Docs only; no `.py` file was read for edit, none
  was written, and the main checkout was not opened.
- **Branch point:** `origin/pm/verify-brief16` (`d0a8fed`), which carries the
  contract as amended 2026-11-22.
- Figures are labelled **MEASURED** (I ran it, dated), **RECORDED** (earlier,
  dated) or **REPORTED** (someone else's, not re-run).

## The decision

**Build the graph runtime as a new package beside the ReAct loop, not as a
rewrite of it, and ship it switched off until the contract says otherwise.**

## Context, in the project's own terms

The owner wants the engine to grow from a hand-rolled ReAct loop into a bounded
state machine: `PlannerNode`, `ContextRetrieverNode`, `WorkerNode`,
`VerifierNode`, `HumanEscalationNode`; an AST dependency graph that feeds each
node a minimal context slice; a durable checkpoint on every transition; a
routing layer; strict tool contracts.

Three things about this project decide the shape of that work before any design
question is reached.

1. **The contract is owner-approved and it scopes a read-only product**
   (§1: the MVP "does not run arbitrary commands, write or delete files, fetch
   network resources, load plugins, or delegate to other agents"; six tools, no
   new tool without a security review).
2. **The threat model's criterion 2 rests on one sentence** — *the agent has no
   write tool* — and that sentence is what keeps attacker class 4 out of scope
   and `secure_search.py` parked.
3. **§7 authorises no runtime change**, and the ReAct arm's exploratory cohort
   needs a frozen runtime to be comparable at all.

A graph runtime does not conflict with any of those. **A `WorkerNode` that edits
files does, with all three at once.**

## Options

**A. A new package beside the loop — `omniagent/graph/`, nothing in `agent.py`
changes.** The ReAct loop stays the shipped runtime and the frozen arm for the
cohort; the graph runtime grows behind an explicit opt-in that defaults off.
*Cost:* two execution paths exist for as long as it takes; the tool layer must
be callable from both, which is a small refactor of call sites, not of
behaviour. *Carried by:* **SWE (Codex)** for the package, **SE** for the tool
contract and sandbox boundary, **AI/ML** for the verifier's acceptance rules.

**B. Rewrite `agent.py` into the graph.** One runtime, no duplication.
*Cost:* it voids the frozen arm (§7) and therefore the cohort; it touches the
file brief 16 and brief 14 both landed in; and the first wrong turn is paid for
in the shipped product. *Carried by:* **SWE**, with **SE** re-doing gates 1–4
against the new path.

**C. Stay with ReAct and add bounded sub-behaviours** (a verifier pass, a
retriever) inside the existing loop. *Cost:* cheapest now, and it does not give
the owner the thing asked for — explicit states, resumable checkpoints and a
graph you can draw. The loop's implicit state stays implicit. *Carried by:*
**FSE**.

**Recommendation: A.** Not because it is cheapest — B is cheaper in the long
run — but because **A is the only option that can be wrong without costing
anything already measured.** Everything this project owns as evidence was
measured against the current loop. A keeps that evidence valid while the new
engine earns its own.

## The eight conflicts

| # | conflict | resolution |
| --- | --- | --- |
| 1 | read-only contract vs a `WorkerNode` that edits | **Resolved: phases 1–3 are read-only and fit §1 unchanged. Phase 4 (edits) is gated** behind a new owner-approved contract *and* a threat-model revision, because it deletes criterion 2's premise. A write tool is not a feature increment here; it re-opens attacker class 4 and with it the parked `secure_search.py` question. |
| 2 | loopback-only endpoint vs cloud nodes | **Resolved: one routing layer, two profiles. `local-only` ships and is the default. `hybrid` is specified and permanently refused at runtime** until a contract amendment. The refusal is the endpoint validator that already exists, not a new flag: a non-loopback base URL cannot be constructed. |
| 3 | no persistent traces; no raw prompts, observations, errors or full URLs | **Resolved: the checkpoint is content-free by default** — node ids, transition ids, SHA-256 digests, counters, enum statuses, durations. Raw text lives in memory for the run and is never written. A `--checkpoint-content` opt-in exists in the spec and is **inert until the SE defines a retention and deletion path**, which §5 requires. |
| 4 | §7 authorises no runtime change; the cohort needs a frozen arm | **Resolved by option A itself.** `agent.py`'s loop is not edited. The graph runtime is not an arm of the current evaluation and must not be compared with the ReAct arm until it has its own frozen protocol hash. |
| 5 | the premise that the loop is unbounded | **Resolved: the premise is wrong and the ADR says so.** `max_steps` is `Field(default=8, ge=1, le=50)` (MEASURED 2026-11-22 at `5005039`), and the loop is `for iteration in range(1, max_steps + 1)` (REPORTED by the PM, not re-read by me). The loop is bounded by construction today. **What the graph adds is not a bound; it is an explicit state you can resume from.** Sell it as that or not at all. |
| 6 | "no frameworks"; tree-sitter | **Resolved for now: stdlib `ast` only.** `ast` is in the standard library, pure Python, and already the basis of `calculate`'s allowlisted evaluator. **tree-sitter is OWNER'S** — it is a native dependency, and threat-model criterion 5 settled how this project treats those: if a native module is the right shape, "hand-rolled and small" stops being true and should stop being written down. That is the owner's call to make explicitly. |
| 7 | file placement | **Resolved: tracked files under `docs/architecture/` only** — this ADR, `graph-runtime-spec.md`, `graph-runtime-engineering-rules.md`. `AGENTS.md` and `CLAUDE.md` are untracked by the owner's instruction, so an engineer in a fresh worktree would never receive rules written there. No `architecture.md`: `system-overview.md` already holds that job. |
| 8 | sequencing against the open MVP work | **Resolved as a dependency statement, not an order** — the PM orders. See below. |

### Where this sits against the open work

**Blocking this work:** nothing. It is a new package and touches no file any
open brief holds.

**Blocked by this work:** nothing. No gate, no release blocker and no
measurement depends on the graph runtime existing.

**Ordering constraints that are real:**

- the **ReAct cohort** must run on a frozen runtime, so phase 1 may be written
  at any time but **no graph run may be reported beside a ReAct arm** until both
  have frozen protocol hashes;
- **gate 2's five guards** (brief 20) sit under the tool layer the graph runtime
  will call; the graph must call *through* them, so it should not land before
  each guard has a test that goes red on its own removal;
- the **package move** (ADR-0002 / readiness D1) decides where
  `omniagent/graph/` lives. Writing the graph into the current flat layout
  **adds a tenth and eleventh top-level module to a namespace already named as a
  release blocker.** Either the package move lands first, or the graph package
  is the first thing written in `src/omniagent/` and the move follows it.
- `securefs.py`, the model question and CI are **independent**: none of them is
  a precondition and none of them is blocked.

## The two routing profiles

One policy layer, two profiles, and the difference between them is a *product
promise*, not a setting.

| | `local-only` — **shipped default** | `hybrid` — **specified, disabled** |
| --- | --- | --- |
| who answers | Ollama on a loopback IP literal | a cloud model for planning, a local model for the rest |
| contract | §2 as amended 2026-11-22 | **needs a new contract**: §1 "no delegation to other agents" and §2 both forbid it |
| what it changes | nothing | the README's "nothing leaves your machine", the privacy notice, the threat model's trust boundaries, and the licence/data questions in `security-and-ethics.md` |
| enforcement | the existing endpoint validator refuses every non-loopback host | **the same validator refuses `hybrid` by construction** — it cannot be enabled by configuration alone, only by changing code that a test pins |

**I read the owner's "do both" as "design both, ship one".** If the owner meant
"enable both", this ADR is wrong and should be returned rather than quoted —
**OWNER'S.** The reason to put it this way round: turning `hybrid` on is a
decision about what the product *is*, and the one thing this project has
consistently refused to do is widen the product quietly.

## Phases, and the contract text each needs

| phase | what it is | contract fit |
| --- | --- | --- |
| **1. the graph, read-only** | `AgentState`, nodes, edges, the bounded transition loop, content-free checkpoints, the six existing tools behind the existing allowlists | **fits §1, §2, §5, §6 unchanged.** Nothing new is permitted to the model |
| **2. the AST context slice** | stdlib `ast` dependency graph, minimal slices, `IMPORTS`/`CALLS`/`MUTATES` edges | **fits unchanged.** It reads files through `Workspace`; it adds no tool and no capability |
| **3. the verifier and escalation** | `VerifierNode` acceptance rules, retry budget, `HumanEscalationNode` | **fits unchanged**, and it is the phase that makes the runtime honest: a bounded machine that cannot say "I give up" just spends its budget |
| **4. the worker that edits** | writing files, running commands | **does not fit.** Needs: §1 rewritten to permit a write capability; a new tool with its own security review; **threat-model criterion 2 re-answered, because its premise is deleted**; attacker class 4 re-opened; and the `secure_search.py` ruling revisited. **Gated — OWNER'S, and not a phase to slip into.** |
| **(parallel) `hybrid`** | cloud routing | **does not fit** §1 or §2. Gated behind its own contract, its own egress policy and its own validator |

## What this document failed to prove

- **That the graph runtime is better than the loop at anything.** No measurement
  exists on either side; there is no baseline for a bounded state machine in
  this project and I did not invent one. The case for it is resumability and
  legibility, which are design arguments, not figures.
- **That the AST slice is cheaper than the current context budget.** Untested.
  The spec says what `ast` can and cannot know; it does not say the slices will
  be smaller than what the loop sends today.
- **The loop's exact form.** I measured `max_steps`'s bounds; the `for … in
  range(...)` line is the PM's reading, carried as REPORTED.
- **That option A's two execution paths will not drift.** They will, unless the
  tool layer is the only thing both call. That is an engineering rule, and rules
  are obeyed by tests, not by documents.
- **Anything about POSIX, or about `securefs.py`.** Unchanged and untouched.
