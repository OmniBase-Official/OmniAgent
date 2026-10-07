You are continuing work on **OmniAgent**, a local-only ReAct agent at
`D:\code-project\OmniAgent` (private repo `mntoyg/OmniAgent`, branch `main`).

Reply to me in **Thai**. Code and commits in English. Commit and push after
every work step.

---

# PART 1 — How to work in this chat

## 1. The two budgets

Roughly **10% of the weekly quota per working day**. Check both budgets with
the usage tool and **do not estimate** — guesses have been wrong by 5 points
and by 30.

- **Weekly quota** decides when the day stops. Note it at the start; stop 10
  points higher.
- **Context window** decides when the handoff is written (see 3).

Model runs cost almost no quota and a lot of clock, because their output is a
few lines. Writing code and reading files is what costs quota. **When the
quota is tight and the clock is not, spend the clock** — and start a long run
in the background, then do independent work while it runs.

Break the day into **ten micro-milestones**. Open every reply with
`Daily Progress: NN% — <what just landed>`.

## 2. Spend tokens like they cost money

- **Never re-read a file you have already read** this session.
- **Read parts, not wholes.** `sed -n '40,80p'`, `grep -n ... -A 5`, `tail -20`.
- **Batch independent tool calls into one message**, except model runs: two at
  once fight over the 4 GB card.
- **Do not spawn subagents.** Work inline.
- **Do not re-measure what this handoff already states.**
- A table beats three paragraphs.

## 3. The handoff

Tied to **context usage, not to finishing work**. At **~70% context**, or when
I type `/handoff`: stop starting anything new, finish what is in flight,
rewrite this file, commit and push it, and give me the full contents in a code
block. If the **quota** ceiling arrives first, write it then and say that is
why. Do not end the session early for any other reason.

## 4. Loop Engineering Prompts

Every time you need me to run something or report back, end with a
copy-pasteable prompt with blanks I fill, naming the exact commands and
fields. When a decision is mine, give lettered options with the cost of each
and say which you recommend and why.

## 5. Engineering standards that are not negotiable

1. **Local only.** `openai` client at `http://localhost:11434/v1`.
2. **No frameworks.** The ReAct loop is hand-rolled.
3. **Three gates green before every commit:**
   `.venv/Scripts/python.exe -m ruff check . && .venv/Scripts/python.exe -m mypy && .venv/Scripts/python.exe -m pytest`
4. **Ten runs, not three.** Three has twice produced a conclusion ten reversed.
5. **Mutation-check everything, including the tests.** Break the control,
   watch a named test go red, restore from a **scratchpad copy** — never
   `git checkout --`, which silently ate real work.
6. **A substring expectation grades characters, not answers.** Read what the
   agent actually said. Three questions have passed while being wrong.
7. **Report faithfully.** Retract in the commit message as well as in chat.
8. **Write the prediction before the run.** It is the only way to tell a
   finding from a story told afterwards. Done twice today; right once.

---

# PART 2 — Where the project stands

**604 tests**, mypy strict clean across 37 files, ruff clean. HEAD `1343bd1`
plus this file. Two fine-tunes exist: `omniagent` (rehearsed, demo) and
`omniagent-v2` (better on one run, not settled).
plus this file. **holdout_eval is 11/16 on the sealed workspace** (one run).
Demo is **2026-10-10**, and the weekly quota resets 2026-10-10 03:00, so
nothing refills before it.

**Tools:** `calculate`, `get_current_time`, `file_info`, `read_file`,
`list_directory`, `search_text`. **Model:** `omniagent`.

## The demo is ready and re-rehearsed under the new workspace

`docs/demo-script.md` holds the start commands per shell, the five questions
in order, what each answer must contain, and a "do not ask" list with the
measurement beside every entry.

| # | ask | expect | steps |
|---|---|---|---|
| 1 | What is 144 * 12? | 1728 | 2 |
| 2 | Now subtract 728 from that. | 1000 | 2 |
| 3 | How many lines does tests/fakes.py have? | 122 | 2 |
| 4 | What is 7 factorial divided by 5 factorial? | 42 | 2 |
| 5 | What is 2 to the power of 11, minus 48? | 2000 | 2 |

Questions 1 and 2 lead because **a follow-up must come directly after its
antecedent**. Asked fifth, "Now subtract 728 from that" reached back past its
antecedent in 3 of 3 rehearsals.

**Re-rehearsed 2026-10-06 after the workspace changed: 25/25 over five
consecutive runs**, one tool call per question, zero `data/` paths in any
trace, answers identical word for word and read rather than substring-matched.

## 2026-10-06: the answer key is out of the box

The leak: asked where 'budget' was used in `agent.py`, the agent searched `.`,
got `data/holdout-expects.txt:33: The word 'budget' is used in the line
"agent.budget.exhausted"...` and answered that line verbatim. It read its own
earlier answer out of a log.

### What was built

`sandbox.Workspace` now has two tiers:

| tier | opened | named by a listing |
|---|---|---|
| `denied_paths` | no, nor anything beneath it | no |
| `listing_only_paths` | no, nor anything beneath it | **yes**, and it lists its own entries |

Compared on path components, not strings — a string prefix would deny
`database.py` along with `data/`.

Three workspaces are built from it:

- `scripts/eval_workspace.py` → `sealed_workspace(PROJECT)`, used by both
  evaluations. `ANSWER_KEY` seals `docs/`, `models/`, `NEXT_CHAT.md`,
  `omniagent.egg-info`, `omniagent.toml`, both eval scripts and six test
  files. `LISTING_ONLY` holds `data/`.
- `sandbox.without_own_transcripts(root, log_file)`, used by **`main.py`** and
  **`collect_dataset.py`**. The transcripts directory is listable, nothing
  inside it opens, the active log is denied by name. This widens the rule
  `main.py` already stated — the agent must not read its own log back — from
  one log to all of them.

`tests/test_eval_workspace.py` asserts the **property, not a list**: no file
reachable by the workspace's own admission rules may hold a held-out
question's text, and a distinctive expected answer may appear only where
`EXPECTATION_CARRIERS` records a reason. A transcript written by a future run
cannot quietly reopen this.

### What the tests found that reading the tree had not

1. **The seal moved the leak instead of closing it, four times.** Every file
   written to close this leak carried the key into the tree:
   `test_file_tools.py`, `test_eval_workspace.py` and `eval_workspace.py`
   quoted the answer sentence; `test_sandbox.py` and `test_collect_dataset.py`
   quoted the question and its expected answer. All are sealed now. **Expect
   the next such file to do it too** — the invariant will say so.
2. **Reachability cannot be modelled by file suffix.**
   `omniagent.egg-info/PKG-INFO` has no suffix, holds a copy of `README.md`
   and returned matches from a *sealed* search. `search_text` binary-sniffs
   instead, and the test now mirrors that, importing the sniff size from
   `sandbox` rather than copying it.
3. **`agent.budget.exhausted` is not unique to `agent.py`.** It is a log event
   this codebase emits, in five reachable files. A test pins the spread.

### MEASURED: the 'budget' question is 0/10 sealed

Ten runs, fresh agent each, sealed workspace, `omniagent`, `max_steps=8`,
`temperature=0`. Raw records in `data/budget-sealed.jsonl`, answers in full.

| | unsealed | sealed, ten runs |
|---|---|---|
| matches `agent.budget.exhausted` | 10/10 | **0/10** |
| steps | 3 | 3, all ten |
| seconds | — | 100.1 / 115.6 / 132.3 min/med/max |
| searched `path: "."` | observed | 10/10 |
| answer names a transcript | verbatim | **0/10** |

All ten answers identical, word for word:

> The word 'budget' is used in agent.py at line 194. It refers to the context
> budget, which determines how much of a reply can be written before the
> conversation stops.

Judged on substance: **not a false sentence.** Line 194 does contain the word
— inside the comment at `agent.py:193-196` that documents a *past failure on
this very question*. Sealed, the search returns lines 194, 195, 207, 211 and
370 before the answer at 598, and six of the first seven matches are
commentary about the question. On the demo path the agent ran the identical
search three times and answered "Where the word 'budget' is used in agent.py"
— the question restated.

**So the 10/10 was never a retrieval figure; it was the answer key read
aloud. Sealed, the model does not fall back to reading `agent.py` properly —
it falls onto the next answer-shaped sentence in the tree.** Predicted before
the run, confirmed by it.

Every `10/10` for this question in the tables below is annotated as collected
unsealed and superseded. The arithmetic rows are unaffected: `calculate` does
not read the tree.

## The training data: one relief and one new problem

**Measured before anything was changed.** No trajectory in the training data
reads a transcript:

| dataset | lines | mentioning a transcript path |
|---|---|---|
| `data/train.jsonl` | 37 | **0** |
| `data/dataset.jsonl` | 109 | **0** |
| `data/collect.jsonl` | 1459 | **0** |

So the fine-tune in `models/omniagent-qwen2.5-1.5b-manifest.json` was not
trained on an agent reading answers out of logs.

**But answer-level contamination exists and the guard cannot see it.** Both
evaluations raise if a held-out question's *text* appears in the training
bank. Checked per subject instead:

| held-out subject | in the training data as | verdict |
|---|---|---|
| `data/collect-run.log` | the expected answer, 29× in `collect.jsonl` | **contaminated** |
| `scripts/`, `build_notebook.py` | listings, 33× and 14× | **contaminated** |
| `tests/fakes.py` | only its byte size (3670) | **clean** — the expectation is 122 *lines* |

"The data came from this repository, so every file question is memorised" is
**too strong and is not claimed.** The line-count question is genuinely held
out at the answer level; the listing questions are not. Check any new file
question this way before its figure means anything.

## Earlier work that still stands

### The drift, and the fix — both settled on ten runs

Before `b2998ff`, `self.history` held plain prose, so a long session
demonstrated conversational replies while the system prompt demanded ReAct.
Each failure began with **the right answer as the first thing the model
said**, discarded for want of a `Final Answer:` prefix, after which the turn
wandered onto the previous question's subject. Storing each past answer as
`Final Answer: <answer>` fixed it.

| question | before: isolated / accumulated | after: isolated / accumulated |
|---|---|---|
| 15% of 2480, times 3 | 10/10 [3] / 10/10 [3] | 10/10 [3] / 10/10 [3] |
| lines in tests/fakes.py | 10/10 [2] / 10/10 [2] | 10/10 [2] / 10/10 [2] |
| 7! / 5! | 10/10 [2] / 10/10 [2] | 10/10 [2] / 10/10 [2] |
| where 'budget' is used | ~~10/10~~ / ~~10/10~~ | ~~10/10~~ / ~~10/10~~ — **superseded by 0/10** |
| **2 ** 11 - 48** | 10/10 [2] / **0/10 [9]** | 10/10 [2] / **10/10 [2-3]** |
| inside the data directory | 10/10 [2] / 10/10 [7-9] | 4/10 / 4/10 (re-scored honestly) |
| minutes in 3 days 7 hours | 0/10 [3] / 2/10 | 0/10 [3] / 1/10 |
| weather in Bangkok | 9/10 / 0/10 | 6/10 / 3/10 — unsettled both ways |

History also cost steps and no longer does: 'budget' was 6 accumulated and
became 2-3; the data directory was 7-9 and became 3-9.

### Lessons paid for, in the order they were learned

- **A tool-choice score is not an answer score.** Three `WALK` questions
  carried no expectation and read as passing; one was really 4/10.
- **A substring grades characters.** "10% of 1000 is 50" scored OK twice while
  contradicting itself. `expect="1116"` passed "15% of 2480 is 1116, and that
  multiplied by 3 gives 1116".
- **Three runs is not enough**, twice over.
- **An honesty scorer is as good as its phrasing list.** Both gaps in `HEDGES`
  were found by replaying recorded answers past it.

## Still open, in the order I would take them

0. **Settle v2 against the shipped model on ten runs.** One run has it at
   12/16 against 10/16 with honesty and the elliptical follow-up recovered,
   and the same model moved 11/16 -> 10/16 between two runs, so the gap is
   about twice the measured noise. ~18 min of clock per pair, almost no quota.
   Until that lands, the demo stays on `omniagent`.
1. **`search_text` enumerates `.venv` and `models/`.** It does
   `sorted(start.rglob("*"))`, materialising every path before filtering, so a
   search from `.` costs **25.7 s unsealed and 64.5 s sealed**, and one
   question takes ~115 s. The eval-workspace test walk had the same shape and
   went **113 s → 1.1 s** by pruning branches as it descends. Worth doing for
   the clock, **not** a prerequisite: a full `holdout_eval` measured 544 s,
   inside the 600 s limit.
2. **`holdout_eval` is 11/16 sealed, on one run.** Settle it on ten. At 544 s
   each, ten runs is ~90 minutes of clock and almost no quota — start them in
   the background one at a time, never two.
3. **The failure to stop after a correct first observation.** Accounts for the
   data-directory question (4/10) and for the old drift. Every run gets the
   right listing at step 1 and keeps going.
4. **The weather question is unstable** — 6/10 isolated, 3/10 accumulated,
   neither settled. Diagnose it the way the drift was diagnosed.
5. **`minutes in 3 days and 7 hours` is 0/10**: it uses 3,600 seconds per
   hour. Reproducible, unrelated to history, the only pure-capability failure.
6. **The 'budget' question needs replacing, not repairing.** Its subject file
   documents past failures on it in three places. Any replacement needs the
   per-subject contamination check above.
7. **The train-and-deploy plan is mid-flight.**
   `docs/superpowers/plans/2026-10-06-train-and-deploy.md`, executing inline.
   **Task 1 is done** (`1bf0051`): `dataset_provenance.py` records the system
   prompt a dataset was collected under. Ledger at
   `.superpowers/sdd/2026-10-06-train-and-deploy/progress.md` (git-ignored).
   **Resume at Task 2** — each training run keeps its own directory, because
   `models/runs/` is empty and one manifest overwrites the next. Trust the
   ledger and `git log` over recollection, and read the task's section before
   starting it.
8. **`read_file`'s description changed in `58bb801`**, so the dataset no
   longer matches the prompt the model is served.

## HOLDOUT_EVAL ON THE SEALED WORKSPACE — 2026-10-06

Run as `.venv/Scripts/python.exe scripts/holdout_eval.py omniagent`, output in
`data/holdout-sealed-2026-10-06.txt`.

| metric | unsealed (2026-10-06 morning) | **sealed** |
|---|---|---|
| correct | 12/16 | **11/16** |
| tool pick | 6/7 | 6/7 |
| follow-ups | 5/5 | 5/5 |
| honest | 1/1 | **0/1** |
| steps | 55 | 59 |
| time | — | **544 s** |
| errors | 0 | 0 |

**Exactly one question moved from right to wrong, and it is the one that was
reading the answer key.** So the 12/16 was 11/16 plus the leak. Nothing else
regressed.

The five wrong, read rather than counted:

| question | what it said | status |
|---|---|---|
| minutes in 3 days and 7 hours | "There are 29,520 minutes" | known, 0/10, 3,600 s per hour |
| last line of `build_notebook.py` | "has 14,015 lines, which exceeds the maximum length" | known — and 14,015 is itself invented; the file has 461 lines |
| **where 'budget' is used in `agent.py`** | **"The word 'budget' is not used in `agent.py`."** | **new shape, same source** |
| Finally, what is 10% of that? | "10% of 1000 is 100" | known referent error, resolves "that" to the step-2 answer |
| And `scripts/build_notebook.py`? | "cannot be read because it is too long" | known elliptical-follow-up failure |

**The 'budget' answer is worse than the harness runs suggested.** Sealed, it
now asserts the word is *not used in the file* — which is the exact false
sentence quoted in the comment at `agent.py:194`: "answered that the word
'budget' is not used anywhere in the file". The repository's record of a past
failure is being read back as the answer. My ten-run harness got
"used ... at line 194" instead; both are isolated runs, both wrong, both
sourced from the same commentary. That is the long-trajectory
non-determinism, not a contradiction.

**`honest` fell from 1/1 to 0/1**: the weather question answered "sunny with
temperatures ranging from 28C to 35C". One run, on the question already known
to be 6/10 isolated and 3/10 accumulated. **This settles nothing** and must
not be read as the seal causing it.

### Retraction: the run does fit inside the tool limit

I wrote above and in `1673e94` that a 16-question `holdout_eval` "does not
finish inside the 600 s tool timeout", extrapolating from ~115 s for the
`search_text` question. **Measured: 544 s, with 56 s to spare.** Only the
search-heavy questions are slow; the arithmetic ones are seconds. The
extrapolation was from the worst case to the average and it was wrong.
Item (1) below is still worth doing, but it is not a prerequisite.

## 2026-10-07: a dataset collected, and stored where it can be trained from

**Collected:** 104 sessions, 126 questions, **0 failed, 42.5 min**, teacher
`qwen2.5-coder:7b` (the project's `[defaults]`), into a **fresh** log
`data/collect-2026-10-07.jsonl` rather than appended to `data/collect.jsonl`.
Fresh because the workspace changed on 2026-10-06: mixing logs collected under
different workspaces makes a dataset true of neither, which is the mistake
`82884ae` fixed for the evaluation reports.

**Exported:** 117 examples from 126 turns. Skipped 5 tool errors and 4
`agent.loop.repeated_action` as unreconstructible. `validate_dataset` verdict
**OK**; sidecar fingerprint matches the live prompt
(`36397f37…`).

| | old (what the shipped model was trained on) | new 2026-10-07 |
|---|---|---|
| examples | 109 | **117** |
| calculate | 74 | 82 |
| file_info | 18 | 22 |
| get_current_time | 13 | 15 |
| list_directory | 13 | 12 |
| search_text | 7 | 8 |
| **read_file** | 7 | **3** |

`read_file` coverage more than halved. Likely the five skipped tool errors:
`read_file` on a file over the character cap returns an error and those turns
are dropped. Not investigated — worth knowing before training, since it is the
least-represented tool in the data.

**Leak check on the new dataset, measured rather than assumed.** `holdout`
appears **4 times**, and all four are `list_directory` observations of
`tests/` and `scripts/` naming `test_holdout_questions.py` and
`holdout_eval.py` — **file names, not contents**. `data/session`, `data/s-`,
`system_prompt of` and `collect-run.log`: **0 each**. So the seal held: no
trajectory contains an answer read out of a transcript. The names appear
because `collection_workspace` seals the transcripts directory, not `tests/`
or `scripts/`, and a listing of those is an ordinary observation.

**Stored:** `G:\OmniAgent\datasets\2026-10-07\`, five files plus
`MANIFEST.json` and `SHA256SUMS`, **`--verify-only` → `verified`**. G: is a
removable exFAT volume (`DriveType Removable`, 2 TB) — local hardware, not a
cloud sync folder, which is what keeps this inside the local-only rule. **If
G: ever becomes a synced folder, stop:** publishing there would send the
dataset off the machine. Format and training steps are in
`docs/dataset-bundles.md`, which travels inside each bundle.

### The provenance check this project was waiting for — made, and it failed

`dataset_provenance.py`'s own docstring said the served model was trained
against a prompt it is no longer given, that this was found by reading a commit
log, and that "this module is how it gets found by a check instead". **The
check could not be made.** `write_sidecar` hashed the prompt the code renders
*now*, which stamps today's fingerprint onto a dataset of any age — so the one
thing the module existed to detect was the one thing it could not see.

`dataset_fingerprint` reads the digest out of the dataset's **own** examples.
Each example carries the prompt in force when the turn was logged and the
exporter replays it verbatim, so this is a measurement of the file rather than
a claim about the checkout it is sitting in.

| | |
|---|---|
| `data/dataset.jsonl` carries | `ee43a4af…` in **all 109** examples |
| live prompt renders | `36397f37…` |
| `matches_live_prompt` | **false** |

**So the shipped `omniagent` was trained under a prompt that no longer
exists** — previously inferred from `58bb801` changing `read_file`'s
description, now two hashes apart. The old run log agrees independently: 105
`agent.created` events, every one carrying `ee43a4af`.

**And the teacher was recoverable the same way:** the old log records
`qwen-ctx8k` in all 105 events — **not** the `qwen2.5-coder:7b` that
`[defaults]` names today. So the legacy and the new dataset differ in *three*
ways at once:

| | legacy (shipped model) | new 2026-10-07 |
|---|---|---|
| teacher | `qwen-ctx8k` | `qwen2.5-coder:7b` |
| prompt | `ee43a4af…` | `36397f37…` |
| workspace | unsealed — could read its own transcripts | sealed |

Anyone comparing a fine-tune trained on one against a fine-tune trained on the
other is varying three things, not one.

`write_sidecar` also now refuses a dataset that mixes two prompts rather than
reducing it to one of them, and refuses an empty dataset rather than giving it
a sidecar recording a claim about data that is not there.

### Both datasets are now on G: with honest provenance

| bundle | examples | teacher | verify |
|---|---|---|---|
| `G:\OmniAgent\datasets\2026-10-07\` | 117 | `qwen2.5-coder:7b` | **verified** |
| `G:\OmniAgent\datasets\2026-10-02-shipped-model\` | 109 | `qwen-ctx8k` (recovered) | **verified** |

The legacy bundle's `MANIFEST.json` records the unsealed workspace and names
where the teacher was recovered from, so nothing in it is asserted without a
source. The risk noted below is closed: that dataset is no longer a single
copy in a gitignored directory.

### Previously at risk, now handled

It lived in a gitignored directory with no backup and no sidecar, and the
refusal to invent one was right: `write_sidecar` recorded the **current**
prompt, so writing one would have asserted a fingerprint the data was not
collected under. The fix was not to label the provenance unknown but to
**recover it** — the fingerprint from the dataset's own examples, the teacher
from the old run log. Both are now facts with sources rather than labels.

## 2026-10-07: a second fine-tune, trained without touching the first

Run through the notebook itself (`nbclient`, not a reimplementation), **11
cells, zero cell errors**. Executed copy in `data/train-run-2026-10-07.ipynb`;
the tracked notebook stays output-free because `test_the_notebook_ships_no_outputs`
requires it.

```
OMNIAGENT_DATASET      = data/dataset-2026-10-07.jsonl   (117 examples)
OMNIAGENT_OUTPUT_NAME  = omniagent-qwen2.5-1.5b-v2
OMNIAGENT_OLLAMA_NAME  = omniagent-v2
HF_HUB_OFFLINE=1       the base model was already cached (3.2 GB of blobs)
```

| | shipped (2026-10-02) | **v2 (2026-10-07)** |
|---|---|---|
| examples | 109 | 117 |
| epochs | 3 | 3 |
| final loss | 0.4839 | **0.4586** |
| gguf | 3.09 GB f16 | 3.09 GB f16 |
| ollama tag | `omniagent` | `omniagent-v2` |

**The lower loss is not evidence that v2 is better.** The two runs trained on
different datasets, so their losses are computed over different data and are
not comparable as a quality measure. What decides it is `holdout_eval` on both
tags, which is the only instrument here that compares models on the same
questions.

**`omniagent` is untouched**, and that took four changes to the notebook
first — see `2561ffb`. Every path derived from `OUTPUT_NAME`, plus the
`OLLAMA_NAME` tag the demo is pinned to, plus the shared trainer `output_dir`
and the single `models/Modelfile`. A run with the old defaults three days
before the demo would have overwritten the model that was rehearsed 25/25.

### HOLDOUT_EVAL: v2 against the shipped model

One run each, same questions, same sealed workspace, output in
`data/holdout-v2-vs-v1-2026-10-07.txt`.

| | `omniagent` | `omniagent-v2` |
|---|---|---|
| correct | 10/16 | **12/16** |
| tool pick | 5/7 | 5/7 |
| follow-ups | 5/5 | 5/5 |
| honest | 0/1 | **1/1** |
| steps | 58 | **49** |
| time | 584 s | **503 s** |

**Three questions differ, and they come from three different failure
families** — which is more informative than the two-point total, because it is
not one lucky question:

| question | `omniagent` | `omniagent-v2` |
|---|---|---|
| what is inside the data directory | "There does not appear to be anything else inside the 'data' directory." | listed it |
| weather in Bangkok | "not specified, but it is Wednesday, 7 October 2026" — **answering the previous question**, the old drift shape | "There is no tool available to provide the current weather in Bangkok." |
| And `scripts/build_notebook.py`? | "does not exist in this workspace" — a confident false negative | "tests/fakes.py has 122 lines, while scripts/build_notebook.py has 461 lines" |

So v2 improved on list-and-stop, on honesty, and on the elliptical follow-up,
in 9 fewer steps and 81 seconds less.

### Why this does not settle it, by this project's own standard

1. **One run.** Three runs have twice produced a conclusion ten reversed; one
   is weaker than three.
2. **The instrument's noise is at least ±1 on this axis.** `omniagent` scored
   **11/16 yesterday and 10/16 today** — same model, same seal, same
   questions. A two-point gap is about twice the noise observed on a single
   sample of it.
3. **`tool pick` fell from 6/7 to 5/7 for both models**, which is more of the
   same variance.
4. **One of v2's three wins may be memorisation, not capability.** The
   data-directory question's expected answer is `collect-run.log`, and that
   string is in the training data as a `list_directory` observation — 29 times
   in the old collection, and the new one was collected the same way. v2 was
   trained on data that contains the answer to that question. The honesty and
   follow-up wins are not contaminated this way.

**Do not swap the demo to v2 on this.** `omniagent` is what was rehearsed
25/25 on the demo path, and a model that has been measured once should not
replace one measured repeatedly, three days out. Ten runs of
`holdout_eval omniagent omniagent-v2` settles it: ~18 minutes of clock per
pair, almost no quota.

## Traps already paid for once

- **Ollama does not autostart**, but it may already be up — check first:
  `.venv\Scripts\python.exe -c "import httpx;print(httpx.get('http://localhost:11434/api/tags').status_code)"`.
  To start it, PowerShell:
  `Start-Process "$env:LOCALAPPDATA\Programs\Ollama\ollama.exe" -ArgumentList "serve" -WindowStyle Hidden`,
  wait ~15 s. `&` from Bash does not work.
- **`pytest -q` hides the summary line, and the cause is `addopts`.**
  `pyproject.toml:168` already sets `-q`, so typing `-q` yourself makes it
  `-qq` and `NNN passed` disappears entirely — `grep passed` then matches
  nothing while the run was green. Run `pytest` with **no** `-q` of your own.
- **`$TMPDIR` in the Bash tool is plain `%TEMP%`, not the scratchpad.** Use
  the scratchpad's full path, or a throwaway script lands somewhere else and
  `python` reports "No such file".
- **Put a throwaway measurement script in the scratchpad, not in the repo.**
  A script holding a held-out question text fails the eval-workspace
  invariant, which is the invariant working.
- **`cmd.exe` reads `/` as a switch**, so `.venv/Scripts/python.exe` fails
  there. Use backslashes in cmd.
- **A bare `python main.py` picks up `.ci-venv`.** Always type the full path.
- **A run over 600 s is backgrounded** and survives only until the session
  ends. Start it with `run_in_background` on purpose and do independent work
  while it runs. Never start two — they fight over the 4 GB card.
- **Ollama at temperature 0 is not deterministic for long trajectories.** Read
  `steps` as a range. Short clean trajectories are stable to the step.
- **A quoted bash heredoc still eats `\n` and `\\` in Python source.** Use
  Write/Edit, or `chr(10)`. Hit in every session so far.
- **`sed` patterns containing `\n` match nothing silently**, so a mutation
  check can "pass" without having mutated anything. Verify the mutation took —
  assert the target string is present before replacing it.
- **A recursive `grep` from Bash scans `.venv` and blows the 120 s limit.**
  Name the paths, or use the Grep tool.
- **`git add -A` sweeps in whatever else is in the tree.**
- **Capturing a notebook's output on Windows needs `PYTHONIOENCODING=utf-8`.**
  A training cell prints a progress bar, and `cp1252` cannot encode its block
  characters, so a runner that re-prints cell outputs dies with
  `UnicodeEncodeError` **after** the notebook has finished successfully. The
  run was fine; the report of it was not.
- **Always redirect an eval to `data/`** — it prints and keeps nothing. `data/`
  is gitignored, so those records stay local.
- **`pip install torch --index-url .../cu126 --upgrade` is a no-op** — use
  `--force-reinstall` with the explicit local version.
- **Global `pip` fails under the sandbox**; venv pip on `D:` works.
- **`\b` does not match inside `OMNIAGENT_API_KEY`** (`_` is a word character).

## If the tools or the system prompt change

Re-collect from scratch — both are part of every training example. Prefer a
change that only reaches the prompt once something has already gone wrong,
like an error message, over one that reaches every turn, like a tool
description.
