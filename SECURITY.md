# Security policy

## Supported versions

| Version | Supported |
| --- | --- |
| 0.1.0 (pre-release, `pyproject.toml`) | the current integration line only |

There are no earlier releases. OmniAgent is pre-release software for one user on one machine.

## Reporting a vulnerability

**Please do not open a public issue.** Use GitHub's private vulnerability reporting:

1. Open the repository's **Security** tab.
2. Choose **Report a vulnerability**.
3. Describe the problem as below and submit.

This works once a maintainer has switched on private vulnerability reporting for the repository. If you do not see the
button, open a public issue that says only "I need a private way to report a security problem", with no details, and a
maintainer will reply there.

## What a report should contain

- what you found and which file or tool it affects;
- the steps to reproduce it, ideally a short script or a failing test, with the exact commit and your operating system;
- who could trigger it and what they would need first (the model, a file in the workspace, a local user);
- what you think the impact is. Please say so plainly when you are unsure.

Do not include real credentials or personal data in a report.

## In scope

The guarantees in the [approved contract](docs/architecture/security/agentic-mvp-contract-2026-11-03.md) and the
[threat model](docs/architecture/security/threat-model-2026-11-02-the-search-boundary.md):

- **the filesystem sandbox** (`sandbox.py`): a model-chosen path that reaches a file outside the workspace, a hidden file,
  a credential-named file, a hard-linked file, or a sealed path, including through `..`, absolute paths, drive letters, UNC,
  symlinks and junctions;
- **the tool allowlist**: the model running a tool that is not allowed for the task;
- **the endpoint policy**: model traffic leaving loopback (only loopback IP literals are accepted; hostnames, including
  `localhost`, are refused);
- **logging and errors**: file contents, prompts, secrets or the endpoint URL appearing in a log line, error message or
  exported dataset.

## Out of scope

- The sandbox is a leash on model-selected reads, **not process isolation or protection against another process on the same
  machine** ([`docs/architecture/security-and-ethics.md`](docs/architecture/security-and-ethics.md)).
- Prompt-injection immunity and model correctness are not claimed; the contract says passing its gates does not prove them.
- The licences and provenance of third-party models and data, and vulnerabilities in dependencies that are not exploitable
  through OmniAgent.
- Findings that need write access to the maintainer's machine or to the workspace the user already chose to expose.

## What to expect

One maintainer looks after this project in their own time, so the response goal is **best effort**: an acknowledgement when
the report is seen, then a fix or a reasoned answer as time allows. No service level is promised.
