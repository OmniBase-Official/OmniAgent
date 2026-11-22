# Repository map

**Baseline:** `ae5cd95` on `main`, 2026-11-04. Adopted from a Codex draft
written at `f37044d` under ADR-0001; no source file changed between those
commits.

**This is a map. It moves nothing and proposes nothing.** The draft this was
adopted from also contained a proposed target tree, an old-to-proposed
mapping, and a five-phase migration sequence. Those sections are **not
adopted** — ADR-0001 records why, and
[ADR-0002](ADR-0002-the-wheel-this-project-builds-is-broken.md) is the design
document for the package move in their place.

## Current map

| Current path | Responsibility / primary owner |
|---|---|
| `agent.py` | Runtime: hand-written ReAct loop, prompt, model client, history, response parsing. **Held by brief 14 as of this baseline.** |
| `main.py` | Runtime: CLI, preflight, workspace setup, REPL. The documented command is `python main.py`; there is no installed entry point. |
| `tools.py` | Runtime: typed model-facing tool registry and the six implementations. |
| `sandbox.py` | Security boundary: workspace path admission and bounded read access. A leash on model-selected reads, not process isolation. |
| `config.py`, `omniagent.toml` | Layered settings and shipped defaults. **Held by brief 14.** The built-in default model (`agent.py:36`) and the TOML default (`omniagent.toml:4`) disagree. |
| `observability.py` | Structured JSONL logs, field-name redaction, truncation. |
| `export_dataset.py`, `validate_dataset.py`, `dataset_provenance.py` | Data pipeline: export, validation, prompt fingerprint and sidecar. Root-level CLI/import paths today. **`dataset_provenance.py` is the ninth root module and `pyproject.toml:46` ships eight — see ADR-0002.** |
| `scripts/collect_dataset.py`, `scripts/publish_dataset.py`, `scripts/run_dir.py`, `scripts/promote_model.py` | Data/model lifecycle: collect runs, publish bundles, record runs, promote a local model. |
| `scripts/eval_scoring.py`, `scripts/eval_workspace.py`, `scripts/holdout_eval.py`, `scripts/session_eval.py` | Evaluation: score answers, establish the evaluation workspace, run holdout/session evaluation, record and report. `eval_workspace.py` exists because the agent once answered a question out of the answer key. |
| `scripts/smoke_train.py`, `scripts/build_notebook.py` | Training: CPU smoke training and notebook generation. **`build_notebook.py` is the source of truth for the notebook; editing the notebook is work that disappears.** |
| `docs/demo1.svg` | Static README demo asset. The cast was recorded on `omniagent-v2`. |
| `tests/` | 30 flat test modules, 658 tests. 20 of the 30 import a flat root module. |
| `data/question-bank/` | Local-only legacy 19-question bank; `data/` is gitignored and excluded from the public source tree. It is not the MVP evaluation baseline. |
| `eval-fixture/` | Tracked stable evaluation subject. **Nothing may be written into it** — it is reachable by design, and adding one file once moved a question's step count from 3 to 2. |
| `notebooks/train_omniagent_lora.ipynb` | Generated training interface. Regenerate from the generator; never edit in place. |
| `docs/` | Public guides, generated demo material, PM briefs and records, the threat model, the contract, and (from ADR-0001) `docs/architecture/`. |
| `.github/workflows/ci.yml` | Hosted lint, type-check and test gates, after an **editable** install — which is why it cannot see the ADR-0002 defect. |
| `.github/workflows/waka-readme.yml` | Scheduled README update through a third-party action at `@master`, with a secret and `contents: write`. |
| `pyproject.toml` | Packaging and all three static-analysis path lists. **The module list is maintained in three places and two of them disagree** (ADR-0002). |
| `requirements.txt`, `LICENSE`, `README.md` | Contributor entry points. `README.md:7` claims "Nothing leaves localhost", which is too broad. |
| `data/`, `models/` | Referenced by source and docs, **absent from `git ls-tree HEAD`.** Operator-managed local locations; assume nothing about their contents or provenance. |
| `omniagent-core` | Not on `main`. Branch `core-offline-runtime` (`fd5176a`), gated by `.github/workflows/core.yml` on a pinned `ubuntu-24.04`. Not merged; merging is undecided. |

## What is not on `main` and should not be mistaken for it

| | |
| --- | --- |
| `secure_search.py` | **Three variants, parked.** 1,016 and 1,199 lines on `origin/codex/search-text-race-safety-20261101-workspace` and `origin/codex/posix-device-race-20261101`; 1,069 uncommitted in a worktree. No brief, no `## Result`. |
| the architecture blog outline | `docs/blog/architecture-series-outline.md`, uncommitted in the Codex architecture-docs worktree. Not adopted, not deleted (ADR-0001). |
| seven `codex/*` branches | Several point at commits already on `main`. |
| 284 MB of scratch | `.scratch/` (96 MB), `.codex-worktrees/` (187 MB), `.brief11-worktree/` (1.3 MB) inside the checkout, all gitignored. They ship to nobody and they make `git status` noisy, which is how three measurements were voided. |

## The one thing a reader should take from this map

The nine root modules are not a style choice with a tidier alternative; they
are **a list that has to be maintained in three config sections**, and the
measurement in ADR-0002 shows two of the three are already wrong. That is the
argument for a package, and it is the only argument this document makes.
