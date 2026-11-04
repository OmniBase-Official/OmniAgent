# ADR-0002: the wheel this project builds is broken, and what that does to the package move

- **Status: Proposed, 2026-11-04.** The defect is measured and not in
  dispute. **The choice between options A to D is the owner's**, because the
  order it fixes them in changes what is in flight and what has to wait.
- **Baseline:** `ae5cd95` on `main`, tree clean before and after. Gates at
  that baseline: `ruff` clean, `mypy` clean over 45 files, **658 passed in
  16.48 s**.
- **Governs:** nothing until approved. It supersedes the *proposed target
  tree*, *old-to-proposed mapping* and *migration sequence* sections of the
  Codex `repository-map.md` draft, per ADR-0001, and it is the design
  document for readiness blocks **D1, D2 and D4**.

## The measurement

`pip wheel` the project and unzip the result:

```
agent.py  config.py  export_dataset.py  main.py
observability.py  sandbox.py  tools.py  validate_dataset.py
```

Eight modules. The repository has **nine** root modules;
`dataset_provenance.py` is not among the shipped eight. And
`export_dataset.py:32` is:

```python
from dataset_provenance import write_sidecar
```

Imported each shipped module from the unpacked wheel, with the project root
*not* on `sys.path`:

| module | result |
| --- | --- |
| `agent` | imports |
| `config` | imports |
| `export_dataset` | **`ModuleNotFoundError: No module named 'dataset_provenance'`** |
| `main` | imports |
| `observability` | imports |
| `sandbox` | imports |
| `tools` | imports |
| `validate_dataset` | imports |

**The artifact this project builds today cannot import its own dataset
exporter.** `scripts/promote_model.py:38` and `scripts/publish_dataset.py:41`
import the same missing module; they are not in the wheel either, so they fail
for a second reason.

### Why nobody has noticed

Every way this project is used puts the repository root on `sys.path`:
`pytest` is configured with `pythonpath = ["."]` (`pyproject.toml:173`), the
README's install instruction is `pip install -e .`, and the documented way to
run it is `python main.py` from the checkout. **An editable install and a
checkout both mask this defect; only a real wheel exposes it.** 658 tests pass
and none of them is an installed-artifact test. That is the gap, not the
missing line.

### The same list, kept in three places, already disagrees with itself

| Where the module list lives | Count | `dataset_provenance` |
| --- | --- | --- |
| `pyproject.toml:46` — `py-modules` | 8 | **absent** |
| `pyproject.toml:55-78` — `mypy` `files` | 9 | present |
| `pyproject.toml:166` — `ruff` `known-first-party` | 8 | **absent** |

Two of the three are wrong in the same way. This is not carelessness; **it is
what a flat layout costs.** A package has one list — `pyproject.toml` finds
`src/omniagent/` and everything inside it is shipped and first-party by
construction. That is the structural argument for readiness D1, and it is now
measured rather than argued.

### A second defect, found by causing it

Building the wheel *inside the checkout* leaves a `build/` directory, which is
**not in `.gitignore`**, and the suite then goes red:

```
FAILED tests/test_eval_workspace.py::test_the_budget_expectation_is_not_unique_to_its_subject
AssertionError: the spread changed: {'build/lib/export_dataset.py', 'build/lib/agent.py'}
1 failed, 657 passed
```

The evaluation invariant counts the files in the workspace that carry an
expectation's answer, and `build/lib/` is a second copy of the source tree.
Deleting `build/` restored 658. **This is the trap the handoff already
names — a new file in the tree is not neutral — reproduced by the packaging
work itself.** Readiness D4 asks for CI that builds and installs the wheel.
On the current configuration, doing that in the checkout turns the suite red.

## The blast radius of the move, measured today

The readiness plan estimated "30 test files and 11 scripts". The actual
figures at `ae5cd95`:

| | matching `(from|import) <flat module>` |
| --- | --- |
| `tests/*.py` | **20** of 30 files |
| `scripts/*.py` | **8** of 11 files |
| root modules | 7 of 9 files |
| total import lines | **63** |
| generated | `notebooks/train_omniagent_lora.ipynb` — regenerate from `scripts/build_notebook.py`, never edit |

Plus the three config lists above, `pytest`'s `pythonpath`, `mypy`'s
`mypy_path`, and the README's command examples. Sixty-three lines is a
morning's mechanical work; the risk is not the count, it is that
`eval-fixture/`, `questions/` and the path-sensitive evaluation questions must
come out byte-identical, and that `build/` artifact above proves the
evaluation notices a directory nobody thought about.

## Options

**A. Ship the missing module. One brief, now.**
Add `dataset_provenance` to `py-modules` and to `ruff`'s
`known-first-party`; add `build/` and `dist/` to `.gitignore`; add a test that
builds a wheel **outside the checkout** and imports every module it contains,
so this defect cannot return. Touches `pyproject.toml`, `.gitignore` and one
new test module — **collides with nothing in flight** (brief 14 holds
`agent.py` and `config.py`; brief 15 holds fixtures and `scripts/`).
*Cost:* the nine generic top-level names stay, so readiness blocker 1 is
untouched, and the two lines added here are deleted again by option B.
*Carried by:* the **fullstack engineer** — and the verification builds a
wheel in a subprocess, so **ask the chair first if it is offered to Codex**;
the SWE sandbox has not been shown to permit it.

**B. Do the package move instead, and let the broken wheel stand until it
lands.** `src/omniagent/` with `cli.py` where `main.py` is, the three dataset
modules under `omniagent/dataset/`, `scripts/` left where it is and out of the
wheel, `[project.scripts] omniagent = "omniagent.cli:main"`. One mechanical
commit, 63 import lines, same test count, same output.
*Cost:* it cannot start until brief 14 and the four `agent.py` defects
(readiness block B) are merged, because a nine-module rename across someone
else's open work in `agent.py` is the worst merge this repository could
arrange. **So "now" means "in two briefs' time", and until then the artifact
stays broken.** It also has no installed-artifact test to prove it worked —
the move would be verified by the same suite that cannot see the defect.
*Carried by:* the **fullstack engineer**, one brief, after 14 and block B.

**C. A, then B. (Recommended.)** Issue A now as a three-file brief that can
run beside briefs 14 and 15. Its wheel-import test is then the instrument
that proves B behaviour-free: the same test, unchanged, must pass against
`src/omniagent/` and `import omniagent.dataset.export` afterwards.
*Cost:* two lines in `pyproject.toml` written and later deleted, and one brief
of scheduling. *Carried by:* **fullstack engineer** for both, A now, B after
brief 14 and block B.

**D. Record it and ship nothing.** No release is authorized, so no stranger
can be hurt by it today.
*Cost:* the README already tells a reader to `pip install -e .`, which hides
the defect, so the first person to build a real wheel finds it — and that is
most likely to be the CI job readiness D4 asks for, or the owner, on the day
they are trying to release. *Carried by:* nobody; this ADR is the record.

## Recommendation

**C.** The reason is not the defect's severity — nothing ships today — it is
that **option A buys the test that makes option B provable.** Without it, a
nine-module rename is verified by a suite that demonstrably cannot see a
missing module, and the project's own standard says a test asserting
"this works" proves nothing if nothing would notice its removal. With it, the
move has an oracle. The two throwaway lines in `pyproject.toml` are the
cheapest thing in this document.

If the owner picks **B** instead, the move's brief must contain the
wheel-import test as its first failing test; the move is then unprovable
without writing option A's test anyway, in the middle of a rename.

## What this does not establish

- **I did not test an installed wheel in a clean virtual environment**, only
  the unpacked wheel with the project root off `sys.path`. That reproduces
  the import failure exactly, and it does *not* establish that a real
  `pip install omniagent` has no further packaging problems — entry points,
  the absent `[project.scripts]`, and `requirements.txt`/`pyproject` drift are
  all untested.
- **Whether `src/omniagent/` is the right shape** beyond fixing these two
  defects. The dataset modules may belong in `scripts/` rather than in the
  wheel at all; that is a product question about who the dataset pipeline is
  for, and it is not answered here.
- **Nothing about `tests/` and `scripts/` reorganisation.** ADR-0001 rejected
  the Codex draft's version of it. No replacement is proposed: the flat
  `tests/` directory has cost this project nothing measurable.
- **Whether the move can be made behaviour-free across the evaluation.** The
  `build/` failure above is evidence that it cannot be assumed, and the proof
  is the move's brief to produce, not this document's.

---

## The owner's ruling — 2026-11-04, recorded by the project manager

**Option C accepted.** Ship the missing module now, do the package move after
brief 14 and the four `agent.py` defects are merged, and use option A's
wheel-import test as the instrument that proves the move behaviour-free.

What follows from it, in order, with the owner's decisions marked:

1. **Option A is issued now** as
   `docs/pm/brief-17-the-wheel-ships-what-it-claims.md` — `pyproject.toml`,
   `.gitignore` and one new test module, colliding with nothing in flight.
2. **The CI fix is a separate brief and a separate chair**, because the
   manager found while verifying this ADR that
   `.github/workflows/ci.yml:37` installs with `-e` and so **cannot see the
   defect this ADR is about**, that `:24` is `runs-on: ubuntu-latest` so the
   Windows junction case never runs anywhere, and that the runner is unpinned
   against brief 06's lesson. Two of those three are security reasons.
3. **Option B waits** for brief 14 and the defects brief. Its instrument is
   brief 17's test, unchanged.

Recorded here by the manager because the decision is the owner's and the
record belongs with the decision. **The architect may restructure this
document's status fields as it sees fit** — the ruling is the content, not the
formatting.
