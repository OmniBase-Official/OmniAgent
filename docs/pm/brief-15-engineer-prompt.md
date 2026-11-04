# Brief 15 — the paste-ready task for the fullstack engineer

Paste everything below the line. The companion brief is
`docs/pm/brief-15-one-category-with-a-real-oracle.md`; `## Result` goes there.

---

You are the **fullstack engineer** on OmniAgent, `D:\code-project\OmniAgent`,
baseline **`main` at `ec7787a`**. Gates re-run by the manager today: **658 passed**, `ruff` clean, `mypy` strict clean over 45
files.

**Read `docs/pm/brief-15-one-category-with-a-real-oracle.md` and execute it.**
This is **section 7 step 3** of the owner-approved contract at
`docs/pm/agentic-mvp-contract-2026-11-03.md`. **No model run, and no test may
contact a model server** — inject a fake client, the way
`tests/test_session_eval.py` already does.

**Branch from `main` at `ec7787a`, work in your own worktree, and commit to
your own branch — never to `main`.** The security engineer is on brief 14 in
`agent.py` and its tests at the same time. The manager merges.

## Why one category and not thirty-six trials

The contract wants 6 categories × 2 variants × 3 repeats. **A record format
that turns out wrong costs all 36 trials**, and this project has paid that
bill twice already: three questions in the old bank were scored on tool choice
alone and read as though their answers had passed, and a run record carried
the commit but not whether the tree was clean, so a void run pooled with ten
good ones. Both were found by reading the artifact afterwards.

So build **evidence grounding** end to end. Its oracle requirement is "exact
expected value derived independently from the fixture", which is exactly the
defect that killed the old instrument.

## What to build

1. **An immutable synthetic fixture with a hash** over a defined ordering, and
   the hash in the record. Not the repository, and **not `eval-fixture/`** —
   that directory is the subject of a question in the old bank. Say what you
   named yours.
2. **An oracle that derives the expected value from the fixture at load
   time**, the way `scripts/holdout_eval.py:41 _lines()` does. Never stored.
   **The answer key must be unreachable by the agent's six tools**: reuse
   `sealed_workspace` and extend the invariant in
   `tests/test_eval_workspace.py` to cover your fixture. Build that test and
   watch it fail before you trust the seal.
3. **Two variants, three repeats — six trials, individually readable, never
   averaged.** Three repeats at temperature 0 is not determinism insurance:
   this project measured one question answering 1 in 10 one day and 6 in 10
   two days later with unchanged text.
4. **The trial record exactly as the contract lists it**: IDs and arm, the
   exact commit **and a clean-tree assertion**, fixture and protocol hashes,
   model tag and digest, endpoint **classification** (`loopback`) and never
   the URL, temperature/`max_steps`/timeout/retry/allowlist, tool names,
   sanitized status, step count, execution status, score. And **none** of:
   prompts, reasoning, raw replies, file contents, raw observations, raw
   arguments, raw errors, the URL. Build it as a **pure function and test it
   directly**, the way brief 12's `question_record()` is.
5. **The allowlist as data.** Declare it per task and check it evaluator-side.
   **Dispatcher enforcement is not in this brief** — it is the security
   engineer's and `tools.py` is forbidden to you. Say in `## Result` that it is
   not done and not yours.

## Mutations — restore from a scratchpad copy, never `git checkout --` alone

Ma hardcode the expected value instead of deriving it, then edit the fixture ·
**Mb write the expected value where the sealed workspace can read it** · Mc add
the prompt to the record · Md average the three repeats into one row · Me drop
the clean-tree field.

**Mb is the one to take seriously.** The seal has moved a leak instead of
closing it once before, and the invariant only covers what it reaches. If Mb
stays green, the invariant is not covering your fixture — report it, do not
patch around it.

## Files you may touch

A new fixture directory · a new module under `scripts/` · a new test module ·
`tests/test_eval_workspace.py`, only to extend the invariant over your fixture.

## Files you may not touch

**`agent.py`, `tests/test_config.py`, `tests/test_endpoint_policy.py`,
`tests/test_local_only.py` — brief 14 is in those right now.** Also
`tools.py` · `sandbox.py` · `secure_search.py` and its branches ·
`scripts/holdout_eval.py` · `scripts/eval_scoring.py` ·
`scripts/eval_workspace.py` · `scripts/session_eval.py` · `eval-fixture/**` ·
`questions/**` · `models/**` · `data/**` · `omniagent-core/**` ·
`.github/workflows/**` · `NEXT_CHAT.md` · `README.md` · `omniagent.toml` ·
`docs/` except your `## Result`.

`scripts/eval_workspace.py` is forbidden although you need `sealed_workspace`
from it: **import it, do not edit it.** If you believe it must change, say so
in `## Result` and stop. It holds the answer-key seal and three briefs have
had to route around it.

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

## The split

**No cohort is authorized by anything.** The contract gates it behind six
security gates, a frozen threshold and an owner decision. Your deliverable is
a harness that runs on a fake client and a record format that survives being
read. The manager runs the probe and, if the owner authorizes it, the cohort.

## Commits

```
git add <fixture dir> scripts/ tests/
git commit -m "measure: one evidence-grounding category with a derived oracle"

git add docs/pm/brief-15-one-category-with-a-real-oracle.md
git commit -m "docs: brief 15 result -- the oracle and the trial record, proved on one category"
```

**Do not run a bare `git push`** — two remotes. Name it:
`git push origin <your branch>`.

## The one thing that would make this wrong

**Building thirty-six trials on an untested record.** That is why this is one
category. If the pattern starts to feel obvious and you find yourself writing
the other five, stop and report that the pattern is ready instead.

The second way: **an oracle that stores its answer.** Same defect as a
substring expectation, one level up — the figure falls when someone edits a
fixture, for a reason that is not the model. Ma exists to make you watch it.
