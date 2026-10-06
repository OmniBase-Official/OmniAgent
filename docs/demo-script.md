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
| 3 | How many lines does tests/fakes.py have? | 122 | 2 |
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
