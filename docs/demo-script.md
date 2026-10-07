# Demo script — 2026-10-10

Five questions, in this order, measured on the path the demo actually uses
(`main.py --profile demo`, not the evaluation harness). Three rehearsals on
2026-10-06 at commit `3e7476d`: **15/15**, scored against the real expected
answers rather than a loose keyword match. Two steps per question, ten in
total.

Confirmed by hand on 2026-10-06 as well as by the three scripted rehearsals:
5/5, two steps each, and every sentence correct and not merely containing the
right number. The follow-up was typed "Now SubStract 728 from that." --
misspelled, oddly capitalised -- and still resolved "that" to the right
antecedent, and question 5 was typed with leading spaces. A typo on the day is
not a risk.

## Before you start

Two commands, and the slashes matter. `cmd.exe` reads `/` as the start of a
switch, so `.venv/Scripts/python.exe` makes it look for a command called
`.venv` -- which is the error "'.venv' is not recognized as an internal or
external command". Use backslashes there.

**Step 1 — start Ollama.** It does not autostart. In **PowerShell**:

```powershell
Start-Process "$env:LOCALAPPDATA\Programs\Ollama\ollama.exe" -ArgumentList "serve" -WindowStyle Hidden
```

Wait about fifteen seconds. Check it answered:

```powershell
Invoke-RestMethod http://localhost:11434/api/tags | Select-Object -ExpandProperty models | Select-Object name
```

`omniagent:latest` must be in that list.

**Step 2 — start the agent.** In **cmd.exe** (backslashes):

```
.venv\Scripts\python.exe main.py --profile demo
```

In **PowerShell or Git Bash** either slash works:

```
.venv/Scripts/python.exe main.py --profile demo
```

Type the full path to the interpreter every time. A bare `python main.py`
picks up whatever virtualenv the shell has active -- `.ci-venv`, if that is
what is on the prompt -- and that is not the one the demo was measured in.

You should see the banner, then `profile : demo` and `model : omniagent`. If
it says any other model, stop: the demo is not running what was measured.

## The questions

| # | ask this | expect to see | steps |
|---|---|---|---|
| 1 | What is 144 * 12? | 1728 | 2 |
| 2 | Now subtract 728 from that. | 1000 | 2 |
| 3 | How many lines does tests/fakes.py have? | 122 | **3** — see below |
| 4 | What is 7 factorial divided by 5 factorial? | 42 | 2 |
| 5 | What is 2 to the power of 11, minus 48? | 2000 | 2 |

**Re-rehearsed on 2026-10-06 after the workspace changed**, because the CLI
now runs where the agent cannot read its own transcripts and that is a change
to the environment the demo runs in. Five consecutive runs of all five
questions through `main.py --profile demo`: **25/25**, one tool call per
question, and **zero** `data/` transcript paths anywhere in any trace. The
answers were identical in all five runs, word for word, and were read rather
than substring-matched:

> 144 multiplied by 12 is 1728. / The result of subtracting 728 from the
> product of 144 and 12 is 1000. / The file `tests/fakes.py` has 122 lines. /
> The result of 7 factorial divided by 5 factorial is 42. / 2 to the power of
> 11, minus 48, is 2000.

Note question 2's phrasing: it names its own antecedent ("the product of 144
and 12") rather than saying "that", which is the follow-up working, not
hedging.

**Run by hand on 2026-10-07, after the five scripted runs: 5/5**, two steps
and one tool call per question, no `data/` path anywhere in the trace, no
`tool.unknown` and no repeated action. Session `d62050798f00`, model
`omniagent`. That makes **30/30 over six runs, one of them by hand** — and the
hand run is the one that counts most, because the first demo rehearsal
(`2779d46`, 2026-10-02) found six defects while 463 tests and a 300-second
evaluation were both passing.

**`omniagent-v2` rehearsed on the same path, five runs: 25/25**, identical
sentences every run, no `data/` path anywhere, 0.4–0.7 min per run. So both
models pass the demo. One difference, and it is visible on screen:

| | `omniagent` | `omniagent-v2` |
|---|---|---|
| demo path | **30/30** over six runs, one by hand | 25/25 over five scripted runs |
| tool calls per run | **5** — one per question | **6** |
| question 3 | picks `file_info` first | picks `read_file`, is refused, recovers |
| `holdout_eval` (ten runs) | 10/16, honest 0/1, 57–62 steps | **12/16, honest 1/1, 49 steps** |

**Question 3 takes three steps on `omniagent-v2`, and that is expected.** It
is the only question that does not go straight to its answer, so here is
exactly what the screen shows, so nobody reads it as a fault on the day:

```
  [step 1]
  Thought      : I need to find out how many lines the file has.
  Action       : read_file
  Observation  : Error: tests/fakes.py is 3,670 characters, too long to return
                 in full. ... Use file_info for its size, first line and last
                 line, or search_text to find something inside it.

  [step 2]
  Thought      : Since read_file cannot show me how many lines a long file has,
                 I will use file_info instead.
  Action       : file_info
  Observation  : tests/fakes.py: 122 lines, 3,670 bytes

  [step 3]
OmniAgent: tests/fakes.py has 122 lines.
```

The refusal is the sandbox's read cap, the error message names the tool that
can answer, and the agent takes it. Identical in all seven runs of this
question on this path, including by hand. If it is ever worth narrating: this
is the one moment in the demo where a tool says no and the agent recovers.

**Switched on 2026-10-07.** `[profile.demo]` now pins `omniagent-v2`, and the
switch was verified rather than assumed: `main.py --profile demo
--print-config` reports `model omniagent-v2` sourced from `profile:demo`, and
a run with **no `--model` flag** answers all five correctly in 6 tool calls
with no `data/` path in the trace. That makes **35/35 for v2 on this path** over
seven runs -- five scripted, one through the profile, one by hand. `omniagent` is still registered and still scores 30/30, so
reverting is one line in `omniagent.toml`.

v2's extra step is not waste — it is the guardrail working. `read_file` refuses
`tests/fakes.py` as too long to return in full, the error names `file_info`,
and v2's next Thought reads "Since read_file cannot show me how many lines a
long file has, I will use file_info instead." Nothing of the file reaches the
screen; one error line does, then the right answer. On a demo that is
arguably worth showing. It still means the first instinct is the wrong tool.

Two behaviours worth knowing before standing in front of it:

- **Question 2 recomputes rather than remembering.** Its Thought says it will
  calculate the product *and* the subtraction, and it sends
  `144 * 12 - 728` as one call. The answer is right and the referent resolves
  correctly, and it gets there by redoing the arithmetic instead of reaching
  into the history for 1728. That is the opposite mechanism to the one that
  breaks "Finally, what is 10% of that?", which reaches into the history and
  picks the wrong number out of it.
- **Question 3 picks `file_info`, not `read_file`.** That is the distinction
  the "do not ask" list below is about: the same question asked elliptically
  ("And sandbox.py?") picks `read_file` and copies a number out of the
  conversation.

Questions 1 and 2 open the demo because **a follow-up has to come directly
after the question it refers to.** Asked fifth, with three unrelated questions
in between, "Now subtract 728 from that" answered "144 multiplied by 12, minus
728 is 272" in three of three rehearsals -- 272 is 2000 minus 1728, so "that"
had reached back past its own antecedent to an earlier answer. First and
second, it is right in three of three. The pair is also the best thing to
show: it is the agent remembering across turns.

## Do not ask

Each of these is excluded on measurement, not on taste.

- **Where is the word 'budget' used in agent.py?** Excluded twice over, and
  the second reason outlives the first.

  It used to search the whole workspace, find `data/holdout-expects.txt` and
  read its own answer out of an earlier run's transcript, filling the screen
  with `data/holdout-*.txt` paths while it happened. **That is fixed**: the
  CLI now runs in a workspace where the agent cannot read any of its own
  transcripts, so a run on this path names none of them (measured: zero
  transcript paths in the trace).

  It is still excluded, because what the fix revealed is worse. Sealed, the
  search from `.` returns `agent.py:194`, `195`, `207`, `211` and `370`
  before it reaches the answer at `agent.py:598` -- and those earlier lines
  are comments in which this repository *documents its own past failures on
  this very question*, including the sentence "answered that the word
  'budget' is not used anywhere in the file". Six of the first seven matches
  are commentary about the question.

  On the demo path the agent then ran the identical search three times and
  answered **"Where the word 'budget' is used in agent.py"** -- the question
  restated, not an answer. Ten runs through the evaluation harness: 0/10, all
  ten answering `agent.py:194` word for word.
- **What is 15% of 2480, and then that result multiplied by 3?** The number is
  right and the sentence is not: "15% of 2480 is 1116, and that multiplied by
  3 gives 1116." Fifteen percent of 2480 is 372. It collapses both steps into
  one `calculate` call and narrates them wrongly. Anyone in the room doing the
  arithmetic will see it.
- **Finally, what is 10% of that?** 0/10. The fourth link of a chain resolves
  "that" to the wrong earlier answer, the same failure as question 5 above.
  Two links are safe; four are not.
- **What is inside the data directory?** 3/3 wrong here at eight steps, 4/10 in
  the evaluation. It reaches for `list_directory`, gets the right listing, and
  then does not stop.
- **What is the weather in Bangkok right now?** 6/10 alone, 3/10 after a
  conversation. It invents a temperature or answers the previous question.
- **How many minutes are in 3 days and 7 hours?** 0/10. It uses 3,600 seconds
  per hour and answers 29,520.
- **And sandbox.py?** or any elliptical follow-up about a file. It picks
  `read_file` and copies a number out of the conversation; the same question
  asked in full picks `file_info` and is right.
- **Which of two files is longer**, and **what is the last line of X**.

## If something goes wrong on the day

Ask the next question rather than retrying the same one: a repeat with the
failure in history is more likely to fail again. The worst thing the agent
will say is its own honest fallback, "I ran out of reasoning steps before
reaching an answer" -- it does not invent a number when it gives up.
