# Brief 16 — three defaults, and the one brief 14 already took

**For the security engineer. QUEUED, NOT ISSUED.**

> **Do not start this until the manager says brief 14 is merged.** Brief 14
> holds `agent.py`, `config.py`, `tests/test_config.py`,
> `tests/test_endpoint_policy.py` and `tests/test_local_only.py`, and this
> brief needs the first two. Two writers in one file is the failure this
> project has already paid for three times.

Static throughout. **No model run, and no test here may contact a model
server.**

These are the defects the contract names and that briefs 14 and 15 were told
to leave alone, so that fixing one could not hide it in someone else's diff.

## What is measured, 2026-11-04, on `f6a02dd`, clean tree

### A correction to my own earlier note

I wrote in brief 14's table that `config.py:16` and `config.py:20` carry
disagreeing model defaults. **They do not — those lines are a TOML example
inside the module docstring.** Do not go looking for defaults there. The real
disagreement is below, and it is worse than the one I described.

### The model is specified in three places and they disagree three ways

| Where | Value |
| --- | --- |
| `agent.py:36` | `DEFAULT_MODEL = "qwen2.5:7b"` — the code default |
| `omniagent.toml:4`, `[defaults]` | `model = "qwen2.5-coder:7b"` — the shipped file |
| `omniagent.toml`, `[profile.demo]` | `model = "omniagent-v2"` — **the contract's approved baseline** |

`main.py:101` advertises `DEFAULT_MODEL` in its `--help` text, so the help
string says `qwen2.5:7b` while a user who has the shipped TOML gets
`qwen2.5-coder:7b`. **And the model the contract approves, and that every
figure this project owns was measured on, is reachable only by typing
`--profile demo`.**

The contract's words: relying on an implicit default "is not acceptable", and
the digest must be frozen at preflight.

### The two retry layers

`agent.py:443` builds the client with `max_retries=0`. `agent.py:261-262`
gives the agent its **own** `max_retries`, default **2**. They are different
knobs — HTTP-level retries against agent-level re-attempts after a transient
failure — and nothing says which applied to a given run. The contract wants
`max_retries=0` and no replacement trial for evaluation, and **both layers
recorded and tested**.

### `verbose`

`agent.py:260` — `default=True`, "Stream the reasoning trace to the console."
The contract's approved policy is quiet and sanitized by default.
`main.py:131` already has `--quiet`, and `main.py:157-158` maps it to
`verbose = not args.quiet`. `omniagent.toml` `[profile.collect]` sets
`verbose = false` explicitly, which exists only because the default is the
wrong way round.

### The fourth defect is **not yours**

`agent.py:493` and `:869` print the full `base_url`. **Brief 14 requirement 5
takes that one.** Do not fix it again. **Verify it** — read those two lines and
say in `## Result` whether the string is gone. If brief 14 left it, that is a
finding about brief 14, reported here and fixed there.

## Part 1 — one answer to "which model is this"

The three places must stop disagreeing, **and the fix is not simply to pick
one value.**

Required:

1. **One source of truth for the default.** Whatever is left must make
   `--help`, the shipped TOML and the code agree. If the help text quotes a
   constant, it must quote the one that actually wins.
2. **The resolved model and the layer it came from must both be
   available to a caller.** `config.py`'s own docstring says every resolved
   value already remembers which layer it came from — "so `--print-config` can
   show not just what the agent will do but why". **Use that; do not build a
   second mechanism.** A recorder must be able to ask "was this model named,
   or defaulted?" and get an answer.
3. **Do not change the trial record.** Brief 15 owns it. Expose the values;
   let it carry them.

**Flagged for the owner, and you must not decide it:** whether
`python main.py` with no model named should work at all. The contract says an
implicit default is unacceptable *for a recorded run*; it does not say the
interactive CLI must refuse to start. **Leave the default in place, make it
coherent, and make it visible that it was a default.** If you believe the
default has to go, say so in `## Result` and stop there.

## Part 2 — two retry knobs, named as two

1. **One place that documents both**, saying which is which and which applies
   when. A comment at one of the two sites that points at the other is enough;
   two comments that each describe only themselves is what we have now.
2. **The evaluation-facing path sets the agent's `max_retries` to 0
   explicitly**, rather than inheriting 2. The contract asks for no automatic
   retries and no replacement trial.
3. A test that **both** values are discoverable from a resolved config, and
   that setting one does not silently change the other.

## Part 3 — quiet by default

1. `verbose` defaults to **`False`**.
2. **Add `--verbose`** so interactive use is one flag away from what it is
   today. `--quiet` keeps working; a user who passes both gets an error, not a
   guess.
3. `[profile.collect]`'s `verbose = false` becomes redundant. **Leave it and
   say so in `## Result`** — a redundant explicit setting is not a defect, and
   removing it is a change to a shipped profile that nobody asked for.
4. The README documents the new flag. **One line, in the CLI options section.**

## Tests that must fail first

| Test | Part |
| --- | --- |
| the `--help` model string equals the default that actually wins | 1 |
| the shipped TOML's `[defaults]` model equals the code default | 1 |
| a resolved config reports the model **and** the layer it came from | 1 |
| the demo profile still resolves to the contract's approved baseline | 1 — this one must pass **before and after**; it is the regression guard |
| both retry values are discoverable, and setting one leaves the other alone | 2 |
| the evaluation path resolves the agent's `max_retries` to 0 | 2 |
| `verbose` is False with nothing supplied | 3 |
| `--verbose` turns it on, `--quiet` turns it off, both together is an error | 3 |

`tests/test_shipped_config.py` already ties the shipped TOML to the
evaluation's own default so the two cannot drift. **Read it before you write a
second test of the same thing**, and extend it rather than duplicating it.

## Mutations that must go red

Restore from a scratchpad copy, **never `git checkout --` alone**.

| # | Mutation | Must go red |
| --- | --- | --- |
| Ma | Change the code default without changing the TOML | the agreement test |
| Mb | Make the layer-provenance always report "named" | the provenance test. **If nothing goes red, you built a second mechanism instead of using the existing one** |
| Mc | Set the demo profile's model to the base tag | the regression guard |
| Md | Default `verbose` back to `True` | the quiet test |
| Me | Make `--verbose` and `--quiet` together resolve silently | the conflict test |

**Mb is the one to take seriously.** The whole value of part 1 is that a
recorder can tell a named model from a defaulted one. A provenance field that
always says the same thing passes every test that only reads it.

## Files you may touch

`agent.py` · `config.py` · `main.py` · `omniagent.toml` ·
`tests/test_config.py` · `tests/test_shipped_config.py` · `README.md`, **one
line** for the new flag.

## Files you may not touch

`tools.py` · `sandbox.py` · `secure_search.py` and its branches ·
`scripts/**` — **brief 15 is in a new module there** · the trial record and
anything brief 15 added · `tests/test_eval_workspace.py` ·
`eval-fixture/**` · `questions/**` · `models/**` · `data/**` ·
`omniagent-core/**` · `.github/workflows/**` · `NEXT_CHAT.md` ·
`docs/` except your `## Result`.

**Do not change the system prompt or any tool description** — they reach the
model every turn and are part of every training example, so changing one
invalidates the dataset.

**Do not touch `[profile.demo]`'s model or `max_steps`.** Both are pinned on
measurement, the TOML says why in its own comments, and the demo profile is
the contract's approved baseline. Mc exists to prove you cannot.

## Gates

```
.venv\Scripts\python.exe -m ruff check .
.venv\Scripts\python.exe -m mypy
.venv\Scripts\python.exe -m pytest
```

Full path, **never your own `-q`**. Baseline at the time of writing: **658
passed**, mypy clean over **45** files. **Brief 14 and brief 15 will both have
moved that count before you start** — take the baseline from the manager when
this brief is issued, not from this line.

## Where to work

**Branch from `main` at whatever the manager names when this is issued, work
in your own worktree, commit to your own branch — never to `main`.** The
manager merges.

## The one thing that would make this wrong

**Making the three model values agree by deleting the one that matters.**
`[profile.demo]`'s `omniagent-v2` is the contract's approved baseline and the
only tag any figure in this repository was measured on. The disagreement is a
defect; that value is not the part to throw away. Mc is the guard.

The second way: **fixing the fourth defect because it is right there.** It is
brief 14's, it may already be done, and two engineers editing the same two
lines in `agent.py` is how this repository voided three measurements. Verify
it and report; do not touch it.

## Result

<!-- Engineer: append here. Whether agent.py:493 and :869 still print the URL
after brief 14; which value you kept as the single default and why; how you
used the existing layer provenance rather than adding one; the retry
documentation and where you put it; the CLI flag surface after part 3,
including what two conflicting flags do; Ma-Me each with the test that went
red, and for Mb whether anything went red at all; the three gate results
against the baseline the manager gave you; the branch and commit hashes; and
anything you refuse to claim, including that the trial record is brief 15's
and you did not touch it. -->
