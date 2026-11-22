# ADR-0001: the architecture record, and what becomes of the Codex drafts

- **Status:** Accepted by the solution architect, 2026-11-04. This decides
  which documents are the record. It decides nothing about what the system
  does, and it amends no owner-approved document.
- **Baseline:** `ae5cd95` on `main`, tree clean before and after.
- **Gates re-run at that baseline today:** `ruff` clean; `mypy` clean over
  **45** source files; **658 passed in 16.48 s**.

## Context

A Codex session, working without a brief, left four uncommitted documents in a
worktree at
`C:/Users/Thanapat Manasom/.codex/worktrees/omniagent-architecture-docs/OmniAgent`,
at baseline `f37044d` (2026-11-02):

- `docs/architecture/system-overview.md` (82 lines)
- `docs/architecture/security-and-ethics.md` (83 lines)
- `docs/architecture/repository-map.md` (113 lines)
- `docs/blog/architecture-series-outline.md` (57 lines)

They have no brief and no `## Result`, and nobody had reviewed them. The
question put to this chair was whether they are the foundation of
`docs/architecture/` or a draft to replace.

## The measurement that decides it

```
git diff --name-only f37044d..HEAD
```

returns **14 files, all of them `NEXT_CHAT.md` or under `docs/`. Not one
source file changed.** So every claim these drafts make about `agent.py`,
`tools.py`, `sandbox.py`, `config.py`, `observability.py`, `pyproject.toml`
and the two workflows is as true today as the day it was written. They are not
stale on fact, and replacing them would be paying to re-derive true sentences.

Spot-checked at `ae5cd95` rather than taken from the drafts:

| Claim | Checked by | Result |
| --- | --- | --- |
| six model-facing tools | `python -c "import tools; print(list(tools.TOOLS))"` | `calculate`, `get_current_time`, `file_info`, `read_file`, `list_directory`, `search_text` |
| loopback default, not enforced | `agent.py:34` | `DEFAULT_BASE_URL = "http://localhost:11434/v1"` — a default. Enforcement is brief 14, in flight |
| `pyproject.toml` ships flat modules | `pyproject.toml:46` | eight `py-modules`, no package |
| the two workflows | `ls .github/workflows/` | `ci.yml`, `waka-readme.yml` |

**What is stale is the ground underneath them.** The owner approved
[the agentic MVP contract](../pm/agentic-mvp-contract-2026-11-03.md) on
2026-11-03 (`159af29`) and
[the release-readiness plan](../pm/release-readiness-2026-11-04.md) landed on
2026-11-04 (`f6a02dd`). All four drafts predate both, so none of them cites
the document that now governs — and one of them contradicts the other.

## Decision, per file

| Draft | Decision |
| --- | --- |
| `system-overview.md` | **Adopted as the foundation**, amended. |
| `security-and-ethics.md` | **Adopted as the foundation**, amended. |
| `repository-map.md` | **Map adopted. Its proposal is not**, and is superseded by ADR-0002. |
| `docs/blog/architecture-series-outline.md` | **Not adopted, not deleted.** Left where it is; its location is recorded below. |

### Why the two are adopted

`security-and-ethics.md` carries a licensing and provenance inventory — base
model, tokenizer, merged weights, GGUF, training data, demo SVG, `llama.cpp`,
the third-party CI action — that **nothing else in this repository has.** The
contract's section 5 closes by saying the gates do not prove "legal rights to
third-party model/data assets", and readiness block D3 makes the model
question the owner's. That inventory is the worksheet for both. Rewriting the
document would lose it and buy nothing.

`system-overview.md` is the only place the data flow and the six trust
boundaries are written down end to end, and it is already careful where this
project has been careless: it states plainly that the README's **"Nothing
leaves localhost"** (`README.md:7`) is too broad for a configurable `base_url`
and for a training workflow that clones `llama.cpp` from GitHub. That sentence
is correct and nobody else had written it.

### Why `repository-map.md`'s proposal cannot stand

Its map half is accurate. Its *proposed target tree*, *old-to-proposed
mapping* and *migration sequence* collide with the readiness plan the owner
already has, in three ways:

1. **Compatibility wrappers preserve the blocker.** The draft's mapping says
   "preserve `import agent` if public users depend on it", and its step 5
   keeps wrappers until a later announced release. Readiness blocker 1 is
   *precisely* that installing this project puts `agent`, `config`, `tools`,
   `main` and `sandbox` into the installing user's top-level namespace. A
   wrapper that preserves `import agent` preserves the blocker it was
   supposed to remove. **Measured: there is nobody to preserve it for.** One
   tag in the repository (`demo-2026-10-10`), `version = "0.1.0"` unchanged
   across sixteen briefs, and the README's own install instruction is
   `pip install -e .` from a clone — there is no published distribution for
   a third party to have imported.
2. **Scope.** It moves `scripts/` into four subdirectories and `tests/` into
   four more, in the same proposal as the runtime move. Readiness D1 keeps
   `scripts/` out of the wheel because it is developer-only, and the one rule
   the move must obey is that it be provably behaviour-free. Every extra
   directory it touches is another chance to move a path-sensitive
   evaluation question, and the evaluation is a frozen contract artifact.
3. **Naming.** `src/omniagent/datasets/` in the draft against
   `omniagent/dataset/` in readiness D1. Trivial in itself, and exactly the
   kind of detail that has to be settled in one place before an engineer
   writes nineteen import lines.

And there is the thing the draft had the evidence for and did not find: its
own table lists `dataset_provenance.py` as a root module, and notes that
`pyproject.toml` explicitly packages top-level `py-modules`. Those two facts
together are a broken wheel. See **ADR-0002**.

### Why the blog outline is not adopted

It is not an architecture artifact. It bakes in the target tree that ADR-0002
has not settled, and it proposes publishing an article series while the
packaging shape and the model question are both open — which is a commitment
to claims we would then have to retract. **Whether it exists at all is the
owner's call, not this chair's.** Nothing is deleted: it stays at
`docs/blog/architecture-series-outline.md` in the worktree named above, and
this paragraph is the record of where it is, in the same spirit as the two
parked `secure_search.py` branches.

## The amendments made on adoption

1. **Rebaselined** from `f37044d` to `ae5cd95`, with the zero-source-drift
   measurement stated, so the baseline is checkable rather than asserted.
2. **The contract is cited as governing.** Both documents now point at
   `docs/pm/agentic-mvp-contract-2026-11-03.md` where they describe current
   behaviour that the contract has already frozen differently — logging
   defaults and endpoint enforcement especially. A description of today's
   defaults is not a description of approved policy, and the drafts could not
   have known the difference.
3. **"This documentation task did not run tests" is removed**, twice, and
   replaced with the gate figures above. A document of record in this project
   does not get to decline to measure.
4. **The `secure_search.py` paragraph is corrected.** The drafts describe the
   2026-11-02 ruling. The 2026-11-04 ruling on the same document supersedes
   it: three variants exist, the work is **parked**, and reopening it needs
   the new owner decision the contract names.
5. **The Hermes Agent reference is dropped** from both the security document
   and (with the outline) from the series plan. A third-party vendor's
   security guide is not a standard this project is held to, and naming it in
   a document of record invites the comparison the draft's own rule forbids.
6. **The measured model identity is recorded** where the drafts had only a
   name: `omniagent-v2:latest`, manifest `05ba6fe701c5`, weights blob
   `sha256-40995d3b…c8ae39c7`, served by Ollama **0.34.4** on this machine
   today.
7. **The packaging defect of ADR-0002 is added** to the security document's
   "missing before a public pilot" list, because an installed artifact that
   cannot import its own module is a release blocker and was not on any list.

## Consequences

- `docs/architecture/` exists, with an index, and the architect's documents of
  record live there.
- The adopted documents describe **today's source**; the contract describes
  **approved policy**. Where they differ the contract wins, and each
  difference is now a named gate rather than a surprise.
- The package move has one design document (ADR-0002) instead of a proposal
  in a map and a plan in a readiness report.
- The blog series stays parked and findable.

## What this does not establish

- **I did not re-verify every source claim in the two adopted documents line
  by line.** I verified the four in the table above, the ones ADR-0002 rests
  on, and the `secure_search.py` and logging paragraphs. The rest is Codex's
  source inspection at a baseline whose source has not moved — which is
  evidence, not proof.
- Whether the blog series should exist. Owner's call.
- Whether the licensing inventory's open questions have answers. The
  inventory lists them; answering them is readiness block D3 and needs the
  owner, not an engineer.
