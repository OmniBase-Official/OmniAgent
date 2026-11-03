# OmniAgent Agentic MVP and Evaluation Contract

**Status: OWNER-APPROVED CONTRACT — 2026-11-03.** Core MVP security and evaluation policies below are frozen. Evaluation thresholds, retention duration, exact model digest, and execution preconditions remain open gates. This approval does not authorize a cohort, service startup, runtime change, commit, or push.

- **Prepared:** 2026-11-03
- **Source baseline:** `f37044dafa8de7d840b97da00fa8a055010b1be3` (`main`, also `origin/main` when checked)
- **Purpose:** Combine the SE security/privacy proposal and the AI/ML evaluation proposal into one contract for review before any agentic runtime work.

## 1. Product goal

OmniAgent should be a local-first repository assistant. The model should choose whether to answer, which permitted tool to call, what arguments to use, and whether more evidence is needed. Application code validates and dispatches every call, returns the real tool result, and enforces the step limit. This is a model-led tool loop; it does not promise parity with ChatGPT or guarantee correct reasoning.

The first-use MVP is for one user on one machine, reading a user-selected workspace. Tools remain read-only. The MVP does not run arbitrary commands, write or delete files, fetch network resources, load plugins, or delegate to other agents.

The approved owner threat model is [the search-boundary threat model](threat-model-2026-11-02-the-search-boundary.md). In particular, `sandbox.py` is a boundary on model-selected reads, not operating-system process isolation. Prompt injection remains possible. Concurrent untrusted writers are outside the current threat model and require a new owner decision before the deployment model changes.

## 2. Frozen runtime contract

### Endpoint and model

**Approved:** Model inference must use an HTTP endpoint on loopback only. Permit the canonical `localhost` endpoint and explicit loopback IP literals (`127.0.0.1` or `::1`) on a configured port. Reject non-loopback hosts, malformed URLs, user information, query/fragment components, redirects to another host, and proxy routing. Do not log the full endpoint URL. A loopback address does not prove that the server process is Ollama or otherwise trustworthy; the MVP assumes the user controls the local model server.

The current source defaults to `http://localhost:11434/v1`, but `base_url` can be overridden. The source does not currently enforce loopback-only access. Enforcement and negative tests are required before a private pilot can claim this contract.

**Approved baseline choice:** the shipped `demo` profile's `omniagent-v2`, with temperature `0` and `max_steps=8`. Freeze the exact model digest and Ollama version at preflight before any completion request. The built-in default (`qwen2.5:7b`) and TOML default (`qwen2.5-coder:7b`) differ, so relying on an implicit default is not acceptable. Model availability and capability are currently unverified.

For evaluation, propose application-level `max_retries=0`, a bounded timeout, and no replacement trial. The OpenAI client is configured with its own retry count at zero, but the agent's separate retry setting currently defaults to two; both layers must be recorded and tested.

### Tool capability

The current registry contains six tools: `calculate`, `get_current_time`, `file_info`, `read_file`, `list_directory`, and `search_text`. These are the only capabilities approved for the MVP; no new tool may be added without a security review. Every task in an evaluation must also have an explicit evaluator-side allowlist. The prompt's tool catalogue is not authorization; the dispatcher must enforce the allowlist.

An unknown or disallowed tool request is a policy violation. The harness must stop that trial and record a sanitized category; it must not run another tool, expose a raw exception, or silently retry the trial. The current runtime has a registry-wide dispatcher, no per-task allowlist, and may return an `Error:` observation to the model, so this behavior needs implementation and mock tests before policy-violation trials are run.

### Filesystem and prompt injection

Use synthetic fixtures for evaluation. The model must not receive the evaluator's answer key or any real credentials. Treat file text, tool results, model output, and filenames as untrusted data. Prompt instructions cannot grant new capabilities; dispatcher and tool boundaries enforce access.

Test path traversal, hidden/denied/credential-like paths, oversized and binary files, and static symlink/junction escapes on each supported platform. State explicitly that these tests do not prove the model is immune to prompt injection or that the process is isolated. Do not claim protection from concurrent writers unless the threat model and platform-specific evidence are changed and approved.

### Logging, traces, export, and retention

Operational logging and evaluation recording are separate systems.

| Data | Operational default | Evaluation artifact |
|---|---|---|
| Prompts, system prompt, chain-of-thought, raw model replies | Never persist or print by default | Do not retain; score the final answer without storing hidden reasoning |
| File contents, raw observations, raw tool arguments, secrets, raw errors or stack traces | Never persist | Never persist; use synthetic fixtures and sanitized result summaries |
| Event status, duration, step count, tool name, model tag/digest, runtime version | May be recorded only in an explicitly enabled, sanitized trace | Record the minimum needed to reproduce the run |
| Final answer | Not part of operational logs | Score in memory; persist answer text only if the owner separately approves a restricted, synthetic-only artifact and retention period; otherwise persist score and answer hash |

Current defaults disable the persistent log file and log-console handler, but `verbose` defaults to `true` and prints reasoning/action details. The shipped `demo` and `collect` profiles specify log files, and observability events include fields used by dataset export. Name-based redaction and truncation do not establish that content is safe. The approved policy is quiet/sanitized behavior by default, dataset export as a separate explicit opt-in with field preview, and an owner-defined deletion/retention period before any persistent trace is enabled.

No user workspace data may enter the evaluation cohort or training pipeline. Do not use a frozen/legacy cohort as the new baseline. Do not automatically train on conversations or evaluation output.

## 3. Frozen evaluation design; run parameters still gated

### Task set and trial count

Use immutable synthetic fixtures, a fixture hash, and an answer key unavailable to the model and its tools. The approved pilot design is **6 categories × 2 variants × 3 repeats = 36 trials per arm**. Treat this only as a small exploratory pilot for discovering failure modes, not as statistically conclusive evidence or a production pass threshold.

| Category | Measurement | Oracle requirement |
|---|---|---|
| Tool selection | Select an allowed tool when evidence is needed | Freeze acceptable tool/action sequence per task |
| Evidence grounding | Base the answer on tool output without inventing facts | Exact expected value derived independently from the fixture |
| Multi-step completion | Carry evidence across a required sequence | Freeze each required step and expected intermediate fact |
| Multi-turn consistency | Use a fact from an earlier turn correctly | Freeze expected fact and answer for each turn |
| Abstention | Abstain only when the fixture is explicitly unanswerable | Distinguish known-unanswerable from missing evidence or tool failure |
| Injection and tool policy | Treat fixture instructions as data and obey the allowlist | Record any disallowed attempt as a policy violation; never execute it |

The prompt, fixture, rubric, allowed tool sequence, and accepted literal answers must be fixed before the first trial. The current runtime does not enforce a per-task allowlist, so the injection/policy category is blocked until a fake-model test proves the harness rejects disallowed calls without side effects.

### Scoring and reporting

Report these metrics separately; do not collapse them into one score:

- task success on answerable trials;
- acceptable tool-sequence rate on tool-required trials;
- evidence-grounded exact-answer rate;
- multi-step completion and multi-turn accuracy;
- valid and invalid abstention rates;
- injection resistance and disallowed-tool-attempt rate;
- step exhaustion, tool-error, timeout, and endpoint-failure rates.

Freeze exact accepted answers and denominators before the run. If a denominator is zero, report `null` and the raw count. Separate wrong answers, valid/invalid abstentions, execution failures, and exhausted trials. PM/owner must select acceptance thresholds and an uncertainty/reporting method before a cohort begins; thresholds must not be chosen after seeing results.

Start with one ReAct baseline arm. A structured-tool-call arm is a separate future decision. Compare protocol arms only if model weights/digest, task text, tools, limits, and other settings stay fixed; otherwise report the runs descriptively and do not attribute differences to protocol alone.

### Reproducibility record

For every trial, record only the metadata needed to reproduce and audit it:

- cohort/trial/task IDs and arm;
- exact commit and clean-tree assertion;
- fixture and protocol hashes;
- model tag and digest, Ollama/runtime version, and endpoint classification (`loopback` only);
- temperature, seed if supported, `max_steps`, timeout, retry policy, and task allowlist;
- tool names, sanitized status/result categories, step count, and execution status;
- score and (if separately approved) final-answer text in a restricted synthetic-only artifact.

Do not store full endpoint URLs, prompts, chain-of-thought, raw model replies, source contents, raw observations, raw errors, credentials, or user data. Artifacts must live outside operational logs, be append-only for the cohort, have an owner-approved retention/deletion period, and never be committed to the repository or fed to training.

### Run and stop rules

Before any cohort, verify the exact commit and clean tree, fixture/oracle agreement, prompt and protocol hashes, model digest, runtime version, loopback endpoint, allowlist behavior, retry behavior, and sanitized recorder with mock tests. Do not measure while another engineer is writing in the same checkout; use a pinned snapshot/worktree and recheck its identity after the run.

Use no automatic retries or replacement trials. Stop the cohort and mark it incomplete on revision/config drift, oracle mismatch, non-loopback endpoint, unexpected tool error, timeout, service/model change, or any prohibited content in a trace. Report started, completed, and failed trials separately.

## 4. One-shot capability probe — procedure approved, execution gated

The approved probe is one synthetic request to the exact loopback endpoint and model digest. It supplies a harmless fake function schema such as `probe_echo`; the returned call is inspected but never executed. Capture only whether a valid structured call was returned, finish reason, tool name, and schema-validation outcome. No files, user prompts, tools with side effects, retries, downloads, service startup, or persistent raw traces are permitted.

The probe answers only whether this server/model pair can emit a structured tool call. It does not establish task success, security, or superiority to the existing ReAct parser. The current runtime probe previously ended in `APIConnectionError`; do not infer model capability from that failure or from Ollama version alone.

Preconditions: owner has frozen the endpoint/model/logging policy; the Ollama service is already running and confirmed local; the model digest is recorded; proxy/redirect behavior is disabled; persistent logs are off; and one request/no-retry behavior is verified. If any precondition fails, stop without sending a completion request.

## 5. Security and test gates before pilot

Before a private pilot, implement and test:

1. endpoint validation and evidence that no request can route to a non-loopback host or proxy;
2. dispatcher-enforced fixed and per-task tool allowlists, including unknown/disallowed-tool stop behavior;
3. sanitized operational logging defaults and a separate evaluation recorder;
4. canary tests proving prompts, file contents, raw arguments/errors, and secrets do not leak into operational logs or traces;
5. path-boundary regression tests on every platform claimed as supported;
6. deterministic fixture/oracle, no-retry, stop-on-drift, and answer-key isolation tests.

Passing these gates reduces the stated risks; it does not prove prompt-injection immunity, model correctness, legal rights to third-party model/data assets, or process isolation.

## 6. Decisions for owner review

| Decision | Approved contract | Remaining gate |
|---|---|---|
| MVP audience and authority | Local, single-user, read-only workspace assistant | None |
| Endpoint | Enforce loopback; reject external hosts, proxy routing, and redirects | Implementation and tests required |
| Baseline model | `omniagent-v2` demo profile, temperature `0`, `max_steps=8` | Exact digest and Ollama version; availability unverified |
| Tools | Existing six read-only tools only; task-specific allowlist in evaluation | Allowlist implementation and tests required |
| Operational logs | Quiet by default; no raw content; sanitized telemetry only by explicit opt-in | Implement and test before pilot |
| Evaluation | Synthetic-only, 36 exploratory trials per arm; ReAct arm first | Freeze task inventory, answer key, and exact rubric |
| Acceptance threshold | No production threshold; 36-trial pilot is exploratory only | AI/ML to propose a threshold/reporting method before cohort; owner approves |
| Final-answer retention | Score in memory; do not persist answer text by default | Any exception requires separate owner approval |
| Retention/deletion | No persistent evaluation traces until a duration and deletion path are defined | SE to propose duration and deletion evidence |
| Probe | One no-retry synthetic structured-call request after preconditions pass | Readiness and safety preconditions; no cohort authorization |

## 7. Next sequence after review

1. SE converts the frozen security decisions into implementation acceptance tests.
2. SWE checks local Ollama readiness without starting services or sending prompts; any completion probe waits for the prerequisites above.
3. AI/ML freezes the task inventory, oracle, threshold, and trial record format against the approved tool contract.
4. AI/ML freezes the task inventory, oracle, threshold, and trial record format against the approved tool contract.
5. Implement only the smallest accepted safety/evaluation harness slice on an isolated branch; run mock tests and review it before the model probe.
6. Run the one-shot capability probe after readiness and safety preconditions pass; then decide whether to retain ReAct or plan a structured backend.
7. Run the exploratory ReAct cohort only after all gates pass and the owner freezes the exact snapshot and artifacts policy.

No cohort, runtime change, commit, or push is authorized by this contract. Probe execution remains gated by the readiness and privacy preconditions above.
