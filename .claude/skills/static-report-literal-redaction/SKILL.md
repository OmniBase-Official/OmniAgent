---
name: static-report-literal-redaction
description: Prevent static AST inspection reports from disclosing source string and bytes literals.
---

# Static report literal redaction

Use when an AST-based inspector renders source expressions or labels into user-visible reports.

## Workflow

1. Trace every value from parsed AST/source into report text, CLI output, logs, and errors.
2. Keep structural evidence useful while replacing string and bytes constants before rendering; avoid returning raw source segments.
3. Normalize labels through a finite set of safe categories and omit requested paths from success and error output. Preserve non-sensitive evidence such as rule type, source line, and finding metadata.
4. Add synthetic-only tests that place unique dummy markers in each report path and assert absence from report, stdout, and stderr while checking positive-control metadata remains.
5. Mutation-test each guard: save the source, disable one guard, confirm its targeted test fails for the expected assertion, restore the saved source, and verify its hash.
6. Run the focused tests, full suite, linter, configured type checker, and diff whitespace check.
7. Have an independent reviewer inspect the exact final snapshot and hashes.

Do not inspect, print, or store real credentials. Do not add broad scanner allowlists. A passing local test does not prove hosted CI or repository policy enforcement.
