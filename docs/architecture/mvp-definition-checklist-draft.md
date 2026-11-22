# MVP definition — a checklist you can sign

**Draft for the owner to edit and sign. 2026-11-22.** Not a decision and not an
approval.

**The rule this draft obeys:** every line names **how it is checked today** — a
gate, a test, or a measurement that exists — and is marked **EXISTS** (the check
runs now and passes) or **TO BE BUILT** (the check does not exist yet, or exists
and does not pass). A line that cannot be checked is not on the list; it is in
the last section, where it belongs.

Baseline for every figure: `origin/integration/canonical-20261122` at `b164aaa`,
**1,065 passed, 2 skipped** (REPORTED by the PM 2026-11-22; I last measured
1,018 at `388fa53` myself, before brief 28 landed).

## A. The contract's six security gates

| # | the line | how it is checked today | state |
| --- | --- | --- | --- |
| A1 | model traffic cannot leave loopback | `tests/test_endpoint_policy.py`, brief 14's 31-form corpus carried onto the canonical validator by brief 22 (+123 tests), and the validator is proved to be the refuser by mutation, not by the network failing | **EXISTS** |
| A2 | the dispatcher enforces a per-task tool allowlist | `tests/test_tool_allowlist_guards.py` from brief 20 (+14), one test per guard, each red when only that guard is removed | **EXISTS** |
| A3 | operational logging is quiet and sanitized by default | `AgentConfig().verbose` is `False`; a persistent `--log-file` is refused; brief 21's `tests/test_endpoint_not_in_messages.py` (+21) | **EXISTS** |
| A4 | no prompt, file content, raw argument, error or secret reaches a log | the canary tests in brief 21 and G's `tests/log_capture.py` memory sink | **EXISTS for the fields they name.** A canary covering *every* field is **TO BE BUILT** |
| A5 | path-boundary regression tests **on every platform claimed as supported** | Windows junction: brief 13's test, mutation-proved. Hard link: G's guard, mutation-proved 2026-11-21 across four tools. **POSIX: no test that notices the guard's removal** | **TO BE BUILT** (the POSIX half) |
| A6 | deterministic fixture and oracle, no retries, stop on drift, answer-key isolation | brief 15's derived oracle and sealed trial record on one category | **PARTLY EXISTS.** `SEALED_FROM_TRIALS` is **absent from the canonical line** (ADR-0003 §I2 row 8) — **TO BE BUILT** |

**A gate is not signed because a test passes. It is signed because removing the
guard turns a named test red.** A1, A2, A3 and the Windows half of A5 meet that
standard today. A4, the POSIX half of A5, and A6 do not.

## B. What a stranger gets

| # | the line | how it is checked today | state |
| --- | --- | --- | --- |
| B1 | `pip install` then a command to type | **no `[project.scripts]` on either line** — `grep -c "project.scripts" pyproject.toml` is `0` | **TO BE BUILT** |
| B2 | installing does not squat on generic top-level names | `pyproject.toml` ships **11 flat modules** (`agent`, `config`, `tools`, `main`, `sandbox`, …) | **TO BE BUILT** (ADR-0002, readiness D1) |
| B3 | the wheel contains every module it imports | `tests/test_wheel_install.py` | **TO BE BUILT.** The test **skips** on a machine that can build wheels — `importlib.util.find_spec("wheel")` returns `None` while `import wheel` succeeds (MEASURED 2026-11-22). A skip reads as green |
| B4 | CI installs the built wheel and runs it on a clean machine | `.github/workflows/ci.yml` installs editable, which is what hides B3 | **TO BE BUILT** |
| B5 | the README's claims are true of what the reader gets | the README still says `ollama pull qwen2.5:7b` while every figure the project owns was measured on `omniagent-v2`, which is not in the repository | **TO BE BUILT** (readiness D3, and it is a decision before it is work) |
| B6 | a version and a changelog that move | `version = "0.1.0"`, unchanged across 28 briefs; one tag | **TO BE BUILT** |

## C. The runtime contract

| # | the line | how it is checked today | state |
| --- | --- | --- | --- |
| C1 | one model default, agreed by code, TOML and `--help` | `python main.py --print-config` shows `model qwen2.5:7b file:defaults`; brief 21 | **EXISTS** |
| C2 | both retry layers named and recorded | `--print-config` shows `client_max_retries 0` and `max_retries 2` | **EXISTS** |
| C3 | the endpoint URL is never printed | brief 21's `tests/test_endpoint_not_in_messages.py` | **EXISTS** |
| C4 | the six tools are the whole model-facing surface | `python -c "import tools; print(list(tools.TOOLS))"` | **EXISTS** — but `main.py --help` offers a seventh choice, `inspect_config_precedence`, as an operator capability. **Say in the contract whether that is in or out** |
| C5 | the model digest and runtime version are frozen at preflight | recorded by hand in ADR-0003 (`omniagent-v2`, manifest `05ba6fe701c5`, Ollama 0.34.4) | **TO BE BUILT** as a preflight check |
| C6 | `localhost` by name is refused, IP literals only | measured on the canonical line; `validate_loopback_url("http://localhost:11434/v1")` raises | **EXISTS — and it contradicts contract §2 as written.** Either the contract is amended or the validator is loosened. **Owner's** |

## D. The evaluation

| # | the line | how it is checked today | state |
| --- | --- | --- | --- |
| D1 | one category with a derived oracle and a sealed trial record | brief 15, on the O line | **PARTLY EXISTS** (see A6) |
| D2 | six categories × two variants × three repeats | one category exists | **TO BE BUILT** |
| D3 | a threshold and a reporting method, approved **before** the cohort runs | nothing proposed | **TO BE BUILT**, AI/ML then owner |
| D4 | the cohort runs on a frozen runtime with a protocol hash | no cohort authorised | **TO BE BUILT** |

**No number from the 19-question bank may be quoted as the MVP baseline.** The
contract forbids it and the bank does not exist on the canonical line.

## E. Housekeeping that a release notices

| # | the line | how it is checked today | state |
| --- | --- | --- | --- |
| E1 | `ruff`, `mypy`, `pytest` green on the canonical line | the three gates, full path, no second `-q` | **EXISTS** |
| E2 | no work exists only in a worktree | measured 2026-11-22: 48 worktrees, **0 unpushed commits**; 18 trees held uncommitted work, now snapshotted | **EXISTS**, and it is a measurement to repeat, not a one-off |
| E3 | a `SECURITY.md` with a reporting channel | absent | **TO BE BUILT** |
| E4 | a licence and provenance inventory for model, data and assets | started in `security-and-ethics.md`; the model question is open | **TO BE BUILT** |

## What is deliberately not on this list

- **`securefs.py`.** Parked pending your ruling; see the memo beside this file.
  An MVP definition that depends on an unresolved question is not signable.
- **The graph runtime.** ADR-0005 is Proposed; phases 1–3 fit the contract and
  nothing in this checklist depends on them.
- **POSIX behaviour.** UNMEASURED, nothing installed on your machine.
- **Anything with no check.** "The agent is useful", "the answers are good" —
  real questions, and not lines you can sign, because nothing here measures
  them. D2 to D4 are the nearest this project has.

## How to use this

Strike what you do not want. **A line you keep is a line somebody has to make
checkable** — the state column already says which ones are work. Counting
today: **12 EXISTS, 16 TO BE BUILT, 2 PARTLY**, and three of the four open
owner decisions (B5, C4, C6) are decisions before they are engineering.
