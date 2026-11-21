# Release Readiness Backlog

Scope: single-user local CLI. Shared publisher destinations and multi-user service use remain unsupported.

## Completed verification

- [x] Checked open PRs #1, #5, #8, and #9 and recorded their current draft/open states.
- [x] Verified PR checks on exact heads: #5 (`835c208a48edbcab75f7e404dbb89b8393923433`), #8 (`0257794e8ff0a2b05976b510b2b838cfc48b02ba`), and #9 (`a2852d1ef15b91c5556cae9dc18f1fb0304c0daf`) all have successful Ubuntu and Windows checks.
- [x] Verified there are no formal GitHub review submissions on PRs #1, #5, #8, or #9.
- [x] Audited `main` CI: it runs Ruff, mypy, and pytest, but has no security-gate workflow, no wheel-install smoke test, and uses version-tagged GitHub Actions.

## Remaining work

### P1 conditional: publisher isolation

- [ ] Obtain a Windows runner with a policy-compliant private root and distinct test identities.
- [ ] Verify publisher ACL, cross-SID access, race/collision, and failure behavior on one exact snapshot; do not weaken fail-closed policy.
- [ ] Keep shared destinations and concurrent untrusted writers unsupported until SE signs off on evidence.

### P2: CI and supply-chain hardening

- [x] Add secret scanning and dependency vulnerability auditing to the local candidate: full-history Gitleaks image pinned by digest and pip-audit pinned to 2.10.1.
- [x] Pin checkout/setup-python to verified full commit SHAs and set checkout credentials not to persist.
- [x] Add a non-editable wheel build/install/import smoke test to Ubuntu CI.
- [x] Replace deprecated `project.license` table metadata and require setuptools 77+ for PEP 639 support in the candidate.
- [ ] Run the new hosted security jobs and wheel smoke test on the exact candidate; local `pip-audit`, mypy, and wheel build tools are unavailable.
- [ ] Have an independent SE review the exact resulting snapshot. Claude cross-review could not run because its 5-hour usage limit was reached.
- [ ] Re-run Ubuntu and Windows gates and have SE review the exact resulting commit/tree.

### P2: PR disposition

- [x] Reviewed PR #1: it is stale/non-mergeable and includes `NEXT_CHAT.md`, `questions/bank-2026-10-10.txt`, and numerous `docs/pm` handoff files; decision is to close it to prevent accidental merge.
- [ ] Close PR #1 through a GitHub account with write access; the connected integration returned HTTP 403 `Resource not accessible by integration`.
- [ ] Review PR #5 diff and decide whether it is ready for non-draft review; CI passes but no formal review exists.
- [ ] Review PR #8 diff and decide whether it is ready for non-draft review; its task deadline is cooperative, not a hard cutoff.
- [ ] Review PR #9 diff and decide whether it is ready for non-draft review; CI passes, but Windows cross-SID/ACL is not covered.

### P3: CI maintenance

- [x] Replace deprecated `project.license` table metadata and raise the build requirement to setuptools 77+ before the setuptools deadline reported in run #54.
- [x] Update checkout/setup-python to Node.js 24 action releases in the candidate; hosted confirmation remains pending.

## Latest evidence

- PR #5 hosted run: [#29](https://github.com/OmniBase-Official/OmniAgent/actions/runs/43848556227) — Ubuntu and Windows passed.
- PR #8 hosted run: [#52](https://github.com/OmniBase-Official/OmniAgent/actions/runs/44871570264) — Ubuntu and Windows passed.
- PR #9 hosted run: [#54](https://github.com/OmniBase-Official/OmniAgent/actions/runs/44875968332) — Ubuntu: 888 passed, 9 skipped; Windows: 896 passed, 1 skipped. Both passed.
- PR #9 CI warnings: GitHub Actions Node.js 20 deprecation and setuptools deprecation for table-form `project.license`.
- Candidate branch: `codex/security-ci-release-hardening-20261121`, based on `5005039144d18da45b646347b62d9753baae94f7`.
- Candidate files: `.github/workflows/ci.yml`, `.github/workflows/security-gate.yml`, `pyproject.toml`, and this `task.md`.
- Local candidate checks: pytest 860 passed, 2 skipped; Ruff passed; workflow YAML and embedded Bash syntax passed; TOML parsing and `git diff --check` passed. Mypy is unavailable; wheel build and vulnerability scanning remain hosted-only.
- No commit or push was made. The candidate has not received an independent SE review or hosted CI result.

No PR was merged or closed as part of this audit. PR #1 remains open because the connected GitHub integration rejected the close request with HTTP 403.
