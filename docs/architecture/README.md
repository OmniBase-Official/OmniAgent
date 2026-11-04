# docs/architecture

The solution architect's documents of record. **These describe the shape of
the system. They do not approve anything** — the owner-approved documents are
[the agentic MVP contract](../pm/agentic-mvp-contract-2026-11-03.md) and
[the search-boundary threat model](../pm/threat-model-2026-11-02-the-search-boundary.md),
and where this directory and the contract differ, the contract governs.

| Document | What it is | Status |
| --- | --- | --- |
| [ADR-0001](ADR-0001-the-architecture-record-and-the-codex-drafts.md) | What became of four uncommitted Codex drafts: two adopted, one half-adopted, one parked | Accepted by the architect, 2026-11-04 |
| [ADR-0002](ADR-0002-the-wheel-this-project-builds-is-broken.md) | The built wheel cannot import its own dataset exporter, and what that does to the package move | **Proposed — awaiting the owner's choice of option** |
| [system-overview.md](system-overview.md) | Data flow, components, trust boundaries, the served model's identity | Current at `ae5cd95` |
| [security-and-ethics.md](security-and-ethics.md) | Evidence ledger, licensing and provenance inventory, what is missing before a pilot | Current at `ae5cd95` |
| [repository-map.md](repository-map.md) | What each path is for, and what is deliberately not on `main` | Current at `ae5cd95` |

## The rules these documents are held to

- **A figure without a run behind it does not go in.** Every number here says
  what measured it and at which commit.
- **Each document ends by saying what it failed to prove.** A design document
  that does not is a story.
- **An ADR records one decision**, its measurement, the options with their
  costs, and the role that would carry each out. Decisions that change scope,
  risk, or anything hard to undo are **proposed here and approved by the
  owner**, never self-approved.
- **Figures go stale.** Re-measure before quoting one that is more than a few
  days old.
