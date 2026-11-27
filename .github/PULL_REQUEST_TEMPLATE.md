## Summary

What this changes and why, in a few lines. One logical change per pull request.

## Checks

Run from your own checkout, with your own virtualenv (see [CONTRIBUTING.md](../CONTRIBUTING.md)):

- [ ] `python -m ruff check .`
- [ ] `python -m mypy`
- [ ] `python -m pytest`
- [ ] `python -c "import agent; print(agent.__file__)"` prints a path inside my checkout

## A test that can fail

- [ ] Every test I added or changed goes red when the code it guards is removed. Say which test and what you removed:

## Data and secrets

- [ ] No secrets, tokens, `.env` files, model outputs, datasets, run logs, or evaluation answer material are included.

## Security impact

Does this touch the sandbox, the tool allowlist, the endpoint policy, logging, or error messages? Write "none", or say what
changes and which test pins it:

## Not tested

What you did not check:
