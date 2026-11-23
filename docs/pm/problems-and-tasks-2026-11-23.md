# Problems to fix, high to low, and the task breakdown (PM, 2026-11-23)

Written after the PM read the AI/ML engineer's two documents and re-ran part of the first measurement. Canonical line: `b164aaa`
(`origin/integration/canonical-20261122`, 1,065 passed, 2 skipped). Evidence labels: MEASURED = the PM ran it today.

## What the AI/ML engineer delivered (checked by the PM)

- `aiml/first-measurement-20261123` @ `3a79cd1`: `docs/pm/measurement-2026-11-23-first-honest-run.md`, marked **partial**. Five new
  non-sealed questions at `b164aaa` with `omniagent-v2:latest`: 3 of 4 checkable correct, 1 wrong (counted 50 `.py` files where the tree has 12),
  1 valid abstention. **Expected values re-checked by the PM against the tree: 12 `.py` files in `scripts/`, `config.py` is 302 lines (MEASURED).**
  Its own grader first said 4 of 4 because the expectation `12` matched `127.0.0.1` in the startup banner: a real High finding, honestly reported.
- `aiml/holdout-instrument-memo-20261122` @ `dc7967f`: memo that brief 12's run-record layer is gone from the canonical line. **Re-checked:
  `question_record`, `_tree_clean`, `_append_question_record` are absent at `b164aaa` and present on the legacy tag (MEASURED).**
- **Gap in the delivery:** the branch holds only the document. The runner script and the raw outputs are **not committed anywhere the PM can
  find**, so the first measurement cannot be re-run from the branch. The PM could not use the AIE's exact question wording.

## The PM's own re-run (MEASURED, five runs, `b164aaa`, `omniagent-v2:latest`, `--verbose`, GPU idle, one run at a time)

Question (PM's wording): "How many .py files are directly inside the scripts directory?" All five runs behaved identically:
1. step 1: `list_directory scripts` returned the correct 12-file listing;
2. step 2: the model called **`count_lines`**, a tool that is not in the registry: `Error: tool is not allowed for this task.`;
3. the turn ended; the CLI printed an **empty `OmniAgent:` line and exited 0**. No answer, no message, no failure signal.

Cause in code: `agent.py:883-884` (`if step.action not in self.allowed_tools: return ""`, pinned by test G2e, which asserts `answer == ""`);
`main.py:230` prints whatever came back and returns 0. This is a different failure from the AIE's (a wrong number, 50): both are on
counting questions, and the AIE's run and mine used different wording, so they do not contradict each other.

## Problems, highest effect first

| # | Sev | Problem | Evidence | Today? |
| --- | --- | --- | --- | --- |
| 1 | **High** (product) | The user gets an **empty answer with exit code 0** whenever the model asks for a tool that does not exist. Silent failure on the main path | MEASURED 5/5 by the PM | **Yes** (SE) |
| 2 | **High** (quality) | The fine-tuned model **invents tools** (`count_lines`) or gives a confident wrong count (50 for 12). Counting is unreliable in two different ways | MEASURED (PM 5 runs; AIE 1 run) | **Yes, diagnosis only** (AIE) |
| 3 | **High** (instrument) | The first measurement is **not reproducible** (runner and raw output uncommitted) and the canonical line has **no run-record layer**, so every measurement is unaudited | MEASURED (branch contents; function absence) | **Partly**: commit the runner now; the record-layer port waits for the owner (AIE) |
| 4 | Medium | **Grader defect:** a substring expectation graded the whole output including the banner (`12` is inside `127.0.0.1`). Whether `eval_scoring.judge()` or the old bank has the same carrier is unchecked | AIE reproduced; PM confirmed the substring fact, not the live code | Queued, no model needed (SE) |
| 5 | Medium | **Contract vs product:** `inspect_config_precedence` is offered as a seventh `--tool` while the contract names six; `localhost` wording in contract §2 versus the owner's loopback-literal ruling; the README claims a model (`omniagent-v2`) a reader cannot pull; README still says "~600 lines" | SAE checklist (REPORTED, not re-run by the PM) | **Yes, as a state check and draft text** (SAE) |
| 6 | Medium | **CI gate defect `scan_report_copy` (brief 29a)** unfixed; whether the Security gates job can go green on a runner is unknown. SE 01 has produced **no commit**: its tree `.scratch/se-brief29a` is clean at the base `e7eed11` | MEASURED (tree state) | If room (SE) |
| 7 | Low | Endpoint printed on a healthy preflight (`main.py:200`): owner's reading of the contract | owner | owner decision |
| 8 | Low | A built wheel is UNVERIFIED (no `setuptools`/`wheel` here; the wheel test skips) | MEASURED skip | one CI run with `-rs` |
| 9 | Open | Owner/PM housekeeping: 29b not merged into integration; clean Codex worktrees; sec-search chair; remote of the canonical line; "Update Coding Time"; paste the Codex message | rulings | owner / PM |

## Task breakdown

**Budget:** owner allowance 46% to 56% weekly, shared by every chair and the PM. The PM read about 51% before this assignment. Chairs stop at
**55%** (hard 56%); re-read the meter before each step. Each chair needs the owner to confirm the allowance **in its own session** if its Rule 2 reading
requires it. Rank order is the order to work in; stop when the meter says stop.

### SE 01
- **S1 (problem 1, High).** Branch `se/brief-30a-empty-answer` cut from `b164aaa`. In `main.answer` (and the REPL path if it prints the same way), when the
  result is empty or whitespace: print a one-line message (`[!] No answer: ...` without echoing model text), return a **non-zero** exit code. **Do not change
  `agent.run()` or the G2e test.** Add tests: a fake model that asks for a disallowed tool, through `main.answer`: exit code non-zero, message present,
  no model text echoed. **Mutation-check** (remove the check; the test must go red; hashes before and after). Three gates with full paths; print `__file__`.
- **S2 (problem 6).** Resume 29a as briefed: cut from `e7eed11`, stdout capture, separate fix commit, mutation check. Only if the meter allows after S1.
- **S3 (problem 4), queued.** Review `scripts/eval_scoring.py` `judge()` for whole-output matching. Report the count of short expectations only; do not quote any sealed expectation.
- Do not merge anything into the integration line; the PM verifies first.

### SAE 01
- **A1 (gate for S1).** A five-line note: does the MVP contract or an ADR say anything about an empty answer, the exit code, or a disallowed tool, and is the
  CLI-level message above allowed. If not, say what to amend. Doc only.
- **A2 (problem 5).** State of three items **exactly as on `b164aaa`**: (a) `inspect_config_precedence` as a seventh `--tool` versus the contract's six;
  (b) the `localhost` wording in contract §2 against the owner's loopback-literal ruling and `docs/pm/proposed-contract-amendment-endpoint-2026-11-22.md`;
  (c) the README model claim and the "~600 lines" statement. Draft amendment text for each, **not applied**, for the owner to approve. Doc only.

### AIE 01
- **I1 (problem 3, partly).** Commit the measurement runner and the raw outputs of the first pass to `aiml/first-measurement-20261123` (non-sealed only), so it can be re-run.
  Fix the grader to read the answer line only, with the q4 output as the regression case; mutation-check it.
- **I2 (problem 2).** Second pass with `--verbose`: the same five questions plus the PM's wording above, ten runs of the counting question inside the set.
  Report per run: tool names, step count, final answer or blank. **Also find where `count_lines` comes from**: does the training data teach an action name that is not in the
  tool registry? Report counts only; no sealed content. One model run at a time; the GPU was idle at the PM's last check.
- **I3, waits for the owner.** The memo's option A (port the record layer onto the canonical line). Not started until the owner answers.

### PM
- Verify each report by re-running it; merge nothing without the owner; track the meter; keep the owner decisions list (problem 7, 9) and ask only what is theirs.

## PM verification of the SE 01 and AIE 01 results, 2026-11-23 (MEASURED, re-run by the PM in throwaway trees; `__file__` inside each)

Weekly meter was reset by the owner: today's allowance is 0% to 14% (day-1 rule); the PM read 2% weekly.

| Task | Definition of done (from the breakdown) | Result |
| --- | --- | --- |
| **SE 01 S1** `se/brief-30a-empty-answer` `682caba` | branch pushed; `main.answer` prints `[!] No answer:` and exits non-zero; no model text, no tool name echoed; `agent.run()` and G2e unchanged; test through `main.answer`; mutation red with hashes; three gates | **Met.** ruff clean, mypy 56 files, **1,072 passed, 2 skipped** (1,065 + 7). Canonical `main.py` restored (`69007bd3d19e`; the SE's file `486daf4c0ff2`, equal before and after): **6 red, 1 passed**; G2e **14 passed**. Message is a fixed sentence by category. The REPL calls `answer()`, so it is covered. **Real model (6 runs, `omniagent-v2:latest`):** 3 runs exit **1** with `[!] No answer: the model asked for a tool that is not allowed for this task.`; the other 3 exit 0 |
| **SE 01 S2** (29a) | | **Not done.** No commit; `.scratch/se-brief29a` clean at `e7eed11` |
| **AIE I1** `aiml/first-measurement-20261123` `6dece93` | runner and raw outputs committed; grader reads the answer line only; mutation-checked | **Partly met.** Runner and 7 tests committed; gates **1,072 passed, 2 skipped**. Raw outputs are not committed (they hold model replies under gitignored `data/`; kept locally). **Gap (Medium, reproduced):** replacing `answer = answer_region(blob)` with `answer = blob` in `main()` leaves **7 passed**, so the wiring that fixes the High finding is not pinned by any test: the tests exercise `grade()` and `answer_region()` directly. Hashes: runner `9c38154ca987` before and after |
| **AIE I2 part 1** where `count_lines` comes from | counts only, no sealed content | **Met, partly re-run.** 0 tracked files mention it at `b164aaa` and on the legacy tag; the registry has 7 entries (PM). The on-disk training-data and model-template counts were **not** re-run by the PM (REPORTED). Conclusion "the model's prior, by elimination" is the AIE's and is **not proven** |
| **AIE I2 part 2** `--verbose` pass | ten runs, tools, steps | **Not run.** The AIE saw another chair's `qwen2.5-coder:7b` on the GPU and stopped, as the one-run rule requires. No partial result |
| **AIE I3** `aiml/record-layer-20261123` `5aba0c2` | record layer ported; clean-tree test mutation-checked; new baseline stated; no fixture or data files; `RUNS_PATH` separated | **Met.** ruling-23 scope; three gates **1,078 passed, 2 skipped** (1,065 + 13); `RUNS_PATH` is `data/holdout-runs.jsonl`, `session_eval.py` keeps `data/session-runs.jsonl`. Mutations on `holdout_eval.py` (`1a843b4196ff`, equal before and after): `_tree_clean` always true **1 red**; report keeps every record (filter 1) **1 red**; filter 2 **3 red**. The result document states the baseline and its denominator |

**Product finding from the PM's six real-model runs on the SE's branch (same counting question, tree truth 12):** answers 10, 10, 9, 10 (wrong, exit 0) and three refusals. **No run gave 12.**
With the AIE's earlier 50, the agent has not yet counted the files correctly in any measured run (PM 11 runs: 0 correct). The silent-blank defect is fixed; the confident wrong number is not.
Not merged anywhere; nothing deleted. Leftover empty directories `pm-verify-fm`, `pm-verify-rl`, `pm-verify-s1` under `.scratch/` (their worktrees are unregistered; the automatic safety check blocked the PM's `rmdir`).

## PM verification of the AIE's second pass, 2026-11-23 (MEASURED, throwaway tree at `c9a00ea`, `__file__` inside it)

Branch `aiml/first-measurement-20261123` @ `c9a00ea`: `docs/pm/measurement-2026-11-23-second-pass.md`, 60 recorded runs (6 questions x 10 passes) at `b164aaa`,
`omniagent-v2:latest`, temperature 0.1 (the AIE states this is **not** the contract's temperature-0 baseline).

| Claim | PM result |
| --- | --- |
| Three gates | **Confirmed.** ruff clean, mypy 56 files, **1,079 passed, 2 skipped** (1,065 + 14) |
| Mutation, hashes (pristine runner `81f0213b7519`, equal before and after) | **Confirmed.** `main()` grades the whole output: **2 red** (the PM's own mutation, the gap I reported earlier, is now pinned). Answer region ignores the stderr marker (the defect found in this pass): **3 red** |
| 15 of 60 runs blank, and exactly the 15 that called an unregistered tool | **Confirmed by an independent recount** of the 60 raw output files with the fixed function: blank q4 7, q5 1, q6 7 (15); unregistered tool q4 7, q5 1, q6 7 (15); blank if and only if unregistered tool in **60 of 60** |
| Default temperature is 0.1; 0.0 sits only under a profile | **Confirmed.** `config.py:65` `default=0.1`; `omniagent.toml` has `temperature = 0.0` under the profile |
| "10,748 lines" is a character count | **Confirmed.** `config.py` is **10,748 bytes** and **302 lines** at `b164aaa`. The origin of "10,306" is unexplained (the AIE says so too) |
| The pass ran on `dd13605`, before the separator fix; `blank` in `runs.jsonl` is wrong for the 15 blank rows | Accepted as reported; the AIE recomputed the counts from the raw files and the PM's recount agrees. The rows themselves were not rewritten |
| Lock file created and removed | **Confirmed absent** after the run (`.git/omniagent-eval.lock`). The first five minutes of the run were not covered (AIE says so) |

Not re-run by the PM: the per-question correct counts (q2 1 of 10, q3 and q1 10 of 10), the abstention classification (a reading, not an oracle), the GPU watcher log, the tool-error counts.
The AIE's findings stand as reported, evidence MEASURED by the AIE and partly re-measured by the PM: the model invents tool names (15 of 60), counts files wrongly (0 of 20), counts lines wrongly (9 of 10), and does not reliably abstain (4 of 10).

## Definition-of-done check and problem register, 2026-11-23 evening (PM; every row re-run by the PM unless marked REPORTED)

**DoD used for every task:** branch pushed to `origin`; three gates green with full paths; each new test shown red under a mutation with file hashes
equal before and after; PM re-ran it in a throwaway tree with the module path inside that tree; the final report sent to the PM chat; **nothing merged
until the owner says so.** No chair pushed anything after 07:22 Thai; all chairs are idle.

| Task | Branch @ SHA | DoD |
| --- | --- | --- |
| SE 01 S1 empty answer | `se/brief-30a-empty-answer` @ `682caba` | **Met** (1,072 passed; 6 red under mutation, G2e 14 green; 3 of 6 real-model runs exit 1 with the fixed line). Report reached the PM only through the branch, not a message |
| SE 01 S2 (29a) | none | **Not met.** No commit; tree clean at `e7eed11`; no report |
| SE 01 S3 (`judge()` review) | none | **Not started** (queued by design) |
| SE (earlier chat) 29b `.gitignore` | `se/brief-29b-gitignore` @ `8071f93` | **Met** (diff verified by the PM; full gates not re-run by the PM) |
| SAE A1 gate note, A2 drafts | `sae/snapshot-classification-20261122` @ `1861191` | **Met.** Claims verified by the PM (seven registry entries, allowlist, contract paragraph, 4,107 lines) |
| AIE I1 runner and grader | `aiml/first-measurement-20261123` @ `c9a00ea` | **Met.** 1,079 passed; `main()` grading pinned (2 red); separator defect pinned (3 red) |
| AIE I2 pass 1-2 | same branch | **Met.** Independent recount of 60 raw files: 15 blank = 15 unregistered-tool runs, 60 of 60. Not at temperature 0 |
| AIE I3 record layer | `aiml/record-layer-20261123` @ `5aba0c2` | **Met.** 1,078 passed; 3 mutations red (1, 1, 3). `_tree_clean()` has one call site (read once per `evaluate()`): the AIE's Medium finding **confirmed** |
| PM: dirty worktrees (ruling 3A) | n/a | **Met** (14 removed after a byte-for-byte snapshot match; 3 empty leftover directories the safety check will not let the PM delete) |
| PM: merges | n/a | **Waiting** on the owner: S1, record layer, 29b, AIE measurement branch |

### Problems, high to low, by kind

| # | Kind | Sev | Problem | State |
| --- | --- | --- | --- | --- |
| 1 | **Quality (model)** | High | Confident wrong answers: file count 0 of 20, line count 1 of 10, a made-up share price in 4 of 10 | open; needs the owner's ruling (tool text, training data, or accept) |
| 2 | **Product** | High | The model invents tool names; the turn then ended with an empty answer and exit 0 (15 of 60 runs) | fix exists on `se/brief-30a-empty-answer`, **not merged** |
| 3 | **Product / Quality** | Medium | After a refused tool the model is not told what it may call; `read_file`'s "too long" error sends it to the wrong tool (9 of 10 miscounts, 3 report characters as lines) | open (AIE option B; changes tool text and prompt) |
| 4 | **Security / Contract** | Medium | `inspect_config_precedence` is a seventh tool in the model-callable allowlist; the contract names six; no security review; the measured runs show the model calling it | open (SE proves metadata-only, or remove) |
| 5 | **Instrument** | Medium | No measurement exists at temperature 0 (the contract baseline); both passes ran at 0.1 | open (AIE option A, about 15 minutes of model time) |
| 6 | **Instrument** | Medium | The record layer reads tree state once per run, not per question; it has never recorded a real model run; bank question index 18 scored on nothing (AIE reading, not re-verified by the PM) | open (AIE R1, R2) |
| 7 | **Security / CI** | Medium | `scan_report_copy` defect (29a) unfixed; the helper is not on canonical; the Security gates job has never run green on a runner | open (SE 01, no result) |
| 8 | **Docs / Contract** | Medium | Contract section 2 still says the default is `localhost` and that loopback is not enforced; README says "~600 lines" against 4,107; README names a model a reader cannot pull | open (drafts exist, awaiting the owner) |
| 9 | **Process** | Medium | Nothing is merged: S1, the record layer, 29b and the AIE branch sit beside the integration line `b164aaa` and will drift | waiting on the owner |
| 10 | **Quality (model)** | Medium | Abstention: 4 of 10 valid | open (with problem 1) |
| 11 | **Product** | Low | The endpoint prints on a healthy preflight (`main.py:200`): the owner's reading of the contract | owner |
| 12 | **Security / Process** | Low | The owner's pre-push hook loads `qwen2.5-coder:7b` on the shared GPU on every chair's push, colliding with a measurement unless `.git/omniagent-eval.lock` exists | documented; chairs told |
| 13 | **Security** | Low | A built wheel is UNVERIFIED (no `setuptools`/`wheel` here; the wheel test skips) | one CI run with `-rs` |
| 14 | **Docs** | Low | ADR-0003 on the carry-over branch still carries the SAE's wrong "both READMEs document localhost" sentence | do not quote it |
| 15 | **Process** | Low | Worktree hygiene: 3 empty leftover directories; the clean Codex trees; seven nested trees found already gone before the PM started (unknown cause) | owner word needed |

## PM verification of the AIE's temperature-0 run, 2026-11-23 (MEASURED, throwaway tree at `dc0c78d`, `__file__` inside it)

Branch `aiml/first-measurement-20261123` @ `dc0c78d` (prediction `9c4a5ca` 16:13:46, pass-through `d5d0b22`, result `dc0c78d` 16:33:46): the 60 runs of pass 2 repeated at temperature 0, same commit
(`b164aaa`), model, questions.

| Claim | PM result |
| --- | --- |
| Prediction and lock came before the first request | **Confirmed.** Lock created 16:13:27, prediction committed 16:13:46, first run file 16:17:59 |
| Gates | **Confirmed.** ruff clean, mypy 56 files, **1,082 passed, 2 skipped**; runner hash `7b167cd43554` equals the AIE's |
| Mutations (hash restored to `7b167cd43554` each time) | **Confirmed.** flag never passed: 1 red; row hard-codes 0.0: 1 red; the other two (wrong value, field dropped) not re-run |
| 60 rows carry temperature 0.0, commit `b164aaa`, clean tree | **Confirmed** from `runs.jsonl` |
| The recorded `blank` field now agrees with the raw files | **Confirmed**: all 60 rows matched to a raw file, 0 disagree (it was wrong in 15 rows in pass 2) |
| blank if and only if an unregistered tool was called | **Confirmed by independent recount, 60 of 60** (10 runs, all q6 `count_lines`) |
| One tool sequence per question at temperature 0 (except q5) | **Confirmed.** q1 `calculate`; q2 `read_file > read_file > inspect_config_precedence`; q3 `read_file`; q4 `list_directory > search_text > calculate`; q6 `list_directory > count_lines`; q5 four sequences |
| Answers | **Confirmed.** q1 identical; q2 "278" in 10 of 10 (never the true 302); q4 "50" in 10 of 10 (true 12); q6 blank in 10 of 10; q3 identical |

Not re-run by the PM: the q5 classification (a reading; q5 reads the real clock), the GPU watcher log, the per-row seconds, the two other mutations.

**What this adds (PM reading, MEASURED by the AIE and recounted by the PM):**
at temperature 0 the failures are not noise, they are **deterministic**: the same wrong answer, ten times. The model has not reported the true file count in any of 40 runs (two wordings, two temperatures); line count 0 of 10;
q2's wrong figure (278) and q4's (50) match nothing the PM could find. The model also called `inspect_config_precedence` (the unreviewed seventh tool) in every q2 run. The AIE's prediction was wrong on q4 and q5 (both stated surprises) and the AIE left it unedited: correct practice.
A single temperature-0 pass of these six questions is now a usable regression test for any fix.
