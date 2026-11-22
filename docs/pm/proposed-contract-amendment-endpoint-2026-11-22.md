# Proposed contract amendment — the endpoint is loopback IP literals only

**Status: APPROVED by the owner on 2026-11-22 (option A) and APPLIED to
`agentic-mvp-contract-2026-11-03.md` §2 the same day, with an amendment record
there. The text below is the proposal as it was put to the owner.**

## The conflict, measured

Contract §2 ("Endpoint and model") says: *"Permit the canonical `localhost`
endpoint and explicit loopback IP literals (`127.0.0.1` or `::1`) on a configured
port."* The owner ruled on 2026-11-22 that **G (`organization/main`, `5005039`)
is the canonical line.** G's `validate_loopback_url` refuses every spelling of
`localhost`.

**MEASURED 2026-11-22 by the PM and, independently, by the SAE**, running brief
14's frozen corpus (8 accepted forms, 23 rejected forms, plus each tree's own
default) through each tree's own `validate_loopback_url` with every socket
forbidden and the module confirmed to be the worktree's:

- O (`3c76fd2`): **0 wrong answers.** Its `DEFAULT_BASE_URL` is
  `http://localhost:11434/v1`.
- G (`5005039`): **5 wrong answers, all of them accepted-form `localhost`
  spellings** (`http://localhost:11434/v1`, `http://localhost:1/v1`,
  `http://localhost/v1`, `http://localhost:11434/`, `http://LOCALHOST:11434/v1`).
  The other 26 forms are answered correctly, including all 23 rejections. Its
  `DEFAULT_BASE_URL` is `http://127.0.0.1:11434/v1`.

G's choice is **deliberate and already documented**: its `README.md` (line 324)
describes `--base-url` as an "OpenAI-compatible loopback IP endpoint" and says
hostnames are refused, and **G's README contains no `localhost` at all** (O's has
six). *(The SAE's ADR says "both READMEs still document localhost"; the PM's
count of G's README is 0, which makes the cost below smaller than the ADR states.)*

## What is proposed

Replace the first sentence of the Approved paragraph's permit clause:

> **Current:** Permit the canonical `localhost` endpoint and explicit loopback IP
> literals (`127.0.0.1` or `::1`) on a configured port.
>
> **Proposed:** Permit **loopback IP literals only** (`127.0.0.1`, any address in
> `127.0.0.0/8`, or `::1`) on a configured port. **Hostnames, including
> `localhost`, are refused.**

and replace the sentence *"The current source defaults to
`http://localhost:11434/v1`…"* with: *"The shipped default is
`http://127.0.0.1:11434/v1`."* The rest of §2 (reject non-loopback hosts,
malformed URLs, user information, query/fragment, redirects, proxy routing; do
not log the full endpoint URL) is unchanged.

## Why (the argument for it, not a proof)

A name is resolved through the hosts file and the resolver, so `localhost` can be
re-pointed; an IP literal cannot. Refusing names removes a class of "it resolved
somewhere else" without costing the single-user, single-machine MVP anything it
needs. **Whether that class matters for this MVP is itself a judgement** (the
threat model puts the actor who edits the hosts file in the weaker attacker
classes); the proposal does not claim more than that it is stricter and is what
G already does.

## What it costs

- **A contract amendment**, which only the owner can approve.
- **A user whose `omniagent.toml`, `.env` or `OMNIAGENT_BASE_URL` says
  `localhost` stops working** and gets an `EndpointPolicyError` instead. How many
  users that is, if any, is **UNKNOWN** (a private-pilot MVP with one user); the
  text of that error was **not reviewed** by the PM.
- O's README and its six `localhost` mentions are legacy and are not carried.

## What changes when the owner approves

1. The contract is amended as above (the PM does this).
2. **The corpus becomes the acceptance test.** Of brief 14's 31 forms, 3 stay
   accepted (`127.0.0.1`, `[::1]`, `127.0.0.2`) and the 5 `localhost` forms move
   to rejected: **3 accepted + default, 28 rejected.** **G's validator already
   answers all 31 as amended**, so no code changes. What is missing is the test:
   G's endpoint test file is 166 lines to O's 307 and does not contain the
   corpus. An SE brief carries it onto G.
3. Nothing in `README.md` needs to change (it already says IP literals).

## The other options, for completeness

- **B. Loosen G's validator to the contract's current wording.** Gives back a
  real, if small, piece of hardening; needs an SE change to code the owner's
  canonical line did not choose.
- **C. Accept `localhost` only when it resolves to a loopback literal.**
  Resolves at validation time, a socket-adjacent behaviour the endpoint tests
  forbid on purpose.

## What this document does not establish

- Whether any real configuration uses `localhost` today.
- The wording of G's refusal message, or whether it leaks the URL (brief 21
  covers the URL-in-messages gap separately).
- That IP-literal-only is *necessary*; only that it is stricter and already built.
