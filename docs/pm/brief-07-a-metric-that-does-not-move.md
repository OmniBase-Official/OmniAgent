# Brief 07 — rebuild the question whose subject the evaluation writes into

**For the SWE.**

`NEXT_CHAT.md` item 0b has carried this since 2026-10-06: a metric that moves
when you measure is not a metric. This brief closes it.

## Read this before anything else — the brief cannot quote its own subject

`tests/test_eval_workspace.py:157 test_no_reachable_file_holds_a_held_out_question`
fails if **any file the agent can reach** contains a held-out question's text,
and `:175` does the same for an expected answer. `docs/` is reachable.
`_DISTINCTIVE` is **12** characters.

So this brief identifies the question **by file and line only** and quotes
neither its text nor its expectation. **You must do the same.** The new question
text and the new expectation go in `scripts/holdout_eval.py` and nowhere else —
not in your `## Result`, not in a commit message, not in a scratch script left
inside the repository. A file that leaks either one turns a green suite red,
and the suite being red is that invariant working.

If you find yourself wanting to paste the question into a report, write
"the question at `scripts/holdout_eval.py:96`" instead.

## What is measured, 2026-10-24, on HEAD `cca7c6a`

The question is `scripts/holdout_eval.py:96`. Its `prefer_tool` is
`list_directory` and its subject is `data/`.

| Fact | Value |
| --- | --- |
| files in `data/` today | **101** — `NEXT_CHAT.md` recorded 85 on 2026-10-11 |
| what `list_directory` returns for that subject | **3,742 characters, 102 lines** |
| is the expected string still in the tool's output? | **yes** |
| does the expected file still exist? | yes, 17,128 bytes, dated 2026-10-02 |
| what `judge()` compares the expectation against | **the agent's final answer**, `scripts/eval_scoring.py:88`: `question.expect in answer.replace(",", "")` |

### The diagnosis, which is not the one in the notes

The notes say the question broke because `data/` is the output directory every
run writes into. That is the cause but not the mechanism, and the mechanism
decides what a fix has to do.

**The expectation is still present in the tool output. It is absent from the
answer.** `judge()` grades the final answer only, so the question requires the
agent to relay one arbitrary entry out of 102 into its reply. An agent that
lists the directory correctly and then summarises it — which is the sensible
reply to a 102-entry listing — is graded WRONG while being right. As the
directory fills, the chance of that one entry surviving into the summary falls.
**The metric degrades as a function of how often it is measured.**

This is the standard this project already keeps: a substring expectation grades
characters, not answers.

## The ruling: rebuild, do not retire

Measured by parsing `scripts/holdout_eval.py` with `ast`: **19 `Question`
objects, 1 unanswerable**, and `prefer_tool` distributed as `None` ×12,
`file_info` ×5, `search_text` ×1, **`list_directory` ×1 — this question.**

Retiring it takes `list_directory` coverage in the holdout evaluation to
**zero**. That is the cost, and it is why the answer is rebuild.

## Goal

A question that exercises `list_directory`, whose correct answer does not
change when the evaluation runs, and whose expectation is the answer rather
than a character sequence that happens to appear near it.

## Step 0 — tell me whether you can run this at all, before you build anything

This brief's verification needs **ten runs of the holdout evaluation against
Ollama on `localhost:11434`**. Before you change a line, establish that you can:

1. Check whether Ollama is already up — it does not autostart but it may
   already be running:
   `.venv\Scripts\python.exe -c "import httpx;print(httpx.get('http://localhost:11434/api/tags').status_code)"`
   To start it, in PowerShell:
   `Start-Process "$env:LOCALAPPDATA\Programs\Ollama\ollama.exe" -ArgumentList "serve" -WindowStyle Hidden`,
   then wait about 15 seconds. `&` from bash does not work.
2. Run the evaluation for **one** session and report what came back.

**If you cannot get that far, stop and say so in `## Result`.** The brief then
splits: you design the replacement and I run the ten. That is a planned
outcome, not a failure — do not work around it, and do not report numbers you
did not produce.

## Choosing the subject — the part that decides whether this works

The new subject must be a directory that **nothing the evaluation or the test
suite writes into**. Candidates, with tracked file counts:

| Directory | Tracked files | Note |
| --- | --- | --- |
| `data/` | — | **disqualified.** Every run writes here. |
| `scripts/` | 11 | `NEXT_CHAT.md:221` records it as **contaminated** — listings appear 33× and 14× in the dataset |
| `tests/` | 27 | pytest creates `__pycache__` here, which is visible to `list_directory`. Verify before adopting. |
| `docs/` | 17 | nothing in the repository writes here |
| `notebooks/` | 1 | too small to need a listing |

Tracked counts are not listings. **`list_directory` shows what is on disk**,
including untracked and generated entries, so verify your candidate's listing
is byte-identical before and after a full `pytest` run and after one evaluation
run. A subject that changes under either is `data/` again with a different name.

### The contamination check is not optional

Before adopting a subject, check it against the published dataset at
`G:/OmniAgent/datasets/2026-10-10-merged/` — 153 examples, present and
readable. Search the collected `.jsonl` files for listings of your candidate
directory and for its distinctive entries. If the model was trained on a
listing of that directory, the question measures recall, not tool use.

There is no script for this; it has been done by hand each time. Write down the
command you used and its output, so the next person runs the same check instead
of inventing a third one.

## Designing the expectation

The failure above is a question whose right answer is a 102-line listing and
whose expectation is one line of it. Avoid repeating that shape:

- Prefer a question with **one** right answer that the agent cannot summarise
  away, over "what is inside X".
- The expectation must be what makes the answer right, not a string that
  merely co-occurs with it.
- Keep `prefer_tool="list_directory"`, because restoring that coverage is the
  point of rebuilding rather than retiring.
- Mind `_DISTINCTIVE = 12`: an expectation of 12 characters or more is checked
  against every reachable file by `tests/test_eval_workspace.py`. Shorter is
  not safer — it is just unchecked. Choose one that is correct, and let the
  invariant tests tell you where it may live.
- `tests/test_eval_workspace.py:199` and `:219` already constrain expectations
  and subjects. Read both before you choose; they encode two earlier mistakes.

## Ten runs, not three

Three runs have twice produced a conclusion that ten reversed. The new
question's score is settled on **ten**, and the old question's replacement is
not "better" until ten runs say so with the variance stated.

- **Write the prediction before the first run.** A finding produced after the
  fact is a story told about a number.
- **Never two model runs at once.** The card is 4 GB and two runs fight over it.
- **A command over 600 seconds is backgrounded and dies with the session.** A
  full holdout run measured 544 s. Start each one in the background on purpose
  and do other work while it runs.
- **Always redirect an evaluation to `data/`** — it prints and keeps nothing,
  and `data/` is gitignored so the records stay local. Yes, that is the same
  directory this brief is removing from the question; writing results there is
  fine, measuring it is not.
- Report all ten results, not a mean. If the variance is not zero, say what it
  was.

## Mutation checks that must go red

Scratch copies **outside the repository**; restore from them; never
`git checkout --` alone; assert the target string is present before replacing
it, because a `sed` pattern containing `\n` matches nothing silently.

| # | Mutation | Must go red |
| --- | --- | --- |
| M1 | Change the new expectation to something the right answer does not contain | the new question scores WRONG — proves the expectation is load-bearing |
| M2 | Change `prefer_tool` to a tool that cannot answer it | the tool-choice axis, not the answer axis. Name which, and say whether the answer axis stayed green |
| M3 | Add a file to the new subject directory | **the score must not move.** This is the whole brief. If it moves, the subject is as unstable as `data/` was |
| M4 | Put the new expectation into a reachable file under `docs/` | `tests/test_eval_workspace.py:175` goes red. Then delete that file — do not commit it |

M3 is the one that matters. M4 proves you understand why this brief cannot
quote itself.

## The three gates

```
.venv\Scripts\python.exe -m ruff check .
.venv\Scripts\python.exe -m mypy
.venv\Scripts\python.exe -m pytest
```

Full path, **no `-q` of your own** (`pyproject.toml:168` already sets it; a
second one deletes the summary line). Baseline **633 passed**. Changing a
question may change how many tests the eval-workspace module generates — if the
count moves, explain why rather than accepting it.

## Files you may touch

- `scripts/holdout_eval.py`
- `tests/test_eval_workspace.py` — **only** if an invariant needs to learn about
  the new subject, and say so explicitly if you touch it

## Files you may not touch

`tools.py` · `sandbox.py` · `scripts/eval_scoring.py` ·
`scripts/collect_dataset.py` · `questions/**` · `models/**` · `data/**` except
as a destination for run output · `omniagent-core/**` ·
`.github/workflows/**` · `NEXT_CHAT.md` · `docs/` except your `## Result` ·
anything on the `core-offline-runtime` branch.

**`tools.py` is in flight with the fullstack engineer on brief 03.** Do not
edit it, and do not change tool behaviour to make a question easier.

If a file is in neither list, ask rather than decide.

## The one thing that would make this wrong

**Replacing one unstable subject with another.** `data/` failed because the
evaluation writes into it. A subject that pytest writes into, or that gains a
`__pycache__`, or whose listing differs between a clean clone and this working
tree, fails the same way on a longer fuse — and the next person will have to
find it the way this one was found, from a score that drifted. M3 is the check
that catches it before it ships.

The second way: making the expectation easy enough to always pass. A question
that cannot be failed measures nothing, exactly like the test replaced in
brief 02.

## Commit

```
git add scripts/holdout_eval.py
git commit -m "measure: the list_directory question no longer asks about a directory we write to"
```

Add `tests/test_eval_workspace.py` only if you changed it, and say why in the
message. **Do not run a bare `git push`** — two remotes, and `main` tracks the
one this work does not belong to.

## Result

<!-- Engineer: append here. Step 0's outcome first. Then the subject you chose
and why, the contamination check command and its output, the stability
evidence, your prediction, all ten run results with variance, M1 to M4, the
three gate results, the commit hash, and anything you refuse to claim.
Quote neither the question text nor the expectation. -->

Step 0: blocked. The Ollama health check failed with WinError 10013 (localhost socket access forbidden). The brief's specified startup command could not find ollama.exe at its configured path, and the retry failed with the same socket error. I could not run the required single-session evaluation, so I stopped before building or changing evaluation data.

---

## PM note on Step 0 — 2026-10-24

**The engineer stopped at Step 0 and reported it, which is exactly what Step 0
is for.** No evaluation data was touched. That is the brief working, not a
failure.

### What was wrong, measured rather than assumed

| Claim in the report | Checked by the manager |
| --- | --- |
| the health check failed | **Ollama was not running at all.** No `ollama` process existed. |
| `ollama.exe` not found at the configured path | **The file is there**, at `AppData/Local/Programs/Ollama/ollama.exe`. The trap list's path is correct. |
| `WinError 10013` | **I get `WinError 10061` from the same endpoint** — "actively refused", the ordinary nothing-is-listening error. |

**`10061` and `10013` are not the same failure, and the difference is the whole
diagnosis.**

- **`10061`, connection refused** — nothing is listening. Start Ollama.
- **`10013`, socket access forbidden** — the *environment* is refusing to let
  the process open the socket. Starting Ollama does not fix that.

The engineer saw `10013` where the manager sees `10061` against the same
address, so there is a sandbox difference between the two environments. What is
**not** yet known is whether that block applies when something is actually
listening — Windows can return either code when the port is empty.

### Ollama is now running

Started with the trap list's own command, and it answers:

```
HTTP 200
omniagent-v2:latest, omniagent:latest, omniagent-v1:latest, qwen-ctx8k:latest, …
```

`omniagent-v2:latest` is the shipped demo model, so the evaluation has what it
needs. It will stay up for this session.

### So: retry Step 0 before anything is reassigned

One command answers the question the brief was built to answer, and guessing it
costs a round trip either way.

**If the retry succeeds**, execute brief 07 whole — nothing about it changes.

**If the retry still returns `10013`**, the sandbox block is confirmed and the
brief splits as it said it would. The halves, so neither of us has to ask:

| Half | Owner | Scope |
| --- | --- | --- |
| design | **the SWE** | choose the subject; prove its listing is stable across a full `pytest` run and an evaluation run; run the contamination check against `G:/OmniAgent/datasets/2026-10-10-merged/` and record the command; design the question and expectation; **M4** (expectation in a reachable `docs/` file turns `tests/test_eval_workspace.py:175` red, then delete that file); the three gates; commit |
| measurement | **the project manager** | the prediction written first, then **M1**, **M2**, **M3** and the ten runs with variance stated |

The design half needs no model at all. Hand it over with the question and
expectation **in `scripts/holdout_eval.py` only** — the constraint at the top of
this brief does not relax because the work was split.

Do not report a measurement you did not produce, in either half.

Step 0 retry: `WinError 10013` (socket access forbidden), verbatim. The manager's successful HTTP 200 is not reachable from this process, so I did not run an evaluation.

Design investigation stopped before changing the question. The brief's static candidate `docs/` is denied by `sealed_workspace` (`ANSWER_KEY` includes `docs`); a `list_directory` call against that evaluation workspace returns `Error: that file is not readable by the agent`. The other static candidate checked, `notebooks/`, is contaminated: `rg -n -F 'train_omniagent_lora.ipynb' 'G:/OmniAgent/datasets/2026-10-10-merged/' -g '*.jsonl'` finds training examples whose `list_directory` observations include that entry, with historical sizes 18,600, 19,518, and 20,846 bytes. It therefore measures recall and its listing differs from the current tree. The remaining obvious candidates are excluded by the brief (written-to directories, the contaminated scripts directory, tests with `__pycache__`, sealed directories, or generated build output).

No replacement question or expectation was written. M1, M2, M3, the ten runs, M4, gates, and commit remain unperformed. The permitted file list does not include `scripts/eval_workspace.py`; changing it to make `docs/` reachable requires the project manager to revise the scope or identify another eligible subject.

---

## PM note 2 — the candidate list is empty, and that is the finding

**2026-10-24. The engineer was right on both counts, and it escalated instead
of widening its own scope or picking a bad subject. That is the behaviour this
brief wanted.**

Also confirmed: **Step 0's retry returned `WinError 10013` again**, with Ollama
up and answering HTTP 200 for the manager. The sandbox block is real and
independent of whether anything is listening. **The measurement half is the
manager's from here.**

### What I got wrong in this brief

I recommended `docs/` as the strongest candidate — "17 tracked files, nothing
writes there". I never checked it against the seal. `scripts/eval_workspace.py:56`
puts **`docs`** in `ANSWER_KEY`, which makes it unreadable *and unnameable*: a
sealed workspace does not even list it. My recommendation was impossible and the
engineer found that in the first place it looked.

### Every candidate, measured under the sealed workspace

What a sealed workspace can list at the root is `__pycache__/`, `data/`,
`notebooks/`, `omniagent-core/`, `questions/`, `scripts/`, `tests/` and the
root `.py` files. `docs/` and `models/` are not named at all.

| Candidate | Sealed listing | Verdict |
| --- | --- | --- |
| `data/` | **101 entries** | written to by every run, and gitignored — **nothing in it is permanent**, so no expectation about it survives a clean clone. It is `LISTING_ONLY`, which is why the question chose it: listable, unreadable. |
| `tests/` | **20 entries** | includes `__pycache__/`, and nine test files are in `ANSWER_KEY` so they are **absent from the listing**. The listing is a function of `ANSWER_KEY` and changes when it does. |
| `notebooks/` | 1 entry, 20,846 bytes | **contaminated.** The dataset holds historical sizes 18,600, 19,518 and 20,846 for it. |
| `questions/` | 1 entry | **contaminated.** Scanning 2,215 examples in `G:/OmniAgent/datasets/2026-10-10-merged/`: `bank-2026-10-10` in **5**, `questions/` in **20**. |
| `omniagent-core/` | 1 entry, `build/` | local build artifact; absent from a clean clone of `main`. |
| `docs/`, `models/` | not named | sealed. |

For scale, `list_directory` itself appears in **421 of 2,215** examples, so the
*tool* is well represented in training. The problem is subject-specific recall,
not the tool.

**There is no existing directory in this repository that is listable, unsealed,
stable, uncontaminated and present in a clean clone.** That is why this brief
could not be executed as written, and it is a better finding than the one it
set out to produce.

### The contamination check, for the next person

No script existed. This is the one that was run, and it should be reused rather
than reinvented:

```python
import pathlib
base = pathlib.Path('G:/OmniAgent/datasets/2026-10-10-merged')
for f in sorted(base.glob('*.jsonl')):
    for line in f.read_text(encoding='utf-8', errors='ignore').splitlines():
        if line.strip() and '<candidate>' in line:
            ...  # count it
```

2,215 examples across `collect-2026-10-07.jsonl`,
`collect-2026-10-10.jsonl` and `dataset-merged-2026-10-10.jsonl`.

### Status

No replacement question was written. Nothing in `scripts/holdout_eval.py`
changed. The old question is still in place and still degrading. **The decision
about what subject can exist at all is the owner's and is on the table.**
