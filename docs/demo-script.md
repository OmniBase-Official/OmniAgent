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

Questions 1 and 2 open the demo because **a follow-up has to come directly
after the question it refers to.** Asked fifth, with three unrelated questions
in between, "Now subtract 728 from that" answered "144 multiplied by 12, minus
728 is 272" in three of three rehearsals -- 272 is 2000 minus 1728, so "that"
had reached back past its own antecedent to an earlier answer. First and
second, it is right in three of three. The pair is also the best thing to
show: it is the agent remembering across turns.

## Do not ask

Each of these is excluded on measurement, not on taste.

- **Where is the word 'budget' used in agent.py?** It searches the whole
  workspace, finds `data/holdout-expects.txt`, and reads its own answer from an
  earlier run's transcript back out of the log. The answer is right and it
  came from the wrong place, and the screen fills with `data/holdout-*.txt`
  paths while it happens.
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
