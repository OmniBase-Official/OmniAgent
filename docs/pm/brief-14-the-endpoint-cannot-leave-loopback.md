# Brief 14 — the endpoint cannot leave loopback

**For the security engineer.** Static throughout. **No model run is needed,
and no test in this brief may open a socket** — that is the point of it.

This is **gate 1** of the owner-approved contract
(`docs/pm/agentic-mvp-contract-2026-11-03.md`, section 5): "endpoint validation
and evidence that no request can route to a non-loopback host or proxy." The
contract is frozen on this; what is missing is the code and the evidence.

## What is measured, 2026-11-04, on `ec7787a` (`main`)

**Re-confirmed 2026-11-05 at `320d411`.** Everything between the two commits
is documents only; no source file changed, so every figure below still holds
exactly. **Branch from `320d411`.**

The contract's claims about the source are **correct, and I checked them
rather than taking them**:

| Claim | Verified |
| --- | --- |
| the default is loopback | `agent.py:34` — `DEFAULT_BASE_URL = "http://localhost:11434/v1"` |
| but nothing enforces it | `agent.py:255` — `base_url: str = Field(default=DEFAULT_BASE_URL, ...)`. A plain `str` field. **Any URL is accepted** |
| the model default disagrees with the TOML | `agent.py:36` `qwen2.5:7b` · `config.py:16` `qwen2.5:7b` · `config.py:20` and `omniagent.toml:4` `qwen2.5-coder:7b` |
| two retry layers disagree | the client is built with `max_retries=0` (`agent.py:443`) while the agent's own `max_retries` defaults to **2** (`agent.py:261-266`) |
| `verbose` defaults to printing the trace | `agent.py:260` — `default=True` |

And one the contract states as policy that the source currently breaks:
**`agent.py:493` and `agent.py:869` put `self.config.base_url` into error text
the user sees.** The contract says "Do not log the full endpoint URL."

Gates on `ec7787a`: ruff clean, mypy clean over **45** files, **658 passed**.

## Goal

`base_url` is validated **where it is configured**, not where it is used, and
nothing in the client can route a request off loopback.

## What must hold

1. **Accepted:** `http://localhost:<port>/...`, `http://127.0.0.1:<port>/...`,
   `http://[::1]:<port>/...`. Any port.
2. **Rejected at configuration time:** every other host, including
   `127.0.0.1.example.com`, `localhost.attacker.test`, `0.0.0.0`,
   `[::ffff:127.0.0.1]`, a bare hostname, an IP that merely starts with
   `127` in a string sense but is not parsed as loopback, `file://`,
   `ftp://`, a URL with user information (`http://user:pw@localhost`), a URL
   carrying a query or fragment, and a malformed URL. **Decide `0.0.0.0` and
   `::ffff:127.0.0.1` deliberately and say why** — one is a bind address, not
   a destination, and the other is loopback wearing an IPv6 coat.
3. **No proxy.** An `HTTP_PROXY`, `HTTPS_PROXY` or `ALL_PROXY` in the
   environment must not be able to carry this request. Construct the client so
   environment proxy settings cannot apply, and **prove it with a test that
   sets those variables** and shows the request would still go direct.
4. **No cross-host redirect.** A 307 to another host must not be followed.
   Either redirects are off or the hop's host is re-checked.
5. **The URL is not printed.** `agent.py:493` and `:869` report a
   classification — "the configured local endpoint" — not the string. The port
   may stay if you argue for it; the host and path may not.

## Tests that must fail first, and must not touch the network

**A rejected URL has to be rejected before a socket exists.** This is the
trap: a bad host also fails at connection time, so a test that merely asserts
"an error happened" passes for the wrong reason and would pass with no
validation at all.

So each rejection test must prove **no connection was attempted** — inject a
transport, client factory or socket shim that raises if it is used, and assert
the validation error arrives instead. If your test would still pass with the
validator deleted, it is not a test of the validator.

| Test | Must fail before, pass after |
| --- | --- |
| each accepted form constructs | new |
| each rejected form raises at config time, with **no connection attempted** | new |
| proxy environment variables cannot carry the request | new |
| a cross-host redirect is not followed | new |
| neither error path prints the host or path | new — assert on the message text |

## Mutations that must go red

Restore from a scratchpad copy, **never `git checkout --` alone**.

| # | Mutation | Must go red |
| --- | --- | --- |
| Ma | Delete the validator entirely | every rejection test. **If any still passes, it was passing on the connection failure** — report which |
| Mb | Accept any host whose string contains `localhost` | `localhost.attacker.test` |
| Mc | Let the client read proxy environment variables again | the proxy test |
| Md | Put `base_url` back into one error message | the message test |

**Ma is the one that matters**, for the reason in the section above.

## Files you may touch

- `agent.py` — the `base_url` field and its validator, the client
  construction, and the two message sites at `:493` and `:869`. **Nothing
  else in it**
- `config.py` — only if the validator belongs there; say which you chose and
  why
- `tests/test_config.py`, or a new `tests/test_endpoint_policy.py` — your
  call, say which
- `tests/test_local_only.py` — if it already asserts something about the
  endpoint, keep it in step

## Files you may not touch

`tools.py` · `sandbox.py` · `secure_search.py` and anything on its branches ·
`scripts/**` · `eval-fixture/**` · `questions/**` · `models/**` · `data/**` ·
`omniagent-core/**` · `.github/workflows/**` · `NEXT_CHAT.md` · `README.md` ·
`omniagent.toml` · `docs/` except your `## Result`.

**Do not change the model defaults, the retry defaults or `verbose`.** All
three are real defects, all three are named in the contract, and each is its
own brief with its own test. Changing one here hides it in this diff. If a
test you write happens to prove one of them wrong, say so in `## Result` and
leave the default alone.

**Do not change a tool's description or the system prompt** — they reach the
model every turn and are part of every training example.

## Gates

```
.venv\Scripts\python.exe -m ruff check .
.venv\Scripts\python.exe -m mypy
.venv\Scripts\python.exe -m pytest
```

Full path, **never your own `-q`**. Baseline **658 passed**, mypy clean over
**45** files. Say what the count moved to.

## Where to work — this is now contract, not preference

The contract's run rules say: "Do not measure while another engineer is
writing in the same checkout; use a pinned snapshot/worktree and recheck its
identity after the run." Three measurements have been voided by exactly that.

**Branch from `main` at `320d411`, work in your own worktree, and commit to
your own branch — never to `main`.** The contract and this brief are on `main`
as of 2026-11-04. The manager merges.

## The split

Nothing here needs a model, and nothing here may contact one. The whole brief
is yours; the manager re-runs Ma–Md afterwards, as always.

## Commit

```
git add agent.py tests/
git commit -m "security: the endpoint is validated as loopback before a socket exists"

git add docs/pm/brief-14-the-endpoint-cannot-leave-loopback.md
git commit -m "docs: brief 14 result -- the endpoint policy has tests now"
```

**Do not run a bare `git push`** — two remotes, and `main` tracks the one this
work does not belong to. Name it: `git push origin <your branch>`.

## The one thing that would make this wrong

**A test that passes because the connection failed.** `http://evil.example/v1`
is unreachable from this machine anyway, so a rejection test can be green with
no validator at all. Ma is how you find out. Every rejection test must prove
the socket was never opened, or it is testing the network instead of the code.

The second way: **validating at request time instead of configuration time.**
A config object that holds an invalid endpoint until something tries to use it
will eventually be used by a path that forgot to check — and the contract's
claim is that no request *can* route off loopback, not that the ones we
remembered to guard do not.

## Result

<!-- Engineer: append here. Which file you put the validator in and why; the
accepted and rejected forms with your deliberate call on 0.0.0.0 and
::ffff:127.0.0.1; how you proved no socket was opened; the proxy and redirect
evidence; Ma-Md each with what went red and, for Ma, whether any rejection
test was passing on a connection failure; the three gate results with the
count explained; the branch and commit hashes; and anything you refuse to
claim. -->
