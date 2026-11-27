# Repository assembly — inventory, integration result, and the plan that was not run

**Brief 24, phases 0, 1, 2 and the written half of 3. MEASURED 2026-11-22**
unless labelled otherwise. Work done in
`.scratch\sae-assembly` under the repository root, a worktree inside the path.

**The main checkout was not read, written, switched or tested.** It still holds
54 uncommitted changes on `chore/local-ai-delegate` (REPORTED by the PM, not
measured by me).

**Budget note:** phases 1 and 2 were run under the owner's explicit override of
the 28% daily ceiling, given in chat on 2026-11-22. Said here because Rule 2
requires it to be said.

## Phase 0, table 1 — every registered worktree

`git worktree list --porcelain`, then per tree `git status --short | wc -l` and
`git rev-list <HEAD> --not --remotes | wc -l`.

| | count |
| --- | --- |
| registered worktrees | **48** |
| **commits not reachable from any remote, across all 48** | **0** |
| clean trees (SAFE-TO-REMOVE) | **30** |
| trees with uncommitted changes (UNKNOWN, see below) | **18** |
| uncommitted status lines in total | **192** |

**Nothing that is committed exists only on this machine.** Every worktree's
`HEAD` is reachable from a remote branch. The only content at risk anywhere is
uncommitted.

The 18 trees holding uncommitted changes, worst first:

| lines | worktree |
| --- | --- |
| 54 * | the repository root — the main checkout, `chore/local-ai-delegate` `af99092`. **REPORTED, not measured: I did not read this tree.** |
| 46 | `.scratch\brief16-proposed-tree-20261109` (detached `af99092`) — the twin of the main checkout's privacy/logging work, classified 2026-11-10 |
| 17 | `~\.codex\visualizations\2026\10\24\…\brief16-operational-telemetry` |
| 12 | `.scratch\pre-user-dataset-bounds-20261119` |
| 12 | `.scratch\pre-user-security-logging-20261119` |
| 9 | `.scratch\security-bootstrap-20261119` |
| 6 | `~\.codex\worktrees\compare-file-lines-secure-20261102` |
| 6 | `~\.codex\worktrees\dataset-input-bounds-20261116` |
| 6 | `~\.codex\worktrees\search-text-race-safety` |
| 6 | `~\.codex\worktrees\search-text-race-safety\.scratch\privacy-publish-gate-20261112` |
| 5 | `~\.codex\worktrees\security-validation-r37` |
| 3 | `~\.codex\worktrees\publisher-primitives-harness` |
| 3 | `.scratch\sec-search-001-remediation-20261112` |
| 2 | `~\.codex\worktrees\search-text-race-safety\.scratch\sec-search-001-20261112` |
| 2 | `~\.codex\worktrees\windows-private-root-fix` |
| 1 | `~\.codex\worktrees\security-ci-release-backlog` |
| 1 | `~\.codex\worktrees\windows-sid-validation` |
| 1 | `.scratch\weekly-usage-budget-20261118` |

**Why all 18 are UNKNOWN and not UNIQUE-WORK.** `git status --short` counts
untracked files, and **I opened none of them**. A line may be a day's work or a
stray cache. *What would settle it:* one `git status --short` per tree with the
filenames read. Two are known to be real work from earlier sessions: the 54 and
the 46.

**The location rule, done for my own trees.** `OmniAgent-sae`,
`OmniAgent-sae-b19` and `OmniAgent-sae-b23` were clean with zero unpushed
commits, so they were moved — `git worktree move`, not copied, not deleted — to
`.scratch\sae`, `.scratch\sae-b19`, `.scratch\sae-b23`. **`D:\code-project` now
contains exactly one folder.** 27 Codex worktrees remain outside the path under
`~\.codex\worktrees`, 11 of them dirty; they are Codex's to move.

## Phase 0, table 2 — the remote branches against G (`5005039`)

57 remote refs classified by ancestry.

| relation | what it means | count |
| --- | --- | --- |
| **in-G** | an ancestor of `5005039` | 2 |
| **stacked-G** | contains G, 1–22 commits ahead | 14 |
| **G-line** | on G's history but not containing its tip | 6 |
| **O-line** | contains `3c76fd2` | 12 |
| other | neither tip is an ancestor | 10 |

**Carries `securefs.py` — blocked pending the owner** (4 branch names, each on
both remotes): `scale-security-hardening-20261113`,
`security-scans-validation-20261120`, `security-runner-fixtures-20261120`,
`windows-private-root-validation-20261121`. Nothing in this assembly touches
them.

**PM-verified and used here:** `origin/claude/se-gate2-guard-tests-09c889`,
`origin/claude/se-brief21-defaults-and-url`,
`origin/claude/se-brief22-endpoint-corpus` — each **stacked-G and exactly 1
commit ahead**, which is why they could be merged one at a time.

**Left out deliberately:** `codex/security-ci-release-hardening-20261121`
(PR #10, draft, red on Security gates — SE 02 is diagnosing it) and everything
not verified by the PM.

**A fact that changed how unit 4 was done:** `origin/pm/verify-brief16` is
**O-line, 119 commits ahead of G**, and `origin/sae/adr-0005-graph-runtime` is
O-line, 116 ahead. **Merging either would drag O's entire code history into the
canonical line.** The documents were therefore carried as *files*
(`git checkout <ref> -- docs/pm docs/architecture`), not as a merge.

## Phase 1 — the integration branch

`integration/canonical-20261122`, branched from **G `5005039`**, four units,
three gates after every one.

| unit | source | result | ruff | mypy | pytest |
| --- | --- | --- | --- | --- | --- |
| baseline | `5005039` | — | — | — | **860 passed, 2 skipped** |
| 1 | SE brief 20 `01a0938` | merged clean | clean | 50 files | **874 passed** (+14) |
| 2 | SE brief 21 `6831ba7` | merged clean | clean | 51 files | **895 passed** (+21) |
| 3 | SE brief 22 `3ac11d7` | merged clean | clean | 51 files | **1,018 passed** (+123) |
| 4 | documents, 44 files | file carry | clean | 51 files | **1,018 passed** |

**The open question the brief named is answered: the three SE briefs merge
cleanly and the suite stays green.** No conflict in any unit, nothing had to be
resolved, nothing was left out. **1,018 passed, 2 skipped — exactly the
predicted number** (860 + 14 + 21 + 123). A prediction written before the run
and met to the test is the strongest evidence this assembly produces.

## Phase 2 — proof, measured

| check | result |
| --- | --- |
| `import agent` resolves inside the worktree | `…\.scratch\sae-assembly\agent.py` ✓ |
| ruff / mypy / pytest | clean / 51 files / **1,018 passed, 2 skipped** ✓ |
| `python main.py --help` | exit 0 ✓ |
| `python main.py --print-config` | runs ✓ |
| `localhost` is refused | ✓ `EndpointPolicyError: base_url must name the local loopback endpoint…` |
| demo profile resolves to `omniagent-v2` | ✓ `model omniagent-v2  profile:demo` |
| `AgentConfig().verbose` | ✓ `False` |
| brief 21's two retry layers are named as two | ✓ `client_max_retries 0`, `max_retries 2` |
| **the wheel test** | **SKIPPED, not passed — see the finding below** |

## The finding this phase produced

**[MEDIUM] `tests/test_wheel_install.py` skips on a machine that can build
wheels, so the regression guard for ADR-0002's defect never runs.**

- **Location:** `tests/test_wheel_install.py:22`.
- **Scenario:** (1) a maintainer edits `py-modules` and drops a module the wheel
  needs; (2) the suite is green because the only test that would notice skipped;
  (3) the broken wheel ships. The actor is a future maintainer, not an attacker.
- **Proof (MEASURED 2026-11-22):** the guard is
  `if any(importlib.util.find_spec(name) is None for name in ("setuptools",
  "wheel"))`. In this venv `import wheel` succeeds (0.45.1) and `import
  setuptools` succeeds (78.1.0), but **`importlib.util.find_spec("wheel")`
  returns `None`**, so the guard fires. `pip wheel` was MEASURED working in this
  same venv on 2026-11-10, which is how ADR-0002's defect was found in the first
  place. Result: `1 skipped in 1.93s`.
- **Remediation:** test the capability, not the module spec — run the build in a
  subprocess and skip only when it actually fails. **The mutation check that
  proves it:** remove `dataset_provenance` from `py-modules` and the test must go
  red. Today it cannot.
- **Unknown:** whether CI's environment skips it too. *What would settle it:* one
  CI run with `-rs`.

## Phase 3 — the plan, written and NOT run

**None of this was executed. It is the PM's to run with the owner's yes.**

**(a) Switch the main checkout — only after Codex's work is on a named branch.**

```
git -C . status --short            # expect 54; confirm with Codex first
git -C . switch -c snapshot/codex-local-ai-delegate-20261122
git -C . add -A
git -C . commit -m "snapshot: Codex's in-flight work, unreviewed"
git -C . push origin snapshot/codex-local-ai-delegate-20261122
git -C . switch integration/canonical-20261122
```

**The snapshot must exist and be pushed before the switch.** A `switch` with 54
uncommitted changes either refuses or carries them onto the new branch; neither
is what anyone wants.

**(b) Remove the SAFE-TO-REMOVE worktrees** — 30 of them, each clean and fully
on a remote, so nothing is lost and each can be recreated with
`git worktree add`:

```
git worktree remove <path>      # per tree, then once:
git worktree prune -v
```

**(c) The 18 UNKNOWN trees — look before removing.** For each:

```
git -C <path> status --short                      # read the filenames, decide
git -C <path> switch -c salvage/<name>-20261122   # only if it is work
git -C <path> add -A && git -C <path> commit -m "salvage: <name>"
git -C <path> push origin salvage/<name>-20261122
```

Then (b). **No tree with uncommitted content is removed until its content is on
a pushed branch or has been read and judged disposable.**

**What this plan does not include, deliberately:** any push to either `main`,
any force-push, any history rewrite, any deletion of a branch, and any change to
which remote is canonical. None of that has been asked for.

## What this document does not establish

- **The contents of the 18 dirty trees.** Counted, not opened.
- **That the integration branch is correct**, only that it is green: 1,018 tests
  passing is not a review of brief 20, 21 or 22, which the PM verified
  separately.
- **That CI agrees.** Not run here.
- **Anything about POSIX, `securefs.py`, or PR #10.** Untouched.
- **That the main checkout can be switched safely.** It was not read.
