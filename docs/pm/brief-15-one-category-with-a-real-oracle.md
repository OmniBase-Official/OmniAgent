# Brief 15 — one category, with a real oracle

**For the fullstack engineer.** Static throughout. **No model run, and no test
in this brief may contact a model server** — use an injected fake client, the
way `tests/test_session_eval.py` already does.

This is **section 7 step 3** of the owner-approved contract
(`docs/pm/agentic-mvp-contract-2026-11-03.md`): freeze the task inventory,
oracle and trial record format. **Narrowed on purpose, and the narrowing is
the point.**

## Why this is one category and not thirty-six trials

The contract asks for 6 categories × 2 variants × 3 repeats = **36 trials per
arm**, with the prompt, fixture, rubric, allowed tool sequence and accepted
answers all frozen before the first trial.

**A record format that turns out wrong costs all 36 trials.** This project has
already paid that bill twice: the old question bank scored three questions on
tool choice alone and read as though their answers had passed, and a run
record carried the commit but not whether the tree was clean, so a void run
pooled with ten good ones. Both were found by reading the artifact, after the
runs.

So: **build one category end to end, prove the shape, and let the other five
follow a form that has been tested.**

### Which category, and why that one

**Evidence grounding.** Its oracle requirement in the contract is "exact
expected value derived independently from the fixture", and that is precisely
the defect that killed the old instrument: a substring that grades characters
instead of answers. Getting this one right is what makes the other five
cheap; getting it wrong is what the last three months were.

## What is measured, 2026-11-04, on `ec7787a` (`main`)

- Gates: ruff clean, mypy clean over **45** files, **658 passed**.
- The old bank lives at `scripts/holdout_eval.py:78`, 19 questions, 18
  checkable. **It is not the contract's evaluation and is not being extended
  here.** Leave it alone.
- `scripts/eval_workspace.py` already seals an answer key from the agent's
  tools, and `tests/test_eval_workspace.py` asserts the property rather than a
  list: no reachable file may hold a question's text or its expected answer.
  **That invariant is the thing to reuse, not to reinvent.**
- `scripts/holdout_eval.py` already records one JSONL line per question with a
  commit and a clean-tree field, from brief 12. **That is the record shape to
  build on.**

## What to build

### 1. An immutable synthetic fixture, with a hash

A directory of synthetic files the task is about. Not the repository: the
contract says synthetic fixtures, and `eval-fixture/` exists for a different
purpose (it is the subject of a listing question in the old bank) — **do not
reuse it and do not write into it.**

The fixture carries a **hash of its own content**, computed over a defined
ordering, and the trial record carries that hash. A fixture that can change
without the hash changing is not immutable; say how you ordered it.

### 2. An oracle that derives the answer, never stores it

The expected value is **computed from the fixture at load time**, the way
`scripts/holdout_eval.py:41 _lines()` does and for the reason its docstring
gives: a written-down answer is wrong the moment the fixture is edited, and
the figure then falls for a reason that is not the model.

**The answer key must be unreachable by the agent's six tools.** Reuse
`sealed_workspace` and extend the invariant in `tests/test_eval_workspace.py`
to cover the new fixture and its oracle. If a test of yours puts an expected
value anywhere the agent can read, that test must fail — build it and watch it
fail before you trust the seal.

### 3. Two variants and three repeats of that one category

Six trials. Enough to exercise the record and the scoring without pretending
to be a cohort. **Three repeats of a temperature-0 model is not determinism
insurance** — this project has measured a question answering 1 in 10 one day
and 6 in 10 two days later with unchanged text — so the record must make the
repeats individually readable, never averaged.

### 4. The trial record, exactly as the contract lists it

Carry: cohort/trial/task IDs and arm; the exact commit **and the clean-tree
assertion**; fixture and protocol hashes; model tag and digest; endpoint
**classification** (`loopback`), never the URL; temperature, `max_steps`,
timeout, retry policy and the task's tool allowlist; tool names, sanitized
status, step count, execution status; and the score.

Carry **none** of: prompts, system prompt, reasoning, raw model replies, file
contents, raw observations, raw tool arguments, raw errors, the endpoint URL.
The contract is explicit, and brief 12's `question_record()` is already a pure
function tested for carrying nothing but its allowed fields. **Follow that
pattern: a pure builder, tested directly.**

### 5. The allowlist as data, and nothing more

Each task declares the tools it is allowed to use. **This brief does not
enforce it in the dispatcher** — the contract assigns that to the security
engineer, and `tools.py` is forbidden here. Define the field, check it
evaluator-side, and record any disallowed attempt as a category. Say plainly
in `## Result` that dispatcher enforcement is not done and is not yours.

## Tests that must fail first

| Test | Must fail before, pass after |
| --- | --- |
| the fixture hash changes when any fixture byte changes | new |
| the oracle's expected value changes when the fixture changes | new |
| no reachable file holds the new expected value — the seal invariant, extended | new |
| the record carries every required field | new |
| the record carries **no** prompt, reply, file content, raw argument or URL | new |
| six trials are recorded individually, not averaged | new |
| a disallowed tool request is recorded as a policy violation, not retried | new |
| the whole thing runs against an injected fake client with **no network** | new |

## Mutations that must go red

Restore from a scratchpad copy, **never `git checkout --` alone**.

| # | Mutation | Must go red |
| --- | --- | --- |
| Ma | Hardcode the expected value instead of deriving it | the oracle test, after editing the fixture |
| Mb | Write the expected value into a file the sealed workspace can read | the extended seal invariant. **If it stays green the invariant is not covering your fixture** — that is a finding, not something to patch around |
| Mc | Add the prompt to the record | the no-content test |
| Md | Average the three repeats into one row | the individually-readable test |
| Me | Drop the clean-tree field | the required-field test |

**Mb is the one to take seriously.** The seal has moved a leak instead of
closing it once before, and the invariant only covers what it reaches.

## Files you may touch

- a new fixture directory — **name it so nothing mistakes it for
  `eval-fixture/`**, and say what you chose
- a new module under `scripts/` for the harness, and a new test module
- `tests/test_eval_workspace.py` — only to extend the invariant over your
  fixture

## Files you may not touch

**`agent.py` and `tests/test_config.py`, `tests/test_endpoint_policy.py`,
`tests/test_local_only.py` — the security engineer is in those on brief 14
right now.** Also `tools.py` · `sandbox.py` · `secure_search.py` and its
branches · `scripts/holdout_eval.py` · `scripts/eval_scoring.py` ·
`scripts/eval_workspace.py` · `scripts/session_eval.py` ·
`eval-fixture/**` · `questions/**` · `models/**` · `data/**` ·
`omniagent-core/**` · `.github/workflows/**` · `NEXT_CHAT.md` · `README.md` ·
`omniagent.toml` · `docs/` except your `## Result`.

`scripts/eval_workspace.py` is forbidden although you need `sealed_workspace`
from it: **import it, do not edit it.** If you believe it has to change, say so
in `## Result` and stop — that is the file three briefs have had to route
around, and it holds the answer-key seal.

If a file is in neither list, ask rather than decide.

## Gates

```
.venv\Scripts\python.exe -m ruff check .
.venv\Scripts\python.exe -m mypy
.venv\Scripts\python.exe -m pytest
```

Full path, **never your own `-q`**. Baseline **658 passed**, mypy clean over
**45** files. New reachable files mean the eval-workspace invariants scan more
of them; if the count moves for a reason that is not yours, say so.

## Where to work

**Branch from `main` at `ec7787a`, your own worktree, your own branch — never
`main` itself.** The contract's run rules forbid two writers in one checkout
and three measurements have been voided by it. The manager merges.

## The split

Nothing here needs a model. **The cohort is not authorized by anything** —
the contract gates it behind six security gates, a frozen threshold and an
owner decision. Your deliverable is a harness that runs on a fake client and a
record format that survives being read. The manager runs the probe and, if the
owner ever authorizes it, the cohort.

## The one thing that would make this wrong

**Building thirty-six trials on an untested record.** That is why this brief
is one category: the next five are cheap once this shape is proved, and
expensive to redo if it is not. If you find yourself writing the other five
categories because the pattern is obvious, stop and report that the pattern is
ready instead.

The second way: **an oracle that stores its answer.** It is the same defect as
a substring expectation one level up — the figure falls when someone edits a
fixture, and it falls for a reason that is not the model. Ma exists to make
you watch it.

## Commit

```
git add <fixture dir> scripts/ tests/
git commit -m "measure: one evidence-grounding category with a derived oracle"

git add docs/pm/brief-15-one-category-with-a-real-oracle.md
git commit -m "docs: brief 15 result -- the oracle and the trial record, proved on one category"
```

**Do not run a bare `git push`** — two remotes, and `main` tracks the one this
work does not belong to. Name it: `git push origin <your branch>`.

## Result

<!-- Engineer: append here. The fixture's name and how you ordered its hash;
how the oracle derives its value; the extended invariant and what it now
reaches; the record's fields, with the forbidden ones named as absent; the six
trials as six rows; Ma-Me each with the test that went red, and for Mb whether
the invariant covered your fixture at all; the three gate results with the
count explained; the branch and commit hashes; that dispatcher enforcement of
the allowlist is not done and not yours; and anything you refuse to claim. -->

### Result — AI/ML engineer, 2026-11-05

Branched from `main` at `87a1297` as the brief names. `main` had already moved
three commits past it (`e041f8d`, `cf7178a`, `c72938e`, all `docs/pm/`), so the
baseline is the commit the brief froze and not `HEAD`. Worktree
`D:\code-project\OmniAgent-aiml-brief15`, branch
`aiml/brief15-evidence-grounding-20261105`, code at **`a083b74`**.

No model was run. No cohort, no probe, no service contact of any kind. The
whole thing runs on an injected fake client, and one of the tests proves that
by replacing `agent.OpenAI` with a function that raises.

**The prediction I wrote before the mutations, quoted as written:** *"Ma, Mc,
Md and Me will go red on the first try. Mb is the one that might not: if my
expectation is the ledger's own token, the fixture is itself a carrier, so a
'no reachable file holds the answer' invariant cannot be the right shape and I
expect to have to assert 'exactly one carrier, and it is the subject' instead.
Mf — emptying my own seal list — I expect to go red immediately."*

Three of those were right. **Mb went red on the shape I predicted. Mf did not
go red, and that is the most useful thing in this report.**

#### 1. The fixture, and how its hash is ordered

**`grounding-cohort/`** — named with no "fixture" in it so a glance cannot
confuse it with `eval-fixture/`, which I neither read nor wrote. Three files:
`README.txt` stating that every value is invented and that the directory is a
subject rather than an answer key, and two synthetic ledgers.

`fixture_sha256()` hashes, in this order: every file under the directory
recursively, sorted by its POSIX path relative to the directory; each
contributes its **relative path**, a NUL, its **text**, a NUL. The path is in
the digest so an added, removed or renamed file moves it — three separate
tests, one per case.

**The text is hashed with newlines normalised to `\n`, not as the bytes on
disk, and that is a trade-off rather than an oversight.** This repository sets
`core.autocrlf=true` and has **no `.gitattributes`**, so the same commit is
CRLF here and LF on a Linux checkout; a byte hash would report fixture drift
that is only a checkout difference. Git printed the warning itself while I
staged the files ("LF will be replaced by CRLF the next time Git touches it"),
so this is measured, not anticipated: after `rm -rf grounding-cohort &&
git checkout -- grounding-cohort` the files on disk hold CRLF and
`fixture_sha256()` returns
`f13f6e68db1393947652ebe5fad33ce800e46fdab38cc7ae570cffd4224cbb8a` — byte-identical
to the digest in the six rows below.

**What the digest therefore does not see: an edit that only rewrites line
endings.** Everything else moves it. I am stating that rather than claiming
immutability I did not build.

#### 2. How the oracle derives its value

Each task names a ledger, a **key column** and the value it holds, and an
**answer column**. The oracle parses the ledger — the header is the first line
whose first token is `record-id`, the rows run to the first blank line, prose
above and below is ignored — finds the rows matching the key, and returns the
answer column of the single match.

It **raises** on zero matches and on two, naming the count. `sorted(...)[0]`
quietly picking one is how an oracle starts lying, and brief 10 already logged
that fragility in `_search_subject`. It also raises if either column is missing,
so renaming a column in the fixture fails loudly instead of scoring nothing.

No accepted value is written down anywhere. A test reads both of this
category's source files and asserts that neither contains any of them.

**The grading is two axes, never combined here:** the accepted value appears in
the answer, and **no other row from the same ledger appears**. That second axis
is the whole lesson of the old comparison question — a substring expectation
graded a reversed answer correct for ten runs because the answer named both
files. Three tests pin it: a grounded answer, an answer naming the accepted
value *and* another row, and an answer naming only another row.

#### 3. The extended invariant, and what it now reaches

`tests/test_eval_workspace.py` gained four tests over a workspace built as
`sealed_workspace(PROJECT, also_deny=SEALED_FROM_TRIALS)`.

**`scripts/eval_workspace.py` was imported and not edited.** The two paths this
category must seal — the module holding the task texts and its test module —
go through `sealed_workspace`'s own `also_deny` parameter rather than into
`ANSWER_KEY`. `SEALED_FROM_TRIALS` is *imported* by the invariant test rather
than restated, so what a trial seals and what the test checks cannot drift; if
they could, a green test would say nothing about the run.

The answer check is **"exactly one reachable carrier, and it is the ledger the
task is about"**, not "no reachable file holds it". The fixture is the subject,
so its own ledger must hold the answer — that is what makes the answer
derivable from evidence. What must not exist is a second carrier.

Reachable-file counts, measured: **51 → 56** to the old invariant's workspace,
and the five added files are exactly mine (three fixture files, the module, the
test module). **During a grounding trial the count is 54**, because the module
and its test are denied.

Also pinned: the fixture's inventory (three files, the way `eval-fixture/`'s is
pinned), and that both accepted values are **14 and 15 characters**, above the
`_DISTINCTIVE = 12` cut — so the older invariant's length filter, which brief
10's Mc showed drops shorter expectations unchecked, would cover them too.

#### 4. The record

27 fields, asserted as one exact dictionary so a missing field cannot pass as
an absent one:

`cohort_id` · `trial_id` · `task_id` · `variant` · `repeat` · `arm` ·
`category` · `commit` · **`tree_clean`** · `fixture_sha256` ·
`protocol_sha256` · `model_tag` · `model_digest` · `runtime_version` ·
`endpoint` · `temperature` · `max_steps` · `timeout_seconds` · `max_retries` ·
`allowlist` · `tools` · `tool_status` · `steps` · `execution_status` ·
`answer_grounded` · `answer_names_distractor` · `tools_within_allowlist`

**Absent, and named as absent:** no prompt, no system prompt, no reasoning or
thought, no raw model reply, no final-answer text, no file contents, no raw
observation, no raw tool argument, no raw error, **no endpoint URL**, no
expected value and no distractor. The test checks this over the *serialised*
record, not its keys, so a forbidden value smuggled inside an allowed field
fails too; it also asserts the absence of `http`, `localhost` and `11434`.

**None of those is a parameter of the builder**, so none can arrive by
accident. The endpoint is a classification: `Preflight` refuses anything but
`"loopback"`, and refuses an empty model digest, a non-zero `max_retries` (the
agent's own default is **2**) and a non-zero temperature.

Two hashes, kept independent on purpose: `fixture_sha256` freezes what is
asked *about* and, because the accepted answers are a pure function of the
fixture, it is already their freeze record; `protocol_sha256` freezes the
asking — prompts, task identities, allowlists, arm, category and the four
limits. Keeping them apart is what lets a mismatch say which half drifted.
Tested: a reworded prompt, a widened allowlist and a changed `max_steps` each
move the protocol hash, and the protocol hash carries no accepted answer.

`run_cohort` takes its `client` with **no default**, so nothing can reach a
model server unless a caller hands one over, and **there is no command-line
entry point** — no cohort is authorized by anything, and an importable `main()`
would be one keystroke from starting one. It **writes nothing to disk**:
retention duration and deletion path are still open gates, and defaulting to a
path inside the repository would pre-empt them. `data/**` was not touched.

#### 5. The six trials, as six rows

Scripted replies on a fake client. **These are not a measurement of any model**
— they exercise the record and the scoring, nothing more. `fixture_sha256` =
`f13f6e68…24cbb8a`, `protocol_sha256` = `85e84fb4…835066b8`, `commit` =
`87a1297`, `tree_clean` = `true`, `endpoint` = `loopback`, `temperature` = 0,
`max_steps` = 8, `timeout_seconds` = 180, `max_retries` = 0 in every row.

| trial_id | task | variant | repeat | tools | tool_status | steps | status | grounded | names distractor | in allowlist |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| `demo-fake/grounding-v1/r1` | grounding-v1 | v1 | 1 | `read_file` | `ok` | 2 | completed | true | false | true |
| `demo-fake/grounding-v1/r2` | grounding-v1 | v1 | 2 | `read_file` | `ok` | 2 | completed | true | false | true |
| `demo-fake/grounding-v1/r3` | grounding-v1 | v1 | 3 | `read_file` | `ok` | 2 | completed | true | false | true |
| `demo-fake/grounding-v2/r1` | grounding-v2 | v2 | 1 | `read_file` | `ok` | 2 | completed | true | false | true |
| `demo-fake/grounding-v2/r2` | grounding-v2 | v2 | 2 | `read_file` | `ok` | 2 | completed | true | false | true |
| `demo-fake/grounding-v2/r3` | grounding-v2 | v2 | 3 | `read_file` | `ok` | 2 | completed | true | false | true |

`started=6 completed=6 failed=0 stopped_on=None`. Started, completed and failed
are counted apart, because a trial that stopped is not a trial that answered
wrongly — and pooling those two is how a derailment got recorded as "not
wrong" for ten runs.

The cohort also stops itself: `revision_drift` if the commit moved under it,
`tree_dirty` if the tree stopped being clean, checked **before and after** the
run against an injectable observer, and `tool_error` / `agent_error` stop the
cohort rather than the trial. Three measurements have been lost to a tree
someone else was writing to; this is that rule in code.

#### 6. The allowlist, and what is not mine

Each task declares its allowed tools as data and the harness checks them
**evaluator-side**: a call outside the list is recorded as
`execution_status="policy_violation"` with `tools_within_allowlist=false`,
counted as failed, and **not retried** — the test asserts the fake received
exactly two calls, so no replacement attempt was made.

**Dispatcher enforcement of the allowlist is not done, and it is not mine.**
Verified rather than repeated from the contract: `agent.py:669` calls
`run_tool(tool_name, step.action_input or "")` with no allowlist parameter, so
dispatch is registry-wide. **In the policy-violation test the disallowed tool
really did execute** — I scripted `calculate`, which is pure arithmetic with no
side effects, precisely so that it could. My test proves the evaluator notices;
it proves nothing about the dispatcher refusing. That is contract §5 item 2 and
the security engineer's gate, and the injection/tool-policy category stays
blocked until it lands.

#### 7. Mutations

Every one restored from a scratchpad copy, never `git checkout --` alone, and
every source file's SHA-256 re-checked against the pristine copy afterwards.

| # | Mutation | What went red |
| --- | --- | --- |
| **Ma** | accepted values hardcoded instead of derived | `test_every_task_derives_its_accepted_answer_from_the_fixture` — the test edits a *copy* of the fixture, so the real fixture was never touched |
| **Mb** | the derived answer written into a new reachable file at the repository root | `test_each_grounding_answer_has_exactly_one_reachable_carrier`, **naming the extra carrier by path** |
| **Mc** | the prompt added to the record | `test_the_trial_record_carries_no_prompt_answer_content_or_url` **and** `test_the_trial_record_carries_every_field_the_contract_lists` |
| **Md** | the three repeats pooled into one row per task | `test_six_trials_are_recorded_individually_never_averaged` — `assert 2 == 6` |
| **Me** | `tree_clean` dropped from the record | `test_the_trial_record_carries_every_field_the_contract_lists` — "Right contains 1 more item: `{'tree_clean': True}`" |

**On Mb specifically, since the brief asked: the invariant does cover my
fixture.** It went red, and it named the second carrier rather than just
failing. The shape had to be "exactly one carrier, and it is the subject"
rather than "no carrier", because the fixture is the subject; a zero-carrier
assertion would have been impossible to satisfy and would have told me nothing.

#### 8. Mf — my own extra mutation, which stayed green. Two defects, both mine.

I emptied `SEALED_FROM_TRIALS` to `()` — the harness then runs every trial in a
workspace where its own task module is readable. **Both of my seal tests stayed
green.** Reported rather than patched around, then fixed, then re-proved.

- **`test_the_trial_workspace_opens_the_fixture_and_seals_this_category`** only
  looped over `SEALED_FROM_TRIALS`. An empty tuple iterates zero times, so the
  assertion was **vacuous**.
- **`test_no_reachable_file_holds_a_grounding_task_prompt`** searched reachable
  files for the contiguous prompt. Measured: the prompt is **not present in its
  own module at all**, because Python's implicit concatenation splits it across
  two string literals — and **not after whitespace normalisation either**, since
  the quote characters survive it. So no textual search of the source can ever
  catch an unsealed module. The test could not do its job.

The fix makes the load-bearing claim **structural**:
`test_the_category_seals_exactly_the_two_files_that_define_it` asserts
`set(SEALED_FROM_TRIALS)` equals the files the interpreter actually loaded this
category from, via `inspect.getfile` and `__file__`, so an empty or wrong list
fails. The textual check stays as a second line, now over normalised text, for
the case it can catch — a prompt copied into prose. Re-running Mf afterwards
turns **two** tests red.

#### 9. A pre-existing hole in the old invariant, measured

Looking for the same weakness in the questions that are not mine, I found a
live carrier:

- **`tests/test_shipped_config.py:88`** holds the old bank's question text
  `"What is inside the data directory?"`, wrapped across two source lines.
- The file is **reachable** through `sealed_workspace(PROJECT)` —
  `workspace.resolve` succeeds and it is in `reachable_files()`.
- `test_no_reachable_file_holds_a_held_out_question` **passes**, because it
  searches for the contiguous string. The occurrence is found only after
  whitespace normalisation.
- Through the real tools: `read_file` refuses it on size ("3,525 characters,
  too long"), but **`search_text("What is inside the data", "tests")` returns
  the line** — and `search_text` from `.` is the exact call that produced the
  original leak.

The surrounding docstring also states how the agent failed that question
("spent all twelve steps and returned 'I ran out of reasoning steps…'"). The
question's *expected answer* is **not** nearby, so this is key-adjacent prose
rather than the answer itself — which is still what `held_out_texts()` bans
"without exception", and for the reason its own docstring gives.

**Not fixed here.** `tests/test_shipped_config.py` is in neither of the
brief's lists, and changing the old invariant's matching would change what it
reaches for questions that are not mine. Logged for whoever owns the old bank.

#### 10. Gates

| Gate | Result |
| --- | --- |
| `ruff check .` | All checks passed |
| `mypy` | Success, **46** source files |
| `pytest` | **694 passed** |

**The count moved for a reason that is mine: 658 → 694, +36 tests** — 32 in
`tests/test_grounding_cohort.py`, 4 in `tests/test_eval_workspace.py`. mypy
**45 → 46**: +1, which is `tests/test_grounding_cohort.py`, because `tests` is
in the configured list.

**One question, and I am not deciding it.** `scripts/grounding_cohort.py` is
**not type-checked by the configured gate**: `[tool.mypy] files` in
`pyproject.toml` is an explicit list, and my module is not in it. The comment
beside `scripts/eval_scoring.py` in that list says why the evaluation scripts
belong there — *"The evaluation scripts produce the numbers this project
quotes, so they are checked like the agent is."* Mine is exactly such a script.
`pyproject.toml` is in neither of the brief's lists, so I asked rather than
decided. **Evidence that the one-line addition is clean:**
`python -m mypy scripts/grounding_cohort.py` → *Success: no issues found in 1
source file*, under the same strict settings.

#### 11. What I did not establish

- **Nothing about any model.** No completion request was sent, by this code or
  by me. The six rows are the record format exercised on scripted replies;
  `model_tag` in them is `fake-no-model` and `runtime_version` says so.
- **Nothing about the other five categories.** The pattern is ready and I did
  not write them — that was the brief's one instruction about where this could
  go wrong. Tool selection needs a frozen required *sequence*, which is an axis
  this record does not yet carry; the other four need their own oracles.
- **Nothing about the threshold.** Contract §6 assigns "propose a
  threshold/reporting method before cohort" to this chair; it is not in this
  brief and is not written.
- **No claim that the fixture is immutable against a line-ending-only
  rewrite.** It is not, by design, and §1 says so.
- **No claim that the dispatcher refuses a disallowed tool.** It does not.
- **No claim that any of this resists prompt injection.** The fixture's text is
  untrusted data to the agent and nothing here tests that.
- **No claim about the old bank's figures.** I did not run it and did not touch
  it.

**Still the manager's:** merging this; the model digest and Ollama/runtime
version, which `Preflight` demands and nobody has frozen; the probe; and the
cohort, if the owner ever authorizes one.
