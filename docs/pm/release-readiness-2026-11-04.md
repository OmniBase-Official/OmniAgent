# What is left before other people can use this

**Written 2026-11-04 by the project manager and solution system architect, at
`1f3698a` on `main`.** Everything measured here was re-derived from the
repository today, not taken from a document.

This is a plan, not an approval. **Nothing in it authorizes a release.**

## First: "deploy it to all people" is two different projects

The owner-approved contract
(`docs/pm/agentic-mvp-contract-2026-11-03.md`, section 1) scopes the MVP as
**"one user on one machine, reading a user-selected workspace"**. Two readings
of the request lead to very different work:

**(a) Distribution — many people, each running it on their own machine.**
The contract's security model mostly survives. Two things change, and both
matter:

- **Attacker class 3 stops being hypothetical.** Strangers will point this at
  repositories they cloned from anywhere. A hostile tree containing a
  junction aimed at `~/.ssh` is no longer a thought experiment, it is Tuesday.
  Brief 13 landed the guard and its test, so **we are ready for this one** —
  but its POSIX case still has no test that would notice the guard's removal
  (open item 3).
- **Attacker class 4 becomes plausible.** Some of those machines are shared,
  multi-user, or run other agents. **This is exactly the condition the threat
  model named as the thing that would reverse the `secure_search.py`
  ruling** (`docs/pm/threat-model-2026-11-02-the-search-boundary.md`,
  criteria 1 and 2). Going public is itself the "new owner decision" the
  contract says is required. **The parked work becomes live again at that
  moment**, and the three variants of it will need one brief and one Result
  rather than three branches.

**(b) Hosting — one deployment serving many users.**
A different project. The contract forbids it, `sandbox.py` is a leash on the
model and not process isolation, and the threat model says so in its own
words. If this is what you mean, say so and the threat model is rewritten
first, not patched.

**The rest of this document assumes (a).** If it is (b), stop here.

## What a stranger actually gets today — measured

| | Measured on `1f3698a` |
| --- | --- |
| install | `pip install -e .`, from a clone. **There is no `[project.scripts]` entry point** — `grep -c "project.scripts" pyproject.toml` is `0` |
| how it runs | `python main.py`, from the checkout. Not a command on their PATH |
| what ships | `pyproject.toml:46` — `py-modules = ["agent", "main", "tools", "observability", "export_dataset", "sandbox", "validate_dataset", "config"]`. **Nine flat top-level modules, no package** |
| the model | `README.md:227` tells them `ollama pull qwen2.5:7b` — the **generic base model** |
| the fine-tune | `omniagent-v2` is **not in the repository and not obtainable from it.** `models/` and `data/` are absent from `git ls-tree HEAD` |
| CI | `.github/workflows/ci.yml` only. `core.yml` lives on the `core-offline-runtime` branch, not on `main` |
| Python | `requires-python = ">=3.12"` |

### Two of those are release blockers, and neither is about code quality

**1. Installing this squats on eight generic top-level names.** `pip install
omniagent` puts `tools`, `config`, `agent`, `main`, `sandbox` into the user's
top-level import namespace. `import config` in any of their other code may now
find ours. This is not a style preference; it is a correctness problem for
anyone who installs it alongside anything else.

**2. The thing we measured is not the thing we ship.** Every figure this
project owns — the ten-run baselines, the question bank, the demo — was
measured on `omniagent-v2`. A stranger following the README gets `qwen2.5:7b`.
So either the fine-tune becomes obtainable, or **the README stops implying
that the measured behaviour is what they will see.** The contract already
flags the adjacent problem in section 5's closing line: passing the gates does
not prove "legal rights to third-party model/data assets". A fine-tune derived
from Qwen2.5 and a dataset collected from this repository both carry terms
that someone has to actually read before redistribution.

## The work, in blocks

### Block A — the contract's own six gates. Blocking, by the contract.

From `agentic-mvp-contract-2026-11-03.md` section 5. These define "ready" and
the owner has already approved them.

| Gate | State |
| --- | --- |
| 1. endpoint validation, no non-loopback host or proxy | **brief 14, in flight** |
| 2. dispatcher-enforced per-task tool allowlist | open. Brief 15 defines the field as data; **enforcement is unassigned** |
| 3. sanitized logging defaults, separate evaluation recorder | open |
| 4. canary tests: prompts, file contents, arguments, errors, secrets do not reach logs | open |
| 5. path-boundary regression tests **on every platform claimed as supported** | partly done — brief 13 covers Windows junctions; **the POSIX case has no test that fails if the guard is deleted** |
| 6. deterministic fixture/oracle, no-retry, stop-on-drift, answer-key isolation | **brief 15, in flight** (fixture/oracle/isolation); no-retry and stop-on-drift open |

**Gate 5 is the one that changes meaning under distribution.** "Every platform
claimed as supported" is a short list today because the claim is small. The
moment the README invites strangers, the claim grows to whatever they run.
Either the list is written down and tested, or the README says Windows only.

### Block B — four defects I verified today, each its own brief

Named in the contract, deliberately excluded from briefs 14 and 15 so they
cannot hide in someone else's diff:

1. `agent.py:36` defaults the model to `qwen2.5:7b`; `omniagent.toml:4` says
   `qwen2.5-coder:7b`. The contract: relying on an implicit default "is not
   acceptable".
2. The client is built with `max_retries=0` (`agent.py:443`) while the agent's
   own `max_retries` defaults to **2** (`agent.py:261`). Two retry layers, and
   the evaluation needs both recorded.
3. `verbose` defaults to `True` (`agent.py:260`) and prints the reasoning
   trace. The contract's approved policy is quiet by default.
4. `agent.py:493` and `:869` print the full `base_url`. The contract: "Do not
   log the full endpoint URL."

Small, independent, and each one testable without a model. **Four briefs, or
one brief with four parts and four commits** — my preference is one brief,
because they all live in `agent.py` and splitting them guarantees a collision.

### Block C — the evaluation the contract asks for

Brief 15 proves the oracle and the trial record on **one** category. Then: the
other five categories, two variants and three repeats each; a threshold and
reporting method proposed and **approved before the cohort runs**; then the
cohort. **None of this is authorized yet** and the contract says the 36-trial
pilot is exploratory, not a pass threshold.

**What it must not become:** a number on the README. The old instrument spent
three months producing figures that could not be quoted, and the contract's own
rule — do not use a legacy cohort as the new baseline — exists because of that.

### Block D — distribution, which the contract does not cover at all

1. **A package, not nine modules.** `src/omniagent/` with `agent.py`,
   `tools.py`, `sandbox.py`, `config.py`, `observability.py`, a `cli.py`
   where `main.py` is now, and the three dataset modules under
   `omniagent/dataset/`. `scripts/` stays out of the wheel: it is
   developer-only.
2. **An entry point.** `[project.scripts] omniagent = "omniagent.cli:main"`,
   so the install story is `pip install omniagent` and then `omniagent`.
3. **The model question, answered in writing.** Either `omniagent-v2` is
   published somewhere a stranger can pull it, with its licence checked, or
   the README states plainly which model it was measured on and what a base
   model does instead. **Do not ship a README whose numbers came from a model
   the reader cannot get.**
4. **CI that installs the wheel on a clean machine and runs it.** Today's
   `ci.yml` tests the checkout. A packaging mistake is invisible to that.
5. **A version and a changelog.** `version = "0.1.0"` has not moved while
   thirteen briefs landed.

### Block E — the hygiene you asked about

Measured today, and most of it is not in the repository at all:

| | |
| --- | --- |
| `.scratch/` | **96 MB** of pytest basetemps and investigation fixtures, inside the checkout, gitignored |
| `.codex-worktrees/` | **187 MB**, inside the checkout, gitignored |
| `.brief11-worktree/` | 1.3 MB, an abandoned worktree. It is what made `ruff` red for days |
| branches | **seven** `codex/*` branches, several pointing at commits already on `main`, two carrying parked `secure_search.py` variants |
| `stash@{0}` | an abandoned brief-11 attempt plus a stray whitespace edit to `scripts/smoke_train.py` that no brief authorised |
| `NEXT_CHAT.md` | **1,101 lines**, half of it superseded. Open item 6, mine |
| `docs/` | 40 files, of which 15 are PM briefs and reports. Fine for a working repo; worth a `docs/pm/README.md` index before strangers read it |

**None of this blocks a release and all of it is cheap.** The 284 MB is
untracked, so it ships to nobody; it costs disk and it makes `git status`
noisy, which is how three measurements got voided.

## The order I would take it, and why

1. **Finish briefs 14 and 15.** Both in flight. Nothing else touches
   `agent.py` until 14 lands.
2. **Block B as one brief** — four small fixes in `agent.py`, right after 14,
   same file, no collision.
3. **Block D1 and D2, the package move, as one mechanical commit.** It renames
   nine modules and rewrites every import in 30 test files and 11 scripts. It
   **must** be behaviour-free and provable: same test count, same output. It
   cannot be done while anyone is in `agent.py`, so it waits for 14 and B.
4. **Gates 2, 3, 4 and the POSIX half of 5.** Security engineer, one at a
   time.
5. **The model question (D3).** This is yours, not an engineer's: it is a
   licence and publishing decision.
6. **Block C's remaining categories, then the threshold, then the cohort.**
7. **Block E whenever a session has nothing better to do.** It is the only
   block I would let slip.

## The one thing that would make this plan wrong

**Treating "clean code" as the blocker.** The code is in good shape: 658
tests, ruff clean, mypy strict over 45 files, a sandbox with an invariant test
that asserts a property rather than a list, and a search walk that is five
times faster with byte-identical output. **What stops a stranger using this is
not the code.** It is that installing it squats on eight generic module names,
there is no command to type afterwards, and the model every number was
measured on cannot be obtained. Those three are the release, and none of them
is a refactor.

The second way: **doing Block D1 before 14 and B land.** A nine-module rename
during someone else's work in `agent.py` is the worst merge this repository
could arrange for itself.

---

# PM verification and the state of the three new chairs — 2026-11-04, `f1f711d`

## Only one of the three chairs has delivered

| Chair | Delivered |
| --- | --- |
| **solution architect** | `sae/architecture-record-20261104`, **merged to `main` at `f1f711d`** after verification. 855 lines across six files, **all under `docs/architecture/`, no production code.** It stayed in its lane exactly |
| **security engineer** | **nothing committed.** No branch, no worktree. Brief 14 has produced no commit |
| **AI/ML engineer** | **nothing committed.** No branch, no worktree |

Briefs 14, 15 and 16 have between them produced **zero commits**. That is not
a complaint, it is the state: the queue is written and nothing is moving
through it yet.

## The architect's findings, re-derived rather than read

**Every one reproduces, and the central one is worse than a style problem.**

| Claim | My result |
| --- | --- |
| the wheel ships 8 modules, the repo has 9 | **confirmed** — the built wheel contains `agent, config, export_dataset, main, observability, sandbox, tools, validate_dataset`. `dataset_provenance.py` is missing |
| `export_dataset.py:32` imports the missing one | **confirmed** — `from dataset_provenance import write_sidecar` |
| the installed artifact therefore breaks | **confirmed by causing it.** Unpacked the wheel outside the checkout, project root off `sys.path`, imported `export_dataset` under `-I`, and got **`ModuleNotFoundError: No module named 'dataset_provenance'`** |
| building in the checkout leaves `build/` and breaks the invariant | **confirmed** — `test_the_budget_expectation_is_not_unique_to_its_subject` failed on `build/lib/agent.py` and `build/lib/export_dataset.py`. I removed `build/` and the suite returned to **658 passed** |
| the module list lives in three places | **confirmed** — `pyproject.toml:46` `py-modules`, `:55` mypy `files`, `:166` ruff `known-first-party` |
| 20 of 30 test modules, 8 of 11 scripts | **confirmed exactly** |
| 63 import lines | **not reproduced.** I measure **48** counting only the nine root modules, and **79** if sibling `scripts/` modules count too. 63 is neither. The conclusion is unaffected — a package move rewrites roughly fifty import lines across 28 files — but **nobody should quote 63 until the definition is stated** |

**ADR-0002 is correctly marked Proposed and says it governs nothing until
approved.** Its options A to D are the owner's to choose, and its
recommendation — C, ship the missing module now and do the package move after
brief 14 and block B, with A's wheel-import test as the instrument that proves
B behaviour-free — is the right shape. **That recommendation is the decision in
front of you.**

## Three things I found while verifying, that make the defect worse

1. **CI is the reason this could not be seen, and the line is nameable.**
   `.github/workflows/ci.yml:37` installs with `-e`. An **editable** install
   puts the checkout on `sys.path`, so `dataset_provenance` resolves and the
   broken wheel passes. **The gate that was supposed to catch this is the
   thing hiding it.**
2. **CI never runs the test that holds the sandbox boundary.** `ci.yml:24` is
   `runs-on: ubuntu-latest`, so the Windows junction case is skipped by its
   `skipif`, and the only path-boundary test CI exercises is the symlink one —
   **which brief 13 proved stays green when the guard is deleted.** CI's green
   says nothing at all about the reparse-point guard.
3. **The runner is unpinned.** Brief 06 pinned `ubuntu-24.04` for `core.yml`
   precisely so a gate could not move under us, and that lesson never reached
   `main`'s own workflow.

# What makes this a project rather than a notebook

You asked what stops this reading as vibe coding. **The code is not the
problem** — 658 tests, ruff clean, mypy strict over 45 files, invariants that
assert properties rather than lists, a search walk five times faster with
byte-identical output. What reads as a notebook is everything around the code,
and all of it is measurable:

| Measured today | Why it reads as a notebook |
| --- | --- |
| **the artifact is broken and nothing tests the artifact** | a project tests what it ships; this one tests the checkout it was written in |
| **`version = "0.1.0"`, one tag in the whole history** | sixteen briefs landed and the version never moved. There is no way to say "the one with the fast walk" |
| **no `CHANGELOG.md`** | the history lives in commit messages and PM briefs. A user cannot see what changed between two states |
| **no `CONTRIBUTING.md`, no `SECURITY.md`, no `py.typed`** | **the project's standards live in the PM's prompts, not in the repository.** Ten runs not three, mutation checks, the no-`-q` trap, never two model runs at once — a stranger cannot find any of it, and CI enforces none of it |
| **`NEXT_CHAT.md`, 1,101 lines, at the repository root** | the front door is a working journal, half of it struck through |
| **`docs/` is 40 files, 19 of them PM briefs and reports** | process outweighs product. There is no user-facing documentation tree |
| **7 `codex/*` branches, 284 MB of in-tree scratch and worktrees** | nothing is pruned, and `git status` noise is how three measurements were voided |
| **the numbers came from a model nobody can obtain** | `README.md:227` says pull the base model; every figure was measured on `omniagent-v2` |

## The shortest path from here, in order

1. **Decide ADR-0002.** My recommendation is the architect's: **C**. It is the
   only option whose first step collides with nothing in flight and whose test
   becomes the instrument for the second step.
2. **Option A as one brief, now** — `pyproject.toml`, `.gitignore`, and a test
   that **builds a wheel outside the checkout and imports every module in
   it**. That test is the one thing on this list that converts "we think it
   ships" into "we know it ships". **Fullstack engineer**; ask first if it is
   offered to Codex, whose sandbox has not been shown to permit a subprocess
   build.
3. **Fix CI so it can see what A fixes**: install the built wheel rather than
   `-e` in at least one job, pin the runner, and add a Windows job — without
   which the sandbox's load-bearing test never runs anywhere. **Security
   engineer**, because two of the three reasons are security ones.
4. **Briefs 14, then 16, then the package move (B).** The order is forced by
   `agent.py`. **Security engineer**, then **fullstack engineer**.
5. **Governance as one small brief, not a ceremony**: `CHANGELOG.md` starting
   today, `CONTRIBUTING.md` stating the gates and the mutation rule where a
   stranger can read them, `SECURITY.md` saying what `sandbox.py` is and is
   not, and a version that moves when something lands. **Fullstack engineer.**
6. **The model question** — **yours**, not an engineer's, because it is a
   licence and publishing decision.
7. **The journal leaves the front door.** `NEXT_CHAT.md` split and moved under
   `docs/pm/`, with the README pointing at user documentation instead.
   **Mine.**

**What I would not do yet:** the cohort, the probe, or anything in the
contract's section 3 beyond brief 15. None of it is authorized, and none of it
changes whether a stranger can install this.
