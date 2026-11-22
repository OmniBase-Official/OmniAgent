# Gate note for SE 01's fix: empty answer, exit code, disallowed tool

**MEASURED 2026-11-23 by reading `docs/pm/agentic-mvp-contract-2026-11-03.md` and
`docs/architecture/` at `origin/integration/canonical-20261122` (`b164aaa`).**

1. **The contract speaks to the disallowed tool, not to the exit code.** §2: an unknown or disallowed tool request "is a policy violation"; the harness "must stop that trial and record a sanitized category; it must not run another tool, expose a raw exception, or silently retry". It says nothing about an empty answer or about a CLI exit status, and no ADR in `docs/architecture/` does either (a search for `exit code`, `empty answer`, `non-zero` returns nothing).
2. **The CLI-level fix is allowed and needs no amendment.** It runs no other tool, retries nothing, and the stop at `agent.py` is untouched; the contract is silent on the layer above it, so it is not contradicted. The graph-runtime spec's invariant T2 (stop, do not retry, substitute nothing) points the same way.
3. **Two constraints the contract does impose on the message, which the fix must meet:** it may carry a sanitized *category* only. §2's logging rule forbids raw model replies, so the line must not echo model text, **and I would also keep the model-chosen tool name out of it** — it is model output, so untrusted data, and a category such as `disallowed tool` is enough.
4. **The acceptance test should assert the specific cause**: non-zero status, one `[!] No answer:` line, and that no tool ran — not merely "the output is not empty". Mutation check: revert the `main.answer` change; that test must go red while G2e stays green (G2e pins the stop in `agent.run()`, which the fix deliberately leaves alone).
5. **One optional line for the contract**, not required: "a refused run exits non-zero." Worth adding when the owner next amends §2, so the CLI behaviour has a source other than a test name.
