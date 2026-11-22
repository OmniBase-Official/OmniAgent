# Security scanning

OmniAgent is a Python 3.12 project. `.gitignore` reduces accidental Git staging of local secret and model-cache files; it does not stop an agent or process from reading those files. Keep credentials outside the workspace and use the operating-system sandbox and repository workspace boundary.

No `.env.example` is required for the local default: the agent uses the loopback Ollama endpoint and a local model name by default. If configuration requirements change, add only dummy values and keep the example subject to Gitleaks scanning.

## Local checks

Install the pinned hooks and run them on the staged files:

```console
python -m pip install pre-commit
pre-commit validate-config
pre-commit run --all-files
```

The hook configuration pins Gitleaks and Semgrep versions. Semgrep also loads the Python `p/security-audit` and `p/secrets` rulesets. Its project rules have positive and negative fixtures under `tests/security/semgrep`; CI runs those separately with `semgrep --test` and excludes them from the ordinary repository scan.

## Dependency audit scope

CI creates a fresh environment, installs the project runtime and `dev` extra, then runs `pip-audit --local`. This covers runtime and development dependencies in that environment. The optional `training` extra is deliberately not installed in CI because it includes large ML packages; it is not covered by this gate. To audit it, install `.[training]` into a separate environment and run `pip-audit --local` there.

The security workflow uses read-only repository permissions, no secrets, and a full-history checkout for Gitleaks. A detected historical secret must be revoked/rotated; adding an ignore rule does not make it safe.
