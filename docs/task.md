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
- C-PM-D4 (2026-11-23) Verified and recorded: S1 and the record layer merge (`1384d63`), the AIE temperature-0 run (`dc0c78d`), SE 01's brief 31 part 1 (`1ce7c81`, gates 1,088 passed, mutations red, real `read_file` output shows the exact count); wrote this register; copied the Codex `AGENTS.md` into `docs/AGENTS.md` (local copy, original kept).
- C-PM-D5 (2026-11-23) Own mistakes, recorded: twice reported a chair as "started" when it was only waiting for the owner; wrote `C-SE-01` "in progress" wrongly (fixed).

## To do
- C-PM-01 Tomorrow: verify the AIE's q7 baseline and its runner flag (`aiml/tool-text-measure-20261123` @ `4b99b0c`, not verified today), then the full tool-text measurement at `1ce7c81`; merge nothing without the owner.
- C-PM-02 DONE 2026-11-24: the main checkout's local `integration/canonical-20261122` was fast-forwarded from `388fa53` to `1384d63` on the owner's word (clean, tree identical to the origin tip; gates in it: ruff clean, mypy 57 files, 1,085 passed, 2 skipped).
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

- C-SE-D4 (2026-11-23) **Brief 31 part 1** pushed: `se/brief-31-tool-text` @ `1ce7c81` (on `1384d63`): the `read_file` "too long" error carries the exact line count from the bounded `Workspace.describe` helper, and no count when it cannot be exact. PM-verified: gates 1,088 passed, mutations red (drop phrase 2 red, wrong count 2 red), hash `296506dc5cf6` restored. **Not merged.** Consumer list done: nothing parses the old shape; header-format constraint for part 2: `tests/test_file_tools.py:179,309` need `result.startswith(".:")`.

## To do (in order)
- C-SE-01 **Brief 31 part 2, `list_directory`: ON HOLD** (the PM wants part 1 measured alone first). When released: count **in the header line** `{shown}: N entries (...)` (colon directly after the name), counting only entries actually shown (a denied entry must not change the count), bound the extension summary, keep the empty-directory string, test the count survives the cap on a ~150-entry directory, mutation per change. Do not touch the system prompt or guard G2e. Known edge accepted for now: `describe` and `read_file`'s success path may count lone-CR files differently.
- C-SE-02 Brief 29a, `scan_report_copy` (`docker cp` after the container exits cannot read a `--tmpfs` mount): cut from `e7eed11` (`organization/codex/security-ci-release-hardening-20261121`); choose a volume with an explicit size check over stdout (stdout would cut the 8 MiB cap to 256 KiB); needs Docker Desktop running; the GitHub-runner behaviour stays UNVERIFIED unless shown.
- C-SE-03 DONE 2026-11-24 (`se/brief-32-config-tool-proof` @ `72b3be3`, both remotes, test-only, not merged; PM re-ran: ruff clean, mypy 58 files, 1,089 passed, 2 skipped, 1 xfailed; the strict xfail flips red under the bounding fix, hash `32ad1823d8af` restored): `inspect_config_precedence` is metadata-only (no execution, no environment, one file, report capped at 2,400 characters). **One Low finding:** its error path echoes the called name from the file (`config_inspection.py:393`), bounded only by the 16,000-character read cap. Owner decides: record it as a seventh approved tool (SAE finalises §2), fix the Low finding first (one line, SE), or remove the tool (SE; the AIE measures).
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

- C-AIE-D4 (2026-11-23) Lead on the model's wrong numbers: "10,306" is in 76 of 7,551 on-disk training/run examples, "278 line(s)" in 20, both in 11 (PM recounted); it is in the `tools.py:626-627` comment (commit `94dd12c`, 2026-10-01), absent from the model template, the runtime prompt and every observation of the AIE's runs. Plausible memorisation, **UNVERIFIED** (the weights' real corpus is not known).
- C-AIE-D5 (2026-11-23) Prepared the control question q7 ("How many lines does observability.py have?", 353 lines) on `aiml/tool-text-measure-20261123`: prediction `97faf15` (before any request), runner flag `--control-file` `4b99b0c`, tests; gates reported 1,096 passed. **Not verified by the PM.** The q7 baseline run at `b164aaa` was **in progress at 17:46** (lock file present).

## To do
- C-AIE-01 **Step 2 of tool text (slipped to tomorrow):** run the temperature-0 pass at `1ce7c81` (`read_file` change only): the six questions plus q7, 10 passes each, plus q7 at `b164aaa` if today's run did not finish; compare per question with `dc0c78d`. q1 and q3 must stay 10/10. q4 and q6 should NOT move (they depend on part 2). Control run at `1384d63` only if q1 or q3 moves (q5 reads the real clock). Read q2 against q7: if q7 is right and q2 still says "278", it is file-specific memorisation.
- C-AIE-00 DONE 2026-11-23 evening: the lock is gone and no run is in flight (PM confirmed; the q7 baseline finished).
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

---

# Update log (PM, 2026-11-23 evening)

- **C-SE-01 progress:** SE 01 finished step 1 (consumer list, nothing parses the old shape) and has not edited code. Stop line raised to 13%; ship `read_file` first, then the `list_directory` header. Ruling: never print an inexact line count (omit it, or "more than N lines" only if N is a proven lower bound).
- **Lead (MEASURED, cause UNVERIFIED):** the numbers the model answers for the line-count question (278 at temperature 0, 10,306 at 0.1) are in the comment at `tools.py:626-627` ("a 278-line file ... answered 10,306"). Possible source: the model learned them from that comment. **C-AIE-05** (new): count, without quoting anything sealed, whether `278` and `10,306` appear in the on-disk training and run data and in the model template.
- **C-PM-06** (new, low): `docs/demo-script.md` and `docs/video-script.md` quote the old `read_file` "too long" text; update them after brief 31 merges. Briefs under `docs/pm/` are history: accept the drift.
- **X-SWE-01** (addition): also update README line 13, which quotes the old `read_file` text, after brief 31 merges.

---

# Day close, 2026-11-23 (PM)

Weekly meter at close: **13%** against the owner's range of 0% to 14% for the day (reset by the owner; the weekly reset time is 2026-11-28 03:00 UTC). Tomorrow is day 4 (about 10:00 Thai); the general cumulative ceiling is then 56%.

## What was done today, and how far it is checked

| Item | Branch @ SHA | Status | Checked by |
| --- | --- | --- | --- |
| S1: an empty answer exits non-zero with a fixed `[!] No answer:` line | `se/brief-30a-empty-answer` @ `682caba` | **merged** into integration | PM re-ran (1,072 passed; mutation 6 red; 3 of 6 real-model runs exit 1) |
| Run-record layer ported to the canonical line | `aiml/record-layer-20261123` @ `5aba0c2` | **merged** into integration | PM re-ran (1,078; mutations red) |
| **Integration line** | `integration/canonical-20261122` @ **`1384d63`** | 1,085 passed, 2 skipped; fast-forward from `b164aaa`; `origin/main` `3c76fd2`, `organization/main` `5005039` untouched | PM re-ran in a throwaway tree |
| AIE first measurement, pass 2 (T=0.1) and the temperature-0 run (60 runs each) | `aiml/first-measurement-20261123` @ `dc0c78d` | pushed, **not merged** | PM re-ran gates and mutations, recounted the 60 raw files twice |
| SAE gate notes, securefs memo, contract/README drafts | `sae/snapshot-classification-20261122` @ `3dbf784` | pushed, docs only | PM verified the main claims in code |
| Brief 31 part 1: `read_file` error carries the exact line count | `se/brief-31-tool-text` @ `1ce7c81` | pushed, **not merged** | PM re-ran (1,088; mutations red; real output "(302 lines)") |
| AIE tool-text prediction, `exit_code` per row, q7 control question and runner flag | `aiml/tool-text-measure-20261123` @ `4b99b0c` | pushed, **not merged** | **NOT verified by the PM** (AIE-reported: 1,096 passed, 5 mutations red) |
| `.gitignore` entries | `se/brief-29b-gitignore` @ `8071f93` | pushed, **not merged** | PM verified the diff and the effect; gates not re-run |
| Ruling 3A: 14 dirty worktrees removed after a byte-for-byte snapshot match; 12 snapshot refs remain | n/a | done | PM |
| Securefs parked (ruling 22); owner rulings 1 to 25 recorded | `docs/pm/owner-rulings-2026-11-22.md` | done | PM |
| This register; `docs/AGENTS.md` copy (original in `~/.codex` kept) | `docs/task.md` | done | PM |

## What we learned today (MEASURED, with the evidence in `docs/pm/problems-and-tasks-2026-11-23.md`)
- The model answers confidently wrong on counting: file count never correct in 40 runs ("50" for 12), line count "278" for 302 at temperature 0, and it invents tool names (`count_lines`) in 15 of 60 runs; every run that called an unregistered tool ended with a blank answer (120 of 120), which S1 now reports and exits non-zero.
- At temperature 0 the failures are the same ten times in ten: they are not noise.
- The two wrong line-count figures are in a comment in `tools.py` and in 76 of 7,551 training examples: a likely source, not proven.
- Abstention: 4 of 10 valid at temperature 0.1, 2 of 10 at temperature 0.

## Left open at close
- **q7 baseline run at `b164aaa` was in flight** (lock file present, `omniagent-v2` loaded, 17:46): first thing tomorrow, confirm the lock is gone and read the result (`C-AIE-00`).
- Unmerged branches waiting for the owner: `se/brief-31-tool-text`, `aiml/first-measurement-20261123`, `aiml/tool-text-measure-20261123`, `se/brief-29b-gitignore`.
- The main checkout's local `integration` branch is still at `388fa53` (`C-PM-02`, owner's word).
- Three empty directories `.scratch/pm-verify-*` and four more created today (the safety check blocks the PM from deleting them): the owner can delete any empty `.scratch/pm-verify-*` folder.
- Codex has not been consulted: every Codex task here is a proposal.

## Plan for day 4 (PM proposal, not a ruling)
1. AIE: confirm no run in flight; run the tool-text pass at `1ce7c81` with q7; report; PM verifies.
2. Owner: decide on `inspect_config_precedence`, the §2 paragraph, the README, the four unmerged branches, the main checkout fast-forward.
3. SE: brief 31 part 2 (`list_directory`) only after the part 1 numbers are read; then 29a (Docker Desktop must be running) and `inspect_config_precedence`.
4. SAE: refresh brief 24 phase 3 after the PM's worktree work; MVP checklist with the owner.

## Addendum, 2026-11-23 evening (after the day close)

- **q7 baseline finished** (AIE-reported, PM re-counted the 10 rows): question "How many lines does observability.py have?" (true count 353) at `b164aaa`, temperature 0: **0 correct, 10 wrong, 0 blank**; "278" in **0** of 10; nine answered "12331 lines" after running to the 8-step budget (`read_file` > `list_directory` looped), one said it could not find the file. All rows carry temperature 0.0, commit `b164aaa`, clean tree. The lock file is gone (PM confirmed). Raw files are local and uncommitted (`.scratch/aie-first-measurement/data/first-measurement/q7-b164aaa/`).
- **What it adds (PM reading):** "278" does not appear for another file, so it looks tied to `config.py` (consistent with memorisation); but the model is wrong on this file too, with a different confident figure ("12331"), so memorisation of 278 is **not** the whole problem.
- **Tomorrow:** the q7 baseline is done; Step 2 needs only the new-tip runs (six questions plus q7 = 70 runs) at `1ce7c81`.

---

# Day 4 start, 2026-11-24 (PM)

## New standing rule: push every activity to BOTH remotes (owner, ruling 26)
Push your own work branch to `origin` (`mntoyg/OmniAgent`) **and** `organization` (`OmniBase-Official/OmniAgent`), naming the remote each time, and show both SHAs in your report (`git ls-remote` on each). "Main repo" means the remote `origin`, **not the `main` branch**: never push to either `main`, never force. A task is not done until both remotes hold the branch. Written as ADDENDUM 3 in `~/.claude/CLAUDE.md` and `~/.codex/AGENTS.md`; local copies in `docs/AGENTS.md`, `docs/CLAUDE.md`, `docs/CODEX.md` (git-ignored, never pushed). The PM backfilled 14 branches to `organization` today; all 14 have the same SHA on both remotes.

## Problems to do today, high to low, by kind
| # | Kind | Sev | Problem | Owner of the next step |
| --- | --- | --- | --- | --- |
| 1 | Quality (model) | High | Confident wrong counts (file count 0 of 40; line count "278" for 302; q7 "12331" for 353). Part 1 of the fix (`1ce7c81`) is **not yet measured** | Claude AIE (run the 70 runs at `1ce7c81`); PM verifies |
| 2 | Product | High | `list_directory` count header (part 2) | Claude SE, **after** the part 1 numbers are read (on hold) |
| 3 | Security / Contract | Medium | `inspect_config_precedence` is a seventh, unreviewed tool the model can call and does call | Claude SE (prove metadata only, a test), then SAE and the owner |
| 4 | Process | Medium | Five branches unmerged: `se/brief-31-tool-text`, `aiml/first-measurement-20261123`, `aiml/tool-text-measure-20261123`, `se/brief-29b-gitignore`, and the SAE docs | Owner decides; Claude SE merges; PM verifies |
| 5 | Docs / Contract | Medium | Contract §2 paragraph stale; README "~600 lines" and the `omniagent-v2` claim; README and demo scripts quote the old `read_file` text | PM (§2, after the owner's word); Codex SWE (README); PM (demo scripts, low) |
| 6 | Security / CI | Medium | `scan_report_copy` (29a) unfixed; Security gates job never green on a runner; "Update Coding Time" workflow | Claude SE (29a, needs Docker Desktop started by the owner); owner (workflow) |
| 7 | Instrument | Medium | Tree state read once per run; bank question index 18 scored on nothing; the q2/q5 gap, task inventory | Claude AIE (R1); owner rules R2 and the rest |
| 8 | Process | Low | Main checkout still at `388fa53`; clean Codex worktrees; empty `.scratch/pm-verify-*` folders; Codex not consulted | Owner's word (PM does the first two) |
| 9 | Process | Low | New push rule: check every report shows both SHAs | PM |

## Day 4 progress (PM)
- **C-SAE-02 done** (`sae/snapshot-classification-20261122` @ `acbda4b`, both remotes); the SAE then pushed its three other branches to `organization` and removed its own four clean worktrees (36 to 32 registered); PM re-checked the SHAs on both remotes and that the four paths are gone.
- **C-SE-03 done** (above). **Answer to the SE's question about the hook:** the pre-push hook reviews only commits that no remote-tracking ref already holds (`rev-list <sha> --not --remotes`). After the push to `origin`, the same commit is already known, so the push to `organization` prints "nothing new to review" and runs no gates. Gates ran on the first push; this is expected, not a fault.
- **Main checkout fast-forwarded** to `1384d63` (ruling 27); three screened origin-only branches (`snapshot/codex-local-ai-delegate-20261122`, its `-index`, `wip/salvage-search-text-race-safety-20261122`) pushed to `organization`; 17 branches now match on both remotes.
- **C-SE-04 done (read-only review of `judge()` in `scripts/eval_scoring.py`, no branch):** five findings, one Medium. `correct = question.expect in answer.replace(",", "")` is a plain substring test after deleting every comma, so "147", "1,470", "4,7", "not 47" and a range all score correct for an expectation of 47 (SE's synthetic probe; PM confirmed by reading the line). Affects `scripts/holdout_eval.py` and `scripts/session_eval.py`, **not** the AIE's `scripts/first_measurement.py` (its own whole-token grader on the answer region). Lows: the hedge check is whole-answer; `right_tool` is membership; a wrong verdict prints the expectation to the console (`(want ...)`). SE's slip: it echoed some real expectations into its own transcript (nothing committed or sent). **New tasks:** C-AIE-06 fix `judge()` (whole-number token, commas only inside thousands groups, several numbers = ambiguous, with a test table and mutations; **owner chooses whether to re-score old runs with both judges**); C-AIE-07 drop `(want ...)` from console marks (small). Neither blocks the tool-text comparison.
- **C-AIE-01 done: Step 2 at `1ce7c81`** (`aiml/tool-text-measure-20261123` @ `3caa8a0`, both remotes; PM recounted the 70 rows, temperature 0.0, clean, exit 60 and 10; lock gone). **Result (AIE-measured, PM recounted the row counts):** the exact line count in the `read_file` error did **not** change the answers: q2 0/10 (now "10,306" x10, was "278" x10), q7 control 0/10 ("12331" x10, an 8-step loop), q1 and q3 10/10 unchanged. q4 (was "50" x10) became blank x10 via the unregistered `count_matches` (exit 1); q6 (was blank x10) became "9" x10; q5 6 to 3 invented. **q4, q6, q5 moved although the diff cannot reach them: unexplained**, so the control at `1384d63` (70 runs) is the next measurement. PM decision: run it (A). Part 2 of brief 31 stays on hold until it is read. The AIE hands off at 68% context: a fresh AI/ML chair takes the control run as task 1.
- **New finding (PM, MEASURED 2026-11-24, Low/Medium hygiene): the canonical `.gitignore` (`1384d63`) lacks ruling 3's three rules** `/docs/pm/*-prompt.md`, `/AGENTS.md`, `/CLAUDE.md` (they exist only on the older O line), so a `git add -A` in a tree that holds a local handoff or instruction file would stage it for a public push. Mitigated on this machine by `.git/info/exclude` (shared by all worktrees; not in the repository). **New task C-SE-07:** add the three rules to `.gitignore` in the same change as `se/brief-29b-gitignore` (`8071f93`, which adds `.ai/`, `.scratch/`, `omniagent-core/`), with a test that `git check-ignore` matches them; mutation-check it.
- **PM handoff:** the PM's context reached 70%; the full opening prompt for the next PM chat is at `D:\code-project\OmniAgent\docs\pm\handoff-prompt.md` (local, git-ignored, never pushed).
- **C-SE-08 done locally (PM, 2026-11-24, owner ruling "A: SE fix then record" for `inspect_config_precedence`): brief 33** `se/brief-33-config-error-bound` @ `bbcbe21` (cut from `72b3be3`; **local only, not pushed** while the eval lock exists; SE pushes to both remotes when the PM says the lock is gone). The echoed name is cut at 200 characters with a `...(truncated)` marker and non-printable characters become `?`; the brief-32 strict xfail is now a real test, plus 9 new boundary tests. **PM re-ran (MEASURED, throwaway tree, since removed):** `agent.__file__` inside that tree; ruff clean; mypy 59 files; pytest 1,099 passed, 2 skipped; mutations (hash `5e70f0cfa474` before and after) raw echo 2 red, no sanitiser 1 red, cap 2000 4 red. Not tested: any model run; the pre-push hook; whether 200 is the right bound; which non-printable characters are legitimate. **Next:** SAE finalises contract §2 (seventh approved tool) after the push; owner approves; owner decides the merge.
- **C-AIE-01b done: control at `1384d63`** (AIE-reported; **PM recounted all 70 raw rows with an independent script**, `python -I`: 70 rows, commit `1384d63` and clean 70/70, temperature 0.0, exit 60 x 0 and 10 x 1; lock gone, verified; prediction commit `2e0dce7` is on `origin` and `organization`). Per question, baseline `b164aaa` | control `1384d63` | step 2 `1ce7c81`: **q1, q3** 10/10 at all three. **q2** "278" | "278" | "10,306", all 0/10 (true 302): the control reproduces the baseline, so the 278 to 10,306 shift belongs to the text change. **q4** "50" | blank x10 (`count_matches`, exit 1) | blank x10: control = `1ce7c81`, not the baseline. **q6** blank | "9" x10 | "9" x10 (true 12). **q7** "12331" | "does not exist" x10 (file exists) | "12331": a third pattern. **q5** 6 invented | 4 | 3. **Reading (PM, agrees with AIE):** q4 and q6 did not move because of SE's commit; the b164aaa baseline came from another server session, so it is **not a clean comparator** ("temperature 0" did not reproduce across sessions on this card). The clean pair is the adjacent one, `1384d63` vs `1ce7c81`: effect only on q2 and q7, and **neither became correct: 0 of 30** with the exact count in the error. Not verified: why sessions differ. **Consequence:** measure every later change against its own parent in the same session sequence (rule for Part 2 and any tool-text change).
- **C-SE-09 done: brief 34** `se/brief-34-line-count-routing` @ `45cbd0e` (one commit on `1384d63`, both remotes equal, PM `git ls-remote`; owner chose option ก "error text only": only the read_file too-long error's last sentence changed, now `For its size or line count, call file_info next (Action: file_info, Action Input: <that path>). Use search_text to locate relevant text.`; no description or system-prompt text changed). **PM re-ran (MEASURED, throwaway tree, removed):** `agent.__file__` inside it; ruff clean; mypy 58 files; pytest 1,090 passed, 2 skipped; mutations (tools.py hash `b36da0eca79e` before and after): path hard-coded 3 red; Action names `search_text` 3 red (hash `16ee564dffdf`, same as SE's); new sentence removed 3 red. **Note:** replacing only the prose "call file_info next" (leaving the `Action:` clause) stays green, so the test pins the actionable call, not the wording. **SE read-only findings (SE-reported, UNVERIFIED by PM):** file_info's description and read_file's description already tell the model to use file_info (three places in all), used 0 of 30; nothing in `inspect_config_precedence`'s description invites line counting. **Not measured:** whether the model uses the new call (AI/ML measures 45cbd0e vs 1384d63, interleaved, one session). **Open:** brief 31 and brief 34 edit the same return statement (SE: likely conflict; decide which survives before either merges). Local prompt for the fresh AI/ML chair: `docs/pm/aiml-measure-brief34-prompt.md` (never pushed).
- **C-AIE-08 done: brief 34 pair measured** (`aiml/brief34-measure-20261124`, prediction `15c89d4`, result `d227107`, both remotes equal, **not merged**; docs only, counts only). AIE 01 (the fresh AI/ML chair, session `local_ee5364bc-...`; the older chair is gone) ran 140 runs, one server session, arms alternated, T=0. **PM recounted all 140 raw rows with an independent script** (70 per arm; commit `1384d63` x70 / `45cbd0e` x70; tree_clean true; temperature 0.0; lock gone). **Result (MEASURED):** q2 (`config.py`, 302 lines): parent "278" x10, `file_info` 0/10; **child "302" x10, `file_info` 10/10, 3 steps**: the closing sentence of the read_file oversize error, `call file_info next (Action: file_info, Action Input: <path>)`, is what moved it. q1, q3, q4 (blank x10), q6 ("9" x10): identical between arms. q5: noise. **Corrections (PM re-checked in the raw files):** (1) **q7 never reached the oversize error** in any of the 50 q7 runs held (first call is always the malformed `observability.py 1`, "no such file"), so the earlier "0 of 30" rested on q2 alone and q7 says nothing about the text; (2) **"12331" is the byte size `list_directory` prints** (`observability.py (12331 bytes)`), a unit error on a real observation, not an invented number: this makes `list_directory` part 2 (brief 31) a motivated lever again; (3) q7 differs between arms (8-step loop vs "does not exist"), not caused by the text; the trees' root listings differ (stale `__pycache__/` in the parent), cause UNVERIFIED. **Established:** one file, one session, 10 runs per arm. **Not established:** another oversize file, another session, whether "278" is beaten or bypassed. The earlier conclusion "error text cannot fix line counts" is withdrawn for the copy-ready next-call form; the exact printed count alone did nothing.
- **Owner ruling 28 (2026-11-24, typed in the PM chat): "A: ship + second-file test"** for brief 34. **Done by the PM (MEASURED):** `integration/canonical-20261122` fast-forwarded `1384d63` to `45cbd0e` on `origin` and `organization` (no force, `git ls-remote` equal on both; `main` unchanged: origin `3c76fd2`, organization `5005039`). The main checkout's local `integration` branch is **not** moved (needs the owner's word). **Next:** AIE 01 second-file test (several oversize files, 1 to 2 passes per arm, parent `1384d63` vs child `45cbd0e`, one session; T=0 repeats are one observation, so spend runs on files, not passes); SE: brief 31 vs 34 conflict (same return statement) and `list_directory` part 2 wait for the result. Owner must type the weekly line (35%) in AIE 01's chat.
- **C-AIE-09 prepared, NOT RUN (AIE 01 stopped at the 25% weekly line, as ordered):** second-file test (`scripts/second_file_measurement.py`, prediction first) on `aiml/brief34-measure-20261124` @ `d2bd673` (both remotes equal; PM re-ran in a throwaway tree: ruff clean, mypy 57 files, pytest 1,102 passed, 2 skipped). **HIGH finding (AIE-reproduced, PM-verified fix): the first version of the AIE's new tests ran `git init`/`git config` under the pre-push hook's exported `GIT_DIR` and set `core.bare=true` in the SHARED `.git/config`** (about 07:20 to 07:27 Thai), so `git status` failed in every worktree for that window. Repaired by the AIE; PM MEASURED now: `core.bare=false`, `git status` works in the main checkout and here, config sha `e3b3e4743ec3` unchanged across my test runs. Fix on the branch: `clean_git_env()` strips `GIT_*`; the regression test `test_a_hooked_environment_does_not_redirect_git_to_another_repository` goes red when the scrub is removed (PM mutation: hash `815dce46354d` before and after, mutated `6fa5011f85cd`, 1 red, 5 green). **Neighbour check (PM, `git grep` at `45cbd0e` and the AIE branch):** no other test runs `git init` or `git config`; `holdout_eval`, `session_eval`, `publish_dataset`, `grounding_cohort` and `first_measurement._git` run read-only git with `-C`, which under the hook's `GIT_DIR` would read the hooked repository, not the named tree (wrong-answer risk, no write). The fix is on an unmerged branch, not on integration. New task **C-SE-10 (low)**: scrub `GIT_*` in those read-only helpers. Not measured: whether another chair was hit in the 07:20 to 07:27 window.

---

# Work of the day (WoD), 2026-11-24 (PM; owner asked to stop work and record it)

**Stopped:** every chair is idle (AIE 01, SE 01, SAE 01 `isRunning` false), no eval lock, no model loaded (`/api/ps` empty), shared `.git/config` `core.bare=false`. Weekly meter at stop: **25%** (the AIE's stop line; the owner had not typed a higher one in the AIE chat), 5-hour about 82%. Nothing half-committed in `pm-b16` (all pushed).

## Done today, and how far it is checked
| Item | Branch @ SHA | State | Checked by |
| --- | --- | --- | --- |
| Control run at `1384d63`, 70 rows | `aiml/tool-text-measure-20261123` (prediction `2e0dce7`) | pushed, docs/counts | PM recounted all 70 raw rows (independent script). The `b164aaa` baseline is **not a clean comparator** (T=0 does not reproduce across server sessions) |
| Brief 33: bound the name `inspect_config_precedence` echoes | `se/brief-33-config-error-bound` @ `bbcbe21` | pushed both remotes, **not merged** | PM re-ran (1,099 passed, 2 skipped; 3 own mutations red) |
| Brief 34: `read_file` oversize error ends with the exact next call (`file_info` + path) | `se/brief-34-line-count-routing` @ `45cbd0e` | **on the integration line** (owner ruling 28) | PM re-ran (1,090 passed, 2 skipped; 3 mutations red) |
| **Integration line** | `integration/canonical-20261122` @ **`45cbd0e`** | fast-forward from `1384d63` on `origin` and `organization`, no force; `main` untouched (`3c76fd2`, `5005039`); the main checkout's local branch **not** moved | PM `git ls-remote` on both |
| Brief 34 pair, 140 runs, one session | `aiml/brief34-measure-20261124` (prediction `15c89d4`, result `d227107`) | pushed, **not merged** | PM recounted all 140 raw rows; checked the q7 and "12331" claims in the raw files |
| Second-file test (prepared, **not run**) + GIT_DIR fix | same branch @ `d2bd673` | pushed, **not merged** | PM re-ran in a throwaway tree (1,102 passed, 2 skipped; scrub mutation 1 red) |
| Incident: AIE tests set `core.bare=true` in the shared `.git/config` (High) | n/a | repaired by the AIE, verified by the PM | PM: `core.bare=false`, config sha `e3b3e4743ec3` unchanged |
| Owner rulings 27 and 28; this register | `docs/task.md` on `pm/verify-brief16` | pushed both remotes | n/a |

## What we learned (MEASURED, with PM recounts)
- **The exact printed line count in the error did nothing; the copy-ready next call did:** q2 (`config.py`, 302 lines) went from "278" x10 (`file_info` 0/10) to "302" x10 (`file_info` 10/10), same session, interleaved. One file, one session.
- **q7 never tested the error text** (first call is always the malformed `observability.py 1`); "12331" is the **byte size** `list_directory` prints, a unit error, which makes `list_directory` part 2 a motivated lever.
- **"Temperature 0" is not reproducible across server sessions on this card;** compare only inside one interleaved session.
- **T=0 repeats are one observation:** spend runs on more files, not more passes.

## Left open at stop
- **Unmerged, all on both remotes:** `se/brief-31-tool-text` `1ce7c81` (conflicts with brief 34 on the same return statement; decide which survives), `se/brief-32-config-tool-proof` `72b3be3`, `se/brief-33-config-error-bound` `bbcbe21`, `se/brief-29b-gitignore` `8071f93`, `aiml/first-measurement-20261123` `dc0c78d`, `aiml/tool-text-measure-20261123`, `aiml/brief34-measure-20261124` `d2bd673`, `aiml/holdout-instrument-memo-20261122` `dc7967f`, `sae/snapshot-classification-20261122` `acbda4b`.
- **Waiting for the owner:** type the weekly stop line (35%) in the AIE 01 chat so the second-file test (40 runs, about 15 minutes of GPU) can run; seventh-tool §2 (SAE writes it now that brief 33 is pushed; owner approves); merge of brief 33; move the main checkout's local `integration` to `45cbd0e`; the other open decisions in the section above (remote that hosts the canonical line, README, `judge()`, `list_directory` part 2, sec-search chair, snapshot refs, 29a, graph-runtime ADR-0005, MVP checklist).
- **New low tasks:** C-SE-10 scrub `GIT_*` in the read-only git helpers (`holdout_eval`, `session_eval`, `publish_dataset`, `grounding_cohort`, `first_measurement._git`); empty folders `.scratch\pm-v34b` and eight `.scratch\pm-verify-*` the safety check stops the PM deleting (owner may delete).
- **Owner request after this WoD:** set up a DeepSeek harness (`@deepseek-ai/dsh`) in this project. **Not started**; the PM audited the repository and put a plan and the conflicts with the contract and rulings 5 to 7 to the owner (see the PM chat). Nothing installed, no files created for it.

## Resume list for tomorrow (day 4 starts about 10:00 Thai; PM, 2026-11-24)
- **Owner rulings today (typed in the PM chat):** DeepSeek Harness = **A: spike only** (permission to download `@deepseek-ai/dsh@0.2.2-rc.5` from npm into a throwaway tree under `.scratch`, nothing else), then **"wait for tomorrow"**. Nothing was installed or created for it. Brief 35 is ready as a local file (`docs/pm/dsh-spike-brief-prompt.md`, never pushed); SE 01 may only start after the owner types a higher weekly line in the SE 01 chat.
- **First things tomorrow:** read the meter (weekly was 25%, 5-hour 85%); owner types the weekly line in the AIE 01 and SE 01 chats (PM proposal 35%); AIE 01 runs the second-file test (prediction pushed, runs not started); SE 01 runs brief 35; SAE writes contract §2 for the seventh tool; decide brief 31 vs 34; move the main checkout's local `integration` to `45cbd0e` (owner's word); then the other open decisions.

---

# Day 5, 2026-11-25 (PM)

- **Owner instruction (typed in the PM chat): weekly pacing for this week and after.** From today (Wed 2026-11-25) to Friday 2026-11-27 the owner allows **25% of the weekly meter per day**; **after this week, the rule is 14% per day** (Rule 2's table). PM reading, to be corrected by the owner if wrong: 25 percentage points **added per day**, counted from the meter reading when the day starts, so today's ceiling is the reading at the start (26% at 07:00 Thai) plus 25, i.e. **51%**; Thursday adds 25 more, Friday 25 more; the weekly reset is Sat 2026-11-28 03:00 UTC. The owner's earlier line for the Claude chairs (25% cumulative, typed in each chair's own chat) stays until the owner types a new one in that chair's chat; a PM relay does not raise it. Chairs hold their own lines (AIE 01 and SE 01 stopped at 25%).
- **Owner standing rules 3 and 4 written** (code review standards; code style and conciseness, owner's text verbatim; one change: the example's unterminated code fence in rule 3 is closed so the Markdown renders; plus a PM-labelled note mapping BLOCKER/MAJOR/MINOR to Rule 1's Critical/High, Medium, Low, which the owner may strike). Written to **`AGENTS.md`, `CLAUDE.md`, `CODEX.md`, `CURSOR.md` in the repository root of the main checkout, local-only** (`.git/info/exclude`; owner ruling 3 and ADDENDUM 3: never pushed). All four files have the same hash and body (`751969a0efcc`; PM compared each to the source with `cmp`); `git check-ignore` matches all four; `git status` clean. **Not written:** `~/.claude/CLAUDE.md` and `~/.codex/AGENTS.md` (user-level, the owner's; the global files are what every chair reads in a worktree, because an ignored root file is not checked out into a `.scratch` tree). Sessions started with the main checkout as working directory load the root `CLAUDE.md` or `AGENTS.md`.
- **Owner clarification (2026-11-25, PM chat): the pacing schedule is for Claude only, not Codex or any other AI, and the 25% a day ends at the weekly reset (Sat 2026-11-28 03:00 UTC); from then Claude is back to Rule 2's 14% a day, every week.** Written as a "CLAUDE WEEKLY PACING SCHEDULE" section at the end of the four local files (`AGENTS.md`, `CLAUDE.md`, `CODEX.md`, `CURSOR.md` in the main checkout root; all four hash `49cbf0d434cd`; still git-excluded, `git status` clean). Codex's table in Rule 2 is untouched.
- **Owner request (2026-11-25, PM chat): assemble the AI instruction files at the repository root, delete the docs copies, delete three tracked docs files, delete `NEXT_CHAT.md` on `mntoyg/OmniAgent`.**
  - **Assembled (local-only, main checkout root):** `AGENTS.md` (copy of `~/.codex/AGENTS.md` + rules 3 and 4 + pacing), `CLAUDE.md` (copy of `~/.claude/CLAUDE.md` + the same), `CODEX.md` (the old docs extract + the same), `CURSOR.md` (rules + pacing; there was never a `docs/CURSOR.md`). PM checked each embedded copy and rules block is byte-identical to its source (Python `in` test), and that `docs/AGENTS.md` and `docs/CLAUDE.md` were byte-identical to the two global files. **Then deleted** the three docs copies (`docs/AGENTS.md`, `docs/CLAUDE.md`, `docs/CODEX.md`; local, ignored, content preserved at the root and in the globals). Note: section 1 of `AGENTS.md` and `CLAUDE.md` duplicates the global file the tool also loads in a session started from the main checkout, and will drift when the global file changes.
  - **Tracked deletions on a branch:** `pm/docs-cleanup-20261125` @ `146e2e7` (one commit on `45cbd0e`, both remotes equal): `docs/demo1.svg`, `docs/demo-script.md`, `docs/video-script.md` deleted. **Consequences fixed in the same commit (PM, MEASURED):** `README.md` lost the `<img src="docs/demo1.svg">` line and the paragraph about the cast (8 lines); `tests/test_notebook.py` lost two tests that read `docs/demo1.svg` (`test_the_demo_svg_is_safe_and_self_contained`, `test_the_demo_svg_shows_the_measured_answers`), their section header and two unused imports (ruff). Gates in the branch tree: ruff clean, mypy 58 files, pytest **1,088 passed, 2 skipped** (1,090 minus the two removed tests). **Left alone, for the owner:** `scripts/make_demo_svg.py` (would regenerate `docs/demo1.svg` if run) and prose that mentions the three files (`ADR-0003`, `repository-map.md`, `security-and-ethics.md`, `docs/pm/brief-19`). **Not merged:** the integration line stays at `45cbd0e` until the owner says to fast-forward it.
  - **`NEXT_CHAT.md` (PM finding, MEASURED):** it exists only on `origin/main` (`3c76fd2`); it is already absent on `organization/main` and on `integration/canonical-20261122`. On `origin/main` it is sealed material (`scripts/eval_workspace.py:58` lists it; `tests/test_eval_workspace.py:321` `test_every_sealed_source_path_exists` fails without it), so a plain delete commit on `main` would turn that test red and the pre-push hook would block it (never skipped). It has been public since 2026-10-11, so a deletion removes it from the tree only; the history keeps it unless the history is rewritten (destructive, force). **Not done; owner to choose the mechanism.**
- **Owner ruling 29 (2026-11-25, PM chat): "Yes, fast-forward"** the docs cleanup. **Done (MEASURED):** `integration/canonical-20261122` fast-forwarded `45cbd0e` to `146e2e7` on `origin` and `organization` (no force; `git ls-remote` equal on both; `main` unchanged: origin `3c76fd2`, organization `5005039`). The main checkout's local `integration` branch is still not moved. **Open:** `NEXT_CHAT.md` on `origin/main` (mechanism to choose; see above).
- **Owner choice for `NEXT_CHAT.md` (2026-11-25): "B: delete on main", then "A: branch only, 40%"** (typed in the SE 01 chat by the owner). **C-SE-11 steps 1 to 4 done: brief 36** `se/brief-36-next-chat-removal` @ `d05c206` (one commit on `origin/main` `3c76fd2`; both remotes equal; `origin/main` unchanged at `3c76fd2`, **not pushed to main**). `NEXT_CHAT.md` deleted (1,158 lines); `NEXT_CHAT.md` stays in `ANSWER_KEY` and is added to `optional_artifacts` in `test_every_sealed_source_path_exists`; a new test `test_a_local_copy_of_the_removed_journal_stays_unreadable`. **PM re-ran (MEASURED, throwaway tree, since removed):** `agent.__file__` inside it; ruff clean; mypy 48 files; pytest 792 passed; mutations (hashes `7249f9293f04` and `ea183ebddf13` before and after): name not optional **red 1** ("a sealed path is not there: ['NEXT_CHAT.md']", same hash `fe959e62c0df` as SE's); name **removed from `ANSWER_KEY` red 1** ("DID NOT RAISE SandboxError", hash `e148a9152e22`): removing the name would unseal a stray local copy. My first attempt at the second mutation did not apply (CRLF); caught by the assert and redone with a regex. **Step 5 (fast-forward `origin/main` to `d05c206`) is NOT done:** needs the owner's own words in the SE 01 chat naming the exception to ADDENDUM 3 item 2. Plainly: the file leaves the tree and the folder view only; the history keeps it (public since 2026-10-11); rewriting history is not requested. **Not checked:** branch protection on `origin/main`; how the integration line (file already absent there) would merge this test change; about 30 docs files (about 70 lines) still mention the file (`docs/pm/handoff-prompt.md:28`, `docs/pm/pm2-codex-prompt.md:46`, `docs/architecture/repository-map.md:37` list it as an entry point): accept or update (PM for `docs/pm`, SAE for `docs/architecture`). Leftover empty folder the safety check stops the PM removing: `.scratch\pm-v36` (owner may delete).
- **Owner ruling 30 (2026-11-25, typed in the PM chat, answering the PM's question "push the NEXT_CHAT.md deletion to origin/main now?"): "yes delete it, and mark it in each AI markdown file: don't make this file again no matter what".** **Done by the PM (MEASURED):** `origin/main` fast-forwarded `3c76fd2` to `d05c206` (the SE's verified brief-36 commit; non-force; origin only; the owner's word in the PM chat is the named exception to ADDENDUM 3 item 2 for this one push). `git ls-remote origin refs/heads/main` = `d05c206`; the root of `origin/main` has no `NEXT_CHAT.md`; `organization/main` unchanged at `5005039` (it never had the file). The hook printed "gates NOT run" because the pushed commit was not HEAD; the same commit's gates (ruff, mypy 48 files, pytest 792) had run on the branch push by the SE and passed, and the PM re-ran them. **Marked:** a "NEVER CREATE NEXT_CHAT.md" section at the end of the four local files (`AGENTS.md`, `CLAUDE.md`, `CODEX.md`, `CURSOR.md`, main checkout root; the same 8-line block, `tail` hashes equal): every spelling, every role, no exception except the owner typing in that AI's own chat. **Not marked:** the user-level `~/.claude/CLAUDE.md` and `~/.codex/AGENTS.md` (the owner's; those are what chairs in `.scratch` trees read). **Offered, not done (needs the owner):** a `.gitignore` line and a test that fail if `NEXT_CHAT.md` reappears, and the same rule in the owner's global files and git-hook directory. **History still holds the file** (public since 2026-10-11).
- **C-SE-12 done: brief 37** `se/brief-37-no-next-chat` @ `7c916d1` (two commits on `146e2e7`, both remotes equal, not merged; integration still `146e2e7`): commit 1 `48a19a4` = two `.gitignore` patterns (bracket classes) + `tests/test_no_next_chat.py` (44 tests, names only); commit 2 `7c916d1` = integration `ANSWER_KEY` gets `NEXT_CHAT.md` plus `optional_artifacts` and the stays-unreadable test (**the integration line did not seal the name; a stray local copy would be readable by the agent**: SE-measured, PM read the integration file). **PM re-ran (MEASURED, throwaway tree, since removed):** `agent.__file__` inside it; ruff clean; mypy 59 files; pytest 1,133 passed, 2 skipped; mutations (hashes before and after equal): normalisation weakened red 11, `.gitignore` lines removed red 12 (SE: 12). **PM-found gaps (MEASURED, `is_forbidden`):** the guard normalises case, `-` and `_` only; **not caught: `next chat.md` (space), `NEXT.CHAT.md` (dot), `next_chat.markdown`, `NEXT_CHAT` (no extension), a trailing space, `NEXT_CHAT.md.txt`**; the `.gitignore` also misses two separators in a row. **Stray copies (PM scan of worktree roots):** `NEXT_CHAT.md` was tracked in `.scratch/pm-b16` (the PM branch descends from `3c76fd2`) and sits in two old trees `.scratch/brief11-stage2-review-20261031-96c6a68a` and `.scratch/brief11-staged-rebuild-20261031` (old Codex trees, owner decision on the clean-worktree list). **PM fixed its own branch:** merged `origin/main` (`d05c206`) into `pm/verify-brief16`, so the file is gone from the PM tree and the branch tip (gates: ruff clean, mypy 48 files, pytest 799 passed). SE note: it echoed a fragment of the sealed answer sentence into its own transcript while grepping an import line (not committed or sent). **Open:** integration fast-forward to `7c916d1` (owner), the gap fix (SE, small), the old trees.
- **C-SE-13 done: brief 38** (third commit on `se/brief-37-no-next-chat`) @ `b860ead` (both remotes equal; integration still `146e2e7`; origin main `d05c206`; not merged). The guard now peels note-like (md markdown mdx txt text rst) and backup (bak old orig tmp copy) suffixes from the right, then compares the stem after NFKC, casefold and removal of every non-alphanumeric character with `nextchat`; `.gitignore` carries 20 generated best-effort patterns (cannot express two separators in a row, fullwidth or zero-width forms, or the bare name; the last on purpose, because a bare pattern would also ignore a directory of that name). **PM re-ran (MEASURED, throwaway tree, since removed):** `agent.__file__` inside it; ruff clean; mypy 59 files; pytest **1,217 passed, 2 skipped**. **PM probes of `is_forbidden`, all as expected:** RTL-override suffix, no-break space, zero-width space, `.MD.bak.txt`, `.orig` all caught; `NEXT_CHATS.md`, `next.md`, `README.md`, `next_chat.md.1`, `*.swp` and a Cyrillic-lookalike spelling not caught (the lookalike is the known limit; `.swp` was my own call). **PM mutations (hashes `32a92ed26b22` and `0cae17394235` before and after, equal to SE's):** all 20 `.gitignore` patterns removed red 31; rule reduced to `rest.lower() == 'next_chat'` red 21. **SE-reported:** one transient `remote rejected (Internal Server Error)` from GitHub on the first push to both remotes after the hook passed; one retry, no hook skip, no force, both succeeded; the survived mutation Mv6 led SE to add three tests. SE context is at 72%; it will hand the chair off (a fresh SE chair needs the owner to paste its prompt). **Open:** fast-forward integration `146e2e7` to `b860ead` (owner), the same protection on `origin/main` (owner), homoglyph defence (low), `.scratch\se-brief37` and `.scratch\pm-v38`.

---

# Proof of work (PoW), 2026-11-25 (PM; Thai calendar day from 07:00, when the date rolled; owner asked what is left)

Each row names its evidence. Evidence labels: MEASURED = the PM ran it; RECORDED = a chair's earlier run the PM re-ran when noted; REPORTED = a chair's claim not re-run. All SHAs below read from `git ls-remote` at 2026-11-25 16:45 Thai.

| # | Work | Evidence (both remotes unless noted) | State |
| --- | --- | --- | --- |
| 1 | Owner rules 3 and 4, Claude-only pacing (25% a day to Fri, 14% from the Sat reset), "never create NEXT_CHAT.md": written into the four root AI files | local-only (git-excluded, never pushed); `git check-ignore` matches all four; `git status` clean; memory notes `weekly-pacing-nov-2026`, `never-create-next-chat-md` | done |
| 2 | Docs cleanup: `docs/demo1.svg`, `demo-script.md`, `video-script.md` removed, README image and two SVG tests removed | `146e2e7` = `integration/canonical-20261122` on origin and organization (fast-forward, no force); MEASURED ruff clean, mypy 58 files, 1,088 passed, 2 skipped | **on the integration line** |
| 3 | `NEXT_CHAT.md` removed from `origin/main` (kept sealed in `ANSWER_KEY`, new stays-unreadable test) | `origin/main` = `d05c206` (fast-forward of `3c76fd2`); `organization/main` unchanged `5005039`; branch `se/brief-36-next-chat-removal` `d05c206` on both; MEASURED 792 passed, mutations red (not optional: "a sealed path is not there"; removed from `ANSWER_KEY`: "DID NOT RAISE SandboxError") | **done on main** |
| 4 | Guards so the file cannot return: 20 `.gitignore` patterns, a 120-odd-test rule (NFKC, casefold, punctuation stripped, note and backup suffixes), integration `ANSWER_KEY` seal | `se/brief-37-no-next-chat` = `b860ead` on both (three commits on `146e2e7`); MEASURED ruff clean, mypy 59 files, **1,217 passed, 2 skipped**; mutations (hashes `32a92ed26b22`, `0cae17394235` before and after) all 20 patterns removed red 31, rule weakened red 21 | pushed, **not on integration** |
| 5 | PM branch freed of `NEXT_CHAT.md` (merged `origin/main`) | `pm/verify-brief16` = `ce323a6`; MEASURED 799 passed | done |
| 6 | Register: rulings 27 to 30, brief 33 to 38 verification entries, WoD of 11-24, resume list, this PoW | `docs/task.md` on `pm/verify-brief16` | done |
| 7 | Fresh SE 01 chair started (old chair handed off at 72% context); reads the register and waits for a stop line | its transcript (28 messages, no work started) | waiting on the owner |

## Left to do, in the order of value (chair; what it needs)
1. **Fast-forward integration `146e2e7` to `b860ead`** (guards + `ANSWER_KEY` seal): PM does it on the owner's word.
2. **Second-file test** (does the brief-34 next-call text work on other oversize files; 40 runs, about 15 minutes of GPU, prediction already pushed): AIE 01; needs the owner to type a weekly line in the AIE 01 chat (its line is 25%).
3. **Stop lines and the meaning of "25% a day"** for the fresh SE 01 and the others: owner types in each chat; PM reading is "+25 points a day counted from the reading at the start of the day" (day 5 started 10:00 Thai; ceiling about 56%; used 32% at 16:45).
4. **Seventh tool record:** merge brief 33 (`bbcbe21`, owner's word), SAE 01 writes contract §2, owner approves.
5. **Merge queue and the brief 31 vs 34 conflict** (same return statement): decide which survives; `list_directory` part 2 is motivated again by "12331 = bytes".
6. **Main checkout's local `integration` is still at `1384d63`** (remote `146e2e7`, soon `b860ead`): owner's word to move.
7. **DeepSeek harness spike** (brief 35, local file ready): SE 01; needs a stop line; spends no Claude meter beyond the chair.
8. **Stale docs:** about 30 files still mention `NEXT_CHAT.md`; ADR-0003, `repository-map.md`, `security-and-ethics.md` still mention the three deleted docs files (PM for `docs/pm`, SAE for `docs/architecture`).
9. **Owner-only:** the "never create NEXT_CHAT.md" rule in `~/.claude/CLAUDE.md` and `~/.codex/AGENTS.md`; the same guards on `origin/main`; delete the empty folders `.scratch\pm-v34b`, `pm-v36`, `pm-v37`, `pm-v38` and eight `pm-verify-*` (the safety check stops the PM); the many `brief16-*` and `op7-*` scratch folders, 36 registered worktrees, the 14 Codex worktrees and the Temp one.
10. **Smaller:** C-SE-10 scrub `GIT_*` in read-only git helpers; 29a `scan_report_copy` (needs Docker Desktop started); `judge()` fix and "(want ...)" removal (AIE); README line-count and `omniagent-v2` claims (Codex, paused); which remote hosts the canonical line; homoglyph defence for the guard (low).
