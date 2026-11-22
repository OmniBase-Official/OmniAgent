# The 21 snapshots of uncommitted work — what each one is

**Brief 26. MEASURED 2026-11-22**, read-only, from the local refs
`refs/snapshots/20261122/*` and **not from the live worktrees**. Manifest:
`.scratch\snapshots-manifest-2026-11-22.md`.

**Nothing was removed, moved, restored or pushed** except this document's own
branch. The main checkout was not touched.

**Both remotes are public.** No content from any snapshot is reproduced here —
**paths only, never file contents** — and nothing in a snapshot should reach a
remote without the PM screening it first.

**Method, so the PM can re-run it:**

```
git diff --name-only refs/snapshots/20261122/<name>^ refs/snapshots/20261122/<name>
git diff --name-only refs/snapshots/20261122/<name> <a remote branch>   # the disposable proof
```

Budget note: run under the owner's explicit override of the 28% daily ceiling,
given in chat 2026-11-22.

## The counts

| verdict | snapshots |
| --- | --- |
| **DISPOSABLE** — proved by an empty diff against a pushed branch | **3** |
| **REAL WORK** — content that exists nowhere else | **18** |
| of those, also carrying **SEALED-OR-SECRET paths** | **1** |
| snapshots examined | **21** |
| trees with no snapshot | **1** (`.scratch\se-ci`, and it is gone — see the end) |

## DISPOSABLE — safe to delete the ref, nothing is lost

| snapshot | proof |
| --- | --- |
| `main-checkout` | `git diff --name-only …/main-checkout origin/snapshot/codex-local-ai-delegate-20261122` → **0 files.** Identical to the pushed branch |
| `main-checkout-index` | same against `origin/snapshot/codex-local-ai-delegate-20261122-index` → **0 files** |
| `codex_worktrees_windows-private-root-fix_OmniAgent` | `git diff --name-only <ref>^ <ref>` → **0 files.** The worktree held nothing uncommitted |

## REAL WORK — content that exists nowhere else

Parent is the commit the tree was sitting on; "files" is what the uncommitted
state adds over it.

| snapshot | parent | files | what it is (by path) |
| --- | --- | --- | --- |
| `scratch_brief16-proposed-tree-20261109` | `af99092` | 46 | the privacy/logging rewrite: `agent.py`, `config.py`, `observability.py`, `README.md`, and deletions under `docs/pm/`. **Differs from the pushed Codex snapshot in 37 files — it is not that work** |
| `scratch_brief16-proposed-tree-20261109-index` | `af99092` | 46 | its staged twin; **23 files differ from the pushed `-index` branch** |
| `_24_…_brief16-operational-telemetry` | `af99092` | 17 | a third variant of the same subject (`agent.py`, `observability.py`, `export_dataset.py`, `scripts/grounding_cohort.py`, 8 test modules). **33 files differ from the pushed snapshot** |
| `scratch_pre-user-security-logging-20261119` | `3c76fd2` | 12 | `config.py`, `main.py`, `observability.py`, `omniagent.toml`, `scripts/collect_dataset.py` + 5 tests |
| `scratch_pre-user-dataset-bounds-20261119` | `3c76fd2` | 12 | `dataset_limits.py` (new), `dataset_provenance.py`, `export_dataset.py`, `scripts/publish_dataset.py` + 4 tests |
| `scratch_security-bootstrap-20261119` | `3c76fd2` | 9 | `.github/workflows/security-gate.yml`, `.gitleaks.toml`, `.gitleaksignore`, `.pre-commit-config.yaml`, `.semgrep.yml`, `docs/security-scanning.md` |
| `codex_worktrees_security-validation-r37_OmniAgent` | `d045397` | 5 | `.github/workflows/ci.yml`, two Windows ACL PowerShell scripts, `tests/conftest.py`, `tests/test_test_fixtures.py` |
| `arch-text-race-safety…privacy-publish-gate-20261112` | `5005039` | 6 | `scripts/promote_model.py`, `scripts/publish_dataset.py`, `validate_dataset.py` + 3 tests |
| `codex_worktrees_compare-file-lines-secure-20261102` | `f37044d` | 6 | `sandbox.py`, `tools.py`, `pyproject.toml`, `README.md`, `tests/test_compare_file_lines.py` and **`secure_search.py`** — the parked module; **blocked pending the owner, do not salvage without a ruling** |
| `codex_worktrees_dataset-input-bounds-20261116` | `3c76fd2` | 6 | `dataset_limits.py`, `dataset_provenance.py`, `validate_dataset.py`, `pyproject.toml` + 2 tests. **Overlaps `pre-user-dataset-bounds` — two attempts at one subject** |
| `codex_worktrees_publisher-primitives-harness` | `5005039` | 3 | `.github/publisher-primitives-{linux.sh,windows.ps1}` and its workflow |
| `scratch_sec-search-001-remediation-20261112` | `b0b3467` | 3 | `tools.py`, `tests/test_file_tools.py`, `README.md` |
| `ees_…_sec-search-001-20261112` | `b0b3467` | 2 | `tools.py`, `tests/test_file_tools.py`. **The same subject as the row above, in a second tree** |
| `codex_worktrees_windows-private-root-fix_OmniAgent-index` | `870e8fb` | 2 | `scripts/prepare_windows_private_test_root.ps1`, `tests/test_windows_publish_acl.py`. **These exist only in the index — the worktree snapshot of the same tree is empty** |
| `codex_worktrees_windows-sid-validation` | `0e1e3f0` | 1 | `tests/conftest.py` |
| `codex_worktrees_security-ci-release-backlog` | `86c215b` | 1 | `task.md` — a working note, not code |
| `scratch_weekly-usage-budget-20261118` | `d930ee4` | 1 | **`AGENTS.md`** — and the owner has since made that file untracked on purpose. Salvage the text if it is wanted, but **do not restore it to tracking** |
| `codex_worktrees_search-text-race-safety_OmniAgent` | `2390568` | 428 | **5 real** — `sandbox.py`, `tools.py`, `README.md`, `tests/test_context_budget.py`, `tests/test_file_tools.py` — and **423 disposable artifacts** under `.scratch/publisher-acl-fix-20261115/`. See the finding below |

### The one that carries SEALED-OR-SECRET paths

**`codex_worktrees_search-text-race-safety_OmniAgent`.** 423 of its 428 files are
a nested `.scratch/publisher-acl-fix-20261115/.pytest-output-base/…` tree — one
worktree's pytest basetemps captured inside another worktree's snapshot.
**Hundreds of those paths end in `workspace/credentials`**, and others sit under
`docs/`, which `ANSWER_KEY` seals.

I have **not opened any of them**, and this document prints no content. By the
test names in the paths (`test_config_precedence_rejects…`,
`test_compound_route_fails_clos…`) they are the synthetic fixtures the sandbox
tests create precisely so that a refusal can be proved — not real secrets. **That
is an inference from path names, not a measurement**, and the right way to settle
it is for the SE to read a sample, not for anyone to push the ref and find out.

## The finding

**[MEDIUM] A snapshot ref carries hundreds of credential-named paths into a
repository whose remotes are both public.**

- **Location:** `refs/snapshots/20261122/codex_worktrees_search-text-race-safety_OmniAgent`,
  423 paths under `.scratch/publisher-acl-fix-20261115/.pytest-output-base/`.
- **Scenario:** (1) someone salvages that snapshot wholesale to a `salvage/*`
  branch; (2) the branch is pushed; (3) both remotes are public, so every
  `workspace/credentials` path is published, and a push cannot be taken back by
  deleting the branch. The actor is a hurried salvager, not an attacker, and the
  precondition is exactly the operation the owner has just approved for these
  trees.
- **Proof (MEASURED 2026-11-22):** `git diff --name-only <ref>^ <ref>` returns 428
  paths; `| grep -vc '^\.scratch/'` returns **5**; a path-only grep for
  `credential` matches hundreds under that prefix. No file was opened.
- **Remediation:** salvage **only the five real files** from this snapshot, by
  path, never the whole tree:
  `git checkout <ref> -- sandbox.py tools.py README.md tests/test_context_budget.py tests/test_file_tools.py`.
  The guard that should go red if this is ever done wrong is the repository's own
  secret scan (`.gitleaks.toml` exists in the `security-bootstrap` snapshot but
  is **not on the canonical line yet**) — which is itself an argument for
  salvaging that snapshot early.
- **Severity reasoning, honestly:** Medium and not High, because the paths are
  very probably synthetic test fixtures. If a sample read shows real material it
  is Critical and the ref must not leave this machine.

## `.scratch\se-ci`

It has **no snapshot** (the PM skipped it: SE 02 was writing there) and **the
directory no longer exists** — `ls` returns nothing, and it is not in
`git worktree list`. **Whether it held anything is UNKNOWN and now
unknowable from here.** *What would settle it:* SE 02 saying what it was, or a
reflog of the branch it carried if it had one. Nothing in this document depends
on it.

## What this document does not establish

- **That the 18 REAL WORK snapshots are worth keeping.** They are unique, which
  is a different question from valuable. Three of them
  (`brief16-proposed-tree`, its index twin, `brief16-operational-telemetry`) are
  three variants of one subject, and two pairs
  (`sec-search-001` ×2, `dataset-bounds` ×2) are duplicate attempts. Somebody has
  to choose; it is not the archivist's call.
- **That any of them still applies.** Several sit on parents (`3c76fd2`,
  `f37044d`, `2390568`) that are O-line or older, and the canonical line has
  moved. A salvage branch from them may not merge.
- **The contents of the 423 artifact paths.** Not opened, by design.
- **Anything about `.scratch\se-ci`.**
