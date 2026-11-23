# Prediction, written before the tool-text change has a SHA

**From:** AI/ML engineer · **2026-11-23** · branch `aiml/tool-text-measure-20261123`, off
`aiml/first-measurement-20261123` @ `dc0c78d`. Written and pushed **before SE 01's SHA exists**, and before any model request
for this step. The two earlier predictions are quoted unedited in their own documents; this one is scored the same way.

## 1. What I know and what I do not

**What I was told (by the PM, nothing else):** SE 01 changes two things on `se/brief-31-tool-text`, cut from `1384d63`.
The `read_file` error for a file that is too long will carry the **line count**, and the `list_directory` output will
carry an **entry count with a per-extension breakdown**. The system prompt and guard G2e are untouched.

**What I have not seen:** the change itself, its wording, its branch, or its diff. I did not look. Every prediction
below is from the PM's description and the behaviour I measured at `b164aaa`; if the real change differs, the
predictions that depend on it are void and I will say which.

**What I did check (read-only):** `1384d63` is `b164aaa` plus five commits. In the code that runs the agent, **only
`main.py` changed (+21 lines): an empty answer now prints `[!] No answer: <fixed sentence>` and exits 1**, and it returns
*before* the `OmniAgent:` line is printed. The rest is my record layer, which does not touch the agent. So the base differs
from my temperature-0 baseline in how a blank answer is *reported*, not in what the agent does.

## 2. The structural prediction the rest depends on

At temperature 0, five of six questions gave the identical answer, steps and tool sequence in all ten passes. **So I
predict each question will again move all-or-nothing: either about ten of ten change, or about none.** A question landing
at 4 of 10 would surprise me, because it would mean the change turned a deterministic path into a sampled one.

## 3. Which questions should change, and which should not

The change can only reach a question if its path goes through a `read_file` error or a `list_directory` result.

| Question | Reachable by the change? | Baseline at T = 0 on `b164aaa` | Prediction |
| --- | --- | --- | --- |
| q1 arithmetic | **No** (`calculate` only) | 10/10, 2 steps | **unchanged** |
| q2 line count | **Yes** (`read_file` error) | 0/10, always "278", 5 steps, never `file_info` | **changes toward correct** |
| q3 first line | **No** (a short file: the success path, not the error) | 10/10, 2 steps | **unchanged** |
| q4 file count | **Yes** (`list_directory`) | 0/10, always "50", `list_directory > search_text > calculate` | **changes toward correct** |
| q5 abstention | **No** (`get_current_time`, `calculate`) | 6 invented / 4 declined | **no systematic change**, see §4 |
| q6 file count, PM's wording | **Yes** (`list_directory`) | 0/10, blank 10/10, `list_directory > count_lines` | **may change toward correct, less sure** |

### The three questions I expect to move, with my confidence

- **q2: 65% that at least 8 of 10 are correct**, and if it flips, in fewer than 5 steps. The error text will state
  the figure the question asks for, and at 0.1 the model already copied the number sitting in that error (10,748). The
  25% case I worry about is the model still answering "278" (it ignored the hint toward `file_info` in 19 of 20 runs).
- **q4: 55% that at least 8 of 10 are correct**, in about 2 steps, answering straight from the listing. The risk is that
  the model still reaches for `search_text` and `calculate` after seeing the count, as it did without it.
- **q6: 45% that at least 8 of 10 are correct; 35% that it stays blank in 10 of 10; 20% something else** (a different wrong
  number, or a split). The invented `count_lines` call looks like the model wanting a count it was not given, so giving
  it one should remove the call; but the two wordings already behave differently on the same listing, so I trust this
  one least. **I expect q4 to move more reliably than q6.**

## 4. q5, separately

q5 does not go through either changed tool (its tool sequences are `get_current_time`, `calculate`, with one older run
touching `search_text`). **I predict no systematic effect: between 4 and 8 of 10 invent a share price (baseline 6), with
six different figures again, because `get_current_time` returns the real clock and the figures follow it.** It is not
a clean test of sampling and I do not treat it as one.

- An **improvement** would be 3 or fewer invented figures. A **regression** would be 9 or 10.
- **What would surprise me:** either of those, or the tool-name sequences changing. A large movement on a question the
  change cannot reach is evidence about the base or the clock, not about the tool text.

## 5. The check that nothing got worse, stated in advance

- **q1 and q3 stay 10/10 with unchanged steps and tool sequence.** Any change is a regression, and because the change
  cannot reach them it would also be evidence of drift I have to explain before attributing anything else.
- **Blank if and only if an unregistered tool was called: predicted to hold in 60 of 60 again** (it held in 120 of 120).
- **A new link, now that `1384d63` exists: a run exits 1 if and only if it printed `[!] No answer`, and a blank answer
  and a non-zero exit coincide in 60 of 60.** I do not record the exit code today; I will add it before the run. A blank
  run that exits 0, or an answered run that exits 1, would be a defect in the fix.
- **No new unregistered tool names beyond `count_lines`.**

## 6. What counts as an improvement and what as a regression

Reported per question, never summed into one score.

- **Improvement:** the correct count goes up **and** blank, unregistered calls and steps do not rise.
- **Not an improvement, reported separately:** a **blank answer turning into a wrong number**. It removes a visible failure
  and adds a silent wrong figure, which I would call worse, and the document will say so.
- **Regression:** any drop in a correct count; a rise in blank or unregistered calls; a rise in steps without a gain; a
  new unregistered name; q1 or q3 below 10/10.
- **Net-neutral:** nothing moves beyond what the question's own baseline spread allows (at temperature 0 that spread was
  zero for five questions, so "nothing moves" means the same answer, steps and tools).

## 7. What would surprise me, in one place

q2 still "278" in all ten · q4 turning **blank** (the model now calling `count_lines` where it did not before) · q6 blank in
10 of 10 **with the count printed in the observation just before it** (the model ignoring information it was given) ·
q4 moving while q6 does not, by a wide margin · any question landing in the middle (3 to 7 of 10) · q1, q3 or q5
moving at all · a blank run that exits 0.

## 8. The limit I am stating before I see any number

The comparison is **against `b164aaa`**, but SE's branch sits on `1384d63`. They differ only by the empty-answer output
format (§1), which I do not expect to change any answer. **Pre-registered rule:** if q1, q3 or q5 move, I treat that as base
drift or noise and **do not attribute anything to the tool text** until a control run at `1384d63` (the parent of SE's
commit, same runner, same discipline, about 14 minutes) separates the two. I will not run that control without asking.
Before scoring q4 and q6 I will also compare the count the tool *printed* with the tree: if the tool states a wrong
number, the model repeating it is a finding about the tool, not about the model.

## 9. What I do not predict

The wall clock; the specific wrong numbers if a question does not flip; the q5 figures; the exact wording the model
uses to report a count.
