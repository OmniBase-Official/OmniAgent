# Assignments, 2026-11-04 — one paste block per chair

Four chairs can start right now and **their file sets do not overlap**. Paste
the block for each chair into that chair's chat. Baseline for all of them:
`main` at `108708c`, **658 passed**, mypy clean over **45** files, ruff clean,
tree clean.

The full brief is always the companion document; these blocks are the
assignment, not a replacement for reading it.

---

## → fullstack engineer

```
Your brief is docs/pm/brief-17-the-wheel-ships-what-it-claims.md. Read it and
execute it. The paste-ready version with everything inline is
docs/pm/brief-17-engineer-prompt.md.

The problem: the wheel this project builds is broken. It ships 8 modules, the
repository root has 9, the missing one is dataset_provenance.py, and
export_dataset.py:32 imports it. Unpack the wheel outside the checkout with
the project root off sys.path and `import export_dataset` raises
ModuleNotFoundError. I reproduced that today.

What you deliver: the module shipped, build/ and dist/ gitignored, and a test
that builds a wheel and imports every module in it -- reading the names out of
the archive, in a subprocess, under -I, with the project root off sys.path.

The one thing that would make it wrong: a test that imports the checkout.
Every variant of this defect survives that. Run your new tests BEFORE fixing
pyproject.toml and paste the failures; if the completeness test passes before
the fix, delete it and start again.

Branch from main at 108708c, work in your own worktree, commit to your own
branch, never to main. Three gates with the full .venv path and never your own
-q. Push with the remote named: git push origin <your branch>. Reply to me in
Thai; code, commits and your report in English.
```

---

## → AI/ML engineer

```
Your brief is docs/pm/brief-15-one-category-with-a-real-oracle.md. Read it and
execute it. The paste-ready version is docs/pm/brief-15-engineer-prompt.md.
Read docs/pm/role-aiml-prompt.md first if you have not -- it carries the
instrument autopsy you would otherwise repeat.

The problem: the contract wants 6 categories x 2 variants x 3 repeats, and a
record format that turns out wrong costs all 36 trials. This project has paid
that bill twice already. So you build ONE category end to end -- evidence
grounding -- and prove the shape.

What you deliver: an immutable synthetic fixture with a hash, an oracle that
derives its expected value from the fixture at load time and never stores it,
an answer key unreachable by the agent's six tools with the seal invariant
extended to cover it, six trials recorded individually and never averaged, and
a trial record that carries no prompts, no replies, no file contents and no
endpoint URL.

The one thing that would make it wrong: an oracle that stores its answer. It
is a substring expectation one level up -- the figure falls when someone edits
a fixture, for a reason that is not the model.

No cohort is authorized by anything. Your deliverable runs on an injected fake
client; no test may contact a model server. If you ever need the real model,
ask me first -- the card is 4 GB and two runs at once is forbidden.

Branch from main at 108708c, your own worktree, your own branch, never main.
Three gates, full .venv path, never your own -q. Push with the remote named.
Thai to me, English in the repository.
```

---

## → security engineer

```
Your brief is docs/pm/brief-14-the-endpoint-cannot-leave-loopback.md. Read it
and execute it. The paste-ready version is docs/pm/brief-14-codex-prompt.md --
the filename says codex and the chair is now yours; ignore the name. Read
docs/pm/role-se-prompt.md first if you have not.

The problem: gate 1 of the contract. agent.py:34 defaults to a loopback
endpoint but agent.py:255 is a plain str Field, so any URL is accepted.
Nothing enforces loopback, nothing stops a proxy carrying the request, nothing
stops a cross-host redirect, and agent.py:493 and :869 print the full base_url
in error text, which the contract forbids.

The one thing that would make it wrong: a test that passes because the
connection failed. http://evil.example/v1 is unreachable from this machine
anyway, so a rejection test can be green with no validator at all. Every
rejection test must prove no socket was opened. Mutation Ma deletes the
validator and asks which rejection tests still pass -- any that do were
testing the network.

Do not touch the model defaults, the retry defaults or verbose. All three are
real defects named in the contract and each is brief 16, which is queued
behind yours. Fixing one here hides it in this diff.

Branch from main at 108708c, your own worktree, your own branch, never main.
Three gates, full .venv path, never your own -q. Push with the remote named.
Thai to me, English in the repository.
```

---

## → solution architect

Not a brief — you do not execute briefs. This is the decision I need prepared.

```
Your next document of record is ADR-0003: the model question, which is
readiness block D3 and the only block with no owner and no plan.

The problem, measured: every figure this project owns was measured on
omniagent-v2. It is not in the repository, cannot be obtained from it, and
README.md:227 tells a newcomer to pull the generic base model instead. So the
README's numbers describe something the reader cannot run. The contract's
section 5 closing line already says passing the gates does not prove "legal
rights to third-party model/data assets".

You already have the foundation: the licensing and provenance inventory in
docs/architecture/security-and-ethics.md, which ADR-0001 called the only thing
in the repository answering D3.

What the ADR has to establish, each either measured or marked unknown:
- what omniagent-v2 is derived from, exactly, and what that base model's
  licence permits for redistributing a fine-tune of it;
- what the dataset permits -- 2,215 examples collected from this repository,
  plus whatever the base model's terms say about training artifacts;
- what actually ships toward a rebuild today: notebooks/train_omniagent_lora.ipynb
  and scripts/promote_model.py are tracked; there is no tracked Modelfile. Say
  whether a stranger could rebuild the tag from what is in the repository, and
  if not, what is missing.

Then the options, lettered, with the cost of each and the role that would
carry it. At least these three, and say if there is a fourth:
- publish the fine-tune somewhere a stranger can pull it;
- ship the recipe instead, so a stranger builds the tag themselves;
- publish neither, and make the README state which model every number came
  from and what a base model does instead.

Status: Proposed. Do not self-approve -- this is a licence and publishing
decision and it is the owner's. End by naming what you could not establish;
"the base model's terms were not read" is a result, and guessing at them is
not.

Branch from main at 108708c, your own worktree, your own branch, never main.
Push with the remote named. Thai to the owner, English in the repository.
```

---

## What is not assigned, and why

- **brief 16** (the four `agent.py` defects) — **queued behind brief 14**,
  same files. Do not issue it until 14 is merged and I have verified it.
- **the CI brief** — `ci.yml:37` installs with `-e` so CI cannot see the
  broken wheel; `:24` is `ubuntu-latest` so the Windows junction test never
  runs anywhere; the runner is unpinned against brief 06's lesson. Two of the
  three are security reasons, so it is SE's, behind 14 and 16.
- **option B of ADR-0002**, the package move — waits for brief 14 and brief
  16, and brief 17's test is its instrument.
- **`secure_search.py`** — parked by owner ruling, three variants, no brief,
  no Result. Reopening needs the new owner decision the contract names.
- **the cohort and the probe** — not authorized by anything.
