# Brief 14 — the paste-ready task for the security engineer

Paste everything below the line. The companion brief is
`docs/pm/brief-14-the-endpoint-cannot-leave-loopback.md`; `## Result` goes
there.

---

You are the **security engineer** on OmniAgent, `D:\code-project\OmniAgent`,
baseline **`main` at `ec7787a`**. Gates re-run by the manager today: **658 passed**, `ruff` clean, `mypy` strict clean over 45
files.

**Read `docs/pm/brief-14-the-endpoint-cannot-leave-loopback.md` and execute
it.** This is **gate 1** of the owner-approved contract at
`docs/pm/agentic-mvp-contract-2026-11-03.md`, section 5. **No model run is
needed, and no test in this brief may open a socket.**

**Branch from `main` at `ec7787a`, work in your own worktree, and commit to
your own branch — never to `main`.** The contract and this brief are on `main`
as of 2026-11-04. The contract's own run rules forbid two writers in one
checkout, and three measurements have already been voided by it. The manager
merges.

## What is already measured

The contract's claims about the source are correct; the manager checked them:

- `agent.py:34` — `DEFAULT_BASE_URL = "http://localhost:11434/v1"`;
- `agent.py:255` — `base_url: str = Field(...)`, a plain `str`. **Nothing
  enforces loopback. Any URL is accepted;**
- `agent.py:493` and `agent.py:869` **print `self.config.base_url`** in error
  text, which the contract forbids.

## What must hold

1. Accept `http://localhost:<port>/…`, `http://127.0.0.1:<port>/…`,
   `http://[::1]:<port>/…` on any port.
2. Reject **at configuration time**: every other host, `127.0.0.1.example.com`,
   `localhost.attacker.test`, `0.0.0.0`, `[::ffff:127.0.0.1]`, bare hostnames,
   `file://`, `ftp://`, user information in the URL, a query or fragment, and
   malformed URLs. **Decide `0.0.0.0` and `::ffff:127.0.0.1` deliberately and
   say why.**
3. **No proxy**: `HTTP_PROXY` / `HTTPS_PROXY` / `ALL_PROXY` must not be able to
   carry this request. Prove it with a test that sets them.
4. **No cross-host redirect**: a 307 to another host must not be followed.
5. **The URL is not printed** — the two error sites report a classification,
   not the string.

## The trap, and it is the whole brief

**A rejected URL also fails at connection time**, so a test that only asserts
"an error happened" passes with no validator at all. Every rejection test must
prove **no socket was opened** — inject a transport or client factory that
raises if used, and assert the validation error arrives instead. **If your test
would still pass with the validator deleted, it is not a test of the
validator.**

Mutation **Ma** is exactly that: delete the validator and report whether any
rejection test still passes. If one does, name it — it was passing on the
network, not on the code.

Mb accept any host containing `localhost` → `localhost.attacker.test` must
fail · Mc let the client read proxy environment variables again → the proxy
test must fail · Md put `base_url` back into one message → the message test
must fail. Restore from a scratchpad copy, **never `git checkout --` alone**.

## Files you may touch

`agent.py` (the `base_url` field and validator, the client construction, and
the two message sites at `:493` and `:869` — nothing else in it) ·
`config.py` only if the validator belongs there, say which you chose ·
`tests/test_config.py` or a new `tests/test_endpoint_policy.py`, your call ·
`tests/test_local_only.py` if it already asserts something about the endpoint.

## Files you may not touch

`tools.py` · `sandbox.py` · `secure_search.py` and its branches ·
`scripts/**` · `eval-fixture/**` · `questions/**` · `models/**` · `data/**` ·
`omniagent-core/**` · `.github/workflows/**` · `NEXT_CHAT.md` · `README.md` ·
`omniagent.toml` · `docs/` except your `## Result`.

**Do not change the model defaults, the retry defaults or `verbose`.** All
three are real defects named in the contract — `agent.py:36` says
`qwen2.5:7b` while `omniagent.toml:4` says `qwen2.5-coder:7b`; the client gets
`max_retries=0` while the agent's own default is 2; `verbose` defaults to
True. Each gets its own brief. Changing one here hides it in this diff. If a
test of yours happens to prove one of them wrong, say so in `## Result` and
leave the default alone.

## Gates

```
.venv\Scripts\python.exe -m ruff check .
.venv\Scripts\python.exe -m mypy
.venv\Scripts\python.exe -m pytest
```

Full path, **never your own `-q`**. Baseline **658 passed**, mypy clean over
**45** files. Say what the count moved to.

## Commits

```
git add agent.py tests/
git commit -m "security: the endpoint is validated as loopback before a socket exists"

git add docs/pm/brief-14-the-endpoint-cannot-leave-loopback.md
git commit -m "docs: brief 14 result -- the endpoint policy has tests now"
```

**Do not run a bare `git push`** — two remotes. Name it:
`git push origin <your branch>`.

## The one thing that would make this wrong

**A test that passes because the connection failed.** `http://evil.example/v1`
is unreachable from here anyway, so a rejection test can be green with no
validator. Ma is how you find out.

The second way: **validating at request time instead of configuration time.**
The contract's claim is that no request *can* route off loopback, not that the
paths we remembered to guard do not.
