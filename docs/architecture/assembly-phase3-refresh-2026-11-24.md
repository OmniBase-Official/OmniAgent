# Brief 24 phase 3, refreshed against `1384d63`

**C-SAE-02. MEASURED 2026-11-24, read-only.** Nothing below was run. `origin` and `organization` both hold `integration/canonical-20261122` at `1384d63`. **Removal of the clean Codex trees is owner-gated and is not planned as if it will happen.**

## What changed since the plan of 2026-11-22

| fact | then | now (MEASURED) |
| --- | --- | --- |
| registered worktrees | 48 | **36** (34 on my first listing; two chairs added trees meanwhile) |
| trees with uncommitted changes | 18 (192 status lines) | **0 of 36** (`git --no-optional-locks status --short` per tree) |
| local snapshot refs | 21 | **12**; the other 9 were deleted on the owner's rulings, recorded in `.scratch\snapshots-manifest-2026-11-22.md`, each with its SHA; the objects survive until `git gc` |
| main checkout | `chore/local-ai-delegate`, 54 dirty | `integration/canonical-20261122`, **0 dirty**, but at **`388fa53`, 10 commits behind** `1384d63` |

## Item by item

| phase 3 item | state | what is left, and whose |
| --- | --- | --- |
| **(a)** snapshot Codex's work, then switch the main checkout | **DONE.** `origin/snapshot/codex-local-ai-delegate-20261122` (`3035da7`) and `-index` (`665b1fc`) exist; the checkout is on the integration branch | **Live, new:** fast-forward the local branch to `1384d63`. **PM, with the owner's yes** (rule 5 of the location addendum: nobody else working in that tree). The two snapshot branches are on **`origin` only**: **PM screens, then pushes to `organization`** |
| **(b)** remove the SAFE-TO-REMOVE trees | **PARTLY DONE.** 48 → 36 | **My four trees** `.scratch\sae`, `sae-b19`, `sae-b23`, `sae-assembly` are clean and on a remote; the first three branches are on **`origin` only**, so push them to `organization` first. **SAE**. Others' trees: not mine, not planned |
| **(b)** the 14 clean trees outside the path | **OWNER-GATED** | Not planned. Conditions only, if the owner says yes: re-check `status` is empty, re-check the branch is on a remote, then `git worktree remove <path>`, one at a time. Three of the 14 hold a `HEAD` that is on one remote only (`collect-turns-byte-limits`, `provenance-export-bounds`: `organization`; `mypy-portability`: `origin`). **Codex** moves its own |
| **(c)** the 18 UNKNOWN trees | **DONE.** Each was re-checked byte-identical to a snapshot, then removed (manifest, 2026-11-23); seven nested trees were already gone from disk | **Live, different shape:** 12 snapshot refs exist in no remote (except `wip/salvage-search-text-race-safety-20261122`, `origin` only). **PM screens each, the owner picks push or delete.** Push by path, never wholesale: `13c7bfb` holds 423 credential-named paths |

## Ordered commands, none run

1. **PM** (owner's yes): `git -C D:\code-project\OmniAgent merge --ff-only origin/integration/canonical-20261122`. Precondition: `status --short` prints nothing.
2. **SAE**: for `sae/adr-0003-two-mains`, `sae/adr-0003-carry-over`, `sae/adr-0005-graph-runtime`: `git push organization <branch>`, then `git ls-remote origin <branch>` and `git ls-remote organization <branch>` print one SHA.
3. **SAE**, after 2: `git worktree remove` for `.scratch\sae`, `sae-b19`, `sae-b23`, `sae-assembly`; `git worktree prune -v`. `sae-b26` last.
4. **PM + owner**: per snapshot ref, push as `wip/salvage-<name>` to both remotes **or** delete the ref. Never `main`, never force.
5. **Owner-gated, not scheduled**: the 14 trees outside the path (the third table row).

## One thing I could not explain

`C:\Users\THANAP~1\AppData\Local\Temp\OmniAgent-brief11-a097263` is a registered tree **outside the project path**, clean, `HEAD` on both remotes. I do not know who made it or whether it is still used. **Owner or PM.**

## Not established

Whether any chair is working in the main checkout now (rule 5); the contents of the 12 snapshot refs beyond the earlier classification; that every tree's branch is the *same* SHA on both remotes (I counted branches containing `HEAD`); anything about CI.
