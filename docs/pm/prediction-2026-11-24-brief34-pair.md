# Prediction for SE brief 34 (`45cbd0e`) against its parent (`1384d63`), written before any request

**From:** AI/ML engineer · **2026-11-24** · branch `aiml/brief34-measure-20261124`. Instruction acted on (PM 01, relaying the
owner): "measure SE brief 34, `se/brief-34-line-count-routing` @ 45cbd0efbd69dc287ce210a1f360192d95a27084 ... against its own
parent 1384d63", one server session, interleaved arms, 7 questions x 10 passes x 2 arms = 140 runs at temperature 0. Nothing is
run until this file is on both remotes. The SHA under test existed before this file (SE wrote it); I have not run it.

## What changed, as I verified it (MEASURED by `git diff 1384d63 45cbd0e`)

One commit, `tools.py` plus a static test. Only the last sentence of the `read_file` too-long error: it used to say "Use
file_info for size or line facts and search_text to locate relevant text", and now says "For its size or line count, call
file_info next (Action: file_info, Action Input: <path>). Use search_text to locate relevant text." No tool description, no system
prompt. The error is reachable only when `read_file` is called on a file over the limit: q2 (`config.py`) and q7 (`observability.py`).
q1, q3, q4, q5, q6 do not reach it on any path I have seen (q3 reads a short file; q4/q6 call `list_directory`, `search_text`,
`count_matches`).

## Design (and what I changed from the PM's proposal)

- **Two trees, one per commit, equal-length names** (`aie-measure-1384d63`, `aie-measure-45cbd0e`), one runner outside both, one
  Ollama session with no restart, `--temperature 0`, `--max-steps 8`, `--control-file observability.py`.
- **Interleave per pass, order alternating**: pass 1 parent then child, pass 2 child then parent, and so on. I do this by calling the
  runner once per arm and pass with `--passes n` on the same `--out` (finished runs are cached, so only pass n executes). This is
  **per-pass, not per-question**, interleaving: finer would need a new flag on a tested runner. In every earlier session each
  question gave one answer and one tool sequence in all ten passes, so within-session drift between blocks of seven runs is
  unlikely to matter; session-to-session drift, which is the thing that broke earlier comparisons, lands on both arms equally.
- **Residual confound I cannot remove:** the two arms differ in tree path. The path is printed by the program (`workspace:` line) and
  I found no sign it reaches the model's prompt (grep only, not proven). If q1/q3/q4/q6 differ between arms inside one session, that
  is the first thing I will suspect.
- Lock `.git/omniagent-eval.lock` before the first request, removed on exit; a watcher logs `/api/ps` every 5 s.

## Predictions, per question

**Before the change can matter: q2 and q7 (the oversize path).**

| Event (child arm unless stated) | My probability |
| --- | --- |
| `file_info` is called at least once in q2 | **50%** |
| `file_info` is called in at least 8 of 10 q2 runs | **35%** |
| q7 behaves like q2 (`file_info` called in both or neither) | **80%** |
| q2 correct (302) in at least 1 of 10 | **40%** |
| q2 correct in at least 8 of 10 | **30%** |
| q2 stays 0/10, with a wrong figure ("278" or "10,306") | **50%** |
| q7 correct (353) in at least 1 of 10 | **40%** |
| Parent arm: `file_info` ever called on q2 or q7 | **5%** |
| Parent arm: q2 correct or q7 correct in any run | **5%** |
| Parent arm reproduces its control: q2 "278", q7 "does not exist", all ten, same sequences | **55%** (session noise is real; the control moved q4, q6, q7, q5 between sessions) |

Reasoning: the model was told to use `file_info` in three places and used it 0 of 30, so more prose is a weak lever; but this edit
is different in kind, a copy-ready `Action:` line with the path filled in, and the model is fine-tuned on that exact format. I put it
near a coin flip, not above, because the central finding so far is that the model does not act on correct information that sits
next to its error (the line count in `1ce7c81`: 0 of 30). If `file_info` is called, I expect the count to be read correctly more often
than not (70%), because `file_info` returns the number directly.

- **Improvement** = `file_info` called in q2 or q7 **and** more correct answers than the parent in the same session. **Called but
  still wrong** counts as the model ignoring even a copied call, and I will report it that way. **Regression** = a correct answer
  at the parent that becomes wrong at the child, any question, or q1/q3 below 10/10.
- **What would surprise me:** `file_info` called in q3 (it does not reach the error); q2 improving but q7 not (or the reverse) in a
  way that points at file-specific memorisation of "278"; the child arm blank on q2 or q7.

**Unreachable questions: q1, q3, q4, q5, q6.**

- q1 and q3 10/10 in both arms, same steps and tools: **95%**. Either moving would surprise me.
- q4 and q6: the two arms give **the same answer and the same tool sequence** in this one session: **80%**, because the changed text
  is not on their path. A difference between arms on q4 or q6 would be a finding about the harness (path, ordering, session state),
  not about the tool text, and I would say so rather than credit SE's commit.
- q5: reads the real clock; the number of invented figures will vary; no claim, except that it does not differ by more than the
  spread I have already seen (3 to 6 of 10 invented) between arms: **75%**.
- Each question gives one answer and one tool sequence across its ten passes within an arm (q5 excepted): **75%**. A question
  landing at 3 to 7 of 10 would surprise me.
- **Links** since `1384d63`: blank if and only if an unregistered tool was called, and blank, exit 1 and the `[!] No answer` line
  coincide, in all 140 runs: **90%**.

## Reporting

Counts only: per question and arm, distinct answers, distinct tool sequences, exit codes, whether `file_info` was ever called,
blank-iff-unregistered-tool. If the arms are indistinguishable I will say so. Raw outputs stay local and uncommitted. This file
is never edited after it is pushed; scoring goes in a separate result document.
