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

## Ruling 10 (owner, later on 2026-11-22): snapshot Codex's uncommitted work (option 1A)

The owner chose to snapshot the main checkout's 54 uncommitted changes and push. Done by the PM from the
existing out-of-band snapshot (taken 15:12 Thai; the main checkout was not read, written or switched):
`origin/snapshot/codex-local-ai-delegate-20261122` = `3035da7` (on-disk state, parent `af99092`, 33 files)
and `origin/snapshot/codex-local-ai-delegate-20261122-index` = `665b1fc` (staged state). Checked before the push:
no secret or personal-data pattern in the added lines; the only sealed-path entries are two **deletions**
(`NEXT_CHAT.md`, `questions/bank-2026-10-10.txt`) of files already in O's public history. **Both remotes are
public** (`mntoyg/OmniAgent` and `OmniBase-Official/OmniAgent`, MEASURED with `gh repo view`), so the snapshot is
public; the hook's advisory warnings (`shell=True`, TLS off) are in a semgrep test fixture. Not verified:
that Codex did not change the checkout after 15:12 (it is paused; the PM did not look).

## Ruling 11 (owner): switch the main checkout to the canonical line (option 2A)

Done by the PM on 2026-11-22, in this order, each step checked:
1. A fresh out-of-band tree of the main checkout (temporary index) equalled the pushed snapshot's tree
   (`0fd7dc9`) and the real index equalled the `-index` snapshot's tree (`5493da8`): nothing had changed since 15:12.
2. No ignored file on disk (`.env`, `data/`, `models/`, the local `docs/pm/*-prompt.md` files) collides with a
   tracked path of the integration tree; they stay in place and are not in the snapshot by design.
3. A local branch `snapshot/codex-local-ai-delegate-20261122` at `3035da7`, HEAD moved to it with a mixed
   reset (working tree untouched): status empty, so everything Codex had is a commit on that branch and on `origin`.
4. The SAE's tree `.scratch/sae-assembly` (clean) was detached, because git allows a branch in one tree only.
5. `git switch integration/canonical-20261122`: the main checkout is at `388fa53`, tree equal to
   `origin/integration/canonical-20261122`, status empty. Gates there: ruff clean, mypy 51 files, **1,018 passed,
   2 skipped**, `agent.__file__` is `D:\code-project\OmniAgent\agent.py`.
6. `.ai/`, `.scratch/`, `omniagent-core/` were ignored by the old `.gitignore` but not by the canonical one;
   they are now in `.git/info/exclude` (local, untracked) so a `git add -A` cannot sweep `.scratch` in.
   **Tell the owner:** the canonical `.gitignore` itself still lacks them (a repo change, not made).

**For Codex when it returns:** its branch `chore/local-ai-delegate` is untouched at `af99092`; its uncommitted work is
on `snapshot/codex-local-ai-delegate-20261122` (and `-index` for the staged state), local and on `origin`.
The message `docs/pm/codex-stop-and-snapshot-prompt.md` has still not been pasted to Codex.

## Rulings 12-13 (owner): the credential-shaped snapshot and the three unpublished files

12. **Salvage by path** (brief 26, decision 2, option B): five real files of snapshot `13c7bfb` are on
    `origin/wip/salvage-search-text-race-safety-20261122` (`7aa7af9`, unreviewed, ungated). The snapshot ref
    itself is never pushed.
13. **Keep local:** `securefs.py` (+227/-3 over the public branch), `scripts/validate_windows_publish_acl.ps1` and
    `tests/test_windows_publish_acl.py`, found on no remote ref, stay only in the local snapshot ref `13c7bfb`.
    **That ref must not be deleted** until the owner rules on securefs (open decision 3) or the three are salvaged.

14. **Delete the three DISPOSABLE snapshot refs** (brief 26, decision 1): `main-checkout`, `main-checkout-index` and
    the plain `windows-private-root-fix` snapshot, each re-verified by an empty diff just before. Done; 18
    refs remain. The `windows-private-root-fix` **`-index`** twin (two staged files) is kept.

15. **Discard the `AGENTS.md` of the weekly-usage-budget snapshot** (brief 26, decision 4, option B): the snapshot ref
    (`e17b9c9`, one untracked 17-line `AGENTS.md`) was deleted. The rules live in `~/.claude/CLAUDE.md` and
    `~/.codex/AGENTS.md` (both present, MEASURED). 17 refs remain.

16. **Issue brief 28 to the SE** (brief 27 result, decision 1): hand-apply on the canonical line the preflight fix
    (status code only), the `38ea900` provenance half (with `dataset_limits` in `py-modules`) and, as a separate
    small change, the `export_dataset.read_records` limits. Brief: `docs/pm/brief-28-se-hand-apply-two-fixes-on-the-canonical-line.md`.
    Still open from brief 27: deleting the three brief 16 refs, deleting `ba3598f` after the fix lands, and the
    sec-search chair.
