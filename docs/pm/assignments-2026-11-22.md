# Assignments, 2026-11-22 evening (PM, on the owner's word: "assign the work to SAE 01, AIE 01, SE 01")

State at issue time (MEASURED by the PM): canonical line `origin/integration/canonical-20261122` = `b164aaa` (1,065 passed, 2 skipped);
12 snapshot refs left; both remotes public; `origin/main` `3c76fd2` and `organization/main` `5005039` untouched.

## Budget rule for every chair (Rule 2)

Claude weekly meter is per account and shared. The PM read **36%** with today's (day 2) ceiling at **40%** (owner ruling 8): about 4 points
for everyone until day 3 begins (about 10:00 Thai on 2026-11-23, ceiling 42%). So **today only the first item of each chair is in scope**; the rest
is queued for day 3. Re-read the meter yourself before starting; at the ceiling finish only the atomic step, leave a clean state, report, stop.

## Who does what

| Chair | Today (small, doc-only or one fix) | Queued for day 3 |
| --- | --- | --- |
| **SAE** (`OmniAgent SAE 01`) | 1. A one-page **securefs decision memo** for the owner (read-only, from refs): what the four branches carry, the three unpublished files kept only in local ref `13c7bfb`, criteria 1-5 pass/fail as far as it can be read, options adopt / reject / park. 2. A **draft MVP definition** checklist: measurable, each line tied to a gate, test or measurement that exists. | Re-check brief 24 phase 3 against `b164aaa`, run it only if still valid. |
| **SE** (`SE: pick one variant per subject`, the chat that holds briefs 27 and 28) | 1. Fix the brief 25 defect `scan_report_copy` (`docker cp` after the container exits cannot read a `--tmpfs` mount): pick stdout or a volume, justify, mutation-check. 2. `.gitignore`: add `.ai/`, `.scratch/`, `omniagent-core/`. | Mutation-check of gates 3-5 on the canonical line. The `claude -p` / `codex exec` feasibility spike **spends the Claude meter**: only on the owner's word. |
| **AIE** (`OmniAgent AIE 01`) | 1. **First honest measurement**: run the agent (`main.py --ask`) at `b164aaa` with the local model on a short fixed set of **non-sealed** questions; record outcome, steps, tool errors, time. One model run at a time, GPU checked free first. 2. A memo on the **holdout instrument and question bank**: where they are, what porting to the canonical line needs, a recommendation. No run. | The holdout session, only after the owner rules on the bank. |
| **PM** | Remove the 18 dirty worktrees (owner ruling 3A) after re-checking each snapshot; verify every chair's report by re-running it. | The 30 clean worktrees need a separate owner word. |

## Owner only (nobody else may decide)

1. Which remote hosts the canonical line, then the branch surgery.
2. The securefs ruling (after the SAE memo).
3. "Update Coding Time": disable the workflow or add the secret. Brief 25 options 8A-E.
4. Whether `main.py:200` (the endpoint printed on a healthy preflight) must be hidden.
5. The sec-search chair, or delete both variants as history.
6. Fast-forward the main checkout to `b164aaa` (it is still at `388fa53`); paste `docs/pm/codex-stop-and-snapshot-prompt.md` to Codex.
7. Graph runtime: the go-ahead for the hybrid spike, the ADR-0005 amendment, the contract and egress policy.

## Rules that apply to every item

Both remotes are public: push only your own document or fix branch to `origin`, remote named, never to either `main`. No sealed path
(`docs/` except your own result document, `models/`, `questions/`, `data/`, `NEXT_CHAT.md`, evaluation scripts) and no secret in a push or
a delegation. Work only under `D:\code-project\OmniAgent\.scratch\<role>-<topic>`. Delete no ref, no worktree. Verification is yours: a test
counts only after you saw it go red with the guard removed. End every report with `QA:` and `Budget:` lines.
