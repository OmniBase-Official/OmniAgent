# OmniAgent task register

**Read this first.** One file that records the work that is **done** and the work still **to do**, split by **AI and role**.
Every role has its own `#` heading, written as `Claude <role>` or `Codex <role>`, so you can find your section by name.
Every task has an ID (`C-PM-01`, `X-SWE-02`, ...): `C-` is Claude, `X-` is Codex.
(ไทย: ไฟล์นี้บันทึกงานที่ทำแล้วและงานที่ต้องทำ แยกตาม AI และบทบาท หาหัวข้อของบทบาทตัวเองแล้วทำเฉพาะงานของตัวเอง)

Last updated: **2026-11-23** by the Claude PM. Update the status of your own tasks when you finish one; the PM re-runs and confirms.

## State of the project (2026-11-23)

- **Canonical code line:** `origin/integration/canonical-20261122` = **`1384d63`** (1,085 passed, 2 skipped; the PM re-ran it). Owner ruling 1: `organization/main` (`5005039`) is the canonical line; O (`origin/main` `3c76fd2`) is kept as the tag `legacy/origin-main-2026-11-05`.
- **Both GitHub remotes are PUBLIC** (`mntoyg/OmniAgent` = `origin`, `OmniBase-Official/OmniAgent` = `organization`). Never push to either `main`. Name the remote on every push. Nothing sealed (`docs/` except your own result, `models/`, `questions/`, `data/`, `NEXT_CHAT.md`, evaluation scripts) and no secret goes into a push.
- **What the agent is:** a local-only ReAct agent (Ollama at a loopback IP literal), seven tools, read-only. It is **not** yet reliable: at temperature 0 it never reported the true file count in 40 runs (it answers "50" for 12, "278" for 302) and it invents tool names (`count_lines`).
- **Rulings:** `docs/pm/owner-rulings-2026-11-22.md` (rulings 1 to 25). **Problems and DoD:** `docs/pm/problems-and-tasks-2026-11-23.md`.
- **Budget (Rule 2):** the Claude weekly meter is per account and shared by every Claude chair. The owner's range for 2026-11-23 is **0% to 14%**; stop at 12%. Re-read the meter before each step.
- **Where to report (owner rule, 2026-11-23):** every Claude chair sends its **final report to the Claude PM chat** (`SendMessage` to `local_f53e8267-9dd0-4f3a-8abf-4e2a642ba10d`), as well as printing it in its own chat. Codex chairs report to the Codex second PM, who relays to the owner.
- **Definition of done (used by the PM):** branch pushed to `origin`; the three gates green with full paths (`.venv\Scripts\python.exe -m ruff check .`, `-m mypy`, `-m pytest`); every new test shown red under a mutation, file hashes equal before and after; the PM re-ran it in a throwaway tree with the module path inside that tree; the report sent; **nothing merged until the owner says so.**
- **Evidence labels:** MEASURED (you ran it), RECORDED (earlier, dated), REPORTED (someone else's claim, not re-run). A teammate's report is a claim until you re-run it.

---

# Claude PM

**Role:** sequence work, write briefs, verify every claim by re-running it, keep the rulings, track the budget. Writes no production code.

## Done
- C-PM-D1 Snapshotted and salvaged all uncommitted Codex work out of band; 14 dirty worktrees removed after each matched a snapshot byte for byte; 12 snapshot refs remain (ruling 3A, manifest `.scratch/snapshots-manifest-2026-11-22.md`).
- C-PM-D2 Switched the main checkout to the canonical line (ruling 11) and verified briefs 24 to 28, 30a, the record layer, the AIE passes and the SE merges (`b164aaa`, `1384d63`).
- C-PM-D3 Recorded owner rulings 1 to 25; ran the weekly pacing; found that the owner's pre-push hook loads `qwen2.5-coder:7b` on the shared GPU (lock file `.git/omniagent-eval.lock` stops it).

## To do
- C-PM-01 Re-verify SE 01's `se/brief-31-tool-text` and the AIE's tool-text measurement when they report; merge nothing without the owner.
- C-PM-02 Fast-forward the main checkout's local `integration/canonical-20261122` to `1384d63` (**owner's word needed**; it is still at `388fa53`).
- C-PM-03 Apply the SAE's replacement for the stale contract §2 paragraph (draft in `docs/architecture/contract-gaps-draft-amendments-2026-11-23.md`) after the owner approves.
- C-PM-04 Remove the clean Codex worktrees (**owner's word needed**); the empty leftover folders `.scratch/pm-verify-*` need the owner to delete them (the safety check blocks the PM).
- C-PM-05 Bring the open owner decisions to the owner, one at a time (list at the end of this file).

---

# Claude SAE

**Role:** solution architect: designs, contracts, ADRs, gate notes. Does not write production code.

## Done
- C-SAE-D1 ADR-0003 (two mains) and ADR-0005 (graph runtime blueprint); the assembly inventory and plan (briefs 18, 19, 23, 24).
- C-SAE-D2 Classified every dirty-tree snapshot (brief 26) and wrote the **securefs decision memo**: owner ruled **park** (ruling 22, `docs/architecture/securefs-decision-memo-2026-11-22.md`).
- C-SAE-D3 Gate notes: a disallowed-tool empty answer may exit non-zero without a contract change; tool output text needs no amendment, but a tail footer is cut by `cap_observation`, so put counts in the header. Draft MVP definition checklist (12 exist, 16 to be built, 2 partly). Draft contract/README amendments (not applied). Branch `sae/snapshot-classification-20261122` @ `3dbf784`.

## To do
- C-SAE-01 When the SE has proved `inspect_config_precedence` returns metadata only, finalise the contract §2 text that records it as a seventh approved tool (otherwise draft the removal).
- C-SAE-02 Refresh brief 24 phase 3 against `1384d63` after the PM finishes the worktree removal (small).
- C-SAE-03 Support the owner in editing and signing the MVP definition checklist (the owner decides; you draft).
- C-SAE-04 Write the securefs five-criteria check only if the owner reopens the question.
- C-SAE-05 Do not quote the old line "both READMEs still document localhost": it is wrong for the canonical line (still in ADR-0003 on `sae/adr-0003-carry-over`).

---

# Claude SE

**Role:** security engineer: guards, tests, CI gates, hardening. Verifies with mutation checks. Pushes only its own branches.

## Done
- C-SE-D1 Briefs 20, 21, 22: one test per gate-2 allowlist guard; three defaults and the endpoint out of messages; the endpoint corpus.
- C-SE-D2 Brief 25 (GitHub Actions security gates, on the Codex PR #10 branch); brief 27 (variant picks); brief 28 (preflight prints status only, bounded provenance readers, bounded export reader), merged at `b164aaa`.
- C-SE-D3 S1 (an empty answer exits non-zero with a fixed `[!] No answer:` line) and the run-record layer, merged at `1384d63`. `se/brief-29b-gitignore` @ `8071f93` (adds `.ai/`, `.scratch/`, `omniagent-core/` to `.gitignore`) is verified and **not merged**.

## To do (in order)
- C-SE-01 **Brief 31, tool text** (in progress, `se/brief-31-tool-text` from `1384d63`): `read_file` "too long" error carries the line count; `list_directory` carries a count **in the header line** (not a tail footer), counting only entries actually shown; bound the extension summary; keep the empty-directory string; do not touch the system prompt or guard G2e; grep every consumer of these outputs first. Tests and mutation per change.
- C-SE-02 Brief 29a, `scan_report_copy` (`docker cp` after the container exits cannot read a `--tmpfs` mount): cut from `e7eed11` (`organization/codex/security-ci-release-hardening-20261121`); choose a volume with an explicit size check over stdout (stdout would cut the 8 MiB cap to 256 KiB); needs Docker Desktop running; the GitHub-runner behaviour stays UNVERIFIED unless shown.
- C-SE-03 Prove by test that `inspect_config_precedence` returns configuration metadata only, or remove it from the registry, the allowlist and the agent route (the measured runs show the model calling it).
- C-SE-04 S3: review `scripts/eval_scoring.py` `judge()` for whole-output matching; counts only, quote no sealed expectation.
- C-SE-05 Mutation-check gates 3 to 5 on the canonical line.
- C-SE-06 The `claude -p` / `codex exec` feasibility spike for the hybrid profile: **spends the Claude meter, only on the owner's word.**

---

# Claude AIE

**Role:** AI/ML engineer: measurement, evaluation, datasets. One model run at a time on the 4 GB GPU; write the prediction first; create `.git/omniagent-eval.lock` before the first request and remove it after; raw outputs stay local.

## Done
- C-AIE-D1 First honest measurement (`3a79cd1`) and its grader fix (answer line only); second pass, 60 runs at temperature 0.1 (`c9a00ea`); the same 60 at temperature 0 (`dc0c78d`, prediction written first at `9c4a5ca`).
- C-AIE-D2 Findings, MEASURED and recounted by the PM: blank answer if and only if an unregistered tool was called (120 of 120); the model invents `count_lines`, `count_matches`; at temperature 0 the wrong answers are deterministic ("50" for 12, "278" for 302); file count never correct in 40 runs.
- C-AIE-D3 Ported brief 12's run-record layer onto the canonical line (merged at `1384d63`); holdout memo (`dc7967f`); tool-text prediction (`63fc1ae`) and `exit_code` per row (`6730573`).

## To do
- C-AIE-01 **Step 2 of tool text:** when the PM sends SE 01's SHA, run one temperature-0 pass (6 questions x 10) on that tip and compare per question with the `dc0c78d` result; q1 and q3 must stay 10/10. Control run at `1384d63` only if q1 or q3 moves (q5 reads the real clock; judge it apart).
- C-AIE-02 R1: read tree state per question, not once per `evaluate()`; R2: rule on bank question index 18 (scored on nothing).
- C-AIE-03 After the owner rules: whether the q2/q5 failures are a training-data gap, a tool-text gap or accepted (synthetic examples only, nothing automatic); a grounding and an abstention question in the contract task inventory with an oracle that does not read the real clock; the six questions as a standing check.
- C-AIE-04 `aiml/first-measurement-20261123` is **not merged** (owner decides).

---

# Codex second PM

**State:** Codex is **paused** (daily limit) and has not been consulted on this file. The tasks below are **proposed by the Claude PM** and are not accepted until the Codex second PM says so.

## Done
- X-PM2-D1 (record only) Codex produced the early briefs and the PR #10 branch `codex/security-ci-release-hardening-20261121`; its uncommitted work is preserved as `snapshot/codex-local-ai-delegate-20261122` on `origin`.

## To do
- X-PM2-01 Read this file, `docs/pm/owner-rulings-2026-11-22.md` and `docs/pm/codex-stop-and-snapshot-prompt.md`. The owner pastes that prompt to Codex; the PM has not.
- X-PM2-02 Reconcile with the Claude PM: the main checkout is now on `integration/canonical-20261122`; Codex's `chore/local-ai-delegate` is untouched at `af99092`. **Do not edit, test or switch branches in the main checkout.** Work under `D:\code-project\OmniAgent\.scratch\<role>-<topic>`.
- X-PM2-03 Decide with the owner which Codex branches still matter (30 clean Codex worktrees exist); do not delete a tree whose commits are on no remote.

---

# Codex SE

**State:** proposed, not yet accepted.

## Done
- X-SE-D1 (record only) Authored the PR #10 security gates workflows and the gitleaks helper that the Claude SE verified in brief 25.

## To do
- X-SE-01 On PR #10 (`e7eed11`): whether the Security gates job can go green on a GitHub runner (never run), and the "Update Coding Time" workflow (disable it or add the secret): **owner decision first**. Coordinate with Claude SE task C-SE-02, which owns the `scan_report_copy` fix; do not duplicate it.

---

# Codex AI/ML Engineer

**State:** proposed, not yet accepted. **Codex cannot reach localhost (WinError 10013), so it cannot run a model here.** Do not delegate to the Local AI and do not run measurements.

## Done
- X-AIML-D1 (record only) `aiml/brief15-evidence-grounding-20261105`: its `grounding-cohort/` tree is byte-identical on the canonical line.

## To do
- X-AIML-01 No task today. After the owner rules on the AIE's options (task inventory, bank, training data), draft documents only if asked.

---

# Codex SAE

**State:** proposed, not yet accepted.

## Done
- X-SAE-D1 (record only) None recorded after 2026-11-05.

## To do
- X-SAE-01 No task today. The Claude SAE holds the open design items (C-SAE-01 to C-SAE-05).

---

# Codex SWE

**State:** proposed, not yet accepted.

## Done
- X-SWE-D1 (record only) Produced the securefs branches (parked, ruling 22) and the Windows ACL / private-root work; none is merged.

## To do
- X-SWE-01 After the owner decides option A or B on the README: edit README line 3 ("~600 lines"; the six core modules are 4,107 lines) and the model claim for `omniagent-v2`; the owner confirms the last sentence about figures.
- X-SWE-02 Whether to salvage the Windows ACL / private-root work from the parked securefs branches is **open** (not blocked by the park); no work until the owner rules.

---

# Owner decisions still open

1. **Main checkout:** fast-forward the local `integration` branch to `1384d63` (PM, owner's word).
2. **`inspect_config_precedence`:** record as a seventh approved tool after the SE proves metadata-only (SE proves, SAE finalises, owner approves), or remove it (SE).
3. **Stale contract §2 paragraph:** apply the SAE's replacement now (PM) or later. **README:** both edits, or the line count only (Codex SWE).
4. **AIE options:** training-data vs tool-text gap; task inventory; bank question 18; merge `aiml/first-measurement-20261123`.
5. **Not merged, waiting for the owner:** `se/brief-29b-gitignore`, `aiml/first-measurement-20261123`.
6. **Remote that hosts the canonical line**, "Update Coding Time", sec-search chair (or delete both variants), the Codex message paste, clean Codex worktrees, the endpoint line printed on a healthy preflight (`main.py:200`).
7. **Graph runtime:** go-ahead for the hybrid spike (spends the Claude meter), ADR-0005 amendment, contract and egress policy.
