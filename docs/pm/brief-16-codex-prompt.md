# Brief 16 — the paste-ready task for the security engineer

> **DO NOT PASTE YET.** This brief needs `agent.py` and `config.py`, which
> brief 14 is holding. Paste it when the manager says brief 14 is merged, and
> take the test-count baseline from the manager at that moment — briefs 14 and
> 15 will both have moved it.

Paste everything below the line. The companion brief is
`docs/pm/brief-16-three-defaults-and-the-one-brief-14-took.md`; `## Result`
goes there.

---

You are the **security engineer** on OmniAgent, `D:\code-project\OmniAgent`.
**Branch from `main` at the commit the manager names, work in your own
worktree, commit to your own branch — never to `main`.** The manager merges.

**Read `docs/pm/brief-16-three-defaults-and-the-one-brief-14-took.md` and
execute it.** Three parts, three commits, a fourth for your report. **No model
run, and no test may contact a model server.**

These are the defects the contract names and that briefs 14 and 15 were told
to leave alone, so fixing one could not hide in someone else's diff.

## Measured on `f6a02dd`, and one correction

**Ignore `config.py:16` and `:20` if you have seen them cited as model
defaults — including in brief 14's table. They are a TOML example inside the
module docstring.** The manager got that wrong; the real disagreement is
three-way and worse:

| Where | Value |
| --- | --- |
| `agent.py:36` | `DEFAULT_MODEL = "qwen2.5:7b"` — the code default |
| `omniagent.toml:4` `[defaults]` | `model = "qwen2.5-coder:7b"` — the shipped file |
| `omniagent.toml` `[profile.demo]` | `model = "omniagent-v2"` — **the contract's approved baseline** |

`main.py:101` puts `DEFAULT_MODEL` in the `--help` text, so the help says
`qwen2.5:7b` while anyone with the shipped TOML gets `qwen2.5-coder:7b`. **The
model the contract approves, and that every figure in this repository was
measured on, needs `--profile demo` to reach.**

Retry: `agent.py:443` builds the client with `max_retries=0`;
`agent.py:261-262` gives the agent its own `max_retries`, default **2**.
Different knobs, and nothing says which applied.

`verbose`: `agent.py:260` defaults to `True`. `main.py:131` already has
`--quiet`, mapped at `:157-158`.

**The fourth defect is not yours.** `agent.py:493` and `:869` print the full
`base_url`; **brief 14 requirement 5 takes it.** Read those two lines and say
in `## Result` whether the string is gone. If brief 14 left it, that is a
finding about brief 14 — report it here, fix it there.

## Part 1 — one answer to "which model is this"

Make the three stop disagreeing, and **not by simply picking one value**. One
source of truth for the default, with `--help`, the shipped TOML and the code
agreeing. And **the resolved model and the layer it came from must both be
available to a caller** — `config.py`'s docstring says every resolved value
already remembers its layer, "so `--print-config` can show not just what the
agent will do but why". **Use that. Do not build a second mechanism.**

**Do not change the trial record** — brief 15 owns it. Expose the values.

**Flagged for the owner, and not yours to decide:** whether `python main.py`
with no model should work at all. Leave the default in place, make it
coherent, make it visible that it *was* a default. If you think the default
must go, say so in `## Result` and stop.

## Part 2 — two retry knobs, named as two

One place documenting both and saying which applies when; the
evaluation-facing path setting the agent's `max_retries` to **0** explicitly
rather than inheriting 2; and a test that both are discoverable and that
setting one does not silently move the other.

## Part 3 — quiet by default

`verbose` defaults to **`False`**; **add `--verbose`** so interactive use is
one flag away; `--quiet` keeps working and **both together is an error, not a
guess**; `[profile.collect]`'s now-redundant `verbose = false` **stays**, and
say so; one line in the README's CLI options.

## Mutations — restore from a scratchpad copy, never `git checkout --` alone

Ma change the code default without the TOML · **Mb make the layer provenance
always report "named"** · Mc set the demo profile's model to the base tag ·
Md default `verbose` back to `True` · Me let `--verbose` and `--quiet`
together resolve silently.

**Mb is the one to take seriously.** The whole value of part 1 is that a
recorder can tell a named model from a defaulted one, and a provenance field
that always says the same thing passes every test that only reads it. If
nothing goes red under Mb, you built a second mechanism instead of using the
existing one.

## Files you may touch

`agent.py` · `config.py` · `main.py` · `omniagent.toml` ·
`tests/test_config.py` · `tests/test_shipped_config.py` · `README.md`, **one
line**.

`tests/test_shipped_config.py` already ties the shipped TOML to the
evaluation's default so the two cannot drift. **Read it and extend it rather
than writing a second test of the same thing.**

## Files you may not touch

`tools.py` · `sandbox.py` · `secure_search.py` and its branches ·
`scripts/**` (**brief 15 is in a new module there**) · the trial record and
anything brief 15 added · `tests/test_eval_workspace.py` · `eval-fixture/**` ·
`questions/**` · `models/**` · `data/**` · `omniagent-core/**` ·
`.github/workflows/**` · `NEXT_CHAT.md` · `docs/` except your `## Result`.

**Do not change the system prompt or any tool description** — they reach the
model every turn and are part of every training example.

**Do not touch `[profile.demo]`'s model or `max_steps`.** Both are pinned on
measurement, the TOML says why in its own comments, and that profile is the
contract's approved baseline. Mc proves you cannot.

## Gates

```
.venv\Scripts\python.exe -m ruff check .
.venv\Scripts\python.exe -m mypy
.venv\Scripts\python.exe -m pytest
```

Full path, **never your own `-q`**. **Take the baseline count from the manager
when this is issued**, not from any number written in the brief.

## The one thing that would make this wrong

**Making the three model values agree by deleting the one that matters.**
`[profile.demo]`'s `omniagent-v2` is the contract's approved baseline and the
only tag any figure here was measured on. The disagreement is the defect; that
value is not the part to throw away.

The second way: **fixing the fourth defect because it is right there.** It is
brief 14's, it may already be done, and two engineers in the same two lines of
`agent.py` is how this repository voided three measurements.
