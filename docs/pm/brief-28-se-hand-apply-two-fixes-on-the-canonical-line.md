# Brief 28 (SE): hand-apply two fixes on the canonical line, from brief 27's picks

Issued 2026-11-22 by the PM, on the owner's word "Issue brief 28" (after the PM verified your brief 27 result,
`docs/pm/brief-27-se-pick-one-variant-per-subject.md`, "PM verification").

## Scope: three small changes, one branch each, cut from `origin/integration/canonical-20261122` (`388fa53`)

Do **not** merge or cherry-pick any snapshot. The snapshots are O-line and conflict (18 / 3 files). Re-make the
change by hand on the canonical line; read the variant only as a reference.

### Change A (Low): the preflight prints the raw server error text
- `agent.py:795` (`check_connection`, `except APIStatusError`) puts `exc.message` into `AgentError`, which
  `main.preflight` prints on stdout. The request path prints only `HTTP <n>`. Make them consistent:
  `f"Model server returned HTTP {exc.status_code}."`.
- Also look at the `obs.event(... exc_info=True)` just above it: say (MEASURED, with your probe) whether the
  traceback it logs can carry the body text into a log line. If it can, that is a second leak on the same path
  and belongs in this change; if it cannot, say so in one line.
- Test: a canary in the error body appears in neither stdout nor stderr for the `preflight` phase. **Mutation-check
  it**: restore the old line, the test must go red; save a copy first, record the file hash before and after.
- Branch: `se/brief-28a-preflight-status-only`.

### Change B (Medium): bounded provenance readers (the `38ea900` provenance half)
- Files to re-make from `38ea900`: `dataset_limits.py`, `dataset_provenance.py`, `tests/test_dataset_provenance.py`.
  Drop its `validate_dataset.py` and `tests/test_validate_dataset.py` (canonical already has the same five
  numbers). Keep the one number canonical lacks, `MAX_SIDECAR_BYTES = 64 * 1024`.
- **Reduce duplication**: canonical `validate_dataset.py:40-44` already defines the five limits. Decide, and
  state why, whether `dataset_limits.py` becomes their single home (and `validate_dataset.py` imports them) or
  whether it duplicates them. Two copies of a security limit drift; prefer one home unless it forces a larger
  change than this brief allows.
- `pyproject.toml`: add `dataset_limits` to the multi-line `py-modules` list (brief 17's list; the variant's
  hunk conflicts with it), **and check the `[tool.mypy] files` list and any other module list in the file**: a
  module missing from one list breaks the installed wheel or leaves it un-typed.
- `tests/test_wheel_install.py` is skipped locally. Prove the import some other way and label it: build a wheel
  if `wheel` can be installed in a **throwaway venv under `.scratch/`**, or at minimum assert by a unit test
  that every top-level module imported by a `py-modules` member is itself in the list. If you can do neither, say
  the wheel edge is UNVERIFIED rather than claim it.
- Mutation-check: with the canonical `dataset_provenance.py` restored, the new tests go red (you measured 5 red
  on the variant; re-measure on your version), hash before and after.
- Branch: `se/brief-28b-bounded-provenance`.

### Change C (separate, small, may be a second PR): `export_dataset.read_records` limits
- Canonical `read_records` reads one 40 MiB line and has no aggregate limit (your probe, peak ~120 MiB); a deep
  line raises an uncaught `RecursionError`. Bound it with the limits from Change B's `dataset_limits.py`, and
  turn malformed shapes into the module's existing error type. Reference only: `ba3598f`'s `export_dataset.py`.
- Do **not** take `ba3598f`'s other numbers (64 MiB, 512 KiB, nesting 32); they broke 27 canonical tests.
- Depends on B (imports `dataset_limits`). Cut `se/brief-28c-export-read-limits` from B's branch, or write C
  after B is accepted; say which.
- Test the existing 27 tests in `tests/test_export_dataset.py` still pass.

## Rules

- Three gates before every commit, full paths: `.venv\Scripts\python.exe -m ruff check .`, `-m mypy`, `-m pytest`.
  Baseline on `388fa53`: 1,018 passed, 2 skipped. Print `agent.__file__` (or the module under change) and
  confirm it is inside your tree.
- Work in a tree **under `D:\code-project\OmniAgent\.scratch\se-brief28`**, nothing outside. Remove it when done.
- **Both remotes are public.** Push only your own branches, to `origin`, remote named, never to either `main`.
  No sealed paths (`docs/`, except your own result document, `models/`, `questions/`, `data/`, `NEXT_CHAT.md`,
  evaluation scripts) and no secret in a push. Canaries in tests must be obvious dummies.
- `securefs.py`, the ACL files and anything under `.github/` are out of scope.
- Delete no ref and no worktree; do not touch the snapshot refs. The PM deletes refs on the owner's word.
- Verification is yours; a test is proven only after you saw it go red with the guard removed.
- Rule 2: re-read the meter at start. Today's ceiling (owner, in the PM's session) is 40% weekly; the PM read
  34% weekly at issue time. If you need the ceiling confirmed in your own session, say so and stop.
- Commits end with `Co-Authored-By: Claude Sonnet 5.5 <noreply@anthropic.com>`; retract any error in the
  commit message too.

## Done when

A and B each have a branch pushed to `origin` with three green gates, a test shown red under mutation, and the
hashes recorded; C either pushed or explicitly deferred with the reason; a result document
`docs/pm/brief-28-result-se.md` on one of the branches; and one message to the PM with the branch names and
SHAs, the owner's open decisions as lettered options (each ending by naming the chair that carries it out),
and your `QA:` and `Budget:` lines.

## The one thing that would make this wrong

**Copying the variant's files in and calling it done.** The variant's `pyproject.toml` hunk and its duplicate
`validate_dataset.py` numbers are exactly what do not belong; a wheel that cannot import `dataset_limits` passes
every local test here because the wheel test is skipped. Prove the module list, and prove each new test can fail.
