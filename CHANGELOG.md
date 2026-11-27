# Changelog

All notable changes are recorded here. The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).
This project has not published a versioned release; `0.1.0` below is the version in `pyproject.toml`, summarised from the
history of the integration line.

## [Unreleased]

Nothing yet.

## [0.1.0]

### Added
- A local-only ReAct agent that talks to a model on the user's machine, with structured logging and a pytest suite.
- A typed tool layer: tool arguments are validated before a tool runs.
- Read-only file tools behind a filesystem sandbox.
- Resilience in the loop: retry with backoff, detection of a model repeating a failing action, clean interruption.
- One settings layer with documented, tested precedence, and a CI workflow.
- A configuration-inspection tool, `inspect_config_precedence`, recorded as the seventh approved tool.
- Export of run logs as a chat-format dataset, publishing with proof of what arrived, and a promotion gate that refuses a run
  the evaluations have not passed.
- A LoRA fine-tuning notebook and its generator.
- Sealed evaluation workspaces: a directory can be listable without being readable, and the agent cannot read its own
  transcripts.
- The MIT licence file.

### Changed
- The default model endpoint is the loopback IP literal `127.0.0.1`, and the printed endpoint no longer appears in messages
  or logs.
- `read_file` refuses a file it cannot return in full, and the too-long error ends with the exact next call.
- One tool observation can take only a bounded share of the prompt.

### Fixed
- An empty answer now exits non-zero instead of printing a blank success.
- The preflight prints the HTTP status, not the model server's error body.

### Security
- Hard-linked files can no longer be used to escape the workspace.
- Per-guard tests pin each tool-allowlist guard, and a 31-form corpus pins the endpoint policy.
- Provenance readers and dataset exports have read limits, and deeply nested configuration, question banks and run manifests
  are refused with a message instead of a traceback.
