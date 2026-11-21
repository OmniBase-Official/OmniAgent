# ADR-0003: the two `main`s — what is on each, measured

- **Status: Proposed, 2026-11-21.** This document measures. **The owner decides
  which line is canonical.** Nothing here merges, ports or recommends a push.
- **Deliverable of brief 18** (`docs/pm/brief-18-sae-the-two-mains-overlap.md`,
  issued after the owner chose option C: measure first, merge nothing).

## Pinned refs — confirmed before any number below

Both remotes fetched 2026-11-21, then re-read:

| Name | Ref | Commit | What it is |
| --- | --- | --- | --- |
| base | merge-base | `85d137d` | 2026-10-12, the last commit both lines share |
| **O** | `origin/main` (`mntoyg/OmniAgent`) | `3c76fd2` | 98 commits past base |
| **G** | `organization/main` (`OmniBase-Official/OmniAgent`) | `5005039` | 23 commits past base, 3 of them not bot commits |

All three **MEASURED 2026-11-21** and identical to the brief's. Every figure
below is labelled **MEASURED** (I produced it, dated), **RECORDED** (an earlier
dated figure) or **REPORTED** (someone else's claim, not re-derived).

**Where the measuring happened:** two throwaway worktrees detached at `3c76fd2`
and `5005039`, outside the repository, plus this branch. **The main checkout
`D:\code-project\OmniAgent` was not read, written or tested** — it is dirty and
Codex is in it.

**The venv trap, checked per worktree.** From each worktree,
`python -c "import sandbox, agent"` printed paths **inside that worktree**, not
the editable install's target. Both trees were returned to a clean
`git status` after every cross-run, and each tree's own suite was re-run
afterwards to prove the restore (MEASURED).

## The answer in one paragraph

**The two lines are redundant, complementary and contradictory at once — the
proportions differ by file, and no single label fits.** Where they overlap they
overlap almost completely: 89% of what O added to the trial-record module
exists verbatim on G, and both sides independently produced an endpoint
validator with **eleven identically-named symbols**. Where they do not overlap
they are disjoint rather than opposed: O's walk optimisation and G's hard-link
guard touch `sandbox.py` with **0%** shared text in either direction. And one
thing is a genuine regression on the canonical remote: **the hard-link
workspace escape PR #3 fixes is reachable on O today, through four of the six
tools.** The decision the owner faces is not "which side is better" but "which
side's *history* do we keep", because the newest work has already voted:
**9 of the 18 `origin/codex/*` branches are built on G's history, not O's.**

## 1. Per PR: what it is for, and where it stands on O

G's non-bot history is exactly three squashed PRs. A squashed PR carries intent
only as far as its message and tests do; **everything about motive below is
inferred and marked so.**

### The cross-run matrix — the single most useful table here

Each tree's `tests/` replaced wholesale by the other's, with
`--continue-on-collection-errors`, then restored and re-verified (MEASURED
2026-11-21):

| tests ↓ / tree → | **O** `3c76fd2` | **G** `5005039` |
| --- | --- | --- |
| **O's tests** | **791 passed** | 39 failed, 496 passed, **34 errors** |
| **G's tests** | 85 failed, 511 passed, 2 skipped, **7 collection errors** | **860 passed**, 2 skipped |

O's own 791 matches the RECORDED figure of 2026-11-05 exactly, which is why I
trust the harness.

**Neither side's tests survive on the other tree.** The collection errors are
the sharp end: a test that cannot import has found a *missing interface*, not a
failing behaviour, and the import errors name precisely what each line built
that the other never had.

**G's tests cannot import, on O** (7, MEASURED):

| missing on O | what it is |
| --- | --- |
| `tools.FIXED_INTERNAL_CAPABILITY_ALLOWLIST` | the tool allowlist — **contract gate 2** |
| `agent.validate_openai_client_endpoint` | G's endpoint check (O has its own, differently named) |
| `sandbox.workspace_scope` | G replaced the module-global workspace with a context manager |
| `eval_workspace.fixture_only_workspace` | G's evaluation workspace |
| `holdout_eval.evaluate_promotion_run` | G's promotion gate |
| `promote_model.MAX_RUN_MANIFEST_BYTES` | G's bound on a manifest |
| `trajectory_utils` | a whole module G added |

**O's tests cannot import, on G** (6, MEASURED): `agent.ENDPOINT_DESCRIPTION`,
`grounding_cohort.SEALED_FROM_TRIALS`, `holdout_eval.SEARCH_MARKER`,
`holdout_eval._append_question_record`, `collect_dataset.already_answered`,
`build_notebook.build_notebook`.

**Read this symmetry carefully.** It does not say the two sides disagree about
behaviour. It says they disagree about *names*, and a red import is the cheapest
kind of red there is. The 85 and 39 ordinary failures are the ones that matter,
and §3 says which are which.

### How much of each side's work is already on the other

Controlled for the shared base: of the substantive lines each side **added**
since `85d137d`, how many appear **verbatim** in the other side's file
(MEASURED 2026-11-21):

| file | O's additions present on G | G's additions present on O | reading |
| --- | --- | --- | --- |
| `scripts/grounding_cohort.py` | **412 of 463 (89%)** | 416 of 646 (64%) | G carries O's file and extends it |
| `config.py` | 11 of 17 (65%) | 12 of 19 (63%) | the same loopback check, written once |
| `agent.py` | 49 of 143 (34%) | 48 of 309 (16%) | a shared core, then each side went its own way |
| `tests/test_endpoint_policy.py` | 16 of 220 (7%) | 16 of 115 (14%) | same feature, two independent test suites |
| `tools.py` | 5 of 51 (10%) | 5 of 495 (1%) | essentially independent |
| `scripts/holdout_eval.py` | 1 of 187 (1%) | 1 of 80 (1%) | independent |
| `sandbox.py` | **0 of 15 (0%)** | **0 of 119 (0%)** | fully disjoint |
| `tests/test_eval_workspace.py` | 0 of 102 (0%) | 0 of 3 (0%) | independent |

### PR #2 — `9c60c00`, "Privacy: isolate evaluation trial groundwork", 2026-11-11

28 files, **+3456/−1560** (REPORTED by the PM; file list MEASURED). Inferred
intent: make an evaluation trial recordable without the operational log, and
stop the agent's log from carrying raw turn material — contract section 2's
"operational logging and evaluation recording are separate systems".

| behaviour | on O | evidence |
| --- | --- | --- |
| loopback-only transport (`LoopbackOnlyTransport`, `validate_loopback_url`, `build_openai_client`, `EndpointPolicyError`, `_ALLOWED_SCHEME`, `_host_refusal`, `build_local_http_client`) | **PRESENT-EQUIVALENT** | 11 symbols with identical names exist on both sides; 34% of O's added lines are verbatim on G. Different extras each side, so neither's tests import on the other |
| `Settings._base_url_is_loopback` | **PRESENT-EQUIVALENT** | added on both sides independently; ~64% shared text |
| trial record / cohort runner | **PRESENT-EQUIVALENT**, G a superset | 31 identically-named symbols; 89% of O's lines verbatim on G. See §4 |
| sanitized operational logging (`observability.py`, `tests/log_capture.py`) | **ABSENT** | **O has not touched `observability.py` since base at all** (MEASURED: `git diff --name-only 85d137d 3c76fd2 -- observability.py` is empty) |
| `main.py`, `omniagent.toml`, `export_dataset.py`, `validate_dataset.py` changes | **ABSENT** | same measurement: O never touched any of them since base |
| deletes `NEXT_CHAT.md` and `questions/bank-2026-10-10.txt` | **CONTRADICTS** | O still modifies both; the merge reports modify/delete |

### PR #3 — `d930ee4`, "fix: block hard-link workspace escapes", 2026-11-11

3 files, +61. Intent is plain from the code: a hard link is a second name for
the same file record, it resolves *inside* the workspace, and `resolve()`
therefore admits it.

| behaviour | on O | evidence |
| --- | --- | --- |
| refuse a hard-linked file on read, describe and listing | **ABSENT** | §2 — measured reachable on O through four tools |
| the CI job that runs it on Windows | **ABSENT** | `.github/workflows/ci.yml` is untouched on O since base |

### PR #4 — `5005039`, "Security remediation: POSIX filename and JSON validation", 2026-11-12

34 files, **+4346/−771** (REPORTED; file list MEASURED).

| behaviour | on O | evidence |
| --- | --- | --- |
| fixed tool allowlist (`FIXED_TOOL_ALLOWLIST`, `FIXED_INTERNAL_CAPABILITY_ALLOWLIST`) — **contract gate 2** | **ABSENT** | the import error above; readiness of 2026-11-04 says gate 2's enforcement is unassigned on O |
| search traversal bound (`MAX_SEARCH_TRAVERSAL_ENTRIES`, `SearchTraversalLimitError`) | **ABSENT**, and **CONTRADICTS** O's walk | O's only `tools.py` addition since base is `_searchable_files` (brief 11); both rewrite the same walk with 1% shared text |
| output caps (`MAX_DESCRIBE_BYTES`, `MAX_LIST_DIR_ENTRIES`, `read_text_range`) | **ABSENT** | symbol diff of `sandbox.py` |
| `workspace_scope` replacing the module-global `_workspace` | **ABSENT**, and **CONTRADICTS** | G removed `sandbox._workspace`; O's tests call `set_workspace` |
| `config_inspection.py`, `trajectory_utils.py` | **ABSENT** | the only two top-level modules either side has that the other lacks (MEASURED: O has none G lacks) |
| the wheel ships every module it imports | **PRESENT-EQUIVALENT** | both sides fixed it independently: O's `tests/test_wheel_completeness.py` (brief 17) and G's `tests/test_wheel_install.py`; both `pyproject.toml` lists now include `dataset_provenance` |
| **POSIX filename validation** | **UNMEASURED** | §7 |
| JSON/manifest validation in `validate_dataset.py`, `promote_model.py`, `publish_dataset.py` | **ABSENT** | O never touched `validate_dataset.py` since base |

## 2. The hard-link escape — reachable on O. Reported to the PM 2026-11-21, before this ADR

**Reproduction** (mine, standalone, no repository fixtures, no network, no model
server): write a secret outside the workspace, `os.link` it to a name inside the
workspace, ask the sandbox for that name. Run on both trees, same file.

| tool | O `3c76fd2` | G `5005039` |
| --- | --- | --- |
| `read_file` | **serves the outside bytes** | refused |
| `file_info` | **serves `size_bytes`, `lines`, `first_line`** | refused |
| `list_directory` | **discloses `outside-secret.txt (37 bytes)`** | hidden |
| `search_text` | **"1 match … outside-secret.txt:1: …"** | "No match … (1 files searched)" |

MEASURED 2026-11-21. Four of the six tools. The two fixture self-checks
(`st_nlink >= 2` on both names) passed, so the platform really did create a hard
link; this is not a mis-built test.

**Mutation — so "G blocks it" is proved, not claimed.** On G I made
`Workspace._has_single_link` return `True`, the only behavioural change.
`sandbox.py` hash before `1e7eb6b93eb00e86ad17f1a71eb37f08cb3df6dd`, mutated
`7de616922706fe4385a1525e59013a210c3ebfd7`. Under the mutation my reproduction
goes **3 failed** and G's own PR #3 test goes **4 failed**
(`read_text`, `read_text_range`, `describe`, `list_dir`). Restored from a
scratchpad copy; hash back to `1e7eb6b…`; `git status` clean; **87 passed, 1
skipped**. Exactly one guard holds all four vectors.

**Independently reproduced by the PM, 2026-11-21** (REPORTED): same two files,
their own detached worktrees, 4 failed / 2 passed on O, 6 passed on G, and the
same mutation reopening all four vectors with the hash restored. Two people,
two sets of worktrees, same result.

**Which gate.** Contract section 5, **gate 5** — path-boundary regression tests
on every platform claimed as supported. That gate was already only partly done
(brief 13 covers Windows junctions; its POSIX case still has no test that
notices the guard's removal). This is a *third* kind of link that no test on O
covers. It also contradicts contract section 1's sentence that `sandbox.py` is a
boundary on model-selected reads: for a hard link, on O, it is not.

**Against the threat model, stated fairly.** This is attacker **class 3**
shaped — the link is static, it exists before the walk, nothing races — so the
`secure_search.py` ruling is untouched by it. The brief-13 reparse-point guard
*provably cannot* catch it: a hard link is not a reparse point, which is why all
four vectors leak. **What I have not established is criterion 2 of the threat
model: name the actor that creates the link.** The agent has no write tool, and
an ordinary clone or archive extraction does not produce a hard link to an
arbitrary outside path. So: the boundary fails whenever a hard link is present,
and who would place one is **UNKNOWN — OWNER'S QUESTION.** It is not resolved
here and it should not be resolved by whoever writes the fix. Under
distribution (readiness block D) class 3 stops being hypothetical, so the PM's
recommendation and mine agree: **fix it before any public release, not an
emergency today.** That is a recommendation, not a ruling. **The SE fixes it; I
measured it.**

**Two costs of G's fix the SE should weigh rather than port blind:** it also
refuses files hard-linked entirely *inside* the workspace, and it fails closed
when `stat` yields no usable `st_nlink` — the same shape as the objection the
owner already sustained against `secure_search.py`.

## 3. The twelve conflicts, classified

`git merge-tree --write-tree --name-only origin/main organization/main`,
re-run by me (MEASURED 2026-11-21): **12 conflicts — 8 content, 3 add/add, 1
modify/delete**, identical to the PM's count. Merged tree
`c32283aa7d9a22709b60df94190a9e057bdc5675`; conflict hunks counted from it:

| file | kind | hunks | classification |
| --- | --- | --- | --- |
| `scripts/grounding_cohort.py` | add/add | **21** | **textual** — one file forked, not two designs (§4) |
| `tests/test_grounding_cohort.py` | add/add | **18** | **textual**, same reason |
| `scripts/holdout_eval.py` | content | 4 | **semantic** — O added 15 symbols, G added 1, 1% shared text |
| `agent.py` | content | 3 | **semantic** — same feature twice, see below |
| `tools.py` | content | 2 | **semantic** — two rewrites of one walk |
| `tests/test_endpoint_policy.py` | add/add | 2 | **textual** — two test suites for one feature; both can be kept |
| `config.py` | content | 1 | **textual** — same check, adjacent lines |
| `sandbox.py` | content | 1 | **textual** — disjoint additions, adjacent lines |
| `pyproject.toml` | content | 1 | **textual** — both extended `py-modules` |
| `tests/test_eval_workspace.py` | content | 1 | **semantic** — different sealed inventories |
| `tests/test_holdout_questions.py` | content | 1 | **semantic**, follows `holdout_eval.py` |
| `NEXT_CHAT.md` | modify/delete | — | **a decision, not a conflict**: G deleted the file, O still edits it |

**55 hunks in all, and 39 of them are in the two trial-record files** — that is,
**71% of the textual pain comes from one file that was copied rather than
merged.**

### The four core files, architecturally

**`agent.py` — the same feature, built twice.** Eleven symbols exist on both
sides under identical names: `EndpointPolicyError`, `LoopbackOnlyTransport` and
three of its methods, `_ALLOWED_SCHEME`, `_host_refusal`,
`build_local_http_client`, `build_openai_client`, `validate_loopback_url`,
`AgentConfig._base_url_is_loopback`. O then added `ENDPOINT_DESCRIPTION` and a
policy prefix; G added `validate_openai_client_endpoint`,
`_validated_client_methods`, a config-precedence route and a model-CLI route.
**Both can hold at once only if one implementation is dropped** — they are not
complementary, they are duplicates with different edges.

**`tools.py` — both rewrote the walk, for different reasons.** O's one addition
since base is `_searchable_files` (brief 11: resolve once, not 4,690 times,
byte-identical output). G added 495 lines: the tool allowlist, a traversal
bound, and a config-inspection capability. **Semantic.** G's bound and O's
pruning are both guards on the same loop; keeping both is a merge somebody has
to design, not apply.

**`sandbox.py` — genuinely complementary, and the merge cannot say so.** 0%
shared text in either direction. O added `Workspace.admit_resolved_child`
(brief 11). G added the hard-link guard, `read_text_range`, five output caps and
`workspace_scope`, and **removed the module-global `_workspace`**. Every one of
those additions could live beside O's. The single conflict hunk is adjacency;
the *removal of `_workspace`* is the real incompatibility, and it is invisible
in the conflict count.

**`config.py` — one check, written once and copied.** 65% / 63% shared text and
the same method name. **Textual.**

## 4. The trial-record area — one design, forked

`scripts/grounding_cohort.py` exists on both sides and on neither's ancestor.
**It is not parallel invention:**

- **31 symbols are identical in name** — `Task`, `Preflight`, `CohortResult`,
  `Observed`, `run_cohort`, `trial_record`, `fixture_sha256`, `protocol_sha256`,
  `grade`, `accepted_answer`, `distractors`, `POLICY_VIOLATION`,
  `STEP_EXHAUSTED`, `TOOL_ERROR`, `AGENT_ERROR`, `COMPLETED`, `ARM`, `CATEGORY`,
  `FIXTURE`, `LOOPBACK`, `PROJECT`, `TASKS` and more.
- **537 of O's 597 lines (90%) appear verbatim in G's file**, the module
  docstring included, word for word.
- **The dates settle the direction.** O's brief 15 merged **2026-11-05**; G's
  PR #2 is **2026-11-11**. G's file is O's file plus 231 lines.

**So: the same design, and G is ahead of it.** What G added on top is schema
enforcement and privacy: `TrialRecordSchemaError`, `FixtureDriftError`,
`FROZEN_FIXTURE_SHA256`, `verify_staged_fixture`, `_opaque_identifier` (trial
identifiers pseudonymised), and validators for cohort inputs, preflight records,
trial identity and observations — plus bounds on steps, repeats, timeout, tool
name length and recorded tools. O's one unique symbol is `SEALED_FROM_TRIALS`.

**This is contract section 3 and belongs to the AI/ML chair.** My reading is
that these are **compatible designs, one strictly later than the other**, and
that a merge here is a *rebase of G's additions onto O's file* rather than a
reconciliation. **I am not resolving it.** Flagged for the AI/ML chair and the
owner. What I did not check: whether G's extra validation changes any *accepted
answer* or any grade — that is an oracle question, and it is theirs.

## 5. The cost of each way out

| | **A. bring O into G** | **B. port G's intent onto O** | **C. reconciling merge** |
| --- | --- | --- | --- |
| files to touch | 88 changed on O since base | 53 changed on G since base | 12 conflicted, 55 hunks |
| semantic conflicts | — | — | **6 of 12** |
| what cannot be done mechanically | O's `holdout_eval.py` (15 symbols, 1% shared), O's `test_eval_workspace.py` inventory, O's brief 11 walk against G's bound | gate 2 allowlist, `observability.py` sanitising, `workspace_scope`, the two new modules, POSIX validation | the `_workspace` → `workspace_scope` change; the two endpoint validators; the two walks |
| tests rewritten, not re-run | O's 34 erroring modules, headed by `test_observability.py` (28), `test_agent_logging.py` (16), `test_resilience.py` (10) | G's 7 non-importing modules plus `test_observability.py` (26) and `test_sandbox.py` (21) | both of the above, minus whatever the merge keeps |
| what you lose | nothing on G; **O's 98 commits become history, not code** | nothing on O; G's 23 commits are re-derived by hand, which is what the dirty checkout appears to be doing already | nothing, if the 6 semantic conflicts are designed rather than resolved |
| what you gain | the newest security work and **9 of 18 Codex branches already rebased for you** | O's documented history, briefs and ADRs stay the trunk | both, at the price of the design work |
| carried by | **PM** (remote/branch surgery) + **SE** (re-apply O's security tests on G) | **SE** for gates 2–5, **AI/ML** for §4, **FSE** for the rest — the largest of the three | **SE** for `sandbox.py`/`tools.py`/`agent.py`, **AI/ML** for §4, **PM** sequencing |

**My recommendation, status Proposed: A — make G the canonical line, and carry
O's unique work onto it as briefs.**

Three measurements drive that, and none of them is diff size:

1. **The security behaviour the contract needs is on G, not O.** Gate 2 exists
   only on G. Gate 5 has a hole on O that I measured today. Gates 3 and 4 exist
   on G and are *absent* on O — O has not touched `observability.py` since
   2026-10-12.
2. **The tests that would survive the move are G's.** G's suite is 860 against
   O's 791, and the 34 collection errors that O's tests hit on G are concentrated
   in modules G rewrote deliberately (`observability`, `agent_logging`,
   `resilience`); the 7 that G's tests hit on O are *missing features*. Rewriting
   tests around a feature you have is cheaper than writing the feature.
3. **The work has already moved.** §6: 9 of 18 `origin/codex/*` branches, and
   every one since 2026-11-11 bar two, are built on G's history. Choosing O
   orphans them.

**What argues against A, honestly:** O carries the project's record — the
contract, the threat model, the briefs, ADR-0001 and ADR-0002, the release
readiness plan. G deleted `NEXT_CHAT.md` and the question bank and has none of
`docs/pm/`. Those are documents, they merge without conflict (`README.md` and
the three `grounding-cohort/` files already auto-merge), and losing them is not
acceptable — so **A means "G's code history, O's documents carried over", not
"abandon O".** If the owner prefers B, the honest cost is that B re-derives by
hand what already exists and tests green on G, which is the most expensive of
the three and the one most likely to be done twice.

**A condition on A, added after the branch measurement below.** The four newest
G-line branches make `sandbox.py` import `securefs.py`, a `ctypes` module that
is **954 lines on the oldest of them and 1,319 on the three newest** (§6).
Neither pinned commit contains it. That is the shape the owner parked twice in
`secure_search.py`, and adopting G's line is also adopting the direction those
branches are travelling. **A is my recommendation for `3c76fd2` against
`5005039` — the two pinned commits — and it does not endorse what is queued
behind G.** If the owner takes A, criteria 1 to 5 of the threat model should be
answered before those branches merge, not after; by the criteria's own wording
they already apply, since they cover "`secure_search.py` **or a successor**".

## 6. The `origin/codex/*` branches — where they sit and where they meet G

Taken from `git for-each-ref`, **not** from the brief's paragraph; the list
differs from it (MEASURED 2026-11-21). "line" is which `main` the branch
descends from — decided by whether G's PR #2 (`9c60c00`) is an ancestor.
**Paths only, with one exception the PM asked for: the hard-link guard, below.
Nothing else on any of these branches was verified or reviewed.**

| branch (`origin/codex/…`) | date | line | ahead | files | ∩ G's PR paths |
| --- | --- | --- | --- | --- | --- |
| `windows-private-root-validation-20261121` | 11-21 | **G** | 22 | 37 | 24 |
| `security-runner-fixtures-20261120` | 11-21 | **G** | 13 | 37 | 24 |
| `security-scans-validation-20261120` | 11-20 | **G** | 7 | 34 | 24 |
| `mypy-portability-20261116` | 11-16 | O | 1 | 3 | 2 |
| `remove-ai-handoff-docs-20261116` | 11-16 | O | 1 | 23 | 1 |
| `scale-security-hardening-20261113` | 11-15 | **G** | 1 | 26 | 22 |
| `posix-json-ci-fixes-20261112` | 11-12 | **G** | 11 | 34 | 34 |
| `security-remediation-batch2-22d6932-validation` | 11-12 | **G** | 8 | 34 | 34 |
| `security-remediation-batch1-20261112` | 11-12 | **G** | 6 | 31 | 31 |
| `agentic-task-mode-fast-tools-20261111` | 11-12 | **G** | 5 | 26 | 26 |
| `phase2-sandbox-hardlink-windows-ci-20261111` | 11-11 | **G** | 1 | 3 | 3 |
| `brief16-eval-privacy-split-20261109` | 11-10 | O | 22 | 28 | 28 |
| `brief16-record-schema-20261109` | 11-09 | O | 7 | 53 | 24 |
| `security-remediation-batch2-20261112` | 11-07 | O | 4 | 8 | 7 |
| `security-remediation-batch2-validation-20261112` | 11-07 | O | 4 | 8 | 7 |
| `agentic-mvp-contract-20261103` | 11-04 | O | 0 | 0 | 0 |
| `posix-device-race-20261101` | 11-01 | O | 5 | 7 | 5 |
| `search-text-race-safety-20261101-workspace` | 11-01 | O | 1 | 5 | 3 |

Three things the table says that a branch list does not:

- **`phase2-sandbox-hardlink-windows-ci-20261111` is not a port.** Its name
  reads like O-line work and it is not: it contains `9c60c00` and none of O's
  commits, and it is 1 ahead / 2 behind G. **No branch on either remote carries
  a port of G onto O** (MEASURED across all 18).
- **The G-line branches are where the newest work is**, and the three newest are
  7 to 22 commits past G's own tip.
- **The two O-line brief-16 branches overlap G's PR paths almost completely**
  (28 of 28, 24 of 53). That is the duplication the PM suspected, visible as
  paths.

### Is the hard-link fix already on the origin line, unmerged?

**No.** Nine `origin/codex/*` branches carry the guard; `origin/main` carries
none; **all nine are on G's history.** Asked by the PM, measured by me
2026-11-21. The guard function was extracted with `ast` from each branch's
`sandbox.py`, whitespace-normalised and hashed; G's is `4c87036f41cc`, 13 lines.

| branch (`origin/codex/…`) | guard text | call sites | line | contains PR #3 |
| --- | --- | --- | --- | --- |
| `phase2-sandbox-hardlink-windows-ci-20261111` | **identical to G** | same 2 | G | no — its own `8d86a17` |
| `agentic-task-mode-fast-tools-20261111` | **identical to G** | same 2 | G | yes |
| `posix-json-ci-fixes-20261112` | **identical to G** | same 2 | G | yes |
| `security-remediation-batch1-20261112` | **identical to G** | same 2 | G | yes |
| `security-remediation-batch2-22d6932-validation` | **identical to G** | same 2 | G | yes |
| `scale-security-hardening-20261113` | **identical to G** | **1 of 2** | G | yes |
| `security-scans-validation-20261120` | **identical to G** | **1 of 2** | G | yes |
| `security-runner-fixtures-20261120` | **identical to G** | **1 of 2** | G | yes |
| `windows-private-root-validation-20261121` | **identical to G** | **1 of 2** | G | yes |

Not one of them has `origin/main` (`3c76fd2`) or brief 14 (`02ba007`) as an
ancestor. **"Already fixed somewhere on the origin line" is false**: the fix
sits on branches that are pushed to the `origin` *remote* but built on G's
*history*. A remote is not a line, and the branch names hide it —
`phase2-sandbox-hardlink-windows-ci` reads like an O-line port and is not one.

**The four branches with one call site are not weaker — measured, not read.**
They lost the `list_dir` call because `list_dir` was rewritten around a
handle-based API; the check became `if not directory and links == 1`. On
`windows-private-root-validation-20261121` my unchanged reproduction gives
**6 passed** — all four vectors closed, the listing one included. On
`posix-json-ci-fixes-20261112`, a two-call-site branch, **6 passed** as well.
So: **IDENTICAL** on five branches, **PRESENT-EQUIVALENT** on the four newest,
and nothing on O.

### What that rewrite brought with it — existence only, not a review

The four branches that rewrote `list_dir` also add modules that `sandbox.py`
imports — `sandbox.py:58` on the newest reads
`from securefs import DirectoryLimitError, SecureRoot`. They do **not** all
carry the same thing, and the difference is the point (MEASURED 2026-11-21,
line counts and `grep -c ctypes` only; the correction below is the PM's catch,
re-derived by me before it was written in):

| ref | `securefs.py` | `publisher_root.py` |
| --- | --- | --- |
| **O** `3c76fd2` | **absent** | **absent** |
| **G** `5005039` | **absent** | **absent** |
| `posix-json-ci-fixes-20261112` | absent | absent |
| `scale-security-hardening-20261113` | **954 lines / 107 `ctypes`** | absent |
| `security-scans-validation-20261120` | **1,319 / 160** | **469 / 55** |
| `security-runner-fixtures-20261120` | **1,319 / 160** | **469 / 55** |
| `windows-private-root-validation-20261121` | **1,319 / 160** | **469 / 55** |

So it is **three branches at 1,319 + 469 and one at 954 with no
`publisher_root.py`** — not four alike, as an earlier draft of this section
said. **`securefs.py` grew from 954 to 1,319 lines in the seven days between
2026-11-13 and 2026-11-20, and `publisher_root.py` appeared in the same
window. That growth is the visible part of the stacking** — the module is not a
finished thing being carried along, it is being built while the branches pile
up.

**Neither pinned commit has any of it.** `securefs.py` and `publisher_root.py`
are absent from **G (`5005039`) itself** and from **O (`3c76fd2`)**. They exist
only on later Codex branches stacked on G. That is precisely what keeps
recommendation A a statement about the two pinned commits and not about the
queue behind them.

**I did not read either module** — the brief limits me to guard text and paths
on these branches, and I have kept to it. The PM has not read them either; both
of us have counted lines and `ctypes` mentions and nothing more. But the shape
has to be named, because a standing owner ruling is about exactly this shape:
on 2026-11-02 and again on 2026-11-04 the owner parked `secure_search.py` —
1,016, 1,199 and 1,069-line variants of raw `ctypes` handle work — **parked,
not continued and not deleted**, reopening it needing a new owner decision plus
criteria 1 to 5 answered in writing
([threat model](../pm/threat-model-2026-11-02-the-search-boundary.md), the
criteria at lines 105–128 and the ruling at 188–192).

**The criteria do not need an argument about resemblance to apply.** Their own
first sentence is: *"Any change to the search boundary — `secure_search.py`
**or a successor** — is merged only when all five are answered in writing, with
evidence."* A module that `sandbox.py` imports in order to walk and admit
directory entries **is** a change to the search boundary, whatever its
provenance. And criterion 5 names the size directly: *"If a 1,200-line ctypes
module is the right shape for this project, then 'hand-rolled and small' stops
being true and should stop being written down."* One of these branches is
already past that number and one is approaching it.

Whether `securefs.py` *is* the parked work resumed, or a new thing the owner
would approve on its own merits, is **OWNER'S QUESTION.** Neither the PM nor I
will answer it from a line count.

## 7. What this brief could not measure

- **PR #4's POSIX filename validation — UNMEASURED.** It is Linux behaviour.
  **WSL is available on this machine** (MEASURED: `kali-linux` default, plus
  `Ubuntu` and `Ubuntu-22.04`, all WSL2; `wsl -e uname -a` answers
  `6.18.58.1-microsoft-standard-WSL2 x86_64`), so this is not permanently
  unmeasurable. **What a run would have needed, exactly:** one of the installed
  distros — `Ubuntu-22.04` or `Ubuntu`, not `kali-linux` or `docker-desktop` —
  with **Python 3.12** (the project's `requires-python = ">=3.12"`), this
  project's runtime dependencies installed into a venv inside that distro, and
  the checkout reachable from it; then the same two reproduction files plus
  G's `tests/test_sandbox.py` run there. That is an install on the owner's
  machine. **The PM has ruled: hold, install nothing, and ask the owner.**
  Nothing here is blocked on it.
- **The POSIX half of gate 5** — the same limitation, and it is the open item
  recorded since 2026-11-04.
- **The dirty checkout.** `D:\code-project\OmniAgent` holds 54 uncommitted
  changes on `chore/local-ai-delegate` and Codex is editing it. It is REPORTED
  that some of it is byte-identical to G's files. **I did not read it.** If it is
  committed to a named branch it becomes a third tree and the matrix above must
  be re-run, not extrapolated.
- **Whether G's extra validation changes any grade or accepted answer** (§4).
  That is the AI/ML chair's oracle question.
- **Any claim about why.** Three squashed PRs and three titles are all the
  intent on record. Everything in the "intent" paragraphs is inferred.

## What this document does not establish

- **Which line is canonical.** The owner's, and the recommendation in §5 is
  Proposed.
- **That G's code is correct.** I ran G's suite and it is green on its own tree;
  I reviewed none of it. The hard-link guard is the one behaviour I proved, and
  I proved it with a mutation, not by reading.
- **That A is cheap.** It is the cheapest of three expensive options, and the
  document-carrying half of it has not been scoped.
- **That the conflict count will hold.** It is a dry run against two moving
  refs. Re-run it on the day the decision is taken.
