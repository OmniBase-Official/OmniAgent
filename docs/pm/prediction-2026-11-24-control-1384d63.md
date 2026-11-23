# Prediction for the control run at `1384d63`, written before any request

**From:** AI/ML engineer · **2026-11-24** · branch `aiml/tool-text-measure-20261123`. Authorized by the PM
("A (control at `1384d63`): yes, it is warranted"). 70 runs: the six questions plus q7, `--temperature 0`, `--max-steps 8`,
`--verbose`, 10 passes, the same runner, on `1384d63`, the parent of SE's commit `1ce7c81`. Nothing in the tree prints a line
count in the `read_file` error. Pushed to both remotes before the first request. The earlier predictions are unedited.

## Why it is run

At `1ce7c81` three questions moved that SE's diff cannot reach (it touches only the `read_file` error): q4 `"50"` x10 to
**blank x10** (via `count_matches`), q6 **blank x10** (via `count_lines`) to `"9"` x10, and q5 from 6 invented figures to 3. The
control separates three explanations.

## The three readings, with my probabilities

| Reading | What `1384d63` would look like | My probability |
| --- | --- | --- |
| **(i) base or session** | q4 blank x10 via `count_matches`; q6 `"9"` x10; q5 about 3 invented, i.e. the same as `1ce7c81` | **45%** |
| **(ii) SE's commit** | q4 `"50"` x10; q6 blank x10 via `count_lines`; q5 about 6 invented, i.e. the same as `b164aaa` | **15%** (the diff cannot reach these paths) |
| **(iii) a third pattern, i.e. cross-session nondeterminism** | q4, q6, q5 differ from **both** earlier sets | **40%** |

I hold (iii) high because the baseline and the step-2 runs were separate server sessions and the project has measured the same
question at 1 in 10 and 6 in 10 on different days. If (iii) is right, **"temperature 0" does not make a figure reproducible across
sessions on this card, and no earlier cross-session comparison of mine is a clean attribution**, including the step-2 one.

## The other questions

- **q1 and q3: 10/10, same steps and tools** (95%). **What would surprise me:** either moving.
- **q2: 0/10** (95%). The answer, with no count printed: **"10,306" in 10 of 10 (45%)**, "278" in 10 of 10 (25%), a mix or another
  figure (30%). This tells whether the 278 to 10,306 shift at `1ce7c81` was the text or the session.
- **q7: 0/10** (95%), "12331" in at least 8 of 10 (70%).
- **A correct answer on q2 or q7 in even one run would surprise me.**
- **Each question gives one answer and one tool sequence across its ten passes** (80%), as five of six did in earlier runs.
  A question landing at 3 to 7 of 10 would surprise me. q5 is excluded: it reads the real clock.
- **Links:** blank if and only if an unregistered tool was called, 70 of 70 (95%); blank, exit 1 and the `[!] No answer` line
  coincide, 70 of 70 (95%), since `1384d63` carries the empty-answer fix.

## What counts as what

- Reading (i) or (iii) means the step-2 movement of q4, q6 and q5 is **not** attributable to the tool text, and the central
  finding (the count in the error is not used, q2 and q7 0 of 20) stands independently of it.
- Reading (ii) would contradict the diff and would mean something in SE's commit reaches paths I could not see.
- I will report counts to the PM first; a long document only if asked.
