# Demo script — 2026-10-10

Five questions, in this order, measured on the path the demo actually uses
(`main.py --profile demo`, not the evaluation harness). Three rehearsals on
2026-10-06 at commit `8914b63`: **15/15**, scored against the real expected
answers rather than a loose keyword match. 11 steps in total.

## Before you start

```bash
# Ollama does not autostart. From PowerShell, not Bash:
#   Start-Process "$env:LOCALAPPDATA\Programs\Ollama\ollama.exe" -ArgumentList "serve" -WindowStyle Hidden
.venv/Scripts/python.exe main.py --profile demo
```

The profile pins `omniagent` (the fine-tune, `num_ctx` 16384), `temperature 0`
and `max_steps 8` — the configuration every published figure was measured at.

## The questions

| # | ask this | expect to see | steps |
|---|---|---|---|
| 1 | Where is the word 'budget' used in agent.py? | `agent.budget.exhausted` | 3 |
| 2 | What is 15% of 2480, and then that result multiplied by 3? | 1116 | 2 |
| 3 | How many lines does tests/fakes.py have? | 122 | 2 |
| 4 | What is 7 factorial divided by 5 factorial? | 42 | 2 |
| 5 | What is 2 to the power of 11, minus 48? | 2000 | 2 |

Question 1 goes first on purpose. Asked fourth it was wrong in three of three
rehearsals; asked first, right in three of three. The search question is the
one that suffers from having a conversation in front of it.

## Do not ask

- **What is inside the data directory?** Replaced question 5 until 2026-10-06.
  It fails 3/3 here at 8 steps, and 4/10 in the evaluation. It reaches for
  `list_directory`, gets the right listing, and then does not stop. When it
  runs out of steps it says "I ran out of reasoning steps before reaching an
  answer", which is honest but is not a demo.
- **What is the weather in Bangkok right now?** 6/10 isolated, 3/10 after a
  conversation. It invents a temperature or answers the previous question.
- **How many minutes are in 3 days and 7 hours?** 0/10. It uses 3,600 seconds
  per hour and answers 29,520.
- **And sandbox.py?** or any elliptical follow-up about a file. It picks
  `read_file` and copies a number out of the conversation. The same question
  asked in full picks `file_info` and is right. Arithmetic ellipsis ("now
  multiply that by 3") is fine.
- **Which of two files is longer**, and **what is the last line of X**.

## If something goes wrong on the day

Ask the next question rather than retrying the same one: a repeat with the
failure in history is more likely to fail again. The agent's own honest
fallback is the worst thing it will say.
