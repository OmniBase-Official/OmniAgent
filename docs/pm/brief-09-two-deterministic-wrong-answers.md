# Brief 09 — two deterministic wrong answers, and a record that is stale

**For the SWE.** Static investigation; the trace run is the manager's half and
is named at the bottom.

## What I retract first

Yesterday I wrote that the expectations `50` and `512` were "new to the record"
and "two new diagnosable defects". **Both were already recorded**, at
`NEXT_CHAT.md:390` and `:391`. I did not check before writing it. The figures
were right; the claim of novelty was not.

And the record itself is now stale for one of them, which is the finding this
brief exists for.

## What is measured, 2026-10-25, over the ten runs of 2026-10-24

Both wrong answers are **byte-identical in all ten runs** — md5 `7ea0d762` and
`aec8b082` over the answer line, every run. These are not flaky.

### The percentage chain

A four-step follow-up chain ending at `scripts/holdout_eval.py:110`. The
arithmetic is sound: 144 × 12 = 1728, − 728 = 1000, half = 500, 10% = **50**.
Steps one to three pass. The fourth answers

> `10% of 1000 is 100.`

So the agent resolves "that" to the **step-two** answer, not the step-three
answer. `NEXT_CHAT.md:390` already calls this a "known referent error, resolves
'that' to the step-2 answer" and quotes the same reply. **The record is correct
and current. Nothing about this one is new except that it is now settled on
ten runs rather than asserted.**

### The line-count ellipsis — the record is wrong

An elliptical follow-up at `scripts/holdout_eval.py:114`, `prefer_tool`
`file_info`, expectation computed as `_lines("scripts/build_notebook.py")`.

`NEXT_CHAT.md:391` records the failure as *"cannot be read because it is too
long"* — a "known elliptical-follow-up failure", and `:584` says v2 improved on
exactly that. **That is no longer what happens.** Measured today:

| Thing | Value |
| --- | --- |
| `_lines(...)`, i.e. the expectation | **512** |
| what `file_info` reports to the agent | **512 lines, 16,767 bytes** |
| `text.count("\n") + 1` | 513 |
| the file ends with a newline | yes |
| **what the agent answers** | **`scripts/build_notebook.py has 513 lines.`** |
| tools it called | `read_file`, `file_info`, `get_current_time`, `calculate` |
| tool axis | **passes** |

**The agent resolves the ellipsis, picks the right tool, is handed 512 by that
tool, and then states 513.** It is off by exactly one, and it called
`calculate` on the way. The instrument is not at fault: the expectation and the
tool agree on 512.

So the current failure is **not** the documented one. v2 did improve on the
ellipsis; what is left is an arithmetic step the agent takes after already
having the answer. The entry at `:391` describes a model that no longer exists.

## Goal

Three things, in order of what they are worth.

1. **Correct `NEXT_CHAT.md:391`** so it describes the failure that happens now.
2. **Establish why 513.** The strongest hypothesis is that the agent reasons
   "lines = newlines + 1" and uses `calculate` to add one to a number it
   already has. `text.count("\n") + 1` is exactly 513, which is suggestive and
   is not proof.
3. **Say whether either is fixable at all**, and by what. If the answer is
   "neither, at this model size", that is a legitimate and useful result — the
   `4740` question is already recorded as an irreducible capability failure, and
   a fourth entry in that category is worth more than a question quietly
   rewritten to pass.

## What you can do without a model — this is your half

1. **Read the system prompt and every tool description** for anything that
   invites a +1 on a line count, or that describes a line count in terms of
   newlines. `tools.py`'s `file_info` docstring and its rendered output are the
   first place to look; the rendered form is `"<path>: 512 lines, 16,767
   bytes"`, which is unambiguous, so if the inducement exists it is elsewhere.
2. **Check the training data.** Scan
   `G:/OmniAgent/datasets/2026-10-10-merged/` for examples that answer a
   line-count question, and report whether any of them is off by one against
   the file as it stood, or phrases a line count as newlines plus one. 2,215
   examples, three `.jsonl` files; the scan from brief 07 works unchanged. **If
   the training data taught the +1, that is the answer and it is a collection
   defect, not a model one.**
3. **Check whether `_lines` and `file_info` can ever disagree.** They agree on
   this file today. Find out whether they agree by construction or by accident
   — a file without a trailing newline, or with `\r\n`, is the interesting case.
   If they can diverge, the question is gradeable only by luck and that is a
   separate defect worth its own entry.
4. For the percentage chain, **check whether the referent error is in the
   training data too**: does any collected example resolve a pronoun to an
   earlier step than the immediately preceding one?

Report what you find and what you looked at and did not find. A negative result
here is useful and must be stated as one, not omitted.

## What you must not do

**Do not change either question to make it pass.** If the agent is wrong, the
question is working. The only reason to touch a question is if the *expectation*
is wrong, and for both of these it is not — the arithmetic is sound and the
expectation agrees with the tool.

Do not change `tools.py` — it is still in flight with the fullstack engineer on
brief 03, and in any case a tool description reaches the model on every turn and
is part of every training example, so changing one invalidates the dataset.

## Files you may touch

- `NEXT_CHAT.md` — **only** the stale entry at `:391` and only to make it
  describe what now happens. Strike in place, do not delete.
- `docs/pm/brief-09-two-deterministic-wrong-answers.md` — your `## Result`

## Files you may not touch

`tools.py` · `sandbox.py` · `scripts/holdout_eval.py` ·
`scripts/eval_scoring.py` · `scripts/eval_workspace.py` ·
`scripts/collect_dataset.py` · `tests/**` · `eval-fixture/**` ·
`questions/**` · `models/**` · `data/**` · `omniagent-core/**` ·
`.github/workflows/**` · `README.md` · anything on `core-offline-runtime`.

**No question and no expectation changes in this brief at all.** If a file is in
neither list, ask rather than decide.

## The three gates

```
.venv\Scripts\python.exe -m ruff check .
.venv\Scripts\python.exe -m mypy
.venv\Scripts\python.exe -m pytest
```

Full path, **no `-q` of your own**. Baseline **633 passed**. You are editing one
Markdown file and writing a report, so the count must not move. If it does, you
touched something outside your list.

## The split

You cannot run the agent: your sandbox returns `WinError 10013` on `localhost`,
confirmed twice on 2026-10-24.

| Half | Owner |
| --- | --- |
| the prompt and tool-description review, the two training-data scans, the `_lines` vs `file_info` divergence question, the `NEXT_CHAT.md` correction, the gates, the commit | **you** |
| a run with the tool arguments printed, to see what `calculate` was actually asked, and any re-measurement of either question | **the project manager** |

**Do not report a measurement you did not produce.** Say plainly that the trace
run is outstanding and whose it is.

## The one thing that would make this wrong

**Concluding from the hypothesis.** `text.count("\n") + 1` being exactly 513 is
suggestive and proves nothing: a model can be off by one for many reasons, and
`calculate` appearing in the trace does not say what it computed. If your scans
come back empty, the honest result is "the inducement is not in the prompt or
the data, and the trace run is needed" — not a story about newlines.

The second way: treating a stale record as a wrong measurement. `NEXT_CHAT.md:391`
was **right when it was written**. v2 improved on the ellipsis, as `:584`
records. The entry is stale, not false, and the correction should say so.

## Commit

```
git add NEXT_CHAT.md docs/pm/brief-09-two-deterministic-wrong-answers.md
git commit -m "docs: the line-count follow-up fails differently than the record says"
```

**Do not run a bare `git push`** — two remotes, and `main` tracks the one this
work does not belong to.

## Result

<!-- Engineer: append here. What you reviewed and what you found, including
negative results. The two training-data scan commands and their counts. The
_lines vs file_info divergence answer. The NEXT_CHAT correction you made. The
three gate results, the commit hash, and anything you refuse to claim --
including that the trace run is the manager's and is outstanding. -->

## Result

### Prompt and tool descriptions

Reviewed `SYSTEM_PROMPT_TEMPLATE` with the live `describe_tools()` rendering, including all six registered tool descriptions and their argument descriptions. The system prompt requires `calculate` for arithmetic and describes `read_file` as line-numbered; `file_info` explicitly reports a line count. Neither the assembled prompt nor the tool descriptions define a line count as newline count plus one, mention that formula, or otherwise instruct a +1. Internal comments in `agent.py` discuss earlier line-count failures, but those comments are not injected into the runtime prompt. I found no prompt-side explanation for the observed answer; the trace is needed to establish what arithmetic was performed.

### Training-data scan 1: line counts

Scanned all 2,215 nonblank examples in the three files under `G:/OmniAgent/datasets/2026-10-10-merged/` (1,404 in `collect-2026-10-07.jsonl`, 658 in `collect-2026-10-10.jsonl`, 153 in `dataset-merged-2026-10-10.jsonl`). The PowerShell command was an inline Python scan piped to ` .\.venv\Scripts\python.exe -`; it parsed log events and merged `messages`, selected line-count questions, and compared final-answer counts against the corresponding `file_info` observations.

- Collected logs: 9 line-count turns, all 9 with a `file_info` fact; 0 answers off by one.
- Merged conversations: 11 line-count question occurrences; 9 include a `file_info` observation and all 9 answers match it. Two answer-only copies match the corresponding tool-backed examples elsewhere in the corpus. 0 off-by-one answers found.
- No line-count answer phrases a count as newlines plus one. The two literal `newline` matches in the corpus are search observations describing newline-delimited JSON logs; neither discusses line counting.

### Training-data scan 2: follow-up referents

A second inline Python scan piped to ` .\.venv\Scripts\python.exe -` grouped collected log turns by file, session and turn, and walked merged conversations in order. It selected follow-ups containing referential cues (`that`, `it`, `this`, `these`, `those`, `the result`, `the answer`, or `the number`), then inspected the preceding questions and answers.

- 17 follow-up contexts in collected logs and 18 in the merged conversations were inspected; the merged set repeats some collected examples.
- I found no example resolving a pronoun to an answer older than the immediately preceding step. The multi-step arithmetic chains resolve to the immediately preceding result. Negative result: the collected examples do not reproduce the observed referent error.

### `_lines` and `file_info`

`_lines` uses `Path.read_text(...).splitlines()`. `file_info` uses `Workspace.describe`, which iterates the file as raw bytes and splits records on LF. They agree for LF, CRLF, and a final line without a newline; they do **not** agree by construction. In-memory checks of the exact underlying operations gave 2 vs 1 lines for bare-CR input and 2 vs 1 for a Unicode line separator. The current `scripts/build_notebook.py` is CRLF, ends with a newline, and both implementations report 512 lines, so this case is unaffected. This is a separate helper-contract mismatch; I did not edit other files because the brief permits only the stale `NEXT_CHAT.md` entry and this report.

### Record and remaining trace

Struck the stale entry at `NEXT_CHAT.md:391` in place and rewrote it to say that v2 now resolves the ellipsis, receives the correct `file_info` count, but answers one higher; the tool axis passes and the expectation agrees with the tool. The previous entry was stale, not false when written. The static scans do not establish why the agent adds one. The tool-argument trace run is outstanding and belongs to the project manager.

Gates: `ruff check .` passed; `mypy` passed with no issues across 42 files; full `pytest` passed, **633 passed**. Neither question nor expectation was edited. Commit and push are not yet performed.

---

## PM verification and the trace run — 2026-10-26

### The engineer's half: accepted, and the negative results are the valuable part

All three scans came back empty and were **reported as results rather than
omitted**, which is what made the trace run worth doing:

- **Prompt and tool descriptions:** nothing defines a line count as newlines
  plus one, mentions that formula, or instructs an increment. The comments in
  `agent.py` that discuss earlier line-count failures are **not** injected into
  the runtime prompt — a distinction worth having checked.
- **Line-count scan:** 2,215 examples (1,404 / 658 / 153 across the three
  files). 9 line-count turns in the collected logs, all with a `file_info`
  fact, **0 off by one**. 11 occurrences in the merged conversations, 9 with a
  tool observation, **all 9 matching**. No answer phrases a count as newlines
  plus one.
- **Referent scan:** 17 + 18 follow-up contexts inspected. **No example
  resolves a pronoun to an answer older than the immediately preceding step.**

The `NEXT_CHAT.md:391` correction is right: struck in place, says **stale**
rather than false, describes what now happens, and states that the cause was
not established.

**A separate finding the brief did not ask for and got anyway:** `_lines` uses
`splitlines()` while `file_info` splits raw bytes on LF, and **they do not
agree by construction** — they diverge on a bare CR and on a Unicode line
separator, 2 against 1 in both cases. They agree for LF, CRLF and a missing
final newline, so `scripts/build_notebook.py` is unaffected today. That is a
helper-contract mismatch living under a question graded by one of the two. It
is recorded and not fixed, correctly, since the brief permitted neither file.

One inconsistency, minor: the report's last line says commit and push are not
yet performed, while the report itself is inside commit `0a4f757`. The text was
written before the commit and then committed with it. Nothing is wrong with the
work.

### The trace run — my half, and it closes both diagnoses

Both sessions replayed with each step's **argument** printed, which the
evaluation's own output does not show. Same agent construction as
`holdout_eval.evaluate`: sealed workspace, `omniagent-v2`, `max_steps=8`,
temperature 0.

**The line count. The agent adds one on purpose.**

    step 1: read_file('scripts/build_notebook.py')
            -> Error: ... too long to return in full ...
    step 2: file_info('scripts/build_notebook.py')
            -> scripts/build_notebook.py: 512 lines, 16,767 bytes
    step 3: get_current_time('')
    step 4: calculate('512 + 1')
            -> 512 + 1 = 513
    ANSWER: scripts/build_notebook.py has 513 lines.

It is handed **512** by the tool the question prefers, and then explicitly asks
the calculator to add one. This is not a transcription slip or a parsing
error: it is a deliberate increment of a count it already had. The hypothesis
in this brief was that it reasons "lines = newlines + 1"; the trace supports it
and does not prove the reasoning, because the thought text is not captured —
but the *action* is unambiguous.

Note `get_current_time` at step 3, between having the answer and spoiling it.
That is `NEXT_CHAT.md` item 3's failure to stop after a correct first
observation, visible in the same five steps.

**The referent error. It skips back exactly one step.**

    [chain step 3] calculate('1000 / 2')   -> 500   ANSWER: Half of 1000 is 500.
    [chain step 4] calculate('1000 * 0.1') -> 100   ANSWER: 10% of 1000 is 100.

Having just produced **500**, it feeds **1000** — the step-two result — into
the next calculation. `NEXT_CHAT.md:390` described this from the answer text
alone; the trace confirms it from the argument.

### What this means, and it is not comfortable

The scans found no inducement in the prompt and none in the 2,215 training
examples, for either failure. The trace shows both are deliberate actions the
model takes. **So both are the model's own priors, not something this project
taught it** — the same category as the `4740` question, already recorded as an
irreducible capability failure.

**Neither is fixable by editing a question, a prompt, or the existing
dataset.** The honest options are to record them as known model limits, or to
address them at fine-tune time with targeted examples, which needs a fresh
collection run. Rewriting either question so it passes would measure nothing.

### A gap in the instrument, found in passing

The third question of the line-count session is scored on tool choice only
(`expect=None`). In the trace it derails completely for nine steps — it tries
a `len` call inside `calculate`, passes two paths as one filename to
`read_file` and `list_directory`, feeds raw JSON as a query string to
`search_text` twice, and finally answers a question nobody asked, about whether
`README.md` appears in either file.

It is recorded as **"no check"**, which is to say *not wrong*. **A question
scored on tool choice alone can hide a total derailment**, and this one does.
That is a defect in the measurement, not in the model, and it belongs on the
open list.
