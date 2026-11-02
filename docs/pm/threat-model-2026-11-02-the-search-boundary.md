# The search boundary: who is the attacker?

**Written 2026-11-02 by the project manager and solution system architect, at
`e159f53`, before judging `secure_search.py`.** The order matters. A
1,199-line security module is easy to argue for after the fact and impossible
to argue against without a written threat model, so the model comes first and
the acceptance criteria are fixed before the code is read against them.

This document decides nothing. It states what we are defending, from whom, and
what a change to that boundary has to show before it is merged. **The decision
is the owner's.**

## What the system is

A local-only ReAct agent. A small fine-tune answers over `localhost:11434`,
and the agent exposes **six tools** to it: `calculate`, `get_current_time`,
`read_file`, `list_directory`, `search_text`, `file_info`
(`tools.py:270-800`).

**Every one of them is read-only.** There is no tool that writes a file,
creates a directory, deletes anything, runs a command, or makes a link. That
single fact decides most of what follows.

`sandbox.py` is therefore **a leash on the model, not a confinement boundary
for the machine.** It exists so that a model which hallucinates
`../../../.ssh/id_rsa`, or which has just read a file telling it to, cannot
turn that into a read. It was never a defence against other processes on this
computer, and it cannot be one: it runs inside the process it would have to
defend against.

## The attackers, in the order they actually threaten us

### 1. The model itself — the real one, and the reason the sandbox exists

A 4 GB fine-tune emits a path because the question suggested it, because a
file it read suggested it, or because it is simply wrong. Traversal, absolute
paths, UNC paths, `~`, credential filenames, hidden files, the evaluation's
own answer key. This has happened repeatedly and is recorded: the agent
answered a question out of `data/holdout-expects.txt`, which is why
`scripts/eval_workspace.py` exists at all.

**Defended by static path checks**, which is what `Workspace.resolve` and the
denied, hidden and credential rules are. **The model cannot win a race,
because it cannot write.** It has no tool that creates a link, so it cannot
set one up and no timing between its calls can conjure one.

### 2. Content the agent reads telling it what to do

Prompt injection through a file in the workspace. Real, and **unrelated to
path resolution** — no enumerator fixes it. Out of scope here.

### 3. A hostile tree that is already on disk — links pointing outside

Someone clones a repository, or unpacks an archive, into the workspace, and it
contains a junction or symlink aimed at `C:\Users\<name>\.ssh`. The agent
walks it and reads what it finds.

**Plausible, and this is the one that matters most after the model.** It is
also **static**: the link exists before the walk begins. Nothing races.

**Already defended, as of `e159f53`.** Brief 11's reparse-point check refuses
it, and I proved the guard is the thing doing the work by removing it and
watching the outside marker leak (`docs/pm/brief-11-the-walk-stops-paying-for-resolve.md`,
Ma and Md).

### 4. A concurrent local process racing the walk

Another process creates, swaps or renames a link **between** the moment the
walk admits an entry and the moment it reads it. This is the attacker
`secure_search.py` is built for, with pinned handles, no delete sharing,
`O_PATH` and `/proc/self/fd` identity checks.

For this attacker to exist it must already be able to **write inside the
workspace**. Anything that can write inside the workspace can also read the
files it wants directly and send them anywhere — it does not need to trick an
agent into reading them on its behalf. We would be hardening a side door in a
house whose front door that same attacker already holds the key to.

The interesting sub-case, stated fairly: a process that can **write** but not
**read** the target, using the agent as a read oracle. On a single-user laptop
where the agent and the attacker run as the same user, that asymmetry does not
exist. It would exist under a sandbox with split capabilities — which is not
how this project runs, and if it ever is, this document is wrong and should be
rewritten rather than quoted.

## What the defence costs

Taken from `secure_search.py`'s own docstring on
`origin/codex/posix-device-race-20261101`, not from reading between lines:

- **1,199 lines** of module plus **1,120 lines** of tests, built on raw
  `ctypes` Win32 handle work and Linux `O_PATH` with `/proc/self/fd` identity
  promotion, replacing **86 lines** of `tools.py`.
- **Windows support limited to 64-bit AMD64 on a local fixed NTFS volume.**
- **Linux requires procfs and a validated ext4 workspace.**
- **Everything else fails closed** — which is the correct choice for a
  security module and a severe one for a tool the agent needs in order to
  work at all. On anything else, `search_text` stops.
- **All symlinks and reparse points refused, including ones whose targets are
  inside the workspace.** Ordinary repositories contain internal symlinks.
- The project's stated premise is local-only, no frameworks, hand-rolled and
  small. This is none of those adjectives, and that is a premise change, not
  a detail.

## The acceptance criteria, fixed now

Any change to the search boundary — `secure_search.py` or a successor — is
merged only when all five are answered **in writing, with evidence**:

1. **Name the attacker.** Which numbered class above, and if it is class 4,
   show how that attacker exists on a single-user local machine without
   already having a cheaper route to the same bytes.
2. **Show the actor can act.** The agent has no write tool. Name the actor
   that creates or swaps the link in the normal workflow, or say plainly that
   none does.
3. **Prove it does not fail closed where we run.** One result per platform the
   project supports, measured, not reasoned: Windows AMD64 on this machine,
   the pinned `ubuntu-24.04` CI runner that gates `omniagent-core`, WSL, and
   any filesystem the owner actually uses. A platform where `search_text`
   stops working is a regression, however secure it is.
4. **Byte-identical output on the real tree**, both workspaces, compared by
   hash, in the same sorted order — the standard brief 03 set and brief 11
   met. Internal symlinks are part of this: if refusing them changes the
   output, say what changed and why that is correct.
5. **Fit the premise, or amend it.** If a 1,200-line ctypes module is the
   right shape for this project, then "hand-rolled and small" stops being
   true and should stop being written down. That is the owner's call to make
   explicitly, not a thing to discover later in a diff.

## My recommendation, which is not the decision

**Do not merge `secure_search.py` as it stands.** Not because the work is bad
— it is careful, and its docstring is more honest about its limits than most
of this repository — but because it defends attacker class 4, the weakest of
the four, while its static refusals now duplicate what fifty lines in brief 11
already do and prove. Criterion 3 is where I expect it to fail hardest: a
module that fails closed off ext4 and off AMD64 turns a read-only convenience
tool into a platform gate.

**Keep the branches.** They are the reference for what a hardened enumerator
looks like if criterion 1 is ever answered — if this agent gains a write tool,
or runs anywhere other than one person's laptop, class 4 becomes real and this
document becomes wrong. Record that, rather than deleting the work.

**What I would do with the next engineer-hour instead:** attacker class 3 is
the plausible one and it is defended by one check whose only test is mine, run
by hand, in a scratchpad. It belongs in `tests/` as a permanent fixture, so
the next person to touch that walk cannot remove the guard and stay green.
That is a small brief, and it is worth more than either branch.

---

## The owner's ruling — 2026-11-02

**Recommendation accepted. `secure_search.py` is not merged.** The two
branches stay as they are: `origin/codex/search-text-race-safety-20261101-workspace`
and `origin/codex/posix-device-race-20261101`. Nothing is deleted and nothing
is ported.

The cost if this is wrong: attacker class 4 becomes real without us noticing,
and the window between admitting an entry and reading it stays open. **The
conditions that would make it wrong are written in criteria 1 and 2 above, and
they are checkable** — the agent gaining a tool that writes, or the agent
running anywhere other than one person's machine. Whoever next adds a write
tool to `tools.py` should read this document before they do.

The engineer-hour goes instead to `docs/pm/brief-13-the-junction-refusal-becomes-a-test.md`:
attacker class 3 is the plausible one, it is defended by a single check, and
that check's only test today is a manager running `mklink /J` by hand.
