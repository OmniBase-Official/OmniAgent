# `securefs.py` — one page for the owner

**MEASURED 2026-11-22 from refs only.** Nothing was run, nothing was merged,
nothing was pushed but this document's branch. No content from any
credential-shaped path is reproduced here.

**You parked `secure_search.py` twice, on 2026-11-02 and 2026-11-04.**
`securefs.py` is the same shape under a new name. This page says what it is,
scores it against the five criteria you already approved, and gives you three
options. **It decides nothing.**

## First, a correction to the brief that commissioned this memo

The assignment said three files — `securefs.py`,
`scripts/validate_windows_publish_acl.ps1`,
`tests/test_windows_publish_acl.py` — exist **only** in the local ref
`refs/snapshots/20261122/codex_worktrees_search-text-race-safety_OmniAgent`
(`13c7bfb`), with `securefs.py` at +227/−3 over the public branch.

**All three parts of that are wrong, measured:**

| claim | measured |
| --- | --- |
| the three files are in `13c7bfb` | **absent.** `git cat-file -e 13c7bfb:<path>` fails for all three. That ref's five real files are `README.md`, `sandbox.py`, `tools.py`, `tests/test_context_budget.py`, `tests/test_file_tools.py` |
| they exist only locally | **no.** All three are on public branches — `security-runner-fixtures-20261120`, `security-scans-validation-20261120`, `windows-private-root-validation-20261121`, on **both** remotes |
| `securefs.py` is +227/−3 over the public branch | **no.** In all three snapshot refs that do hold it, it is **byte-identical** to `origin/codex/windows-private-root-validation-20261121:securefs.py` — `git diff --numstat` prints nothing |

The three snapshot refs that do hold those paths are
`codex_worktrees_security-validation-r37_OmniAgent`,
`codex_worktrees_windows-private-root-fix_OmniAgent-index` and
`codex_worktrees_windows-sid-validation_OmniAgent`.

**Why this matters to your decision:** there is no hidden local variant to
weigh. **The newest `securefs.py` is already public on four branches.** The
decision is only whether it comes onto the canonical line.

**Correction, 2026-11-23, by the PM's re-check, then re-measured by me:**
unpublished revisions do exist in the local snapshot refs, and the two points
above overstate. The ref `13c7bfb` holds all three files under the nested tree
`.scratch/publisher-acl-fix-20261115/` (my check looked only at top-level
paths); its nested `securefs.py` (1,178 lines) is **+227/−3 against the
954-line `scale-security-hardening` blob and +125/−266 against the newest
1,319-line public blob**, so the earlier "+227/−3" figure was real, just
measured against the oldest carrier. The nested `securefs.py`, the nested
`.ps1` and test, `security-validation-r37`'s `.ps1` and test,
`windows-private-root-fix-index`'s test and its `prepare_windows_private_test_root.ps1`
are on **no remote ref at the same path** (MEASURED 2026-11-23, blob ids
compared against every remote ref). They are **probably superseded earlier
revisions, which is UNVERIFIED**; reading them against the public versions would
settle it. The recommendation below does not depend on it.

## What the four branches carry

| branch (on both remotes) | `securefs.py` | `publisher_root.py` |
| --- | --- | --- |
| `codex/scale-security-hardening-20261113` | **954 lines** | absent |
| `codex/security-scans-validation-20261120` | **1,319** | **469** |
| `codex/security-runner-fixtures-20261120` | **1,319** | **469** |
| `codex/windows-private-root-validation-20261121` | **1,319** | **469** |

`securefs.py` grew 954 → 1,319 in the seven days to 2026-11-20, and
`publisher_root.py` appeared in the same window. **Neither file exists on either
`main`, nor on the canonical integration line.** 160 mentions of `ctypes` in
`securefs.py`, 55 in `publisher_root.py`.

What it does, from its own docstring: handle-relative filesystem access for
directories an attacker can write to; no symlinks, reparse points or mounts
below a pinned root; **Linux** uses `openat2` with `O_PATH` plus a procfs
identity re-check; **Windows** uses `NtCreateFile` against retained directory
handles; **"other platforms fail closed"**, and on Linux **"if procfs is
unavailable, access fails closed"**.

## The five criteria, scored

These are your criteria from
[the threat model](../pm/threat-model-2026-11-02-the-search-boundary.md), lines
105–128. They apply to this module by their own wording: *"any change to the
search boundary — `secure_search.py` **or a successor**"*, and `sandbox.py`
imports `securefs` in order to walk and admit directory entries.

| # | criterion | verdict |
| --- | --- | --- |
| 1 | **Name the attacker** | **HALF.** The docstring names it exactly: *"directories writable by an attacker"* — that is **class 4**, the concurrent local writer. The second half of the criterion, showing how that attacker exists on a single-user machine without a cheaper route to the same bytes, **is not answered anywhere I can read.** It is a document, and no document was written |
| 2 | **Show the actor can act** | **FAIL.** The agent still has no write tool. Nothing names the actor that creates or swaps a link in the normal workflow. *Not established by me either:* I did not audit all four branches for a new write capability — only for these two modules |
| 3 | **Prove it does not fail closed where we run** | **FAIL, and by design.** The module says other platforms fail closed and Linux fails closed without procfs. The criterion asks for **one measured result per supported platform** — Windows AMD64, the pinned `ubuntu-24.04` runner, WSL. **No such run exists**, and I could not produce one: the module is on no branch I may build from, and POSIX remains UNMEASURED on this machine |
| 4 | **Byte-identical output on the real tree** | **UNMEASURED.** No comparison of `search_text` output with and without it has been run by anyone, on either workspace |
| 5 | **Fit the premise, or amend it** | **FAIL unless you amend.** Criterion 5 names the figure itself: *"if a 1,200-line ctypes module is the right shape for this project, then 'hand-rolled and small' stops being true and should stop being written down."* It is 1,319 lines plus a 469-line companion. That is past the number in your own criterion |

**Score: one half-answer out of five, and two of the failures are missing
documents rather than bad code.** Nothing here says the code is wrong. It says
**nobody has done the work your ruling requires before it can be merged.**

## What I could not read, and will not guess

- **The code itself, line by line.** I read the docstring, the platform gates,
  the public surface and the sizes. 1,319 lines of `ctypes` handle work is a
  security review, not a skim, and it is the SE's.
- **Whether it is correct on Windows or Linux.** Not run. Criterion 3 cannot be
  answered by reading, and this memo does not pretend otherwise.
- **The four branches' other work.** Out of scope by the brief that created the
  earlier inventory, and still unread.

## The three options

**A. Adopt.** Bring `securefs.py` and `publisher_root.py` onto the canonical
line. *Cost:* you are adopting an unreviewed 1,788-line `ctypes` surface that
fails closed on any platform it does not explicitly support, and criterion 5
says this is the moment "hand-rolled and small" stops being true in the README
and the threat model. **Carried by: SE for the review, SAE for the premise
amendment, owner to approve both.**

**B. Reject.** Rule it out as `secure_search.py` was, and keep the branches as
reference. *Cost:* the Windows ACL and private-root work on those branches is
lost with it unless it is salvaged separately — those parts are not the
boundary module and may be worth keeping on their own. **Carried by: PM to
retire the branches, SE to salvage the non-`securefs` parts.**

**C. Park, with the condition written down.** Keep the four branches, merge
none, and require criteria 1–5 answered **in writing with evidence** before the
question reopens — which is exactly the ruling you already made about
`secure_search.py`, applied to its successor. *Cost:* the four newest security
branches stay unmergeable, which blocks nothing today but grows. **Carried by:
PM to record it, SAE to write the criteria check if and when someone wants to
answer it.**

**My recommendation: C, and say so in a sentence that names `securefs` rather
than `secure_search`.** The reason is not the code. It is that the project
already has a ruling for exactly this shape, the ruling was right, and the only
thing that has changed is the filename. **A is defensible the moment someone
answers criteria 1 to 3 with evidence; today nobody has.**

## What this memo does not establish

- That `securefs.py` is wrong, slow, or insecure. **Unreviewed, not condemned.**
- That the four branches contain nothing worth having. They contain Windows ACL
  validation and private-root work that is not the boundary module.
- Anything measured on Linux. UNMEASURED, nothing installed.
