# Brief 05 — the fingerprint is the file Linux actually holds

**For the security engineer.**

Brief 04 found it and reported it rather than fixing it, which was right. The
owner has now decided: the pinned fingerprint becomes the canonical LF hash and
the workflow stops rewriting its dependency's bytes.

## What is wrong, measured twice

`omniagent-core/CMakeLists.txt:16` demands

```
edea14f935e2729d157e063b1ebdde3deeca9714389aaf0d5a20424b6b98a5ff
```

That is the SHA256 of `include/llama.h` **as it sits in a Windows working tree
with `core.autocrlf=true`**. The canonical git blob — what every Linux checkout
of commit `869034b4bb93a425ea989d30fc3d000f5a461d58` holds — is

```
d5cf9203bea63b575e76cba4881f29cfd1b611451578b01582b75b72ecbb04bc
```

Replaying `CMakeLists.txt` lines 15–18 verbatim against the canonical blob:

```
-- computed: d5cf9203bea63b575e76cba4881f29cfd1b611451578b01582b75b72ecbb04bc
CMake Error: Unsupported llama.cpp API: use commit 869034b4bb93a425ea989d30fc3d000f5a461d58
```

**The check refuses the canonical form of the exact commit it names, and the
error message tells the reader to use the commit they already have.** That
message is why this went unnoticed for twelve days: it misdirects. The
2026-10-11 ctest log and the project manager's own build on 2026-10-23 both
passed only because WSL reads the CRLF copy through `/mnt/d`.

`omniagent-core` supports Linux and nothing else, by its own
`CMakeLists.txt:5`. The fingerprint must therefore be the value a Linux
checkout produces.

## Goal

Three things.

1. `CMakeLists.txt` accepts the canonical LF header and refuses anything else,
   with an error message that does not misdirect.
2. The workflow's CRLF normalization step is gone.
3. The workflow **proves the fingerprint still refuses a changed header**, so
   the check is not taken on faith.

## Do this in the right order, or you will have nothing to test with

**Get a working LF build before you change the hash.** The moment you flip the
value, the `/mnt/d` path everyone has been building from stops configuring, and
you will have no way to verify anything.

A local LF checkout, no network, from the copy already on disk:

```sh
git clone /mnt/d/code-project/OmniAgent/models/llama.cpp /tmp/llama-lf
sha256sum /tmp/llama-lf/include/llama.h
```

WSL's git has no `autocrlf`, so that working tree is LF. **Confirm the hash is
`d5cf9203…` before you trust it for anything.** If it is not, stop and report —
everything below rests on it.

Then configure against it with the current hash still in place and watch it be
refused. That refusal is your "watch it fail first" step for this brief, and it
is the behaviour you are about to invert.

## Files you may touch

- `omniagent-core/CMakeLists.txt`
- `.github/workflows/core.yml`
- `omniagent-core/README.md`

## Files you may not touch — read this list, it is the point

`omniagent-core/src/**` · `omniagent-core/include/**` ·
`omniagent-core/tests/**` · `models/**` · `tools.py` · `sandbox.py` ·
`.github/workflows/ci.yml` · anything on `main` · `NEXT_CHAT.md` ·
`docs/` except your `## Result` in this file.

Brief 04 listed only what was allowed and never said whether `CMakeLists.txt`
was forbidden. That ambiguity is why a defect got worked around instead of
reported. **If a file is not in the two lists above, ask rather than decide.**

Work in the existing worktree on `core-offline-runtime`:

```
cd ../OmniAgent-core
```

The fullstack engineer is on `main` in the other checkout. Do not switch its
branch.

## What `CMakeLists.txt` must say

Replace the expected hash with the canonical value, and **rewrite the error
message so it names both things it could mean**. The current wording cost this
project twelve days:

```cmake
file(SHA256 "${LLAMA_SOURCE_DIR}/include/llama.h" LLAMA_API_HASH)
if(NOT LLAMA_API_HASH STREQUAL "d5cf9203bea63b575e76cba4881f29cfd1b611451578b01582b75b72ecbb04bc")
    message(FATAL_ERROR
        "include/llama.h does not match the pinned llama.cpp API.\n"
        "  expected: d5cf9203...\n"
        "  found:    ${LLAMA_API_HASH}\n"
        "Use commit 869034b4bb93a425ea989d30fc3d000f5a461d58, checked out with "
        "LF line endings. A CRLF working tree (git core.autocrlf=true, or a "
        "Windows checkout read through /mnt) hashes differently and is refused.")
endif()
```

Print the computed hash. A fingerprint failure that does not say what it found
is a fingerprint failure nobody can diagnose.

Do **not** make CMake normalize line endings before hashing. That was the
rejected option; the fingerprint is meant to be exact.

## What the workflow must change

- **Delete** the "Reproduce the fingerprint's line endings" step entirely. The
  `actions/checkout` of `ggml-org/llama.cpp` already produces LF on the runner,
  which is now the value being checked.
- Update the `sha256sum --check` line to `d5cf9203…`.
- **Add a step that proves the fingerprint can still fail.** Copy the header to
  a throwaway tree, convert it to CRLF, configure against that tree, and assert
  the configure **fails**. Put it in a temporary directory; `git status` must be
  clean afterwards and the real checkout must be untouched. Configure-only is
  enough — the fingerprint fires before anything is compiled, so this costs
  seconds, not minutes.

A gate whose central check has never been observed failing is a gate on faith.
This step is the fingerprint's own M-check, living in CI where it keeps working
after everyone forgets why it is there.

## What the README must change

The paragraph that currently reads "The API fingerprint expects the CRLF
representation of `include/llama.h`… The CI workflow converts LF to CRLF before
checking this fingerprint" is now false. Replace it with the LF hash, and say
plainly that a CRLF working tree is refused and why — someone on Windows will
hit this and the README is where they will look.

Keep the sentence that it is not verification of the complete dependency
source. That remains true and brief 04 was right to keep it.

## Mutation checks that must go red

Copy each file to a scratch directory outside the repository first and restore
from that copy — never `git checkout --` alone. Assert the target string is
present before replacing it; a `sed` pattern containing `\n` matches nothing
silently, so a mutation can appear to pass without having mutated anything.

| # | Mutation / control | Expected |
| --- | --- | --- |
| C1 | Configure against `/tmp/llama-lf` **after** the change | **succeeds** — this is the whole point |
| C2 | Configure against the CRLF tree on `/mnt/d` after the change | **refused**, and the message names line endings |
| M1 | Change one byte of content, not a line ending, in the LF header | refused, and the printed `found:` hash differs |
| M2 | Revert the hash in `CMakeLists.txt` to `edea14f9…` | C1 breaks — proves C1 depends on the new value and not on something else |
| M3 | Delete the new CI refusal step | nothing locally — say what in the repository would notice, and if the answer is nothing, say so |

Then build and run `ctest` fully against `/tmp/llama-lf` and paste the output.
**4/4 must pass.** The project manager measured configure 5 s, build 82 s,
ctest 0.20 s on `/mnt/d` with cmake 3.28.3 and g++ 13.3.0; an LF tree on ext4
should be no slower. If the tests fail against an LF checkout, that is a far
larger finding than this brief — stop and report it.

## Gates

From the **main checkout**, unchanged: `.venv\Scripts\python.exe -m ruff
check .`, `-m mypy`, `-m pytest`. Full path, **no `-q` of your own**. Expect
**633 passed**. If that number moved, you touched something outside your list.

In the worktree: `ctest --test-dir <build> --output-on-failure --no-tests=error`,
4/4.

## The one thing that would make this wrong

**Making the build work again without the fingerprint still being able to
refuse anything.** The failure mode is a hash that matches whatever is lying
around — normalized before hashing, or quietly made a warning, or a CI step
that reports success because the configure it tested did not run. C2, M1 and M2
exist to show the check still bites. If you cannot produce a refusal, the
fingerprint is decoration and this brief has made the repository less safe, not
more.

The second way: fixing the local build by editing `models/llama.cpp`. It is
third-party source and it is on the forbidden list. The LF clone in `/tmp` is
how you get a working build; the Windows checkout stays as it is.

## Commit

One commit on `core-offline-runtime`, in the worktree:

```
git add omniagent-core/CMakeLists.txt .github/workflows/core.yml omniagent-core/README.md
git commit -m "fix(core): pin the fingerprint to the header Linux actually checks out"
```

`git show --stat` must list exactly those three files.

**Do not push.** The project manager pushes the branch after verifying, which
will be the first time this workflow runs on `ubuntu-latest`.

## Result

<!-- Engineer: append here. The LF clone's hash, the refusal you watched before
changing anything, C1, C2, M1, M2, M3 each with what happened, the full ctest
output against the LF tree, the three Python gate results, the commit hash, and
anything you refuse to claim. -->
