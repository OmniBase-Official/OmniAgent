---
name: extract-pure-parser
description: Move a pure text parser into a focused module while preserving callers and behavior.
---

# Extract a pure parser

Use when a large orchestration module contains a deterministic parser with no I/O or mutable external state.

## Workflow

1. Map parser definitions, imports, callers, public names, fixtures, and tests before editing.
2. Move only the parser data model, patterns, and pure parsing helpers into the new module.
3. Move shared parser/dispatcher values into a small dependency-neutral module instead of importing the tool registry.
4. Preserve compatibility imports in the original module and add identity checks for re-exported objects.
5. Compare the moved AST against the original implementation where possible; do not redesign parsing behavior during extraction.
6. Cover malformed, empty, multiline, competing-marker, inline-call, quoted, code-fenced, Unicode, and oversized input.
7. Run the full test suite, linter, configured type checker, syntax checks, and diff whitespace check.
8. Review the exact final snapshot independently before any commit or push.

Keep transport, prompts, orchestration, tool dispatch, and logging outside the parser module.
