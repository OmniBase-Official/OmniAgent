# Prediction for the control question q7, written before the tool-text change has a SHA

**From:** AI/ML engineer · **2026-11-23** · branch `aiml/tool-text-measure-20261123`. A second file next to
`prediction-2026-11-23-tool-text.md`, which is unedited and still governs the six original questions. Pushed before SE 01's
SHA and before any model request for this step.

## 1. Why this question exists

At temperature 0 the model answered **"278" lines for `config.py` in 10 of 10 runs**, and at 0.1 it answered "10,306" in 6.
Both figures sit in a comment in `tools.py` and in 76 of 7,551 on-disk training examples, and in none of the model's
context in any of my runs. So after SE 01's change a surviving "278" would be ambiguous: the new `read_file` text did not
help, or the model is repeating something it memorised about `config.py`. The PM asked for a control that separates the two.

## 2. The question and the file I chose

**q7: "How many lines does observability.py have?"**, the same wording as q2 with the file name changed, asked in the
same runner, with the same flags, 10 passes, at **both** tips (`b164aaa` and SE's), temperature 0. The true count is derived
from the tree at run time, never written down.

**Why `observability.py`:** at `b164aaa` it has **353 lines and 11,978 characters.** It is the closest file to `config.py`
(302 lines, 10,748 characters) among the root modules, so `read_file` takes the same too-long error path. Neither figure
contains 278, 10,306, 10,748 or 302, and SE 01's change touches `tools.py` (and `main.py` for another brief), not this file.
**What it does not control for:** `observability.py` may also be in the training data, and its true count may be
memorised or misremembered like anything else. I have not checked and will not read it before the run.

## 3. How the PM's reading maps onto the outcomes

| q2 (config.py) at the new tip | q7 (observability.py) at the new tip | Reading |
| --- | --- | --- |
| still "278" | answers a wrong figure, or "278" | the text did not help, and the figure is not file-specific |
| still "278" | the **true count** | the text helps, and "278" for `config.py` is file-specific memorisation |
| the true count | the true count | the text helps; memorisation was not what was in the way |
| the true count | a wrong figure | the text helps for one file and not the other; I would not interpret it without more runs |

## 4. The prediction

**Baseline at `b164aaa` (10 extra runs of q7, temperature 0):**
- **q7 is wrong in at least 8 of 10 runs**, 80% confident, for the same reason q2 is: the `read_file` error gives a
  character count and no line count, and the model then reports a figure it was not given.
- **"278" is the answer in at most 2 of 10 runs** (80% confident). I expect "278" to be tied to `config.py` and the most common
  wrong answers to be the character count (11,978) or another invented figure. **What would surprise me: "278" in 5 or more
  of 10.** That would mean the figure is generic and not about `config.py`.
- **The ten passes agree with each other** (the same answer, steps and tool sequence in all ten) with 80% confidence, as
  five of six questions did at temperature 0. A split at 3 to 7 of 10 would surprise me.
- **The true count (353) in 3 or more of 10 at baseline would surprise me:** it would mean the model can get the line count
  of this file without being told, which q2 never showed.

**At the new tip, once the `read_file` text carries the line count:**
- **q7: 65% that at least 8 of 10 are correct**, the same confidence I gave q2, for the same reason, and **I expect q2 and
  q7 to move together.** I put 75% on "both at 8 or more correct, or both at 2 or fewer".
- The cell I trust least is the first row of §3 (both fail): it would mean the line count in the error is read past, which is
  what the model did with the hint toward `file_info` in 19 of 20 runs.
- **What would surprise me:** q7 correct while q2 is still "278" (15%; it would be the file-specific reading and the most
  informative outcome), or q2 correct while q7 is not (10%).

**Improvement, regression and net-neutral are as defined for the six questions.** A blank turning into a wrong figure is
reported apart and is not counted as better.

## 5. Timing and scope

If SE 01 ships the `read_file` change first and the `list_directory` change later, I measure **q2 and q7 only** at the
first tip, and the rest later at the final tip. If the SHA slips past today, q7 goes into tomorrow's run. q7 is **one extra
question and replaces none of the six.** It will be switched on by a flag (`--control-file observability.py`) so the
original six-question run is unchanged, and the baseline needs its 10 runs at `b164aaa` too.

## 6. What I do not predict

The specific wrong figures if q7 fails; the wording the model uses; the wall clock; any behaviour of the `list_directory`
change on this question (it does not use it).
