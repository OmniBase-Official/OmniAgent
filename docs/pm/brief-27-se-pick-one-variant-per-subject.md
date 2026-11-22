# Brief 27 (SE): pick one variant per subject among the duplicate snapshot attempts

Issued 2026-11-22 by the PM on the owner's ruling "A: owners pick" (brief 26, decision 3): the chair that
owns each subject picks one variant; the others are then deleted. The deleting is the PM's, on the owner's word.

## The subjects and their variants (local refs `refs/snapshots/20261122/*`, parents in the manifest
`D:\code-project\OmniAgent\.scratch\snapshots-manifest-2026-11-22.md`)

1. **Brief 16 (privacy / logging / telemetry), three attempts at one subject**
   - `scratch_brief16-proposed-tree-20261109` (`1978f52`) and its `-index` twin (`3350a5b`)
   - `_24_01a16bed-071f-73b3-b1ad-dd4fb343315f_brief16-operational-telemetry` (`8e72843`)
   - Measured by the PM: they differ from the pushed Codex snapshot by 37 / 23 / 33 files, so they are not copies.
   - **Context that changes the question:** brief 16 itself is already verified on the O line (`af99092`) and its
     three defaults plus the URL-out-of-messages fix were carried onto the canonical line by brief 21. So the
     question is not "which attempt is the brief" but **"does any variant hold something the canonical line
     lacks, and if so, which one"**.
2. **dataset-bounds, two attempts**: `scratch_pre-user-dataset-bounds-20261119` (`ba3598f`, 12 files) and
   `codex_worktrees_dataset-input-bounds-20261116_OmniAgent` (`38ea900`, 6 files).
3. **sec-search-001, two attempts**: `scratch_sec-search-001-remediation-20261112` (`381520d`, 2 files) and
   `ees_search-text-race-safety_OmniAgent_.scratch_sec-search-001-20261112` (`3675a88`, 3 files).
   **Chair not named by the owner** (`secure_search.py` is parked): do subjects 1 and 2 first; for 3 only
   state the facts, do not pick, until the owner names who owns it.

## What to produce (read-only; read the refs, not the live trees)

For each subject: a table of the variants against **the canonical line** (`origin/integration/canonical-20261122`,
`388fa53`): what each variant adds that the canonical line lacks, what it merely duplicates, and what it would
break (name a test or a gate). Then **one pick, or "none, the canonical line already has it"**, with the
command and output that supports it (MEASURED), and for the pick whether it merges onto the canonical line
or needs a rebase (several parents are O-line or older; do not cut from the integration branch and paste).
Two variants that touch different files may both be right: say so instead of forcing one.

## Rules

- Both remotes are **public**: push nothing except your own document branch (cut from
  `origin/integration/canonical-20261122`, remote named). The PM screens and pushes any salvage.
- Do not remove, move or restore anything; do not delete a ref (the PM does).
- `securefs.py` and the ACL files are not in scope (owner ruling 13: kept local).
- Verification is yours: a variant is "the good one" only on a run you did; the original author's name is not evidence.
- Rule 2 applies: re-read the meter at start. The owner's ceiling today is 40% weekly; if you need it confirmed
  in your own session, say so and stop.

## Done when

Subjects 1 and 2 each have a pick (or "none") with evidence, subject 3 has the facts and no pick, your branch
is pushed and named, and one message to the PM lists the owner's open decisions as lettered options, each
ending by naming the chair that carries it out, plus your QA and Budget lines.

## The one thing that would make this wrong

**Picking the variant with the most files, or the latest date.** The brief 16 trio is the trap: the fix may
already be on the canonical line, in which case the right answer is "none" and the variants are history.
