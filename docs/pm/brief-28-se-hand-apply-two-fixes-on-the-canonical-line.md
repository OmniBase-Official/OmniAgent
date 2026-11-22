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

## PM verification of the SE result, 2026-11-22 (MEASURED, re-run by the PM)

Result: three branches on `origin` (`mntoyg/OmniAgent`): A `a6e7c38`, B `a10a41b`, C `ccefadc` (C contains B). Checked in two
throwaway trees under `.scratch/` (removed afterwards), `agent.__file__` and `dataset_limits.__file__` inside them.

| Claim | PM result |
| --- | --- |
| Gates: A 1,021 passed / 2 skipped; C (so B too) 1,062 passed / 2 skipped | **Confirmed.** ruff clean, mypy clean (A 52 files, C 54), pytest 1,021 and 1,062, same two skips (POSIX filenames; wheel build tools) |
| A: test goes red when the old line is back | **Confirmed.** Canonical `agent.py` (`8a61a2063a5d`) restored: 2 failed, 1 passed; restored fix (`6961cc0922ff`, equals the SE's hash before and after): 3 passed |
| A: `exc_info=True` event does not carry the body | **Confirmed by reading code**: `observability.event` does `_ = message, exc_info` and logs with `exc_info=None` (`observability.py:338,352`). The SE is right that the brief 27 probe's "log has canary: False" was weak evidence |
| B: provenance tests red on the canonical `dataset_provenance.py` | **Confirmed.** canonical file back: **20 failed, 14 passed**; fix restored: 34 passed |
| B: module lists | **Confirmed.** `dataset_limits` is in `py-modules` and the mypy `files`; removing it from `py-modules` turns `tests/test_module_lists.py` red (1 failed, 2 passed), restored 3 passed; `pyproject.toml` hash `bb59b4401838` equals the SE's before and after |
| C: `read_records` bounded | **Confirmed.** canonical `export_dataset.py` back: **5 failed, 36 passed**; fix restored: 41 passed. Probes run from the C tree: 40 MiB line gives `DatasetError ... exceeds maximum line size of 4194304 bytes` (peak ~8 MiB), deep line gives `DatasetError ... nested deeper than the limit` |
| Hostile provenance lines | **Confirmed.** list line, string line, deep array, bad `messages`, list/deep/30 MiB sidecars all give `ProvenanceError` (were `AttributeError`, `TypeError`, `RecursionError`, or accepted) |
| One home for the limits | **Confirmed**: `validate_dataset.py` imports the five from `dataset_limits.py`; no duplicate constants |

Hash note: the SE's `dataset_limits.py` and `dataset_provenance.py` hashes equal the **committed blobs** (`32e286446610`, `677c49d31e62`);
files on this machine hash differently because `core.autocrlf=true` (CRLF on disk). The SE's `export_dataset.py` hash
(`2457ce9ec67a`) does not equal the committed blob (`765fcd4bf4d6`); likely a state before a last formatting edit. Not
treated as a defect (behaviour was re-measured above), recorded because it is unexplained.

**Not verified:** a built wheel (no `setuptools`/`wheel` here; the SE's empty-directory import test and my pass of
`test_module_lists.py` stand in, the wheel itself is UNVERIFIED); the wheel test still skips locally; Windows symlink or
junction log paths in `read_records`; `collect_turns` budgets (not asked for); every individual `dataset_limits` guard
mutation (I re-ran the file-level mutations, not the SE's per-guard list).

**Two things for the owner to know:**
1. **Behaviour change in C:** an undecodable (non-UTF-8) line in a run log used to crash the whole export with an uncaught
   `UnicodeDecodeError`; it is now skipped like any other torn line. Reasonable, but it is a change of behaviour.
2. **SE observation, not a finding:** `main.py:200` prints the endpoint URL on a healthy preflight (stdout, loopback IP literals
   only). Whether that breaks the contract's "do not log the full endpoint URL" is the owner's reading; nothing changed.

None of the three branches is merged into the canonical line; nothing on `origin` besides the SE's three branches and this document.
