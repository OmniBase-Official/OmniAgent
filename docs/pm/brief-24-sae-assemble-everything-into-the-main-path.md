# Brief 24 — assemble everything that is spread out into `D:\code-project\OmniAgent`, without breaking it

**For the solution architect (SAE). Issued 2026-11-22 by the PM at the owner's
request. Start only when the weekly meter allows (day 3, ceiling 42%, from 10:00
Thai time on 2026-11-23); do not start it while the meter is at or past today's
ceiling.**

## The owner's request, and the rule that came with it

The owner wants **every AI to work only under `D:\code-project\OmniAgent`** and to
stop building folders outside it (the standing location rule, appended to
`~/.claude/CLAUDE.md` and `~/.codex/AGENTS.md` today), and wants the files that are
spread out **brought into that folder, without breaking the codebase and checking
that it works,** because there is a lot of backlog and legacy code.

**What is spread out (MEASURED by the PM, 2026-11-22, `git worktree list`):** 49
registered worktrees — **30 Codex-app worktrees under
`C:\Users\Thanapat Manasom\.codex\worktrees`**, **6 siblings in `D:\code-project`**
(`OmniAgent-pm-b16`, `-pm-G`, `-pm-O` are the PM's; `OmniAgent-sae`, `-sae-b19`,
`-sae-b23` are yours), 1 in `AppData\Local\Temp`, 8 under `.scratch`, 3 session
trees under `.claude\worktrees`, and the main checkout. Dozens of remote branches
(`origin/codex/*`, `origin/claude/*`, `origin/sae/*`, `origin/pm/*`) carry the work.

## What "assemble" does NOT mean

- **It does not mean merging into either `main`.** The owner has not named which
  remote hosts the canonical line. **No push to a `main`, no force-push, no
  history rewrite.**
- **It does not mean copying O's legacy code.** O is preserved as the tag
  `legacy/origin-main-2026-11-05`; ADR-0003's carry-over inventory already says
  which O items are carried and which are dropped. Documents carry now; code
  carries only through issued, verified briefs.
- **It does not mean including branches nobody has verified.** The PM has verified
  briefs 16, 20, 21 and 22 only.

## Hard blocker, owner's: the main checkout is not ours yet

`D:\code-project\OmniAgent` holds **54 uncommitted changes that Codex is editing**,
on branch `chore/local-ai-delegate` (base `af99092`). **Do not read, write, switch
branches in, or test it** until the PM tells you Codex has committed that work to a
named snapshot branch (the owner has to paste the PM's message to Codex first; as
of this brief it has not been delivered). **Everything below is done in a worktree
inside the path** (`D:\code-project\OmniAgent\.scratch\sae-assembly`). The *switch*
of the main checkout is a separate step the PM performs with the owner's go.

## Phase 0 — inventory (read-only; do this first and send it before Phase 1)

One file, `docs/architecture/repository-assembly-inventory.md`, in two tables:

1. **Every registered worktree** (`git worktree list --porcelain`): path, branch,
   `HEAD`, number of dirty files, commits **not reachable from any remote branch**
   (`git rev-list <HEAD> --not --remotes`), and a verdict:
   **SAFE-TO-REMOVE** (everything on a remote and the tree clean),
   **UNIQUE-WORK** (list the unpushed commits and dirty files), or **UNKNOWN** (say
   what would settle it). **Remove nothing in Phase 0.** Your own three siblings
   are in the table too: say so if they hold anything the remote does not.
2. **Every remote branch** on `origin` and `organization`: its relation to G
   (`5005039`): *already in G*, *stacked on G*, *O line*, *carries `securefs.py`
   (blocked pending the owner)*, *PM-verified*, or *not yet verified*, and what is
   in it that is not anywhere else.

Count first, then judge: **the number of items whose only copy is in a worktree is
the figure the owner most needs.**

## Phase 1 — build the assembled tree, in a worktree inside the path

Branch `integration/canonical-20261122` **from G (`5005039`)**, in
`D:\code-project\OmniAgent\.scratch\sae-assembly`. Add the units **in this order,
one merge commit each, running the three gates after every unit** (a unit that
turns a gate red is reported and left out, not fixed by you):

1. SE brief 20 — `origin/claude/se-gate2-guard-tests-09c889` (`01a0938`)
2. SE brief 21 — `origin/claude/se-brief21-defaults-and-url` (`6831ba7`)
3. SE brief 22 — `origin/claude/se-brief22-endpoint-corpus` (`3ac11d7`)
4. **Documents:** from `origin/pm/verify-brief16` (tip carries the amended contract,
   the briefs, the owner-rulings record) the `docs/pm/` and `docs/architecture/`
   files that G lacks; and ADR-0005 and its two companions from
   `origin/sae/adr-0005-graph-runtime`. Do **not** carry the 22 untracked paste
   twins (they are local-only by the owner's ruling).

Brief 20, 21 and 22 touch disjoint files, but **no one has run all three
together.** Whether they merge cleanly and the suite stays green is an open
question; **report the result either way.** Resolve any textual conflict as the
brief's own author would, and say exactly what you did.

## Phase 2 — prove it works (measured, not read)

On the finished integration branch, in its own worktree:

- the three gates, outputs quoted (`.venv\Scripts\python.exe -m ruff check .`,
  `-m mypy`, `-m pytest`; full path, never your own `-q`);
- `python -c "import agent; print(agent.__file__)"` prints a path **inside the
  integration worktree** (the shared venv's editable install points at the main
  checkout);
- `python main.py --help` and `python main.py --print-config` run;
- the existing wheel tests (`tests/test_wheel_*`) pass;
- **PM spot-check for a regression of what is already measured:** `localhost` is
  refused (`validate_loopback_url("http://localhost:11434/v1")` raises), the demo
  profile still resolves to `omniagent-v2`, `AgentConfig().verbose` is `False`;
- the count of tests: baseline G **860 passed, 2 skipped** + brief 20 (14) + brief 21
  (21) + brief 22 (123) = **expected 1,018 passed, 2 skipped**. **A different
  number is a finding;** explain it.

## Phase 3 — the plan, not the action

A short section in the inventory: the exact ordered commands that would (a) switch
the main checkout to the integration branch (only after the snapshot of Codex's
work exists), (b) remove each SAFE-TO-REMOVE worktree, (c) move the
UNIQUE-WORK trees' contents onto named pushed branches first. **Do not run (a),
(b) or (c).** Removing or switching is the PM's, with the owner's yes.

## Rules

- **Work only under `D:\code-project\OmniAgent`.** Your three siblings
  (`OmniAgent-sae`, `-sae-b19`, `-sae-b23`) are exactly what the rule ends: once
  Phase 0 shows their contents are on a remote, move them inside
  (`git worktree move ... D:\code-project\OmniAgent\.scratch\<name>`) or list them
  SAFE-TO-REMOVE. Do not create any new folder outside the path.
- Nothing is installed on the owner's machine. POSIX stays UNMEASURED.
- **Standing rules** (`~/.claude/CLAUDE.md`): Rule 1 (reproduce, label every figure
  MEASURED / RECORDED / REPORTED, `QA:` line) and Rule 2 (the weekly meter is per
  account and shared by every Claude chair; read it before each long run and stop at
  today's ceiling; end with `Budget:`). The repository's pre-push hook runs ruff,
  mypy and pytest.
- Docs you may touch: `docs/architecture/repository-assembly-inventory.md` only.
  Every other change is a merge commit of an existing branch.

## Done when

- the inventory (Phase 0) sent to the PM **first**, with the worktree and branch
  tables, **before** Phase 1 starts;
- `integration/canonical-20261122` pushed to `origin` (a branch, not a `main`; the
  remote named on the command), gates green, the test count explained;
- Phase 2's checks quoted; Phase 3's plan written;
- one message to the PM with the owner's open decisions as lettered options, each
  ending by naming the chair that would carry it out.

## The one thing that would make this wrong

**Removing or moving a worktree whose commits are on no remote.** The cost of that
mistake is unrecoverable; the cost of leaving a SAFE tree for a day is nothing.
Count unpushed commits before you say SAFE, and when unsure say UNKNOWN.

## PM verification, 2026-11-22 (MEASURED, re-run by the PM)

`origin/integration/canonical-20261122` at `388fa53`, checked out detached under
`.scratch` (removed afterwards; the commit is on `origin`).

| Claim (SAE, REPORTED) | PM result |
| --- | --- |
| Branches from G `5005039`, five commits | **Confirmed.** `git log organization/main..` lists 8 commits: the 3 SE originals plus the SAE's 5 |
| Non-doc changes are only briefs 20, 21, 22 | **Confirmed.** 11 non-`docs/` files: README, agent, config, main, omniagent.toml and 6 tests |
| Gates: 1,018 passed, 2 skipped | **Confirmed**, prediction written first. ruff clean, mypy 51 files clean, pytest **1,018 passed, 2 skipped** (40.8 s), `agent.__file__` inside the tree |
| Unit 4 is a file carry, not a merge of O-line refs | Not re-run; consistent with the diff (55 files, all docs plus the 11 above) |
| [MEDIUM] wheel test skips on a machine that can build wheels | **Reproduced, with a corrected cause.** Under pytest `find_spec("wheel")` is `None` (no top-level `wheel` package in the venv; `pip list` shows only setuptools 78.1.0). Plain `python` finds `setuptools/_vendor/wheel` only after `setuptools` has been imported, so the SAE's `import wheel` check succeeds for a different reason. With the guard deleted the test **passes in 22.8 s** on setuptools alone. So the guard is stricter than the build needs. **Narrower than reported:** `.github/workflows/ci.yml:39,68` install `wheel` explicitly, so CI most likely runs the test; whether it does is UNVERIFIED (needs one CI run with `-rs`). Local-only skip: rate **Low-Medium**, not Medium |

Not re-run: the 57-ref branch table, the 48-tree inventory, phase 3 (written, not run).
Observation: the integration branch lives on `origin` (`mntoyg/OmniAgent`, "O"), a G-line
branch on the O remote, because the owner has not named the canonical remote.
