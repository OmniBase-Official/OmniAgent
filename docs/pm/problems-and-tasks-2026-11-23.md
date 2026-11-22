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
