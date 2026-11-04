You are continuing work on **OmniAgent**, a local-only ReAct agent at
`D:\code-project\OmniAgent` (**public** repo `mntoyg/OmniAgent`, MIT, branch
`main` — public since `e06bb05`; this line said "private" until 2026-10-26).

Reply to me in **Thai**. Code and commits in English. Commit and push after
every work step. **Name the remote: `git push origin main`.** `main` tracks
`organization/main`, so a bare `git push` goes to the wrong repository.

---

# HANDOFF — 2026-10-26, written at 66% context

**Read this block, then `git log --oneline -20`. Everything below PART 1 is
older and parts of it are struck through; trust the strikes.**

**The next chat starts from `docs/pm/handoff-prompt.md`**, not from this file.
That prompt is regenerated whenever a session reaches **70% context**, which is
the standing rule as of 2026-10-26: at 70%, stop and write the next chat's
whole opening prompt — the role it takes, the budgets, the standards, the
measured state, the open list and the trap list — not a summary. Keep this
block in step with it. The role from 2026-10-26 onward is **project manager
and solution system architect**.

**If the next chat is Codex rather than Claude, it starts from
`docs/pm/pm2-codex-prompt.md`** — the same job, written for a second manager
taking the chair when the Claude session is out of weekly budget or over 70%
context. It differs where Codex differs: no model evaluation (`WinError
10013` on `localhost`), no WSL/Linux build, no reading of Claude's weekly
usage, and a third verdict, `REPORTED, UNVERIFIED (needs a model run)`, for a
figure the acting manager could not re-run. It also carries the baton rule —
`git log`, `git status`, find the briefs whose `## Result` is still the empty
comment, declare which HEAD you took over at, and **never manage a brief you
executed**. Whichever of the two prompts a session regenerates, it puts its
name, the date and the HEAD at the top; keep both in step with this block.

**Since 2026-11-03 there is an owner-approved contract and it governs
everything in this file: `docs/pm/agentic-mvp-contract-2026-11-03.md`.** It
reframes the project from "evaluate the fine-tune" to "ship a local-first
repository assistant MVP against frozen security gates", and it says **do not
use a frozen or legacy cohort as the new baseline** — so the figures below are
measurements of the old instrument and **none of them is the MVP's baseline**.
Read the contract, then `docs/pm/handoff-prompt.md`, before anything here.

The repository is **public**, MIT. `main` is at `61dbc62`. **658 tests**, ruff
clean, mypy strict clean over **45** files. Three gates still:
`.venv\Scripts\python.exe -m ruff check .`, `-m mypy`, `-m pytest` — full path,
**never your own `-q`**.

## Who does what now

- **project manager** — this role. Writes briefs to `docs/pm/brief-NN-*.md`,
  verifies by re-running, never writes production code. **A second manager,
  Codex, takes the chair when this session cannot** — started from
  `docs/pm/pm2-codex-prompt.md`. Only one of them issues briefs at a time.
- **fullstack engineer** — a second Claude session. Currently **free**.
- **SWE** and **security engineer** — both Codex, one session. Currently free.
  **Codex cannot run model evaluations**: its sandbox returns `WinError 10013`
  on `localhost`, confirmed twice on 2026-10-24 with Ollama answering for the
  manager. Any brief needing a model run is split in advance — engineer
  designs, manager measures.

Each brief has a paste-ready twin at `docs/pm/brief-NN-codex-prompt.md` or
`-engineer-prompt.md`. Ten briefs are done; read any of them for the shape.

## What landed in this run

| Brief | Outcome |
| --- | --- |
| 01 | Task 4 — the hosted-notebook framing, narrowed to one docstring |
| 02 | the notebook is provably its generator's output |
| 03 | `search_text` prunes: **26.6–31.2 s → 1.7–1.9 s**, byte-identical output |
| 04 | a fourth gate for `omniagent-core`, on `ubuntu-24.04`, 4/4 |
| 05 | the llama.cpp fingerprint is the LF blob, not a Windows CRLF artefact |
| 06 | the gate's runner and action pinned |
| 07 | no existing directory can be a stable eval subject — the empty candidate list |
| 08 | `eval-fixture/` built; the replacement question is **10/10 over ten runs** |
| 09 | both deterministic wrong answers traced to the model's own priors |
| 10 | no question is scored on nothing — open items 1 and 2 both closed |
| 11 | the walk stops paying for `resolve()` — 4,690 calls to **1**, ~5× faster, output byte-identical by hash |
| 12 | a record that refuses to pool — `--report` drops all 209 existing records and says so |
| 13 | the junction refusal has a test — and only the junction test is load-bearing |
| 14 | the endpoint cannot leave loopback (contract gate 1) — **in flight** |
| 15 | one category with a real oracle (contract section 7 step 3) — **in flight** |

Plan `2026-10-06-train-and-deploy` is **closed**, Tasks 1–4.

**Superseded as a baseline by the contract, kept as a measurement.
`omniagent-v2` scored 13/18 four times and 14/18 six times over ten runs,
2026-10-26 at `43aba72`** — 6/7 tool pick, 5/5
follow-up, 1/1 honest, 54 steps every run. ~~11/16, zero variance,
2026-10-24~~ is struck as a *baseline* and not as a measurement: brief 10
made two questions checkable and replaced a third. It **did** reproduce —
all fourteen untouched questions came back byte-identical, marks and steps.

**This is the first non-zero score variance the project has measured.** One
question moves, the comparison follow-up; the failing set is `{4, 9, 16, 18}`
six times and `{4, 9, 16, 18, 19}` four times.

~~Wall clock is not stable although the score is: 237 s to 1,508 s.~~ **Ten
runs today: 192–206 s, a 1.07× spread.** The old measurement was real; the
reading of it was not — the spread is not a property of the evaluation.

**Full detail and the scored prediction:
`docs/pm/brief-10-no-question-is-scored-on-nothing.md`.**

## Open, in the order I would take it

~~1. `agent.budget.exhausted` needs replacing~~ — **closed by brief 10.** Its
replacement has one reachable carrier against five and scores 10/10 on both
axes. The retired question had **never once called `search_text`** in ten
runs, on the bank's only `search_text` question, so that tool had no coverage
at all until now.

~~2. A question scored on tool choice only can hide a total derailment~~ —
**closed by brief 10.** 19 questions, 18 checkable, none scored on tool
choice alone or on nothing.

1. **The agent's ability to compare two files is measured by nothing.** The
   answer axis checks that a filename appears and every answer names both
   files, so a reversed answer scores right — measured, not argued. Every
   route to closing it costs more than it is worth. **The owner's decision.**
2. **The derailment is not deterministic.** The comparison follow-up answered
   1/10 on 2026-10-24 and **6/10** on 2026-10-26, same text, same 9 steps.
   Unattributed. Five of the six passes carry a wrong number and are recorded
   as `ANSWER OK`.
3. **`sandbox.resolve()` is what keeps `search_text` above a second** — 4,660
   calls costing 1.13 s, 74% of what remains after brief 03. Needs
   `sandbox.py`, which every brief so far has forbidden.
4. **`data/holdout-runs.jsonl` records the commit but not whether the tree was
   clean**, and currently pools one void run with ten good ones.
5. **`_lines` and `file_info` do not agree by construction** — 2 vs 1 on a bare
   CR and on a Unicode line separator. No current file is affected.
6. **`NEXT_CHAT.md` is 1,101 lines** and still wants splitting. Mine to do.
7. **Something external writes `.tmp-omnipatch-*` into the tree** — ~1 MB of
   Bandit output, now gitignored (`34b65f2`) but **not identified**. A tool
   that can write here can write anything here.
8. `omniagent-core` is on branch `core-offline-runtime`, gated and green, not
   merged. Merging is undecided.

## Traps learned in this run, beyond the list at the end of this file

- **Read the socket error code.** `10061` means nothing is listening — start
  Ollama. `10013` means the environment is blocking the socket — reassign the
  work. **Ollama does not survive across days; restart it at the start of any
  session that measures.**
- **Timing order matters.** Running a baseline first warms the page cache for
  the candidate. I recorded a walk at 4.58 s that is really 1.6 s. Reverse the
  order and run again.
- **Score variance and clock variance are different measurements.** The
  evaluation has zero score variance and a 6.4× clock spread.
- **A brief's figures go stale.** Brief 03 sat three days and its baseline
  moved by 2,068 paths. Re-measure before re-issuing.

## My own brief-template defects, five of them — check these before issuing

1. **The mutation table must not require a file the forbidden list forbids.**
   Briefs 04, 05 and 08 each did. Two engineers had to invent a substitute.
2. **Name the files a brief forbids, not only the ones it allows.** Brief 04
   named only permissions, and a defect got worked around instead of reported.
3. **`docs/` is sealed** — it is in `ANSWER_KEY`, so `reachable_files()`
   returns 308 files with none under it. Briefs 07 and 08 told two engineers
   that quoting a question there would fail the invariant. It would not. Keep
   the no-quoting discipline as **defence in depth**, and say so.
4. **The commit block must name the report file.** Brief 03 did not, and the
   engineer had to ask whether to commit its own `## Result`.
5. **Ask whether the engineer can run what the verification needs** before the
   brief depends on it. Brief 05 assumed a WSL build; brief 07 assumed Ollama.

## The standing rules that have paid for themselves

Ten runs, not three. Write the prediction before the run — mine about a
trailing slash was wrong on ten runs, and writing it first is why that is a
result instead of a story. Mutation-check everything, restoring from a
scratchpad copy, never `git checkout --` alone. A substring expectation grades
characters, not answers. **`git log` and the test output are the truth; the
engineer's summary is a claim** — every brief in this run was re-run by the
manager, and three of them turned up something the report had not.

---

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

**628 tests**, mypy strict clean across 41 files, ruff clean. HEAD `3025796`
plus this file. Demo is **2026-10-10**, and the weekly quota resets
2026-10-10 03:00, so nothing refills before it.

**The demo runs on `omniagent-v2`** since `4a7d0bb`. Ten runs of
`holdout_eval` over both tags, zero variance in either: ~~**12/16 against
10/16**~~, honest **1/1 against 0/1**, **49 steps** every run against 57–62.

**Superseded for `omniagent-v2` on 2026-10-24: the current question set scores
`11/16`, zero variance over ten runs** (`5/7` tool pick, `5/5` follow-up,
`1/1` honest, **57 steps identical to the step**). This is **not** a regression
from 12/16 — brief 01 added a tracked file, brief 02 changed
`scripts/build_notebook.py` and brief 08 replaced a question, so three of the
things the set asks about have moved and the figures are not comparable. The
set of failing expectations was **byte-identical in all ten runs**, so all five
failures are reproducible rather than flaky. **Wall clock was not stable
although the score was: 237 s to 1,508 s, a 6.4× spread**, which is worth
knowing before anyone times this evaluation from a single run. `omniagent`
has not been re-measured against the current set.
Then the demo path itself: **35/35 over seven runs**, one of them by hand.
`omniagent` is still registered and still 30/30 there, so reverting is one
line in `omniagent.toml`.

**Tools:** `calculate`, `get_current_time`, `file_info`, `read_file`,
`list_directory`, `search_text`. **Models:** `omniagent-v2` (demo),
`omniagent` (previous), both local in Ollama.

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

**Re-rehearsed 2026-10-07 after the workspace changed: 25/25 over five
scripted runs, plus 5/5 run by hand -- 30/30 over six**, one tool call per question, zero `data/` paths in any
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

0. **Decide what the demo runs on — both models now pass both paths.** v2
   rehearsed 25/25 on the demo path over five runs, so the last gap is closed
   and the choice is a judgement, not a missing measurement. See the table in
   `docs/demo-script.md`: v2 wins the instrument (12/16 vs 10/16, honest 1/1
   vs 0/1, 49 steps vs 57-62, all with zero variance over ten runs) and costs
   one extra tool call on demo question 3, where it tries `read_file`, is
   refused, and recovers to `file_info`. Switching means editing
   `[profile.demo]` in `omniagent.toml`, which `tests/test_shipped_config.py`
   covers.
0b. ~~**Retire or rebuild the data-directory question.** Its expectation is a
   fact about `data/`, which is the output directory every run writes into --
   85 files now, and the question flipped from OK to WRONG because of that.
   A metric that moves when you measure is not a metric.~~
   **DONE 2026-10-24, `40dd252`. Rebuilt, not retired.** `data/` had reached
   **101** files and `list_directory` on it returned 3,742 characters over 102
   lines. The mechanism was not the one recorded here: the expected string was
   **still in the tool output** and missing from the *answer*, because
   `scripts/eval_scoring.py:88` grades `expect in answer` only — so the
   question required the agent to relay one arbitrary entry out of 102, and a
   correct summary was graded WRONG. Retiring it would have taken
   `list_directory` coverage to zero: it is 1 of 19 `Question` objects with
   that `prefer_tool`.
   **No existing directory could replace it** — measured under a sealed
   workspace, every candidate was written-to, contaminated, generated, or
   sealed (`docs` and `models` are in `ANSWER_KEY` and are not even named).
   So `eval-fixture/` was built: five files and one subdirectory, tracked,
   unsealed, uncontaminated by construction because the dataset predates it,
   and byte-stable across a full `pytest` run. Contamination count **zero for
   all six filenames** over 2,215 examples. The new question scores
   **10/10 over ten runs**.
1. **`search_text` resolves every leaf under a refused branch.** ~~It does
   `sorted(start.rglob("*"))`, materialising every path before filtering, so a
   search from `.` costs **25.7 s unsealed and 64.5 s sealed**~~ — **that
   diagnosis is retracted, 2026-10-23, measured.** Materialising the paths is
   **1.6 s of a 26.6 s run, 6%**. The cost is
   `workspace.resolve(workspace.display(candidate))` called once per candidate
   **file**: **69,186 of them are refused** by `sandbox.py:181 _is_hidden`
   under `.venv`, `.ci-venv` and `.git`, each paying a full path resolution and
   a raised `SandboxError` that is thrown away. That is **23.3–25.5 s, 87–88%
   of the run**, stable over three runs. Reading the 400 files it does scan is
   **0.04 s warm**. So the 25.7 s already recorded was essentially all
   `resolve()`.

   The prescription in the old note — prune branches as the walk descends, the
   way `tests/test_eval_workspace.py:113` does — **is still the right fix**,
   and it is worth ~25 s rather than the ~1.5 s the old diagnosis implied.
   Pruning dot-directories takes the enumeration from 87,482 paths at 1.6 s to
   **4,578 paths at 0.06–0.08 s**. Brief:
   `docs/pm/brief-03-search-text-prunes-as-it-descends.md`.

   **DONE 2026-10-26, `0c04ffa`, verified in `7d79a8f`.** A search from `.`
   went from **26.6–31.2 s to 1.7–1.9 s**, and the output is **byte-identical**
   — checked by reimplementing the old candidate selection verbatim and
   comparing output strings over ten cases, including the no-match case, a
   single-file start and three subdirectory starts. `resolve()` calls fell from
   roughly **74,000 to 4,660**, a 94% cut. Two tests guard the ordering: drop
   the `sorted()` and both go red.
   **The under-a-second target was missed and the reason is measured.**
   `_searchable_files` takes 1.53 s of which `resolve()` is **1.13 s, 74%** —
   the calls that legitimately have to happen, since the brief required asking
   the workspace rather than copying its rules. **Going below a second means
   making `sandbox.resolve()` cheaper, not pruning harder.** That is open and
   unbriefed.

   One question still takes ~115 s and a full `holdout_eval` measured 544 s,
   inside the 600 s limit, so this remains worth doing for the clock and
   **not** a prerequisite.

   **Separately, and not in that brief:** of the 400 files a root search
   scans, **285 are under `models/`** and 92 under `data/`, against 9 under
   `docs/`. `models/` is neither hidden nor denied, so it is in scope by the
   workspace's own rules and takes 71% of the budget. Narrowing that is a
   tool-behaviour change and the 153-example dataset was collected against the
   current behaviour, so it needs a decision and a re-collection, not a patch.
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
| ~~And `scripts/build_notebook.py`?~~ | ~~"cannot be read because it is too long"~~ | **STALE** — v2 resolves the ellipsis, calls `file_info` and receives 512 lines, then answers 513; tool axis passes and expectation matches the tool. Cause not established; trace run outstanding. |

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

### SETTLED on ten runs: v2 is better, and by exactly two points every time

Ten pairs, one at a time, `data/holdout-pair-1..10.txt`, summaries in
`data/holdout-pair-summaries.txt`. 174.7 minutes, 0 failures. Run 1 is the
pair measured earlier the same day under the identical configuration.

| | `omniagent` | `omniagent-v2` |
|---|---|---|
| correct | **10/16 in all ten** | **12/16 in all ten** |
| tool pick | 5/7 ×10 | 5/7 ×10 |
| follow-ups | 5/5 ×10 | 5/5 ×10 |
| honest | 0/1 ×10 | **1/1 ×10** |
| steps | 57–62 | **49 in all ten** |
| seconds | 584–757 | 436–630 |

**Zero variance in the score for either model across ten runs.** v2 is also
steadier in trajectory: 49 steps every single run against 57–62.

### Retracted: there is no "±1 instrument noise"

Earlier today I wrote that `omniagent` moving 11/16 → 10/16 showed the
instrument was noisy by about a point, and used that to argue a two-point gap
was near the noise floor. **That was wrong.** Ten runs put both models on the
same score every time. The 11/16 came from one question, and the cause is
worse than noise:

**"What is inside the data directory?" measures a directory the measurement
writes into.** `data/` held a handful of files yesterday and holds **85**
today, because every evaluation, collection and training run writes its output
there. The expectation `collect-run.log` is still present — the test asserting
that passes — but the listing is now long, and `omniagent` answers:

> I am unable to determine what text exists inside the 'data' directory
> because no files there appear to have plain text content

It lists the directory, which is allowed, then tries to **read inside** it,
which the listing-only tier refuses, and concludes it cannot tell. The refusal
is correct about contents; the answer is wrong about the question, which asked
for the listing it already had.

So the figure moved because I ran evaluations. **A question whose expectation
is a fact about `data/` cannot be a stable metric while `data/` is the output
directory.** Retire it, or derive its expectation from the tree the way
`_lines()` does.

And this reframes v2's win on that question. It is not only the memorisation
risk noted below: v2 **stops after the correct first observation** and
`omniagent` does not, in all ten runs each. That is open item 3 in this file —
the clearest remaining target — showing up as a measured difference between
two models rather than as a diagnosis.

### What still qualifies v2's lead

1. **`tool pick` is 5/7 for both models in all ten runs**, down from the 6/7
   `omniagent` scored on 2026-10-06. Unexplained, and it is not variance —
   it is the same value twenty times. Likely the same cause as the
   data-directory flip, since that question carries the `list_directory`
   expectation.
2. **One of v2's two correct wins may be memorisation, not capability.** The
   data-directory question's expected answer is `collect-run.log`, and that
   string is in the training data as a `list_directory` observation — 29 times
   in the old collection, and the new one was collected the same way. v2 was
   trained on data that contains the answer to that question. The honesty and
   follow-up wins are not contaminated this way.

**The demo still stays on `omniagent`, and the reason has changed.** It is no
longer "v2 is unmeasured" — v2 is now measured more thoroughly than the
shipped model ever was. It is that **`omniagent` is what was rehearsed 30/30
on the demo path, and v2 has never been run on that path at all.**
`holdout_eval` drives the agent directly; the demo is
`main.py --profile demo`, and that gap has hidden two defects before
(`06f9ab0`). Five scripted runs plus one by hand of the five demo questions
against `omniagent-v2` is what would justify a swap, and it costs ~10 minutes
of clock.

## 2026-10-10: demo shipped, and a second collection to close two gaps

**Demo verified on the day and tagged.** Five runs of the five questions
through `main.py --profile demo` (no `--model`, so the profile produced it):
**25/25**, 6 tool calls per run, identical answers, zero `data/` paths. With
the earlier seven runs that is **60/60 for `omniagent-v2` on the demo path**.
Tag `demo-2026-10-10` pushed, annotation carrying the figures. The repo stays
**private** — publishing it was offered and declined.

**A second collection, aimed at the two thin tools.** Bank at
`questions/bank-2026-10-10.txt` (`2c909d5`), 50 questions in 42 sessions,
teacher `qwen2.5-coder:7b`, 0 failed, 32.8 min. 36 exported of 50; 14 dropped
as 7 tool errors, 3 budget-exhausted, 3 repeated-action, 1 format violation.

Merged with the 2026-10-07 collection, which is allowed here because all three
things the no-pooling rule protects are identical: same teacher, same prompt
fingerprint `36397f37…`, same workspace rule.

| tool | 117 | +36 | **merged 153** |
|---|---|---|---|
| calculate | 82 | — | 82 |
| **list_directory** | 12 | +18 | **30** |
| **search_text** | 8 | +20 | **28** |
| file_info | 22 | — | 22 |
| get_current_time | 15 | — | 15 |
| read_file | 3 | — | 3 |

`validate_dataset` verdict **OK**. Published to
`G:/OmniAgent/datasets/2026-10-10-merged/` with the two raw logs, the bank
and the bundle doc; `--verify-only` reports **verified**.

### `read_file` cannot be fixed with more questions

Measured, not assumed: `MAX_INTACT_READ_CHARS` is **2,400**, and only **6 of
52** tracked files render under it. Of those, `.gitignore` and
`.github/workflows/ci.yml` are dot-prefixed so the sandbox refuses them, and
`tests/test_holdout_questions.py` is sealed during evaluation. **Three files
remain readable** — `tests/__init__.py`, `requirements.txt`,
`omniagent.toml` — which is exactly the three `read_file` examples in the
data. More questions would return more errors and `export_dataset` drops those
turns. Fixing it needs readable material (a small corpus) or a different cap,
not a bigger bank.

**Partly answered 2026-10-24, `40dd252`.** Re-measured before `eval-fixture/`
landed: **4** tracked files were readable by a sealed agent *and* rendered
intact — `tests/__init__.py` (78 rendered chars), `requirements.txt` (238),
`tests/test_local_only.py` (924, which only exists because brief 01 added it)
and `LICENSE` (1,262); 36 were denied or unreadable and 37 too long. Note that
`omniagent.toml` is in `ANSWER_KEY`, so the earlier count of three included a
file that is sealed during evaluation. **`eval-fixture/` added six more, all
rendering intact at 173-202 chars, so the readable set is now 10.** That is
the small corpus this entry asked for, arriving as a side effect of fixing the
`list_directory` question. Whether it is enough to move `read_file`'s share of
the dataset is **not** measured: it needs a fresh collection run, and the
dataset on `G:` predates the directory.

### The teacher was chosen on measurement and on the hardware

`gemma4:12b` timed at **178 s per session against 30 s** for
`qwen2.5-coder:7b` — six times slower, with no quality difference visible on
the three-question probe, which was arithmetic-only and could not have shown
one. And 7.6 GB on a 4 GB RTX 3050 Laptop in an MSI GF63 Thin means hours of
sustained spill to RAM on a chassis that cannot shed it. Dropped on both
counts.

## 2026-10-11: Task 2 done, and the generator lesson

**The notebook is generated.** `2561ffb` put the run scoping in
`notebooks/train_omniagent_lora.ipynb`, but `scripts/build_notebook.py` writes
that file, which Task 2 of the plan said from the start. I ran the generator
with `--help`, which it does not accept and so simply regenerated, and four
tests went red at once with the previous day's work inside them. Restored from
a scratchpad copy (not `git restore` alone), then moved all four changes into
the generator where they survive regeneration.

~~`test_the_notebook_and_its_generator_agree` is the guard that was missing: it
asserts each guarantee's exact text appears in **both** files. Mutation-checked
both ways -- reverting the generator alone turns it red, reverting the notebook
alone turns it red plus three others.~~

**Superseded 2026-10-23, `8b2a80a`. That test was deleted.** It was not the
guard it reads as. It asserted that six fixed snippets appear in both files, so
it could only ever see drift in a line one of those snippets names. The drift
that actually happened -- an unused `import json` the generator emits and the
notebook had removed from it alone -- was invisible to it, and it was green
throughout.

**And the mutation check above is why that went unnoticed for twelve days.**
Both mutations were chosen by reverting a *guaranteed* snippet, which is the
one thing the test is built to see. A mutation drawn from the test's own
assumptions can only confirm what the test already covers. Replaced by
`test_the_committed_notebook_is_what_the_generator_produces`, an equality check
over the whole document, with `test_the_generator_is_deterministic` beside it.

**Task 2 complete** (`ee0c0e6`). `scripts/run_dir.py`: `new_run_dir` names a
run for the second it started in and counts `-2`, `-3` on collision;
`write_manifest` refuses a manifest missing `base_model`, `examples` or
`strategy` and names every missing field. The manifest cell writes
`models/runs/<timestamp>/manifest.json`, copies the adapter beside it, and
keeps the flat path as a copy so old readers keep working. Seven tests, all
watched failing against a stub; three mutations each caught by one test.

Two deliberate deviations: the plan's test snippet used a naive datetime
(ruff DTZ001 refuses it), and the trainer's `output_dir` stays at
`models/runs/<OUTPUT_NAME>` rather than the timestamp directory, because
checkpoints and the run record are written at different points in the
notebook. **Unifying them is worth doing and is not done.**

**Task 3 can now proceed** -- its Consumes block has its producer.

### Public-readiness audit (V1) -- clean except the licence, now fixed

| check | result |
|---|---|
| tracked files over 1 MB | **none** -- the two 3 GB GGUFs are untracked, so a clone stays light |
| `.env` / `.pem` / `.key` / credential filenames ever committed | **none** |
| secret-shaped strings in the tree | all fixtures that test the secret scanner or prove `api_key` never reaches a log |
| README for an outsider | 724 lines: Ollama, pull a model, venv, `pip install -e .`, `python main.py` |
| LICENSE | was **missing** while `pyproject.toml` claimed MIT -- added in `351da6b` |

**The repository is public** as of 2026-10-11, with `NEXT_CHAT.md` included on
the owner's decision. `gh repo view` confirms visibility PUBLIC, licence MIT
detected, clone size **571 KB** — the two 3 GB GGUFs stay untracked as the
audit predicted. Description and topics set so the landing page says what the
project is. Not fully reversible: forks and caches are outside anyone's
control from here. One question remains open for it: `NEXT_CHAT.md` is tracked and is
an internal record of every failure and retraction. I think it should stay --
it is the evidence that the figures were measured rather than claimed -- but
that is the owner's call.

### Task 3 complete, and the mutation that exposed my tests

`86ddb50`. `scripts/promote_model.py` replaces `ollama create omniagent -f
Modelfile` typed by hand, which is how a model nobody evaluated could reach the
tag the demo is pinned to -- as nearly happened on 2026-10-07.

`check_run` refuses a run whose manifest records a different system prompt than
the one it would be served under, whose gguf is missing or unnamed, or that has
no Modelfile. `check_scores` refuses an evaluation carrying `errors`, one with
nothing `checkable`, and any score below the floor. Both return **reasons**
rather than raising, so a refusal prints every problem at once. The connection
error from a stopped Ollama is deliberately uncaught: a promotion that quietly
tagged nothing would be worse than one that stops.

**Two of four mutations were not caught, and the fault was in my tests.** The
plan predicted that making `check_scores` ignore `errors` should turn the
errored-evaluation test red. It did not: both that test and the
nothing-checkable test used `Score(correct=0, checkable=0)`, which the
checkable guard *and* the floor also refuse — **the guards masked each other
and each test was being satisfied by a different one**. Rewritten with scores
that would otherwise pass (`correct=12, checkable=16, errors=[...]`), so each
test can only be refused by the guard it is about. Both mutations now turn
exactly one test red. Worth remembering as a shape: a test that asserts "this
is refused" proves nothing if several independent guards would refuse it.

### The repository is public, with a cast at the top of the README

`docs/demo1.svg` (`3025796`), 7 KB, generated by `scripts/make_demo_svg.py`
from a real session (`f582a32fba9d`, `omniagent-v2`). SVG rather than GIF: a
fraction of the size, sharp at any zoom, real searchable text, CSS keyframes
only because GitHub strips `<script>` from an SVG served through `<img>`. The
beat it exists for is question 3 — `read_file` refuses, the error names
`file_info`, the agent takes the hint.

Two tests keep it honest: the SVG carries no script and **no external
reference** (it is in a public README, so it must fetch nothing), and it shows
the answers the agent actually gives, so the README cannot drift.

`docs/video-script.md` (`fdddbca`) is the recording script, five beats, every
command run before being written down. **Recording it is the owner's job** --
there is no screen recorder here.

### The eval-workspace invariant has now caught the key five times

`test_file_tools.py`, `test_eval_workspace.py`, `eval_workspace.py`,
`test_sandbox.py`, `test_collect_dataset.py`, and now
`scripts/make_demo_svg.py` -- the demo questions are held-out questions, so the
generator holding them made them reachable. Every one was found by that test
and none by review. **Expect the next file that mentions a demo question to do
it too.**

### ~~Next: Task 4, the last one in the plan~~ -- DONE 2026-10-23, `675e0de`

The user wants to record a how-to video and then open the repository so others
can clone it. V1 is done. V2 is the demo order and the exact commands to type
on screen; `docs/demo-script.md` already holds a measured five-question
sequence that works on the demo path, 60/60 over twelve runs.

**The plan `docs/superpowers/plans/2026-10-06-train-and-deploy.md` is complete.**
Tasks 1-4 all done; Task 4 landed in `675e0de` on 2026-10-23. Measured by the
project manager on the committed state, not read from a report: `ruff check .`
**All checks passed**, `mypy` **clean over 42 source files** (41 before), and
`pytest` ~~631~~ **632 passed in 10.35s**. Mutation M1 -- putting the word back
into the docstring -- gives **1 failed, 631 passed** with exactly the new test
red, re-run after the assert was wrapped in parentheses, which is how it is
known the assert did not become an always-true tuple.

Three errors in the plan's own Task 4 section were found by searching before
writing the brief, and are recorded in the plan: `README.md` was listed as a
file to modify and contains no occurrence of the string; `build_notebook.py`
was listed when its sentence is correct as written; and
`tests/test_local_only.py` was listed as an existing test file when it did not
exist.


## 2026-10-23: brief 01, brief 02, and the plan closed**The plan `docs/superpowers/plans/2026-10-06-train-and-deploy.md` is done.**Tasks 1-4 complete. HEAD `3ee7950`. **~~631~~ ~~632~~ 633 tests**, ruff clean,mypy strict clean over 42 files.- **Brief 01 (`675e0de`)** -- Task 4. Only `scripts/smoke_train.py` ever  contradicted the manifest. Three errors were found in the plan's own Task 4  section before a line was written: `README.md` listed as a file to modify  while holding no occurrence of the string, `build_notebook.py` listed when  its sentence is correct as written, and `tests/test_local_only.py` listed as  an existing test file when it did not exist.- **Brief 02 (`8b2a80a`)** -- the notebook is now provably its generator's  output. The generator gained `build_notebook()` returning the dict with no  I/O, a deterministic `cell_id` (sha256 of index plus source, 8 hex), `OUT`  anchored to `__file__` instead of the working directory, and a `__main__`  guard. It had been writing the notebook **at import time**, so any test that  imported it would have overwritten the real file and compared it to itself.Verified by the project manager on the committed state, not read from a report:importing the generator from `C:/` leaves the notebook's sha256 **and mtime**unchanged and `git status` clean; running it twice from `C:/` leaves`c71c8ea6...` byte-identical with no stray `C:/notebooks`; mutating the**notebook alone** gives `1 failed, 632 passed` with only the comparison testred; neutering that test's assert turns the file green again, which is how thered is known to come from it.`scripts/build_notebook.py --help` still regenerates instead of printing help,because the script takes no arguments. It is now harmless: the regeneration isbyte-identical, so the 2026-10-11 accident cannot take a day's work with itagain.**Still open from this round:** nothing in brief 01 or 02. The data-directoryeval question is untouched and needs ten runs, so it waits for quota.
## Traps already paid for once

- **Ollama does not autostart**, but it may already be up — check first:
  `.venv\Scripts\python.exe -c "import httpx;print(httpx.get('http://localhost:11434/api/tags').status_code)"`.
  To start it, PowerShell:
  `Start-Process "$env:LOCALAPPDATA\Programs\Ollama\ollama.exe" -ArgumentList "serve" -WindowStyle Hidden`,
  wait ~15 s. `&` from Bash does not work.
- **Read the socket error code; the two mean different things.** `WinError
  10061` is "actively refused" — nothing is listening, so start Ollama.
  `WinError 10013` is "socket access forbidden" — the *environment* will not
  let that process open the socket, and starting Ollama does not fix it. On
  2026-10-24 an engineer reported `10013` and "`ollama.exe` not found" while
  the binary was at the documented path and the manager got `10061` from the
  same address: Ollama was simply not running, **and** that engineer's sandbox
  blocks the socket. One code is a thing to do, the other is a thing to
  reassign, and reading them as the same failure costs a round trip.
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
- **A quoted bash heredoc still eats backslashes in Python source, and the
  worst case is silent.** `\n` and `\\` are the known ones, but **any `\`
  followed by a digit becomes an octal escape**: a Windows path written as
  `G:\datasets\2026-10-10` came out as `datasets` plus U+0082 plus `6-10-10`,
  with only a `SyntaxWarning: invalid escape sequence` to show for it, and the
  commit went through. **Use Write/Edit for anything containing a backslash,
  and write Windows paths with forward slashes in prose.** Hit three times on
  2026-10-10 alone, after being written down here twice.
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
- **A mutation drawn from the test's own assumptions proves nothing.** On
  2026-10-11 `test_the_notebook_and_its_generator_agree` was mutation-checked
  by reverting one of the six snippets it asserts -- the one thing it is built
  to see -- and passed. It could not see a line outside that list, which is
  exactly the drift that then sat in the repository for twelve days. Pick the
  mutation from what the code must do, not from what the test looks at.
- **`git push` with no remote named goes to `organization/main`**
  (OmniBase-Official/OmniAgent), not to `origin` (mntoyg/OmniAgent). `main`
  tracks the organization remote and `push.default` is unset. Name the remote.
- **`omniagent-core/` is not on `main`.** It is a C++20 CPU runtime on the
  branch `core-offline-runtime`, ~~(`cfbde93`), outside all three gates~~ now
  at `9638a04` **with a fourth gate of its own**, `.github/workflows/core.yml`,
  running four `ctest` targets on every push that touches `omniagent-core/**`.
  CMake still hard-fails off Linux/GCC-Clang and still hard-fails without a
  local llama.cpp checkout pinned by SHA256 to `869034b4`, which lives under
  gitignored `models/`. ~~so a clone of that branch cannot build it~~ —
  **that was true until `52c3b11`, 2026-10-23.** The pinned fingerprint was the
  hash of a **Windows CRLF** working tree, so a clean Linux checkout of the
  named commit was refused by the check that names it. It is now the canonical
  LF hash `d5cf9203…`, and the error message prints what it computed.
  ~~Its only evidence is a ctest log dated 2026-10-11, 4/4 passed under WSL.~~
  **Hosted evidence: run `39927752691` on `ubuntu-latest`, 4/4 passed, 1m 21s,
  image `ubuntu24/20261012.334`**, including a step that proves the fingerprint
  still refuses a CRLF header and one that records the runner's `/tmp` as
  `magic 0xef53`, which `src/local_file.cpp:19-25` allows. Its one Python file
  passes ruff and mypy strict as written. **Nothing guards the gate file from
  being deleted.** ~~`ubuntu-latest` began migrating to Ubuntu 26 on
  2026-10-19, so the `/tmp` type the gate depends on can change with no commit
  here — pinning `runs-on: ubuntu-24.04` is open and undecided.~~
  **Pinned 2026-10-23 in `da1a5be`:** `runs-on: ubuntu-24.04` with the reason
  beside it, and both checkouts at `actions/checkout@v5`. Verified on run
  `39929249216`: **4/4 passed in 1m 49s**, `/tmp` still `0xef53`, the
  CRLF refusal still firing, and **both deprecation annotations gone**. When the
  `ubuntu-24.04` label is retired this job will fail loudly on an unknown label
  rather than quietly measure a different filesystem, which is the trade.
  `actions/checkout` is at `v7.0.1`; `v5` clears the Node.js 20 deprecation and
  is two majors behind, by decision.

## If the tools or the system prompt change

Re-collect from scratch — both are part of every training example. Prefer a
change that only reaches the prompt once something has already gone wrong,
like an error message, over one that reaches every turn, like a tool
description.
