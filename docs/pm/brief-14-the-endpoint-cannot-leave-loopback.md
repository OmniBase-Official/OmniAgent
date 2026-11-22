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

**Done, 2026-11-05, by the security engineer.** Branch
`se/brief14-endpoint-loopback-20261105`, cut from `main` at `320d411` as the
brief names. Code and tests: `a5e9e51`. This Result: the commit after it.

## Where the validator went, and why

`validate_loopback_url()` is in `agent.py`, beside `DEFAULT_BASE_URL`, and it
is applied by a pydantic field validator in **both** configuration models:
`AgentConfig` and `config.Settings`.

`agent.py` holds the function because `agent.py` owns the endpoint constant and
`config.py` already imports from it; the other direction would be a new import
edge. `config.Settings` gets the validator as well, and that is the part worth
arguing for: `Settings` is the layer the TOML, the environment and the command
line land in, and `AgentConfig` is only built later, in `Settings.agent_config()`.
Validating in `Settings` is what makes `resolve()` refuse a bad endpoint *while
it still knows which layer supplied it* — the error reads
`base_url (environment): ...`. Without it, `resolve()` returns a `Settings`
object holding a foreign endpoint and the refusal waits for whoever calls
`agent_config()`, which is the brief's second failure mode ("validating at
request time instead of configuration time") wearing a different hat.

The host rule is one function, `_host_refusal()`, with two callers. The second
is `LoopbackOnlyTransport`, below.

## Accepted and rejected

**Accepted** (9 forms, each constructs `AgentConfig`, `Settings`, and passes the
function directly): the shipped default, `http://localhost:11434/v1`,
`http://127.0.0.1:11434/v1`, `http://[::1]:11434/v1`, `http://localhost:1/v1`,
`http://localhost/v1` (no port), `http://localhost:11434/` (root path),
`http://127.0.0.2:11434/v1`, `http://LOCALHOST:11434/v1`.

Two of those are decisions: **`127.0.0.0/8` is accepted in full**, because it is
loopback in full and `127.0.0.2` reaches this machine and nothing else; and
**case does not matter**, because `urlsplit` lower-cases the host, so there is no
way in or out through capitalisation.

**Rejected** (23 forms): a foreign host; `127.0.0.1.example.com`;
`localhost.attacker.test`; `localhost.` (trailing dot); `0.0.0.0`; `[::]`;
`[::ffff:127.0.0.1]`; a bare hostname (`ollama`); `2130706433`; `0x7f000001`;
`127.1`; `file://`; `ftp://`; `https://localhost`; user information;
`http://localhost:11434@evil.example/v1`; a query; a fragment; a non-numeric
port; a malformed IPv6 host; no host; `not a url at all`; the empty string.

### The two the brief asked me to decide deliberately

**`0.0.0.0` (and `::`) — rejected.** They are bind addresses: they mean "every
interface this machine has", which is what a server listens on, not what a
client connects to. Where they connect at all, the destination is chosen by the
operating system rather than by this configuration, and "the endpoint is
whatever the OS decides" is not a loopback guarantee. Python agrees enough to
make this cheap: `is_loopback` is `False` and `is_unspecified` is `True`, so
they get their own message rather than the generic one.

**`::ffff:127.0.0.1` — rejected, and this one needed the explicit check.**
Measured: `ipaddress.ip_address("::ffff:127.0.0.1").is_loopback` is **`True`**
in Python 3.12, and `.ipv4_mapped` is `127.0.0.1`. So a rule written as "accept
anything `is_loopback`" would have **accepted** it, and I would not have noticed
without running it. It is refused because the contract names two literals, and
every additional spelling of one destination is another near-miss for a reader,
or for a later string comparison, to get wrong. It would have reached the same
server, so the cost is real but small: a user who writes it is told to write
`127.0.0.1`. The check for the mapped form has to come **before** the
`is_loopback` check, which is the only subtle line in the function.

### One decision the brief did not list

**`https://localhost:11434/v1` — rejected.** An allowlist has to answer every
scheme, and this one is not in the brief's accept or reject list. Nothing issues
a certificate that validates for `localhost`, so `https` here would mean either
a self-signed chain or verification turned off — a new trust surface for a hop
that never leaves the machine. If the owner ever wants TLS on loopback, this is
one constant.

## How I proved no socket was opened

An autouse fixture in `tests/test_endpoint_policy.py` makes any connection
attempt an immediate failure, patching three layers: `socket.socket.connect`,
`socket.socket.connect_ex`, `socket.create_connection`, and
`httpx.HTTPTransport.handle_request`.

**I checked the guard itself rather than trusting it.** A shim that patches the
wrong layer would let a rejection test pass on the network anyway, which is the
whole trap. In a scratchpad script with the same four patches applied, all three
of these were caught: a real `httpx` request through the real transport,
`socket.create_connection`, and `socket.socket().connect`. The guard is at the
right level.

Every rejection test asserts at **configuration** time — `AgentConfig(...)`,
`Settings(...)`, `resolve(...)` — so no client exists to connect with, and the
agent-level test (`test_building_an_agent_with_a_rejected_endpoint_never_reaches_a_client`)
shows `ReActAgent` cannot be reached with a bad endpoint because the config
object cannot be built.

## Proxy evidence — and a correction to mutation Mc

Requirement 3 holds, but **not for the reason the brief's mutation assumes**, and
the difference is measured.

`httpx` reads `HTTP_PROXY`/`HTTPS_PROXY`/`ALL_PROXY` **only when it builds its
own transport**: `allow_env_proxies = trust_env and transport is None`
(`httpx/_client.py:685`). The production client always passes an explicit
transport — `LoopbackOnlyTransport` — so the environment's proxies can never
mount in front of it.

Measured, with all three variables set to `http://proxy.invalid:8080`:

| client | proxy mounts | transport chosen for the endpoint |
| --- | --- | --- |
| `build_local_http_client()` as shipped | 0 | `LoopbackOnlyTransport` |
| same, `trust_env=True` (**Mc**) | 0 | `LoopbackOnlyTransport` |
| same, explicit transport dropped (**Mc-prime**) | 3 | a proxy-mounted `HTTPTransport` |
| plain `httpx.Client(trust_env=True)`, no transport | 3 | a proxy-mounted `HTTPTransport` |

So **Mc as written changes no routing**, and the only assertion that catches it
is the flag assertion (`client.trust_env is False`). The mutation that catches
the real guard is **Mc-prime**, dropping the explicit transport, and it goes red
on the routing assertions and on two more tests besides. Both are in the Result
rather than one, because a mutation that goes red on a flag while the behaviour
is unchanged is exactly the kind of green that proves nothing.

`trust_env=False` stays, as the second and independent guard: it keeps `.netrc`
and the SSL environment out as well, and it is what would still refuse a proxy
if that function ever stopped passing a transport. The docstring says which of
the two is load-bearing, because my first draft of it said the wrong one.

## Redirect evidence

Two proofs, and the SDK made the second one necessary.

`openai`'s own `_DefaultHttpxClient` sets `follow_redirects=True`
(`openai/_base_client.py:873`), so the question is whether our `False` survives
when we pass our own client. It does: a per-request override happens only if
`options.follow_redirects` is set, which this code never sets.

- At the httpx level: a `MockTransport` answering 307 with
  `Location: http://evil.example/v1/models`. The response comes back as a 307
  and the handler saw exactly **one** request, to the loopback host.
- Through the client the agent actually builds (`build_openai_client`, the same
  function `ReActAgent.__init__` calls, with only the innermost transport
  swapped): `models.list()` raises `APIStatusError` with code 307 and the
  handler again saw exactly one request, to the configured host. Two entries
  would mean the redirect was followed; an `evil.example` entry would mean it
  was followed off host.

`LoopbackOnlyTransport` is the belt to that braces, and the reason it exists: a
redirect hop is a URL the configuration never saw, so the host rule runs again
on **every** request, first hop or later, before the inner transport is called.
A direct unit test (`test_the_transport_refuses_a_foreign_host_before_the_socket`)
shows it refusing `http://evil.example/v1/models` with no socket.

## The endpoint is no longer printed

Both sites (`agent.py:493` and `:869` as the brief numbered them) now say
`the configured local endpoint`, from one constant, `ENDPOINT_DESCRIPTION`, so
the two cannot drift apart.

**The port is gone too**, which the brief left to me. The user configured it, so
it tells them nothing they do not know, and it is the part of the string that
identifies one machine's setup in a log — the same reason the host is going.

## Mutations

Restored from scratchpad copies, never `git checkout --`.

`agent.py` before any mutation and after every restore:
`42dcbca39b55bcbd12604078dd4f22f9f7f10cc98538ae6f45ecad6f29311d54`.
`config.py`, likewise:
`c317b343fddd037030d8ca81fc24ef3887c97ac2f64005ff78994b948720908c`.
Both verified identical after each of the five runs. The committed `agent.py`
differs from that hash by one docstring, corrected after Mc (above):
`07f254e3fcd2c97d7f2b844a4f1d1e6eb57b8a3ccf16d95d1b4c8c11a8155856`.

| # | Mutation | Result |
| --- | --- | --- |
| **Ma** | the validator returns its input unchanged — the state of `agent.py:255` before this brief | **73 of 90 red.** Every rejection test, in all three layers |
| **Mb** | `if _LOOPBACK_NAME in host` | **6 red**, and exactly the right six: `localhost.attacker.test` and `localhost.`, in each of the three layers |
| **Mc** | `trust_env=True` | **1 red**, the proxy test — on its flag assertion only. See the correction above |
| **Mc-prime** | the explicit transport dropped | **4 red**: the proxy test (on routing), both redirect tests, and the wiring test |
| **Md** | `base_url` back into the connection-check message | **1 red**, the connection-check message test, printing the leak: `Cannot reach a local model server at http://127.0.0.1:65500/v1` |

### Ma, which is the one that matters

**No rejection test survived Ma.** The 17 that stayed green under it are the 17
that are not rejection tests: the 9 accepted forms, the shipped default, the
proxy test, the transport unit test, the two redirect tests, the wiring test,
and the two message tests. **Not one rejection was passing on a connection
failure.** The list of survivors is in the run output and each one is accounted
for above.

Two of those survivors deserve naming, because they are a second guard and the
role's warning about independent guards applies: `LoopbackOnlyTransport` refuses
a foreign host whether or not the config validator exists, so its own test stays
green under Ma. That is deliberate — the two guards sit at different times
(configuration, and immediately before the socket) and each has its own test and
its own mutation.

## Gates

Run in the worktree with the full venv path and no second `-q`:

```
ruff check .   All checks passed!
mypy           Success: no issues found in 46 source files
pytest         748 passed in 9.19s
```

Baseline was **658 passed** over **45** files. The count moved to **748**: `+90`,
all of them in the one new module `tests/test_endpoint_policy.py` (the rejection
and acceptance tables are parametrised three ways each, which is most of it).
Files moved **45 → 46**: the new test module. **No existing test changed and
none broke.**

**Also run on `main`, not only in the worktree** — the lesson from brief 17. A
third worktree at `main` (`c72938e`), with this branch merged into it
(`0bb8440`), in a directory with no `.venv` of its own: ruff clean, mypy clean
over 46 files, **748 passed**. The merge was clean. Nothing in these tests reads
a path, so the brief-17 failure mode (repository root as a boundary, with
`.venv` inside the repository) cannot apply here, and now that is measured
rather than argued.

## What I did not touch

- **The three defaults stay wrong on purpose**: `agent.py:36` `qwen2.5:7b`
  against `omniagent.toml:4` `qwen2.5-coder:7b`; the client's `max_retries=0`
  against the agent's own default of `2`; `verbose=True`. Each has its own
  brief. **No test of mine proves any of the three wrong** — my tests set
  `max_retries` and `verbose` explicitly to keep the fixtures small, which is
  not evidence about the defaults.
- **`tests/test_local_only.py`**: the brief allowed touching it "if it already
  asserts something about the endpoint". **It does not** — it is about the
  training notebook's framing, and `base_url`, `localhost`, `endpoint`, `11434`,
  `socket` and `proxy` do not appear in it. Left alone.
- Tool descriptions and the system prompt.

## What I refuse to claim, and three leaks this brief does not close

1. **Gate 1's logging half is not met by these two sites.** `base_url` still
   reaches the logging layer verbatim in three `obs.event` payloads in
   `agent.py`: the `config=self.config.model_dump()` field of `agent.created`,
   and the `base_url=` field of `agent.connection.unreachable` and
   `agent.llm.unreachable`. `observability.py:57-65` redacts by name and
   `base_url` is not in `_SENSITIVE_HINTS`, so nothing masks it. The persistent
   log file and the log console are off by default, so **by default nothing is
   written** — but any enabled trace carries the full endpoint, which is what
   the contract forbids. Those three call sites are not the two message sites
   the brief gave me, and the fix touches the redaction policy and therefore the
   dataset exporter, so **I left them and am reporting them instead of widening
   this diff.** They need a brief.
2. **`main.py:170` prints the full endpoint** on every run
   (`endpoint : http://localhost:11434/v1`). `main.py` is not in my "may touch"
   list. Reported, not changed. Whether a startup banner on the user's own
   console counts as "logging the endpoint" is the owner's call, but it is
   inconsistent with the two sites I just classified.
3. **Pydantic's envelope repeats the input.** My message never does — a URL
   carrying `http://user:pw@localhost` is refused with "it carries user
   information" and no echo, and that is tested on `errors()[0]["msg"]`. But
   `str(ValidationError)` appends `input_value=...`, so code that catches a raw
   `ValidationError` and prints it will show the URL, credential included. The
   path a *user* reaches does not: `config.resolve` rebuilds the message from
   `msg` alone. I am not claiming the credential cannot be printed; I am
   claiming the validator does not print it.

And the three standing ones: `sandbox.py` is a leash on the model, not process
isolation; none of this is evidence about prompt injection; and a loopback
address does not prove the server on it is Ollama or trustworthy, which is the
contract's own assumption and still unverified.
