# Brief 15 — one category, with a real oracle

**For the AI/ML engineer.** Reassigned 2026-11-04: this was written for the
fullstack engineer before the AI/ML chair existed, and it is section 7 step 3
of the contract, which is that chair's. Static throughout. **No model run, and no test
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

**Still current at `87a1297`:** 658 passed, mypy clean over 45 files, ruff
clean. Branch from `87a1297`, not from `ec7787a`.

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

**Branch from `main` at `87a1297`, your own worktree, your own branch — never
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
