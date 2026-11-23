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

17. **Delete the three brief 16 snapshot refs** (brief 27, decision 2): `scratch_brief16-proposed-tree-20261109` (`1978f52`),
    its `-index` twin (`3350a5b`, same tree) and `_24_...brief16-operational-telemetry` (`8e72843`). Done by the PM; none was on a
    remote; objects survive until `git gc`, SHAs are in the local manifest. 14 snapshot refs remain.

18. **Merge brief 28's A, B and C into `integration/canonical-20261122`** (owner: "Merge A/B/C"). Given to the SE; PM re-verifies the
    merged tip. Branches: A `a6e7c38`, C `ccefadc` (contains B `a10a41b`), integration tip before the merge `388fa53`. Not decided: the
    endpoint line in the preflight banner (`main.py:200`); deleting `ba3598f` and `38ea900` (waits for the merge to be verified).

    **Ruling 18 done, PM-verified 2026-11-22 (MEASURED):** `origin/integration/canonical-20261122` = `b164aaa`, a fast-forward from
    `388fa53` (two `--no-ff` merges: A `a6e7c38`, then B+C `ccefadc`). `a6e7c38`, `a10a41b`, `ccefadc` are ancestors; the tip differs from C by
    exactly A's two files (`agent.py`, `tests/test_preflight_error_text.py`). `origin/main` still `3c76fd2` and `organization/main` still `5005039`.
    In a throwaway tree at `b164aaa` (module paths inside it): ruff clean, mypy 55 files, **1,065 passed, 2 skipped**; restoring `agent.py` of
    `388fa53` (`8a61a2063a5d`) turns the preflight test red (2 failed), the merged file (`6961cc0922ff`) before and after gives 3 passed.
    Not done: the main checkout on this branch is still at `388fa53` (not fast-forwarded: owner's word needed); wheel build still UNVERIFIED.

19. **Delete the two dataset-bounds snapshot refs** (brief 27, decision; owner: "Delete 2 refs"): `scratch_pre-user-dataset-bounds-20261119`
    (`ba3598f`) and `codex_worktrees_dataset-input-bounds-20261116_OmniAgent` (`38ea900`). Done by the PM after the brief 28 merge (`b164aaa`)
    was verified; neither was on a remote; objects survive until `git gc`. 12 snapshot refs remain. Deliberately not carried over: `ba3598f`'s
    `collect_turns`/`build_examples` budgets (not asked for) and its smaller limits (they broke 27 canonical tests).

20. **Ruling 3A done (2026-11-23, PM):** 14 dirty worktrees removed after each was shown byte-identical to a snapshot commit; branches untouched; the
    28 other registered worktrees were not touched. The seven nested `search-text-race-safety/.../.scratch/*` trees were found already missing from disk
    (their content is in snapshots `9da92ab`, `3675a88`, `13c7bfb`). **Owner word still needed** for the clean Codex-app trees.
21. **Weekly ceiling raised again (owner, 2026-11-23, in the PM session):** "today the weekly usage is use from 46% to 56%". Relayed to SAE 01, SE 01 and
    AIE 01; **SAE 01 holds until the owner says it in its own session** (its Rule 2 reading: an override binds only in the session where the owner gives it).

22. **Park `securefs.py` (and its companion `publisher_root.py`)** (owner, 2026-11-23: "Park securefs"; SAE memo option C,
    `docs/architecture/securefs-decision-memo-2026-11-22.md` on `origin/sae/snapshot-classification-20261122` at `6412cd1`). This is the same
    ruling the owner made for `secure_search.py` on 2026-11-02 and 2026-11-04, applied to its successor and **named for `securefs`**:
    - **Condition to reopen:** the owner's five criteria (`docs/pm/threat-model-2026-11-02-the-search-boundary.md`, lines 105-128) answered
      **in writing with evidence**: (1) name the attacker and show it exists on a single-user machine without a cheaper route; (2) show the
      actor that can act; (3) one MEASURED result per supported platform (Windows AMD64, the pinned `ubuntu-24.04` runner, WSL) showing it does not
      fail closed where we run; (4) byte-identical `search_text` output on the real tree; (5) fit the "hand-rolled and small" premise or amend
      it (the module is 1,319 lines plus a 469-line companion, past the 1,200 the criterion names). The SAE's score today: one half-answer of five.
    - **Nothing is merged.** The four branches (`scale-security-hardening-20261113`, `security-scans-validation-20261120`,
      `security-runner-fixtures-20261120`, `windows-private-root-validation-20261121`) stay as they are, on both remotes.
    - **Nothing is deleted:** the four snapshot refs `13c7bfb`, `900d8b6`, `033b308`, `f44cbf3` stay until someone reads the unpublished nested revisions
      against the public ones (UNVERIFIED that they are superseded). Ruling 13 ("keep local") therefore stands in practice, with the weaker reason.
    - **Not decided here:** whether to salvage the Windows ACL / private-root work (not the boundary module) from those branches. That was
      memo option B's second half; it is still open and is not blocked by the park.
    - **Unreviewed, not condemned:** nobody has said the code is wrong. The code review (1,319 lines of `ctypes`) is the SE's, only if the question reopens.

23. **Port brief 12's run-record layer onto the canonical line** (owner, 2026-11-23: "Port record layer"; AIE memo option A,
    `aiml/holdout-instrument-memo-20261122` at `dc7967f`). Scope as the memo states it: `question_record`, `_tree_clean`,
    `_append_question_record`, `RUNS_PATH` and `report()` plus `tests/test_holdout_record.py`, onto the canonical line; the clean-tree test
    mutation-checked; the canonical bank declared a **new baseline with its own stated denominator**. No fixture, no new public data files, the
    old bank is not restored, no figure from before 2026-11-22 is called comparable. Carried by the AI/ML chair; the PM verifies before anything merges.

24. **Merge brief 30a (S1) and the run-record layer into `integration/canonical-20261122`** (owner, 2026-11-23: "Merge S1 + records"). Branches:
    `se/brief-30a-empty-answer` `682caba` and `aiml/record-layer-20261123` `5aba0c2`, both cut from `b164aaa`, disjoint files, `merge-tree` clean.
    Carried by SE 01; the PM re-verifies the merged tip. **Not in this ruling:** `se/brief-29b-gitignore` (`8071f93`) and the AIE measurement branch
    `aiml/first-measurement-20261123` (`c9a00ea`): they stay unmerged until the owner says so.
    Standing rule (owner, same day): every chair sends its final report to the PM chat, not only its own.

    **Ruling 24 done, PM-verified 2026-11-23 (MEASURED):** `origin/integration/canonical-20261122` = `1384d63`, a fast-forward from `b164aaa` (two `--no-ff` merges:
    S1 `a49b2b7` from `682caba`, record layer `1384d63` from `5aba0c2`). Exactly five files changed (`main.py`, `scripts/holdout_eval.py`, `tests/test_empty_answer_exit.py`,
    `tests/test_holdout_record.py`, `docs/pm/record-layer-2026-11-23-result.md`). `origin/main` still `3c76fd2`, `organization/main` still `5005039`; 29b and the AIE
    measurement branch are not in the tip. Throwaway tree at `1384d63`, module paths inside it: ruff clean, mypy 57 files, **1,085 passed, 2 skipped**; canonical `main.py`
    restored (`69007bd3d19e`; merged `486daf4c0ff2` before and after): S1 tests **6 red, 1 passed**, G2 guards **14 passed**; `_tree_clean` always true: **1 red**, restored hash `1a843b4196ff`.
    SE 01 wrote S1 and merged it; this re-run is the independent check. Not verified: GitHub Actions behaviour (no `.github/` on this line); the main checkout's local
    `integration/canonical-20261122` is still behind origin and was not touched.

25. **Fix tool text** (owner, 2026-11-23, answering the AIE's option A after the temperature-0 run): change the **output and error text** of `read_file` (the "too long to return in full" error)
    and `list_directory` (an additive footer) so the facts a counting question needs are in front of the model. **Scope limits set by the PM, not yet ruled by the owner:** the system prompt
    is untouched; guard G2e and the contract §2 rule that a disallowed tool ends the turn are untouched (so "tell the model what it may call after a refusal" is **not** part of this ruling:
    it would need a contract change). Carried by SE 01 on `se/brief-31-tool-text` from `1384d63`; the AIE re-measures at temperature 0 on that tip against a prediction written first; the SAE
    writes a gate note on whether the contract bounds tool text. Nothing merges until the owner says so.

26. **Push every activity to BOTH remotes** (owner, 2026-11-24: "every activity should push to main repo and organization repo"). PM reading, recorded so the owner can correct it: "main repo" is the remote `origin` (`mntoyg/OmniAgent`) and "organization repo" is the remote `organization` (`OmniBase-Official/OmniAgent`); it does **not** mean the `main` branch, which stays guarded (never push to it, never force). Written as **ADDENDUM 3** (OmniAgent-only) at the end of `~/.claude/CLAUDE.md` and `~/.codex/AGENTS.md` (originals backed up before the append; the original bytes are unchanged), with local copies `docs/AGENTS.md`, `docs/CLAUDE.md` and `docs/CODEX.md` (`CODEX.md` is a new extract: there is no separate `codex.md`; Codex reads `AGENTS.md`). Pushing both is part of "done". Backfilled the same day by the PM: 14 chair branches pushed to `organization` and compared (same SHA on both remotes for all 14); `origin/main` `3c76fd2` and `organization/main` `5005039` untouched. This also means the integration line now exists on both remotes, which does **not** settle ruling 1's open question of which remote hosts the canonical line.

    **Ruling 26 confirmed by the owner (2026-11-24: "Yes, origin"):** "main repo" is the remote `origin`; the `main` branch of either remote stays guarded.

27. **Fast-forward the main checkout** (owner, 2026-11-24: "Yes, fast-forward"). Done by the PM: before, the checkout was clean on `integration/canonical-20261122` at `388fa53`, an ancestor of `1384d63`, no file collision with local untracked files; `git merge --ff-only origin/integration/canonical-20261122`; after: HEAD `1384d63`, status empty, tree identical to the origin tip. Gates run in it: ruff clean, mypy 57 files, 1,085 passed, 2 skipped (`agent.__file__` is `D:\code-project\OmniAgent\agent.py`). The local ignored copies in `docs/` (`AGENTS.md`, `CLAUDE.md`, `CODEX.md`, `task.md`) were not touched.
