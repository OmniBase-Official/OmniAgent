# Brief 26 (SAE): read the uncommitted content of the 18 dirty worktrees, from snapshots

Issued 2026-11-22 by the PM on the owner's ruling "3A: the SAE reads the 18, then they are removed".

## Why this is read-only and why it reads snapshots, not trees

The PM already froze every dirty tree as a local commit: 21 refs `refs/snapshots/20261122/*`
(manifest: `D:\code-project\OmniAgent\.scratch\snapshots-manifest-2026-11-22.md`, with restore
steps). They live in the shared object store, so any worktree can read them. **Read the refs, not
the live trees**: the trees are Codex's, one may still be written, and opening them proves nothing
the snapshot does not. Refs ending `-index` hold the staged state of the same tree.
`.scratch\se-ci` has **no** snapshot (SE 02 was writing); if that tree still exists, list it and stop.

## Both remotes are public

`gh repo view` (MEASURED 2026-11-22): `mntoyg/OmniAgent` and `OmniBase-Official/OmniAgent` are both
PUBLIC. Anything pushed is public and may be cached. So **you push nothing**; the PM pushes a
salvage branch only after screening it.

## What to produce, per snapshot ref (21 refs, 17 trees)

Use `git diff --name-status <parent> <ref>` and `--stat` (the parent is in the manifest), then read
only what you need to classify. Report one row per tree with:

1. **Verdict**, one of:
   - `DISPOSABLE`: the content is already on a remote branch or is generated (prove it: the
     `git diff` between the snapshot and that remote branch is empty or only build output);
   - `REAL WORK`: unique content a person would miss (say what it is, how many lines, which
     branch of work it belongs to, and whether a pushed branch already covers it);
   - `SEALED OR SECRET`: any path under `docs/`, `models/`, `questions/`, `data/`, `NEXT_CHAT.md`,
     the evaluation scripts, or any `.env`, key or credential (the `ANSWER_KEY` list in the
     project). **Report the path only; never print or quote the content.**
2. **Evidence**: the command and its output (MEASURED), not a guess from a folder name.
3. **For `REAL WORK`**: the branch name you propose (`salvage/<name>-20261122`) and whether it is
   safe to publish.

Also say, for the **-index** twins, whether the staged state adds anything the worktree state lacks.

## Deliverable

A table in a document on a branch of yours (from `origin/integration/canonical-20261122`), pushed to
`origin` with the remote named, and **one message to the PM** with the owner's open decisions as
lettered options, each ending by naming the chair that would carry it out. Nothing is created,
pushed to a `salvage/*` ref, or removed by you.

## Out of scope (do not do)

Removing or moving any worktree (the PM does, after the owner's word); touching the 27 Codex-app
trees' locations; a push to either `main`; a force-push; reading `.env`.

## Budget

Rule 2 applies. The owner raised today's ceiling to 40% in their own session; if you need that
confirmed in yours, say so and stop rather than rely on this message.

## The one thing that would make this wrong

**Calling a tree `DISPOSABLE` because its name looks like scratch, or its file count is small.**
Two trees have already surprised this project (a 1,069-line `secure_search.py` was parked in one).
`DISPOSABLE` needs a diff that proves it, and an unproven tree is `REAL WORK` until shown otherwise.

## Done when

All 17 trees classified with evidence; the 4 `-index` twins compared; `se-ci` accounted for; the
branch pushed and named; the message sent.

## PM verification, 2026-11-22 (MEASURED, re-run by the PM from the snapshot refs)

SAE report: `origin/sae/snapshot-classification-20261122`. Re-run, nothing pushed or removed.

| Claim | Result |
| --- | --- |
| 3 DISPOSABLE by empty diff | **Confirmed.** `main-checkout` vs `origin/snapshot/codex-local-ai-delegate-20261122`: 0 files; `-index` vs the `-index` branch: 0; `windows-private-root-fix` worktree snapshot vs its parent `870e8fb`: 0 |
| The `-index` twin of `windows-private-root-fix` holds two files the worktree snapshot lacks | **Confirmed.** `M scripts/prepare_windows_private_test_root.ps1`, `M tests/test_windows_publish_acl.py` (2 files differ from the worktree snapshot). Worth keeping: the staged state was the only copy |
| Three brief 16 variants are not copies | **Confirmed.** 37 / 23 / 33 files differ from the pushed Codex snapshots |
| `AGENTS.md` is the only content of the weekly-usage-budget snapshot | **Confirmed** |
| `.scratch\se-ci` no longer exists | **Confirmed** (not on disk). What it held is unknowable from here |
| `search-text-race-safety` snapshot (`13c7bfb`): 428 paths, 5 outside `.scratch/` | **Confirmed**: 428 / 5 |
| "423 are pytest basetemps, hundreds end in workspace/credentials" | **Corrected.** 346 paths are `.pytest-output-base`; **77 are a nested worktree's real files** (`.scratch/publisher-acl-fix-20261115/`: tests 34, scripts 13, docs 5, workflows, source). Only **46** paths contain "credential" (case-insensitive), not hundreds. So "only five are real" is wrong: 5 + 77 are real work, and the nested tree may or may not be covered by a pushed branch (not checked) |
| The credential-shaped content is synthetic | **Partly confirmed, still UNVERIFIED for 3 tokens.** Content patterns (AWS, GitHub, OpenAI-style, Slack keys, PEM header) match in only 3 test files (`test_publish_dataset.py`, `test_sandbox.py`, `test_validate_dataset.py`), all inside a secret-scanner's own tests (labels such as "OpenAI-style key", "AWS access key"). Of the 5 distinct tokens: the AWS one contains `EXAMPLE`; the GitHub one's body is a plain a-z0-9 run; the two `sk-` and the Slack token are not provably dummy from their form. Six matching lines are **not** already in G's or O's public history (3 in `test_publish_dataset.py`, 3 in `test_validate_dataset.py`) |

**Rule for the salvage:** that ref is **never pushed wholesale**. It stays a local ref (nothing pushes it);
salvage by path only. Deleting it unread would lose the 77 real files of the nested tree.
Not verified: whether any salvage branch merges onto the canonical line (several parents are O-line or older).

## Salvage executed, 2026-11-22 (owner: "salvage by path"; decision 2, option B)

PM built `origin/wip/salvage-search-text-race-safety-20261122` = `7aa7af9`, one commit on the snapshot's own
parent `2390568` (already on `organization`), by plumbing (temporary index, no tree touched). It carries only
the five real files of snapshot `13c7bfb`: `README.md`, `sandbox.py`, `tools.py`,
`tests/test_context_budget.py`, `tests/test_file_tools.py` (+339/-8 against the parent). Screened first: 0
secret or personal-data pattern in the added lines. MEASURED after the push: `git ls-remote` returns `7aa7af9`;
the pushed tree has no path under `.scratch/`; exactly one commit beyond the parent.
Named `wip/` so the hook's clean-tree gates are skipped by design: **the branch is unreviewed and ungated.**
The snapshot ref itself stays a **local-only** ref (not pushed). Still open: whether the 77 real files of the
nested `publisher-acl-fix-20261115` tree are covered by a pushed branch; the branch does not merge onto the
canonical line (O-line parent) until its owning chair rebases it.

## The 77 nested-tree files, checked 2026-11-22 (owner: "PM checks"; MEASURED)

Snapshot `13c7bfb`, nested tree `.scratch/publisher-acl-fix-20261115/`, excluding `.pytest-output-base`:
76 files have a blob (the diff counted 77 paths; the odd one is not a blob, not investigated).
Method: every file's blob hash at its path, compared with every remote ref (60 refs; `origin` and
`organization` mirror each other for these).

- **73 of 76 are byte-identical, at the same path, on `codex/scale-security-hardening-20261113`**
  (tip `3576aeb`, 2026-11-15, the same SHA on both remotes). The nested tree is that branch's work: covered.
- **3 are on no remote ref at all** (no identical blob at any path on any ref):
  - `securefs.py`: differs from the branch's version by **+227 / -3** lines (an unpublished revision of
    the ctypes module that is the owner's open decision 3);
  - `scripts/validate_windows_publish_acl.ps1` (8,275 bytes): absent on that branch;
  - `tests/test_windows_publish_acl.py` (3,443 bytes): absent on that branch (a different file of the same name
    is in the `windows-private-root-fix` `-index` twin).
- The three belong to the `securefs` / publisher-ACL line, which the owner has **not ruled on**. They are
  preserved only in the local snapshot ref `13c7bfb`, **not pushed**. That ref therefore must not be
  deleted until the owner rules, or until these three are salvaged by path.

## PM re-check of the SAE's challenge to the securefs findings, 2026-11-23 (MEASURED, owner: "Verify now")

The SAE (`b13d087`) said the three files are absent from `13c7bfb`, that `securefs.py` is byte-identical to a public branch, and that all
three are public on both remotes. Re-run by the PM from the refs (68 remote refs, both remotes fetched):

| Claim | Result |
| --- | --- |
| The three paths are absent from `13c7bfb` | **True at the top level** (`git cat-file -e` fails for all three). **But** `13c7bfb` holds them under the nested tree `.scratch/publisher-acl-fix-20261115/` (all three present), which is what brief 26 and ruling 13 meant. The SAE checked only the top-level paths |
| They live in three other snapshots | **Confirmed**: `security-validation-r37` (`900d8b6`), `windows-private-root-fix-index` (`033b308`), `windows-sid-validation` (`f44cbf3`) |
| `securefs.py` in those three is byte-identical to the public branch | **Confirmed**: blob `b28ed99b4e`, 1,319 lines, same as `codex/windows-private-root-validation-20261121`, `security-runner-fixtures-20261120`, `security-scans-validation-20261120` on **both** remotes |
| The +227/-3 figure is wrong | **Not wrong, but against a different base.** The nested copy (blob `de39fe0668`, 1,178 lines) vs `codex/scale-security-hardening-20261113` (954 lines) is **+227/-3, reproduced exactly**. Against the newest public `securefs.py` (1,319 lines) it is +125/-266: an older or different revision |
| Nothing is only local | **Not true.** The nested `securefs.py` blob is on **no** remote ref at that path (all 68 checked). Also on no remote at the same path: the nested `.ps1` (8,275 bytes) and test (3,443 bytes); the `.ps1` of `security-validation-r37` (`c9f4bf12`); the test of `security-validation-r37` (`4ba9d366`) and of `windows-private-root-fix-index` (`586f9662`). The public `.ps1` and test files are **larger** (54,527 and 22,250 bytes on `windows-private-root-validation`), so the unpublished ones may be superseded earlier revisions: **UNVERIFIED** (no history walk) |

**Net:** the earlier PM finding stands for the nested copies (unpublished, not hidden-valuable); the SAE is right that the current 1,319-line
`securefs.py` is already public on both remotes and that the memo's question is whether it comes onto the canonical line. The SAE's
"everything is already public" overstates by a handful of older revisions. Consequence: none of those four snapshot refs (`13c7bfb`, `900d8b6`,
`033b308`, `f44cbf3`) is deleted until the owner rules; the memo's recommendation (park) is unaffected.
