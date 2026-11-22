# Brief 27 result (SE): one pick per subject among the duplicate snapshot attempts

Author: SE chair. Date: 2026-11-22. Read-only classification: nothing was restored, moved, deleted or
pushed except this document branch. Compared against the canonical line
`origin/integration/canonical-20261122` (`388fa53`). Snapshot refs are `refs/snapshots/20261122/*`
(local only).

Method. Each variant's *delta* is `parent..snapshot` (parents are O-line commits `af99092`, `3c76fd2`,
`b0b3467`, none of which is an ancestor of `388fa53`). Three ways, all MEASURED on 2026-11-22 in a
scratch worktree `.scratch/se-pick-variants` at `388fa53`:

1. `git merge-tree --write-tree --merge-base=<parent> 388fa53 <snapshot>`: does the delta apply?
2. Each variant's own tests run against the canonical code, then the failure reasons clustered.
3. Executable probes of the behaviour the variant claims to fix, run on canonical (`docs/pm/brief-27-probes/`).

Baseline on `388fa53`: `1018 passed, 2 skipped` (`python -m pytest -o addopts="" -q`), module paths printed
and inside the scratch tree.

## Does the delta apply to the canonical line?

| Variant | Files | `merge-tree` conflicts on `388fa53` |
| --- | --- | --- |
| `scratch_brief16-proposed-tree-20261109` (`1978f52`) | 46 | **18** (incl. `agent.py`, `observability.py`, `main.py`) |
| `...-proposed-tree-20261109-index` (`3350a5b`) | 46 | **identical tree to `1978f52`** (`git diff` empty) |
| `_24_01a16bed...brief16-operational-telemetry` (`8e72843`) | 17 | **13** |
| `scratch_pre-user-dataset-bounds-20261119` (`ba3598f`) | 12 | **5** (`validate_dataset.py`, `export_dataset.py`, `scripts/publish_dataset.py`, 2 more) |
| `codex_worktrees_dataset-input-bounds-20261116_OmniAgent` (`38ea900`) | 6 | **3** (`validate_dataset.py`, `pyproject.toml`, `tests/test_validate_dataset.py`) |
| `scratch_sec-search-001-remediation-20261112` (`381520d`) | 3 | **2** (`tools.py`, `tests/test_file_tools.py`) |
| `ees_search-text-race-safety...sec-search-001-20261112` (`3675a88`) | 2 | **2** (same files) |

`1978f52` (and its twin) also deletes 20 files under `docs/pm/` that exist at its parent (its worktree lacked
them); the canonical line has only some of them, so a wholesale take would remove briefs.

## Subject 1: brief 16 trio. Pick: **none, the canonical line already has it** (one narrow salvage, below)

Context the file counts hide: "brief 16" in these snapshot names is an *earlier* attempt at operational
telemetry privacy; the verified brief 16 is "three defaults and the endpoint out of messages", already on
the canonical line (`6831ba7`, integrated as `1abcd47`).

What the variants add against the canonical line:

| Subject matter | Canonical line | Variant | Verdict |
| --- | --- | --- | --- |
| Persistent operational log file | **refused** (`config.py:75-85`, `observability.configure` raises) | still writes a sink, with safe-field telemetry | canonical is stricter. Variant tests that call `configure(log_file=...)` fail with the refusal (27 failures in `test_v3_observability`, 16 in `test_v3_agent_logging`, each with that refusal): old design, not a gap |
| Content in log lines | probe: a turn with question/thought/answer canaries; log lines carry only `record_type`, `event`, `runtime_version`; canaries 0 in logs (`probe_log_canaries.py`) | carries `status`, `step_count`, `tool_name`, `duration_ms`, `model_tag` | canonical logs strictly less. The variants' `KeyError: 'status'`/`'tool_name'`/`'duration_ms'` failures are schema choices, not leaks |
| Request-path server error text | `Model server error (HTTP 500).` canary not in stdout or log (MEASURED) | same | duplicate |
| **Preflight server error text** | **`[!] Model server returned HTTP 500: SERVER_ERROR_CANARY` on stdout** (`agent.py:795` prints `exc.message`) | `1978f52`: `agent.py:702` drops the message. `8e72843`: still prints it | **the one real gap**; only `1978f52` fixes it |
| `export_dataset` disabled outright | supported, documented in `README.md:487-499`, 27 tests in `tests/test_export_dataset.py` | refuses (`dataset writing is disabled`, `operational logs cannot be exported`) | contradicts the canonical README and tests; would turn those red. Do not take |
| `tests/test_mvp_security_acceptance.py` (only `1978f52`) | disallowed-tool guard covered by brief 20 (`tests/test_tool_allowlist_guards.py`); endpoint text by brief 21 | | duplicate, and it imports the O-line cohort (`TrialRecordSchemaError` on canonical) |

Finding.

1. **[SEVERITY: Low] Preflight prints the raw model-server error message**
   - Location: `agent.py:795` (`check_connection`, `except APIStatusError`).
   - Scenario: (1) a model server answers the model-list request with an HTTP error whose body message is
     arbitrary text; (2) `main.preflight` prints `[!] Model server returned HTTP <n>: <message>` on stdout.
     The request path (`agent.py:1248`) already prints only `HTTP <n>`. Actor: whoever controls the model
     server's error body, which on a loopback-only deployment is the owner. Hence Low, and a consistency
     gap with the request path rather than a boundary break.
   - PoC: `python docs/pm/brief-27-probes/probe_preflight_error_text.py` from the repo root.
     MEASURED 2026-11-22 on `388fa53`: `STDOUT has canary: True | STDERR(log) has canary: False`,
     output `[!] Model server returned HTTP 500: SERVER_ERROR_CANARY`.
   - Remediation: print only the status code in `check_connection`, as `1978f52` does at its line 702
     (`f"Model server returned HTTP {exc.status_code}."`), plus a test that a canary in the error body is
     in neither stdout nor stderr for the `preflight` phase. Hand-apply on the canonical line: the
     variant's `agent.py` cannot be merged (conflicts above).

Pick for subject 1: **none**. Salvage: a three-line change and one test, re-made on the canonical line,
not a merge of any snapshot. `1978f52`, its `-index` twin and `8e72843` are history after that.

## Subject 2: dataset bounds. Pick: **`38ea900` (codex dataset-input-bounds), its provenance half only**

What the canonical line already has, and what it lacks (probes `probe_fingerprint_hostile_lines.py`,
`probe_sidecar_and_export_limits.py`, MEASURED on `388fa53`):

| Input path | Canonical line | Result |
| --- | --- | --- |
| `validate_dataset.py` limits (256 MiB, 4 MiB line, 100,000 records, 1,000,000 lines, nesting 128) | present (`validate_dataset.py:40-44`) | **same six numbers `38ea900` introduces**; its `validate_dataset.py` half is a duplicate |
| `publish_dataset` sums-file limits | present (`scripts/publish_dataset.py:55-57`) | duplicate |
| `dataset_provenance.dataset_fingerprint` | `read_text()` of the whole file, then `json.loads(line).get(...)` | line `[1,2]` -> `AttributeError`; `"x"` -> `AttributeError`; `{"messages": 5}` -> `TypeError`; 200,000-deep array -> `RecursionError`. None is a `ProvenanceError` |
| `dataset_provenance.read_sidecar` | `json.loads(path.read_text())`, no size cap, annotated `dict` | `[1]` returned as a `list`; deep -> `RecursionError`; 30 MiB sidecar accepted (peak ~90 MiB) |
| `export_dataset.read_records` | no line or aggregate limit | one 40 MiB line yielded as a record (peak ~120 MiB); deep line -> uncaught `RecursionError` |

Finding.

2. **[SEVERITY: Medium] Provenance and export readers are unbounded and crash on malformed input**
   - Location: `dataset_provenance.py:67` (`dataset_fingerprint`), `:121-135` (`read_sidecar`),
     `export_dataset.py` `read_records` / `collect_turns`.
   - Scenario: (1) someone hands `export_dataset.py` or the provenance step a dataset or run log they
     did not write (downloaded, shared); (2) a non-object line, deep nesting, or a very long line;
     (3) an uncaught traceback instead of `ProvenanceError`/`DatasetError`, or memory proportional to the
     file with no cap. Precondition: an untrusted input file, which the normal local workflow does not
     create, hence Medium, not High.
   - Remediation: bounded line reads and `ProvenanceError` for every malformed shape, as `38ea900` does;
     the test that goes red when the guard is removed is `tests/test_dataset_provenance.py` of `38ea900`.

Variant comparison.

| | `38ea900` (6 files) | `ba3598f` (12 files) |
| --- | --- | --- |
| Provenance (`dataset_fingerprint`, `read_sidecar`) | **fixes it**: with the variant's `dataset_limits.py` + `dataset_provenance.py` overlaid, every probe line above gives a `ProvenanceError` (`is not an object`, `JSON nesting that is too deep`, `exceeds maximum size of 65536 bytes`, `must contain a JSON object`) | fixes it |
| `export_dataset.read_records` limits | **no** | **yes** (only variant that has it) |
| `validate_dataset`, `publish_dataset` | duplicates the canonical line | different numbers (64 MiB, 512 KiB, nesting 32) and a different `dataset_limits` API |
| Applied to the canonical line | `dataset_limits.py` + `dataset_provenance.py` + `tests/test_dataset_provenance.py` apply with no conflict (the canonical `dataset_provenance.py` equals the parent's); full suite still green | taking its code wholesale: **27 canonical tests fail** (20 in `tests/test_publish_dataset.py`, 7 in `tests/test_validate_dataset.py`, e.g. `test_a_giant_single_line_is_refused_at_the_line_limit`, `test_verify_refuses_oversized_sha256sums_file`) |

Mutation check of the pick (Rule 1): with `38ea900`'s `dataset_limits.py` in place and the canonical
`dataset_provenance.py` restored, its provenance tests go red:
`test_provenance_refuses_an_over_limit_dataset`, `..._an_overlong_record`, `..._too_many_records`,
`..._too_many_physical_lines`, `..._deeply_nested_json` (5 red). The file's sha256 prefix before and
after the restore matched (`5d19b19dc495`).

Pick for subject 2: **`38ea900`, provenance half only**: `dataset_limits.py`, `dataset_provenance.py`,
`tests/test_dataset_provenance.py`. Drop its `validate_dataset.py` and `tests/test_validate_dataset.py`
(the canonical line already has the same numbers). It needs **a hand merge, not a rebase of the snapshot**:
its `pyproject.toml` hunk conflicts with brief 17's multi-line `py-modules` list, so add `dataset_limits`
to that list yourself. `dataset_provenance` imports it at top level, so omitting it breaks the installed
wheel; `tests/test_wheel_install.py` is *skipped* in this environment (`setuptools/wheel build tools are
unavailable`), so that edge is **not tested here**.
Not covered by the pick: the `export_dataset.read_records` limits. `ba3598f` is the only variant that has
them, but cannot be taken whole; the export half is a separate small change, to be written on the
`dataset_limits.py` of `38ea900` (SE).

## Subject 3: sec-search-001. Facts only, no pick (chair unnamed)

- Canonical line: `tools.py` already carries its own bounded traversal, `MAX_SEARCH_TRAVERSAL_ENTRIES = 10_000`
  (`tools.py:542`), `SearchTraversalLimitError`, and returns a fixed error with no partial matches;
  `tests/test_file_tools.py::test_search_traversal_limit_discards_partial_matches` covers it
  (`43 passed` in that file on `388fa53`). It does not use `sorted(start.rglob("*"))`.
- `381520d` (87 lines in `tools.py`): an `os.scandir` budget of 5,000 entries and a `_collect_search_candidates`
  helper, a sorted candidate list, and a note when the 400-file limit stops the scan. Its tests against
  canonical code: `3 failed, 42 passed`. The three failures are the wording `stopped at the 400-file limit`
  (canonical words the file limit differently), the constant `MAX_SEARCH_ENTRIES` and the private helper
  `_collect_search_candidates`: names and wording, not a measured hole.
- `3675a88` (18 lines): keeps the `rglob` walk lazy and sorts only the visited matches. Its tests against
  canonical code: `1 failed, 44 passed`; the failure, `test_search_text_does_not_enumerate_after_file_budget`
  (`assert 0 == 2`), is about enumeration after the file budget, which the canonical entry cap bounds
  (reading of the code, not run).
- Both parent on `b0b3467` (an O-line commit); both conflict on `tools.py` and `tests/test_file_tools.py`.
- Open for the owner, once a chair is named: whether either holds anything the canonical cap does not.
  The only candidate is the explicit "stopped at the 400-file limit" note in `381520d`. This session did
  not decide it.

## Not in scope or not covered

- `securefs.py` and the ACL files (owner ruling 13).
- The race-safety (TOCTOU) behaviour of the two sec-search variants against canonical was not exercised;
  only their test suites and the traversal bound were.
- The skipped wheel test (above). No model server was contacted.

QA: 2 findings (C/H/M/L: 0/0/1/1) - 2 reproduced - not tested: sec-search TOCTOU, the installed-wheel
import of `dataset_limits`, `export_dataset` log-source refusal beyond reading its tests.
