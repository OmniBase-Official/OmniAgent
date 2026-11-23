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
