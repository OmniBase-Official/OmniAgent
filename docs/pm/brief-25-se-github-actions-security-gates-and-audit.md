# Brief 25 — the failing Security gates workflow, and an audit of every workflow

**For the security engineer (SE). Issued 2026-11-22 by the PM.** Codex has hit its
daily limit and is paused, so this is picked up by a Claude chair. **Today's weekly
ceiling is 40%, by the owner's explicit instruction** (it read 27% when this was
written; the meter is per account, shared by every Claude chair). Stop at 39%.

No model run; nothing here contacts a model server. **GitHub is read-only for you:
read logs, read PRs, read files. You do not write to GitHub.**

## What is failing (MEASURED by the PM, 2026-11-22, `gh run list` / `gh run view --log-failed`)

| Where | Workflow | State | Cause as far as the log says |
| --- | --- | --- | --- |
| `OmniBase-Official/OmniAgent` PR **#10** (draft) `codex/security-ci-release-hardening-20261121`, "Validation: harden CI and add wheel smoke checks" | **Security gates** | red on every run since 03:39Z; run `44991088728` is the latest | job **"Gitleaks / synthetic report contract"**: it runs `python .github/scripts/gitleaks_report.py contract .github/scripts/gitleaks-report.tmpl .github/scripts/gitleaks-report-mutant.tmpl`; the script prints `security scan failed stage=scan_commit_summary` and exits 1 |
| the same PR | **CI** | green on the last two runs (one earlier run was red, `44981619700`) | not analysed |
| **both** repos, `main` | **Update Coding Time** (waka-readme) | red every day since at least 2026-11-16 | `Invalid inputs ... Environment variables are misconfigured`: no usable `WAKATIME_API_KEY` secret. **Report it, do not change it:** supplying a secret or removing the workflow is the owner's decision |

PR #10 is **Codex's work in progress**, and **Codex's local checkout also holds an
untracked `.github/workflows/security-gate.yml`, `.semgrep.yml` and
`tests/security/semgrep/`** (the PM has not read them; they are not available to
you). Do not assume the PR head and that file agree.

## What you do

1. **Find the cause of the `scan_commit_summary` failure.** Read the PR head
   without checking out Codex's branch for editing:
   `git fetch organization` then `git worktree add` **inside the path** (below) at
   `organization/codex/security-ci-release-hardening-20261121`. Read
   `.github/workflows/*.yml`, `.github/scripts/gitleaks_report.py` and its templates.
   **Reproduce it locally** if the script is OS-agnostic (it runs on `ubuntu`; WSL
   exists but **nothing may be installed on the owner's machine**, so say plainly
   what you could not run). The script has a *mutant template*: it is a contract
   test that a deliberately broken report is rejected. Say whether the failure is
   the script, the templates, the workflow's invocation, or the scanned history
   (e.g. what `scan_commit_summary` reads from a shallow checkout).
2. **Fix it on your own branch,** based on the PR head, **named
   `claude/se-ci-fix-pr10`** (or similar), pushed to `origin` with the remote named.
   **Do not push to Codex's branch, do not push to either `main`, do not open,
   edit, comment on or close any PR, and do not trigger workflows** (`gh workflow
   run`, `gh api -X POST` and the like). The PM decides how it reaches GitHub.
3. **Mutation-check the fix.** The point of a "contract" step is that it can fail:
   break the property it guards (restore from a saved copy; hashes before and
   after) and show the step goes red. A security gate that cannot go red is the
   failure this project keeps finding (brief 20: three of five gate-2 guards could
   be deleted with the suite green).
4. **Audit every workflow** on the PR head **and** on G (`organization/main`,
   `5005039`) in the Rule 1 finding format (severity, location, scenario, a
   reproduction or an explicit UNVERIFIED, remediation). Check at least: actions
   **pinned to full commit SHAs** (tags can be moved); **`permissions:` least
   privilege** at workflow and job level; **runner pinned** (`ubuntu-24.04`, not
   `ubuntu-latest`; the Windows runner version); **install is not editable**
   (`pip install -e` hides a broken wheel: ADR-0002); `pull_request_target` or
   untrusted input in `run:` (script injection through `${{ github.event.* }}`,
   branch names, PR titles); `actions/checkout` with `persist-credentials`;
   secrets echoed to logs; third-party actions and downloaded binaries (the
   gitleaks binary: how is it fetched and verified?); and whether a failing job
   would actually block a merge (required checks) or only paint a PR red.
5. **Say what the workflows do NOT cover** relative to the six gates of the
   contract (§5), in one table. The repository's own gates are ruff, mypy and
   pytest; say whether CI runs the same three and on which platforms.

## Do not touch

The main checkout `D:\code-project\OmniAgent` (Codex's 54 uncommitted changes live
there: do not read, write, switch branches in or test it), `agent.py` and the other
production modules, the waka-readme workflow (report only), and any other branch.

## Where to work (the owner's location rule)

**Only under `D:\code-project\OmniAgent`:** `git worktree add
D:\code-project\OmniAgent\.scratch\se-ci <commit>`. No sibling folder, nothing on
another drive. Remove the worktree when you are done, after pushing.
**Run `python -c "import agent; print(agent.__file__)"` from your worktree and
confirm it prints a path inside it** (the venv's editable install points at the
main checkout).

## Gates

Full path, never your own `-q`: `.venv\Scripts\python.exe -m ruff check .`,
`-m mypy`, `-m pytest` on your branch. The repository's pre-push hook runs them.

## Standing rules (`~/.claude/CLAUDE.md`)

Rule 1: reproduce before you report, label every figure MEASURED / RECORDED /
REPORTED, end with `QA:`. **Rule 2 with the owner's override: stop at 39% weekly.**
End with `Budget:`.

## Done when

- the cause of the red job stated and **reproduced** (or marked UNVERIFIED with what
  would settle it);
- a fix branch pushed, gates green, and the mutation table;
- the workflow audit and the gate-coverage table;
- one message to the PM with the owner's open decisions as lettered options, each
  ending by naming the chair that would carry it out.

## The one thing that would make this wrong

**Making the job green by weakening it.** A red "contract" step may be telling the
truth (the report format really is wrong, or the history scan really finds
something). Fix the cause; never relax the check, widen an allow-list or skip the
step to turn the PR green.
