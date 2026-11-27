# Contributing to OmniAgent

OmniAgent is a local-only, read-only ReAct agent in Python. Thank you for looking at it. This page says how to set up,
what a good change looks like, and where things live. The rules the maintainers hold every change to are in
[`AGENTS.md`](AGENTS.md); this page links to them and does not repeat them.

## Set up

You need Python 3.12 or newer (`requires-python` in [`pyproject.toml`](pyproject.toml)). From a clone:

```bash
python -m venv .venv
.venv\Scripts\activate          # macOS/Linux: source .venv/bin/activate
pip install -e ".[dev]"
```

The README's [Setup](README.md#setup) section covers installing Ollama and a model. **The test suite needs no model server**: a scripted
fake client stands in for it.

## Run the three gates

All three must be green before you propose a change, run from your own checkout with your own virtualenv:

```bash
python -m ruff check .
python -m mypy
python -m pytest
python -c "import agent; print(agent.__file__)"   # must print a path inside your checkout
```

`pyproject.toml` already sets `-q` for pytest; do not add another. The last line matters when you keep several checkouts
or worktrees: an editable install points at one tree, and a green run against the wrong tree proves nothing.

## What a good change looks like

- **One logical change.** A fix and an unrelated tidy-up are two changes.
- **A test that can fail.** A new test must go red when the code it guards is removed. For a security guard (the sandbox,
  the tool allowlist, the endpoint policy), remove the guard on a copy, confirm the specific test fails for the right
  reason, then restore it. A test that two independent guards would both satisfy proves neither.
- **No new outbound call, cloud provider, telemetry or dependency** without prior discussion: the agent talks to a model on
  loopback only and its tools are read-only.
- **Say what you did not test.** A short note in the pull request is enough.

## Data and sealed material

Do not add model outputs, datasets, run logs, secrets, tokens, `.env` files, or evaluation answer material (answer keys,
held-out question banks). The repository is public. Search such material by counting matches, never by pasting them.

## Commits

[Conventional Commits](https://www.conventionalcommits.org/), in English, saying what changed and why
(`fix: refuse a nested config instead of raising`). Use your own git identity; do not set a placeholder.

## Branches and pull requests

Branch from the integration line, `integration/canonical-20261122`, and open a pull request against it. The project's
public home is [`mntoyg/OmniAgent`](https://github.com/mntoyg/OmniAgent), whose default branch is
`integration/canonical-20261122`; `OmniBase-Official/OmniAgent` is a mirror. The hosted CI workflow
([`.github/workflows/ci.yml`](.github/workflows/ci.yml)) runs for both `main` and the integration branch. Run the gates
yourself first all the same.

## Where things are

- [`docs/architecture/README.md`](docs/architecture/README.md): the architecture documents and their status.
- [`docs/architecture/security/`](docs/architecture/security/): the approved contract and the threat model.
- [`docs/architecture/repository-map.md`](docs/architecture/repository-map.md): what each path is for.

To report a vulnerability, follow [`SECURITY.md`](SECURITY.md), not a public issue. Participation is governed by
[`CODE_OF_CONDUCT.md`](CODE_OF_CONDUCT.md).
