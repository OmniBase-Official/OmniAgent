# Proposed contract amendment: `inspect_config_precedence` is the seventh approved tool

**Status: PROPOSED. Not applied.** The owner approves, edits or declines; nothing edits
`agentic-mvp-contract-2026-11-03.md` until then. Owner ruling in the PM chat, 2026-11-25:
"A: Tool 7 record". Task C-SAE-01.

**MEASURED 2026-11-25 at `3b4bcd6`** (`origin` and `organization` agree), in a tree under
`.scratch\sae-seventh-tool` with `config_inspection.__file__` and `agent.__file__` printed
inside it. Evidence labels: MEASURED (I ran it), REPORTED (someone else's claim, not re-run).

## (a) The text, before and after

**Contract §2 "Tool capability", first paragraph (line 33).**

> **Before:** The current registry contains six tools: `calculate`, `get_current_time`,
> `file_info`, `read_file`, `list_directory`, and `search_text`. These are the only
> capabilities approved for the MVP; no new tool may be added without a security review.
> Every task in an evaluation must also have an explicit evaluator-side allowlist. The
> prompt's tool catalogue is not authorization; the dispatcher must enforce the allowlist.
>
> **After:** The current registry contains seven tools: `calculate`, `get_current_time`,
> `file_info`, `read_file`, `list_directory`, `search_text`, and `inspect_config_precedence`.
> The seventh statically describes the layer order of one workspace Python `resolve()`
> function: it parses the file without running it and returns the layer labels and branch
> conditions as written there (each at most 200 characters, the whole report at most 2,400),
> never environment values and never any other part of the file. It reaches files through the
> same sandbox admission as `read_file`. These are the only capabilities approved for the
> MVP; no new tool may be added without a security review. Every task in an evaluation must
> also have an explicit evaluator-side allowlist, which names `inspect_config_precedence`
> only for the tasks that need it. The prompt's tool catalogue is not authorization; the
> dispatcher must enforce the allowlist.

**Contract §6 row "Tools" (line 139).**

> **Before:** | Tools | Existing six read-only tools only; task-specific allowlist in evaluation | Allowlist implementation and tests required |
>
> **After:** | Tools | Seven read-only tools only (the six, plus inspect_config_precedence); task-specific allowlist in evaluation | Allowlist implementation and tests required |

The third column is left as it is. It may be stale (brief 20 added per-guard allowlist tests); that is
not this amendment's question, and I have not checked it.

*I wrote "never any other part of the file" with care: the report does copy two kinds of text
from the file, labels and `if` conditions, and the paragraph says so. A claim of "metadata only"
without that would be false.*

## (b) What the tool does and does not do

Every line below is tied to a file; the tests were run by me (below).

| claim | where | proof |
| --- | --- | --- |
| it opens exactly one file, admitted by the sandbox | `config_inspection.py:646-647` (`workspace.resolve`, then `workspace.read_text`) | `tests/test_config_precedence_metadata_only.py::test_m3_only_the_named_file_is_opened` (`:155`), with a canary at `:170` showing the recorder does see a second read when one happens |
| the admission is the one the other tools use: UNC and null byte, outside the root, denied paths, hidden files, credential-named files, hard links | `sandbox.py:136-170` (`resolve`), `:238-240` (`read_text` resolves again) | read by me; the other file tools call the same two methods |
| it never runs the file | imports are `ast`, `dataclasses`, `sandbox` only (`config_inspection.py:5-8`); a count of `exec(`, `eval(`, `compile(`, `os.environ`, `getenv`, `open(`, `subprocess`, `socket`, `urllib`, `write_text`, `unlink` is **0** | MEASURED by `grep -c`, plus `ast.parse` at `:623` |
| environment values never reach the report | `config_inspection.py:446-500` | `test_m1_environment_values_do_not_reach_the_report` (`:84`) |
| source outside the layer rows (constants, comments, other function bodies) never reaches the report | `:422-445`, `:502-618` | `test_m2_source_outside_the_layer_rows_does_not_reach_the_report` (`:105`) |
| the file read is capped, and a longer file is refused, not cut | `sandbox.py:60` (`MAX_READ_CHARS = 16_000`); `config_inspection.py:653-655` | MEASURED by probe: a file past the cap returned `Error: c.py is too large to inspect completely.` |
| at most 20 layers, and a report past 2,400 characters is refused | `config_inspection.py:10-12`, `:477-478`, `:636-638` | `test_m4_an_error_about_the_source_is_bounded_like_the_report` (`:191`) |
| a name taken from the file is cut at 200 characters with a visible marker, and non-printable characters show as `?` | `config_inspection.py:372-386` (`_bounded_name`) | `tests/test_config_error_bound.py` (9 tests, `:67-157`) |
| labels are shown through `repr`, and conditions have their whitespace collapsed and are refused over 200 characters | `config_inspection.py:445`, `:86-115` | read by me; the 14 tests below pass |

**Re-run (MEASURED 2026-11-25, `3b4bcd6`):** `tests/test_config_precedence_metadata_only.py` and
`tests/test_config_error_bound.py` together: **14 passed**.

**Mutation, so the evidence is not "the tests pass":** I replaced the body of `_bounded_name` with
`return name` (no cap, no sanitiser) in my tree and ran `tests/test_config_error_bound.py`: **4 failed, 5 passed**
(`test_a_name_one_over_the_limit_is_cut_and_marked`, `test_an_over_limit_name_is_cut_and_marked_in_the_error`,
`test_a_whitespace_only_name_is_bounded_like_any_other`, `test_control_and_bidirectional_characters_are_shown_as_question_marks`).
I restored `config_inspection.py` from a saved copy: hash `5e70f0cfa47475cd` before and after, equal; the tree was clean.
The PM's own three mutations of brief 33 (raw echo 2 red, no sanitiser 1, cap 2000 4) are **REPORTED**, not re-run by me,
and I did **not** mutate brief 32's four checks.

## (c) What stays true

- **Read-only, no network, no writes, no delegation:** contract §1 (line 13) is unchanged, and the module has no
  write, network or process call (the count above).
- **Loopback-only:** the tool never touches the model endpoint.
- **Tool outputs are capped:** the report at 2,400 characters (`config_inspection.py:12`); the loop's own observation
  cap (`agent.py`, `cap_observation`) still applies on top of it.
- **The dispatcher enforces the allowlist:** `tools.py:443` refuses a name outside `FIXED_TOOL_ALLOWLIST`, and `:458`
  narrows it to the task's list. The name is in the fixed list (`tools.py:301-311`, at `:309`) and the tool is
  registered at `tools.py:1300-1307`.

## (d) Residual risks, with honest severity

1. **[LOW] A hostile file makes the tool "crash" instead of refusing.** *MEASURED 2026-11-25.* A 14,000-character file
   holding `def resolve():` and one line of 7,000 `1+1+...` terms makes `ast.parse` raise `RecursionError`.
   `config_inspection.py:624` catches `(SyntaxError, ValueError)` and `:658` catches `(TypeError, ValueError)`, so it reaches
   the dispatcher's catch-all at `tools.py:502-512`, which logs `tool.crashed` at ERROR and returns
   `Error: tool 'inspect_config_precedence' raised RecursionError: maximum recursion depth exceeded during ast construction`.
   A 3,000-link attribute chain (`a.b.b...`) does the same. *Actor:* whoever wrote a file in the workspace the model is
   pointed at. *Impact:* a raw exception name in the model's observation; no file content leaks (the text is fixed).
   *Fix:* add `RecursionError` to the `except` at `config_inspection.py:624`; the test is the 7,000-term file asserting the
   clean `cannot inspect` error, and it must go red when the fix is removed. **SE.**
2. **[LOW] File text reaches the model's context.** Labels and conditions are copied from the file, up to 20 rows, 2,400
   characters in all. It is the same channel as `read_file` on the same file, and it carries the same prompt-injection
   exposure. **Prompt injection through a label was not tested.**
3. **[LOW] A route outside the model.** `agent.py:622-631` and `:829-830` send a question that mentions `config` or
   `configuration` together with `precedence`, `override`, `layer order` or `priority order` straight to the tool, with
   `config.py` hard-coded (`agent.py:904-946`), **without a model call**. It honours the task allowlist, but a refusal
   there is an answer string, not the §2 policy-violation stop. Not a security hole; it matters to evaluation validity (see (f)).
4. **[LOW, UNVERIFIED] Two resolutions of one path.** The tool resolves, then `read_text(display(path))` resolves again
   (`config_inspection.py:646-647`, `sandbox.py:240`). A concurrent writer between the two calls is the weak attacker class 4
   of the threat model. *What would settle it:* reading the sibling tools' call order; I did not.
5. **UNMEASURED: the model's use of the tool.** The brief says the model calls it on line-count questions about
   `config.py`. **I did not verify that.** What I can say is that the dispatcher *permits* the model to call it with any
   `path` the sandbox admits, and that a file with no `resolve()` gets a clean error (probe: no `resolve`, and an empty file).
   Whether the model misuses it is for AI/ML to measure.

## (e) What the owner approves, and what declining does

- **A. Approve as written.** The PM applies the two replacements above with an amendment record, as was done for the
  endpoint (2026-11-22). No code changes. Risk 1 stays open as a Low.
- **B. Approve, and ask the SE to close risk 1 first.** A one-line catch and one test; then the PM applies the text. My
  recommendation, because the sentence about sanitized errors is easier to defend with it closed.
- **C. Decline.** The SE removes the tool from the registry (`tools.py:1300-1307`), from `FIXED_TOOL_ALLOWLIST`
  (`tools.py:309`; `main.py:94` follows) and removes the route (`agent.py:622-631`, `:829-830`, `:904-946`) with its tests;
  AI/ML then re-measures anything that depended on it. The contract then stays at six, as it reads today.

## (f) The effect on the evaluation

**Yes, the evaluator-side allowlist must name it, or leave it out, task by task.** `FIXED_TOOL_ALLOWLIST` already contains
the name, and an agent built without `allowed_tools` allows every name in it (`agent.py:703-706`). So an evaluation
that does not pass an explicit list lets the model call this tool in every category, and a call in the injection and
tool-policy category (contract §3, line 71) would be *allowed*, not a policy violation. The amendment's "names
`inspect_config_precedence` only for the tasks that need it" turns that into a rule. Separately, the deterministic route
(risk 3) intercepts a fixture question whose text matches it before the model is asked; fixture authors must avoid that
wording or count the question as a route test, not a model trial.

## What this document does not establish

- That the model uses the tool correctly, or that a label can carry an injection (never tested).
- That brief 32's checks M1 to M3 fail when their guards go (I did not mutate them).
- That `_append_conditions` and the merge rows (`config_inspection.py:502-618`) are free of other failure paths
  beyond the one I probed; I probed six input shapes, not a fuzz.
- Whether §6's third column is stale; anything about CI.
