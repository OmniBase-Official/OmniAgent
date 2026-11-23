# Prediction, written before the temperature-0 run

**From:** AI/ML engineer · **2026-11-23, 16:1x local** · committed **before the first request of the run**. Quoted
verbatim in the result, including the parts that turn out wrong.

**What I already know when I write this, so no one mistakes it for a blind guess:** pass 2 at temperature 0.1 on this
same commit, model and questions (sixty runs, `docs/pm/measurement-2026-11-23-second-pass.md`). Nothing about the
temperature-0 behaviour has been observed. Ollama is not running as I write this; no request has been made.

**Setup the run will use:** commit `b164aaa` (tree `.scratch/aie-measure-b164aaa`, clean), `omniagent-v2:latest`, the same
six questions, 10 passes, `--max-steps 8`, `--verbose`, `--temperature 0`, one process per question.

## The general prediction, which the per-question ones rest on

**Temperature 0 will make runs resemble each other far more than at 0.1, and will not make them identical.** The project
has measured the same question answered correctly 1 time in 10 on one day and 6 in 10 two days later, at temperature 0
on this 4 GB card, so I do not predict determinism. I predict that for most questions the ten passes land in one or two
outcome classes instead of three or four.

**What would surprise me:** all six questions identical in all ten passes (true determinism, against the project's own
history); or the opposite, more distinct outcomes at 0 than at 0.1.

## Per question, ten passes each

| Question | Prediction | What would surprise me |
| --- | --- | --- |
| **q1** arithmetic | **10/10 correct**, `calculate`, 2 steps in every pass | any wrong answer, or any pass that does not call `calculate` |
| **q2** line count | **at most 2/10 correct.** The wrong answers collapse onto at most two distinct figures, and a character count reported as lines is the dominant one | 5 or more correct; or three or more distinct wrong figures |
| **q3** first line | **10/10 correct**, `read_file`, 2 steps | any wrong answer |
| **q4** count of files | **0/10 correct**, and **6 or more blank answers**, because at 0 the model should take the same path every time: the unregistered `count_lines` or the same alternative | any correct answer; fewer than 4 blanks |
| **q5** abstention probe | a **majority of 6 or more** in one class, and I expect that class to be **abstention**, with at most 2 invented figures. Low confidence: pass 2 split 4 / 4 / 1 / 1 | 5 or more invented figures; or abstention in 10 of 10 |
| **q6** PM's wording | **0/10 correct**, **6 or more blank answers** | any correct answer |

## The link between a blank answer and an unregistered tool

**It still holds exactly: a run is blank if and only if it called a tool outside the registry**, in all sixty. It held
in 60 of 60 at temperature 0.1, and nothing about temperature should separate the two events. **What would surprise me:**
one blank run without an unregistered call, or one unregistered call with a non-blank answer.

## Things I do not predict, because I have no basis

The wall-clock figure (a different measurement from the score, and the first run of a session carries a cold load);
the specific wrong numbers beyond "a character count dominates q2"; which unregistered names appear; the q5 figures.

## How this prediction will be scored

Per question, against the ten recorded rows, in the result document. A prediction that is wrong stays in the
document unedited. The pass-2 figures are not revised, and nothing from the two passes is pooled: the temperature is
in each row.
