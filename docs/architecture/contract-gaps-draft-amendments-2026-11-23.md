# Three contract-versus-product gaps at `b164aaa` — state, and draft text

**MEASURED 2026-11-23, by reading the committed blobs at
`origin/integration/canonical-20261122` (`b164aaa`).** Nothing was run and
nothing below is applied. **Draft text for the owner to approve, edit or refuse.**

## (a) `inspect_config_precedence` against "six tools"

**State.** It is not only an operator `--tool` choice. By source at `b164aaa`:

- `tools.py` registers it: `TOOLS["inspect_config_precedence"] = Tool(...)`, so the registry has **seven** entries (`calculate`, `get_current_time`, `file_info`, `inspect_config_precedence`, `read_file`, `list_directory`, `search_text`);
- it is in `FIXED_TOOL_ALLOWLIST` (`tools.py:300-310`), so the dispatcher **permits the model to call it**, and `main.py:94` builds the `--tool` choices from that same set;
- `agent.py` also takes a deterministic route on the question text (`_is_config_precedence_request`, `agent.py:829`), and a second capability, `inspect_default_model_cli`, sits in `FIXED_INTERNAL_CAPABILITY_ALLOWLIST` (`tools.py:313`) outside the registry.

Contract §2 says the six named tools "are the only capabilities approved for the MVP; no new tool may be added without a security review". **I found no security review of it** in `docs/architecture/` or the ADRs. Not run: whether it reads anything outside the config files, which is the question that decides its severity.

**Draft amendment, option 1 (record it as approved):** replace the first sentence of §2's tool paragraph with —
> The registry contains seven tools: `calculate`, `get_current_time`, `file_info`, `read_file`, `list_directory`, `search_text`, and `inspect_config_precedence`, which reads configuration metadata only and never file contents or secret values. `inspect_default_model_cli` is an internal capability and is not model-facing. No further tool may be added without a security review.

*Only true if the SE confirms it, by test, that the tool returns metadata only.*

**Draft, option 2 (hold the line at six):** no text change; the SE removes it from `FIXED_TOOL_ALLOWLIST` and the registry, and the deterministic route in `agent.py` goes with it.

## (b) The `localhost` wording

**State: the amendment was applied.** `docs/pm/proposed-contract-amendment-endpoint-2026-11-22.md` says approved and applied, and the canonical contract §2 now reads "Permit **loopback IP literals only** (`127.0.0.1`, any address in `127.0.0.0/8`, or `::1`)" with an amendment record. **But §2's next paragraph is stale** and contradicts it:

> *Current text (line 23):* "The current source defaults to `http://localhost:11434/v1`, but `base_url` can be overridden. The source does not currently enforce loopback-only access. Enforcement and negative tests are required before a private pilot can claim this contract."

At `b164aaa` the default is `http://127.0.0.1:11434/v1` and the validator enforces it (brief 14 and brief 22's corpus). **Draft replacement:**
> The default endpoint is `http://127.0.0.1:11434/v1`. `base_url` can be overridden, but the validator refuses any value that is not a loopback IP literal, and that refusal is pinned by a corpus of accepted and rejected forms.

**A retraction of mine.** I wrote on 2026-11-22 that "both READMEs still document `localhost`". **Wrong for the canonical line:** the README has **0** mentions of `localhost` at `5005039` and at `b164aaa`, and 6 only on O (`3c76fd2`). The PM's count was right and the cost of the amendment is smaller than I said.

## (c) The README: the model claim and "~600 lines"

**State.**
- Line 3 says the agent is "written from scratch in **~600 lines** of Python". The six core modules are **4,107 lines** at `b164aaa` (`agent.py` 1,330; `tools.py` 1,296; `sandbox.py` 477; `main.py` 349; `observability.py` 353; `config.py` 302). Stale by roughly seven times, and it is the sentence that sells the "hand-rolled and small" premise.
- Line 12 presents the demo as a real session on `omniagent-v2`; line 241 tells a reader to `ollama pull qwen2.5:7b`. Every figure this project owns was measured on `omniagent-v2`, which is not in the repository and cannot be pulled from it.

**Draft replacement for line 3:**
> A local-only ReAct agent, written from scratch in plain Python with no agent framework (about 4,000 lines across six core modules).

**Draft addition under the demo caption (line 12):**
> The demo above was recorded on `omniagent-v2`, a local fine-tune that is **not distributed with this repository**. The default model is the generic `qwen2.5:7b`; behaviour and speed will differ from the recording, and no figure in this repository has been measured on it.

*The last clause is the owner's to confirm — I have not checked every figure in the README against its model.*

## What I did not check

- Whether `inspect_config_precedence` is metadata-only (decides (a)'s option).
- Every README figure's model, and README text outside the lines quoted.
- Anything at runtime: all of the above is from committed blobs.
