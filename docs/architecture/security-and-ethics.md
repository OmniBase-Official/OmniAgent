# Security, privacy, ethics, and release posture

**Baseline:** source at `ae5cd95` on `main`, 2026-11-04. Adopted from a Codex
draft written at `f37044d` under ADR-0001; no source file changed between
those commits. Gates re-run at this baseline: `ruff` clean, `mypy` clean over
45 files, 658 tests passed in 16.48 s.

**Governing documents, in order:**
[the agentic MVP contract](../pm/agentic-mvp-contract-2026-11-03.md) (owner
approved, 2026-11-03) and
[the search-boundary threat model](../pm/threat-model-2026-11-02-the-search-boundary.md)
(owner approved, with rulings of 2026-11-02 and 2026-11-04). This page is an
evidence ledger under them, not a policy of its own. **Source inspection is
not an independent security audit. No legal or safety certification is
claimed here.**

## Product capability statement

At this revision, the model-facing registry in `tools.py` exposes six typed
tools: arithmetic, local time, file read, directory listing, literal text
search, and file metadata. The file tools are read-only and scoped by
`sandbox.py` to an operator-selected workspace. There is no model-facing
arbitrary shell, file-write, network-fetch, plugin, or multi-agent capability.
Verified at this baseline by importing the registry, not by reading it.

This describes the ReAct tool registry only. Operator-run training and
maintenance workflows can download packages and models, clone `llama.cpp`,
invoke local processes, publish datasets to a selected destination, and
register a model in Ollama. **Keep these capabilities outside statements about
what the model itself can do.**

## Threat model and the two rulings

The owner-approved threat model distinguishes four attackers: (1) a mistaken
or adversarial model selecting paths, (2) prompt injection in workspace
content, (3) a hostile repository that already contains links, and (4) a
concurrent local process racing filesystem operations. Only 1 and 3 are
defended. The sandbox is a leash on model-selected reads, **not** process
isolation.

**Ruling of 2026-11-02:** `secure_search.py` is not merged. The race attacker
it defends must already be able to write inside the workspace, and anything
that can write there can read the same bytes directly; the proposed
implementation also fails closed off AMD64 and off ext4, which turns a
read-only convenience tool into a platform gate.

**Ruling of 2026-11-04, which supersedes the first in scope:** a third variant
turned up in flight, so **three now exist** — 1,016 and 1,199 lines on
`origin/codex/search-text-race-safety-20261101-workspace` and
`origin/codex/posix-device-race-20261101`, and 1,069 uncommitted in a
worktree. **The work is parked: not continued, not deleted, and none of the
three has a brief or a `## Result`.** Reopening it requires the new owner
decision the contract names and criteria 1 to 5 of the threat model answered
in writing. This document does not override either ruling.

**What would reverse them is written down and checkable:** the agent gaining a
tool that writes, or the agent running anywhere other than one person's
machine. **Public distribution is the second condition**, which is why
[the release-readiness plan](../pm/release-readiness-2026-11-04.md) says that
going public is itself the decision the contract requires.

## Evidence ledger

### Verified from source at the stated baseline

- **Local default, configurable endpoint:** `agent.py:34` defaults to
  `http://localhost:11434/v1`; `config.py` resolves `base_url` from built-in,
  TOML, `.env`, environment, or CLI values. **The application does not enforce
  localhost-only egress at this baseline.** Prompts and observations are sent
  to the configured endpoint. Contract gate 1 (brief 14) exists to close this.
- **Narrow model tools:** `tools.py` defines six registry entries with
  Pydantic argument schemas. Unknown names do not create new capabilities.
  `calculate` walks an allowlisted AST rather than calling `eval()`. **There
  is no per-task allowlist** — contract gate 2, unassigned.
- **Read boundary:** `sandbox.py` resolves candidate paths under a configured
  workspace; refuses hidden and credential-like paths, selected
  key/certificate suffixes, non-regular files, UNC/NUL paths, binary content,
  and oversized reads; and supports denied paths for transcripts. These
  controls do not prove all secrets are recognized.
- **Reparse points are refused, and one half of that is load-bearing:** brief
  13 committed a junction test that goes red when the guard is removed. Under
  the same mutation the symlink test stays green, because the directory
  classification drops symlinks on its own. **By reading the code — not
  measured, there is no Linux here — a POSIX-only suite would stay green if
  the guard were deleted**, and contract gate 5 asks for path-boundary tests
  on every platform claimed as supported.
- **Prompt injection remains possible:** file content is returned as model
  context. Path validation does not distinguish instructions from data or
  prevent the model from following malicious content. The limited tool set
  reduces available actions but does not establish correct model behavior.
- **Logs contain sensitive content by design:** `agent.py` records questions,
  prompt, model reply, tool input, and observations through
  `observability.py`. **Contract delta:** the approved policy is quiet and
  sanitized by default, with dataset export as a separate explicit opt-in.
  Today `verbose` defaults to `True` (`agent.py:260`) and `agent.py:493` and
  `:869` print the full `base_url`, which the contract forbids. Field-name
  redaction and truncation are heuristics, not content classification.
- **Dataset lineage is partial:** `dataset_provenance.py` fingerprints the
  system prompt represented in a dataset and writes a sidecar.
  `validate_dataset.py` checks structure and secret-like content. These
  controls do not establish copyright, consent, lawful basis, model identity,
  or source-file permission.
- **Training crosses network boundaries:** `scripts/build_notebook.py` loads
  the named Hugging Face base model/tokenizer, clones
  `https://github.com/ggml-org/llama.cpp.git` on mutable `master` if missing,
  uses installed Python packages, and runs local conversion/Ollama commands.
  `scripts/smoke_train.py` also resolves model/tokenizer names through
  Transformers. **Local Ollama inference does not make this workflow
  offline**, and `README.md:7` says otherwise.
- **Repository automation contacts external services:**
  `.github/workflows/ci.yml` runs on GitHub and installs Python packages.
  `.github/workflows/waka-readme.yml` runs a third-party action from
  `@master`, uses a WakaTime secret, and has `contents: write` — external
  automation with write authority on a mutable reference.
- **Software license:** the repository includes an MIT `LICENSE`. That file
  alone does not license third-party models, weights, tokenizers, datasets,
  screenshots, package dependencies, or external conversion tools.
- **CI gates:** checked-in CI runs Ruff, mypy, and pytest on Ubuntu after
  editable installation. **An editable install masks the packaging defect in
  ADR-0002**, so CI as configured cannot see it. CI establishes nothing about
  model quality, data rights, vulnerability posture, egress policy, or
  release signing.

Relevant source tests include `tests/test_local_only.py`,
`tests/test_sandbox.py`, `tests/test_link_refusals.py`,
`tests/test_observability.py`, `tests/test_export_dataset.py`,
`tests/test_validate_dataset.py`, `tests/test_dataset_provenance.py`, and
`tests/test_notebook.py`. They pass at this baseline. **Passing is not proof
of the property**; a refusal test earns its place only when removing the guard
turns it red.

### Not established by the inspected repository

- Whether any dataset examples were collected with informed consent or may
  lawfully be used for fine-tuning and redistribution.
- The exact license, usage restrictions, redistribution rights, and
  attribution obligations for the selected base model, tokenizer, fine-tuned
  weights, or GGUF artifacts. A model identifier in a notebook is not a
  license record.
- Whether screenshots/demo transcripts contain only synthetic data or include
  a person's data; the README calls the demo a real session, and its
  provenance has not been audited.
- A complete software bill of materials, dependency license compatibility
  review, reproducible lockfile, model artifact checksum/attestation, or
  signed release process.
- A network egress policy, privacy/retention policy, supported deployment
  threat model, independent penetration test, or legal review.
- Whether every secret-like value is caught by the log formatter or dataset
  validator. Redaction tests cannot prove detection of arbitrary secrets in
  natural-language content.

### Missing before a public pilot or broader release

- **The contract's six gates.** They are the definition of ready and the
  owner has already approved them; one is in flight, one is partly done, four
  are open. The readiness plan tracks their state.
- **An installed-artifact test.** The wheel this project builds today cannot
  import its own dataset exporter (ADR-0002). Nothing in CI would notice.
- **A `SECURITY.md`** with a private vulnerability reporting channel,
  supported versions, response expectations, and a disclosure process.
- **A data and privacy notice** explaining endpoint configuration,
  prompt/log contents, retention/deletion, training-data reuse, and how users
  can avoid collecting sensitive workspace content.
- **A provenance/licensing inventory** for the exact base model, tokenizer,
  adapter/merged weights, datasets, screenshots, third-party assets, and
  redistributed artifacts. Record unknowns rather than inferring rights. The
  table below is the start of it, not the finish.
- **Dependency and workflow hardening:** evaluate version/hash pinning,
  replace mutable third-party workflow references with reviewed immutable
  revisions, reduce workflow write permissions, and document package/model
  download destinations.
- **An explicit release checklist** that separates software MIT licensing from
  model/data/asset rights and requires CI, vulnerability review, provenance
  checks, and platform support evidence.
- **Counsel review** for intended publication and use jurisdictions,
  including privacy/data protection, copyright/database rights, consumer
  disclosures, and model redistribution terms. The MIT warranty disclaimer is
  not a substitute for jurisdiction-specific advice.

## Licensing and provenance inventory

| Asset | What is known | What remains unknown / action |
|---|---|---|
| OmniAgent source | Root `LICENSE` is MIT. | Confirm newly added docs/assets are intended to follow the repository license and preserve notices. |
| Python dependencies | Declared in `pyproject.toml` and mirrored in `requirements.txt`; runtime and training extras are distinct. | Generate and review an exact-version SBOM/license report for each release; ranges are not an inventory of installed artifacts. |
| Base model and tokenizer | Notebook names `Qwen/Qwen2.5-1.5B-Instruct`; runtime defaults to an Ollama tag, with model IDs chosen by operator. | Verify exact revisions, terms, attribution, acceptable use, redistribution, and derivative/quantization conditions for each selected artifact. |
| The served fine-tune | Measured 2026-11-04: `omniagent-v2:latest`, manifest `05ba6fe701c5`, weights blob `sha256-40995d3b…c8ae39c7`, Ollama 0.34.4. 3.1 GB, built locally four weeks ago. **Not in the repository and not obtainable from it.** | A Qwen2.5 derivative carries the base model's terms. Establish redistribution rights **before** any answer to readiness block D3 that involves publishing it. |
| Fine-tuned weights, adapters, GGUF | Generated locally by the training workflow; manifests include some build metadata/checksum information. | Establish artifact-specific lineage, complete license notices, exact base/tokenizer revisions, dataset fingerprint, and redistribution permissions. |
| Training/evaluation data | Run logs can include questions and workspace observations; a prompt fingerprint sidecar exists. `questions/` and `eval-fixture/` are tracked; the 153-example merged dataset lives outside the repository at `G:/OmniAgent/datasets/`. | Identify authors/sources, consent, privacy, copyright, permitted use, and redistribution status. Do not infer rights from being in a public repository. |
| Demo SVG/screenshots | `docs/demo1.svg` is generated by `scripts/make_demo_svg.py`; `README.md:11` describes the session as real, on `omniagent-v2`. | Confirm whether user-identifying or third-party content is present and record source/model/license/consent. |
| `llama.cpp` and external tools | The notebook clones upstream `master` and invokes its converter. | Pin reviewed revisions, record applicable licenses/notices, and verify model conversion/redistribution terms. |
| External CI action | The WakaTime workflow calls a third-party action at `@master`, uses a secret, and holds `contents: write`. | Review action provenance, permissions, data sent to the service, retention, and immutable revision pinning. |

## Safeguards for the current MVP

1. Keep the ReAct registry small and read-only. **Do not add shell, write,
   browser/network, plugin, delegation, or account-connected tools** without a
   new threat model, capability-specific tests, human approval design, and an
   audit trail. A write tool reverses the `secure_search.py` ruling by the
   threat model's own criteria.
2. Keep inference at the local default unless the operator deliberately
   changes it; explain that changing the endpoint sends prompt context there.
   Do not present a configurable local default as enforced network isolation.
3. Treat workspace contents and model outputs as untrusted. Avoid putting
   secrets or data the operator cannot share in the workspace, and review logs
   before export or publication.
4. Minimize log scope, protect file permissions/storage, set retention and
   deletion routines, and inspect exported examples before training. Field
   redaction is not a substitute for review.
5. Record exact model and dataset provenance before distributing trained
   artifacts; stop publication while rights are unknown.
6. Require explicit human approval for any future action with external side
   effects, identifying the target, the data, the consequence, and an
   auditable decision record.

## Ethical use and user expectations

- Tell users that model answers can be incorrect and that the project has not
  established suitability for consequential decisions. Keep a human
  responsible for checking outputs before acting on them.
- Make log and training reuse visible and operator-controlled. Before examples
  are exported or published, review whether prompts, tool observations, or
  files contain personal, confidential, copyrighted, or otherwise restricted
  material.
- **Do not treat any evaluation in this repository as a safety or fairness
  assessment.** The 19-question bank measures its own tasks and nothing else,
  and the contract forbids using it as the MVP baseline at all. The
  contract's own 36-trial pilot is exploratory by its own terms. Demographic
  coverage, disparate impacts, and downstream harms have not been
  established.
- **Do not describe "local" as equivalent to "private."** A local endpoint
  removes one network transfer in the default inference configuration, while
  local logs, backups, workspace access, a configured remote endpoint,
  package downloads, and CI workflows each have their own exposure and
  retention boundary.
- **Do not publish a number measured on a model the reader cannot obtain**
  without saying so in the same sentence. Readiness block D3 is the decision;
  until it is made, the demo cast and the training comparison table both name
  models absent from the repository.
