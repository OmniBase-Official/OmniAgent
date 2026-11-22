# Brief 28 result (SE): two fixes and a read bound, hand-applied on the canonical line

2026-11-22. Every branch is cut from `origin/integration/canonical-20261122` (`388fa53`). No snapshot was merged
or cherry-picked; `38ea900` and `ba3598f` were read as references only. Pushed to **origin**
(`mntoyg/OmniAgent`, public) as three branches; nothing else was pushed and no ref was deleted.
Baseline on `388fa53`: 1,018 passed, 2 skipped. Gates run from the tree under `.scratch/se-brief28`
with `agent.__file__` and `dataset_provenance.__file__` printed inside it.

| Change | Branch | Three gates (ruff / mypy / pytest) |
| --- | --- | --- |
| A (Low) preflight prints `HTTP <n>` only | `se/brief-28a-preflight-status-only` (`a6e7c38`) | clean / clean / 1,021 passed, 2 skipped |
| B (Medium) bounded provenance readers | `se/brief-28b-bounded-provenance` (`a10a41b`) | clean / clean / 1,057 passed, 2 skipped |
| C export `read_records` limits | `se/brief-28c-export-read-limits`, cut **from B's branch** (it imports B's `dataset_limits.py`) | clean / clean / 1,062 passed, 2 skipped |

## A. Preflight

- `agent.py:795` now reads `f"Model server returned HTTP {exc.status_code}."`, as the request path does.
- **The `exc_info=True` event does not carry the body (MEASURED).** `observability.event` accepts `exc_info` and
  never persists it (`observability.py:338`, and `:352` passes `exc_info=None`) and keeps only a closed field
  schema. The written `agent.connection.error` record is checked in the test and holds no canary. The brief 27
  probe's "log has canary: False" line was **not** valid evidence for this (its stderr redirect did not see the
  log handler's stream); the new test reads the in-memory sink instead. One-line answer: no second leak.
- Test `tests/test_preflight_error_text.py` (3 tests: exception text, CLI stdout+stderr, event arguments and
  written records). Mutation: old line restored -> 2 red; the body passed to the event as `detail=` -> 1 red.
  `agent.py` sha256 prefix: before `085d847ca63f`, fixed `6961cc0922ff`, after each restore `6961cc0922ff`.

## B. Bounded provenance readers

- **One home.** `dataset_limits.py` now defines the five limits `validate_dataset.py` had, plus
  `MAX_SIDECAR_BYTES = 64 KiB`; `validate_dataset.py` imports them. Cost of the single home: a few lines changed
  there, and `tests/test_validate_dataset.py` reads `MAX_JSON_NESTING` from `dataset_limits` (mypy strict forbids
  reading a name that was only imported, and a re-export alias is lint-banned). The tests that *patch*
  `validate_dataset.MAX_*` still work. `validate_dataset` keeps its own nesting check; folding it onto
  `has_excessive_json_nesting` is a further change, not made here.
- **Re-made, not copied.** Kept from `38ea900`: the streaming reader and the shapes it refuses. Changed: names
  match the canonical constants (`MAX_DATASET_EXAMPLES`); the mixed-prompt error keeps the canonical message
  (`mixes N distinct system prompts`) by collecting a set; one sidecar size check, not two (the variant's
  `seek`-based check and its `read(MAX+1)` check made each other redundant, which hides a missing guard from a
  mutation run: removing the first left the suite green).
- **`pyproject.toml`**: `dataset_limits` added to `py-modules` and `dataset_limits.py` to `[tool.mypy] files`.
  There is no third module list in the file (checked).
- `tests/test_module_lists.py` (new): every `py-modules` entry exists; every top-level repository module a
  listed module imports is itself listed; every listed module is in the mypy `files`. Mutation: removing
  `dataset_limits` from `py-modules` -> red, naming `dataset_provenance imports dataset_limits` and
  `validate_dataset imports dataset_limits`; removing it from the mypy list -> red.
- **Wheel edge.** A real wheel build was **not possible**: neither `setuptools` nor `wheel` is installed and I did
  not install packages from the network. So the built wheel is **UNVERIFIED**. What was measured instead: the exact
  `py-modules` set (12 files) copied into an empty directory and every module imported from there with the repo
  off `sys.path`: `imports failed: none`; with `dataset_limits.py` withheld: `export_dataset`,
  `dataset_provenance`, `dataset_limits`, `validate_dataset` fail with `No module named 'dataset_limits'`.
  `tests/test_wheel_install.py` stays skipped here.
- Tests: `tests/test_dataset_limits.py` (12, each limit on its own) and 24 added to
  `tests/test_dataset_provenance.py` (nine hostile line shapes, six sidecar shapes, a sidecar exactly at the
  limit, two prompts in one line). Mutations, each a single guard turned off, each red:
  `dataset_limits.py` fstat guard, byte total, line length, physical lines, records, blank-line counting,
  nesting; `dataset_provenance.py` non-object, system-content type, sidecar object, sidecar size, sidecar
  nesting, `OSError` wrap. Canonical `dataset_provenance.py` restored: the new tests go red. Hashes before and
  after equal: `dataset_limits.py` `32e286446610`, `dataset_provenance.py` `677c49d31e62`, `pyproject.toml`
  `bb59b4401838`.

## C. `export_dataset.read_records`

- Streams through `dataset_limits.iter_dataset_lines`; a limit breach raises `DatasetError` naming the file
  (not skipped as a torn tail); a line nested over `MAX_JSON_NESTING` raises `DatasetError`; the byte and record
  limits also apply to all the log files together. A line that is not JSON, not UTF-8 or not an object is still
  skipped, as before (a half-written tail is normal).
- A UTF-8 failure used to be an uncaught `UnicodeDecodeError` for the whole file; it is now a skipped line. That is a
  behaviour change, chosen to match the existing torn-tail rule.
- Probe `docs/pm/brief-27-probes/probe_sidecar_and_export_limits.py` on this branch: the 40 MiB line gives
  `DatasetError ... line 1 exceeds maximum line size of 4194304 bytes` (peak ~8 MiB, was ~120 MiB); the deep line
  gives `DatasetError ... nested deeper than the limit` (was `RecursionError`).
- Five tests added to `tests/test_export_dataset.py`; the existing ones still pass. Mutations (aggregate bytes,
  nesting, aggregate records, error conversion, unbounded read restored) each red. `export_dataset.py`
  `2457ce9ec67a` before and after.
- Not done: `collect_turns` / `build_examples` budgets (`ba3598f` has them); not asked for in the brief.

## Observation, not a finding

`main.preflight` prints `endpoint : {agent.config.base_url}` on a healthy preflight (`main.py:200`). Brief 21 took
the URL out of error messages and logs; this banner is stdout on success and only loopback IP literals are
accepted. Whether it is covered by the contract's "do not log the full endpoint URL" is the owner's reading; I
changed nothing.

QA: 0 new findings; 2 gaps closed (Low, Medium) - both reproduced before and after - not tested: a built wheel,
Windows-only file behaviour (symlink or junction log paths in `read_records`), `collect_turns` budgets.
