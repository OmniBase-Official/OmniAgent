# Video script — how to use OmniAgent

For a 6–8 minute screen recording that ends with "clone it and run it
yourself". Every command here has been run; every question in the demo
sequence is measured. Nothing in this file is a guess.

**The one rule:** anything not in the measured list below has to be rehearsed
before it goes on camera. Three separate defects in this project were found by
a hand run while the test suite and the evaluations were green — `2779d46`
(six of them), `06f9ab0` (two more, visible only on the demo path), and the
step-count error in this very document on 2026-10-10. A question you have not
run is a question you do not know the answer to.

## Before you record

```bash
.venv/Scripts/python.exe -c "import httpx;print(httpx.get('http://localhost:11434/api/tags').status_code)"
```

Expect `200`. If not, start Ollama and wait ~15 s:

```powershell
Start-Process "$env:LOCALAPPDATA\Programs\Ollama\ollama.exe" -ArgumentList "serve" -WindowStyle Hidden
```

Then, off camera:

- `git status` is clean, so nothing half-finished is on screen.
- `.venv/Scripts/python.exe -m pytest` passes. The count it prints is the
  number you quote in the recording; do not quote one from memory.
- Terminal font large enough to read at 1080p. The ReAct trace is indented and
  the indentation carries meaning.
- Close anything that might surface a notification.

## Beat 1 — what it is (30 s, no terminal)

Say it plainly: a ReAct agent that runs entirely on your own machine through
Ollama, with the loop hand-written rather than taken from a framework. Nothing
leaves localhost. The point of the project is not the agent — it is that every
claim about it was measured.

## Beat 2 — start it (30 s)

```bash
.venv/Scripts/python.exe main.py --profile demo
```

The banner is worth pausing on: profile, workspace, session id, log file,
endpoint `http://localhost:11434/v1`, model `omniagent-v2`. Point at the
endpoint — that is the whole local-only claim in one line.

## Beat 3 — the five questions (3 min)

Type them in this order. **The order matters**: a follow-up has to come
directly after the question it refers to. Asked fifth, "Now subtract 728 from
that" reached back past its antecedent in three of three rehearsals.

| # | type this | expect | steps |
|---|---|---|---|
| 1 | `What is 144 * 12?` | 1728 | 2 |
| 2 | `Now subtract 728 from that.` | 1000 | 2 |
| 3 | `How many lines does tests/fakes.py have?` | 122 | **3** |
| 4 | `What is 7 factorial divided by 5 factorial?` | 42 | 2 |
| 5 | `What is 2 to the power of 11, minus 48?` | 2000 | 2 |

Measured at **60/60 across twelve runs** on this path, one of them by hand.

**Narrate question 2.** The answer comes back as "the result of subtracting 728
from the product of 144 and 12 is 1000" — it names its own antecedent instead
of saying "that". That is the memory working, and it is visible in the
sentence.

**Narrate question 3, and do not apologise for it.** It takes three steps and
the second observation is an error:

```
Observation : Error: tests/fakes.py is 3,670 characters, too long to return in
              full. ... Use file_info for its size, first line and last line,
              or search_text to find something inside it.
Thought     : Since read_file cannot show me how many lines a long file has,
              I will use file_info instead.
Action      : file_info
```

This is the best moment in the demo. A tool refuses, the error names the tool
that can answer, and the agent takes the hint. Say that out loud — it is the
difference between a guardrail and a crash.

## Beat 4 — the filesystem boundary (1 min)

Still inside the session, show the tool list:

```
/tools
```

Then, off the agent and in a second terminal, show the boundary directly.
These are tool-level calls and their output is exact:

```bash
.venv/Scripts/python.exe -c "import sys;sys.path.insert(0,'.');from pathlib import Path;from sandbox import set_workspace, without_own_transcripts;import tools;set_workspace(without_own_transcripts(Path('.').resolve(), Path('data/demo.jsonl')));print(tools.read_file('C:/Windows/win.ini'));print(tools.read_file('.env'))"
```

```
Error: path is outside the workspace (D:\code-project\OmniAgent); only files
under it can be read
Error: hidden files and directories (anything starting with '.') are not
readable
```

**Do not ask the agent to read a file outside the workspace as a question.**
Whether the model reaches for `read_file` with that path is not measured, and
an unrehearsed question on camera is the mistake this project has already paid
for three times. Call the tool directly, as above, where the refusal is
certain.

## Beat 5 — clone and run it yourself (1–2 min)

Show `README.md`, then the four steps it already documents:

```bash
git clone https://github.com/mntoyg/OmniAgent.git
cd OmniAgent
python -m venv .venv
.venv\Scripts\activate
pip install -e .
ollama pull qwen2.5-coder:7b
python main.py
```

Note the licence on screen: MIT, so viewers can use, modify and redistribute
it. Say the base model is Qwen2.5-1.5B-Instruct under Apache-2.0, and that
the fine-tune is reproducible from the dataset and adapter rather than only
from the published weights.

## Do not ask, on camera or otherwise

Each of these is excluded on measurement. The full reasoning, with figures, is
in `docs/demo-script.md`.

- **Where is the word 'budget' used in agent.py?** 0/10. It answers from a
  comment in `agent.py` that documents a past failure on this same question.
- **What is 15% of 2480, and then that result multiplied by 3?** The number is
  right and the sentence is wrong: "15% of 2480 is 1116, and that multiplied by
  3 gives 1116". Anyone doing the arithmetic in the room will see it.
- **Finally, what is 10% of that?** 0/10. Four links of a chain is one too
  many; two are safe.
- **What is inside the data directory?** Its answer depends on what the last
  run wrote there.
- **What is the weather in Bangkok right now?** It invents a temperature, or
  answers the previous question.
- **How many minutes are in 3 days and 7 hours?** 0/10 — it uses 3,600 seconds
  per hour.
- **Any elliptical follow-up about a file** ("And sandbox.py?"). It picks
  `read_file` and copies a number out of the conversation. The same question
  asked in full picks `file_info` and is right.

## If something goes wrong while recording

- Wrong answer on a measured question: stop, do not edit around it. It means
  something changed since the last rehearsal, and the recording is not the
  problem to fix first.
- Model missing: `ollama list`, and the demo profile pins `omniagent-v2`.
  Falling back to `omniagent` is one line in `omniagent.toml` and is also
  measured, at 30/30 on this path.
- A step count differs from the table: that is a real finding. Note it and
  re-rehearse before publishing the video.
