# Brief 04 — the fourth gate for `omniagent-core`

**For the security engineer.**

1,221 lines of C++20 sit on the branch `core-offline-runtime` (`cfbde93`),
outside all three gates. Its only evidence is a `ctest` log dated
**2026-10-11 15:57**, 4/4 passed, built under WSL — twelve days old and not
re-run since. The branch is public. This brief gives that code a gate that can
fail, and checks that its README claims have tests behind them.

## Where you work — read this first

Brief 03 is in flight on `main` and owns `tools.py`. **Do not work in the main
checkout.** Make a worktree for the branch:

```
git worktree add ../OmniAgent-core core-offline-runtime
```

Everything in this brief happens there, on `core-offline-runtime`. You touch no
file on `main`, and the two tasks cannot collide.

## What is measured, 2026-10-23

| Fact | Value | How |
| --- | --- | --- |
| llama.cpp origin | `https://github.com/ggml-org/llama.cpp.git` | `git -C models/llama.cpp remote -v` |
| pinned commit | `869034b4bb93a425ea989d30fc3d000f5a461d58` | local checkout `rev-parse HEAD` — **matches the pin** |
| expected `include/llama.h` SHA256 | `edea14f935e2729d157e063b1ebdde3deeca9714389aaf0d5a20424b6b98a5ff` | `CMakeLists.txt:16` |
| actual local SHA256 | **identical** | `sha256sum models/llama.cpp/include/llama.h` |
| checkout size | 213 MB | `du -sh` |
| ctest targets | `make_tiny_gguf`, `core` (TIMEOUT 60), `secure_heap`, `offline_imports` | `CMakeLists.txt:59-84` |
| existing CI | `ubuntu-latest`, ruff/mypy/pytest, `timeout-minutes: 10`, triggers on `main` only | `.github/workflows/ci.yml` |

`models/llama.cpp` is gitignored, so **a clone of the branch cannot build**.
That is the hole this gate closes.

### Two things I checked before writing this, so you do not have to

1. **`OMNI_CORE_TESTING=1` does not relax any check.** `CMakeLists.txt:65`
   defines it `PUBLIC` on the library, which looked like the test build
   exercising a different code path than the shipped one. It appears exactly
   once in the sources, at
   `include/omniagent/local_inference_engine.hpp:66`, and all it does is
   `friend struct EngineTestAccess`. `src/local_file.cpp` and
   `src/local_inference_engine.cpp` contain no such guard, so path and
   filesystem validation are identical in both builds. **If you change that,
   say so loudly** — it would mean the tests stop being about the shipped code.

2. **The filesystem allowlist and the test fixture do not contradict each
   other.** `README.md` says a model on `/mnt/c` or `/mnt/d` is refused, and
   `src/local_file.cpp:19-25` enforces ext4/XFS/Btrfs/tmpfs/ramfs/overlayfs
   unconditionally. The fixture nonetheless loads successfully, because
   `tests/core_tests.cpp:63` does `fs::copy_file(argv[1], model)` — it copies
   the GGUF off the build directory to its own `root` first. **That makes the
   runner's temporary filesystem part of the gate**: on a runner where that
   root is not an allowed type, `core` fails for a reason that has nothing to
   do with the code. Confirm the type on `ubuntu-latest` and record it.

## Goal

Two things, and no more.

1. A CI job that builds `omniagent-core` and runs its four `ctest` targets, and
   that **can go red** — demonstrated, not asserted.
2. Every security claim in `omniagent-core/README.md` mapped to a named test
   that can fail. Any claim with no test behind it is either given one or
   struck from the README.

## Files you may touch, in the worktree only

- Add: `.github/workflows/core.yml`
- Modify: `omniagent-core/README.md`
- Modify or add: files under `omniagent-core/tests/`

Do not touch `tools.py`, `sandbox.py`, `.github/workflows/ci.yml`,
`omniagent-core/src/**`, or `omniagent-core/include/**`. If a claim turns out to
be false about the code rather than merely untested, **do not fix the code** —
record it in `## Result` and stop. Changing a security boundary is a separate
decision.

## The workflow it must produce

A **separate** file, not a job inside `ci.yml`. A C++ build failure must not
block the Python gates, and vice versa — they fail for unrelated reasons and
share nothing.

```yaml
name: core
on:
  push:
    paths: ["omniagent-core/**", ".github/workflows/core.yml"]
  pull_request:
    paths: ["omniagent-core/**", ".github/workflows/core.yml"]
  workflow_dispatch:
```

Triggers must cover **both** `main` and `core-offline-runtime`, or the gate is
invisible on the branch where the code actually lives. The `paths` filter keeps
it off documentation commits.

The llama.cpp checkout is done **by the workflow, not by CMake**:

```yaml
- uses: actions/checkout@v4
  with:
    repository: ggml-org/llama.cpp
    ref: 869034b4bb93a425ea989d30fc3d000f5a461d58
    path: models/llama.cpp
```

`CMakeLists.txt:13` says "this build never downloads it", and that stays true —
the workflow supplies the source, the build does not fetch it. This is a
deliberate reading of standard 1 and it is recorded here so nobody has to guess
later.

**Then verify the pin before building**, as its own step:

```
sha256sum models/llama.cpp/include/llama.h
```

and fail the job unless it equals
`edea14f935e2729d157e063b1ebdde3deeca9714389aaf0d5a20424b6b98a5ff`. CMake
checks the same hash, but it does so after configuring half a build and reports
it as a CMake error. A moved ref or a tampered mirror should fail closed in one
step with one sentence.

Then configure, build and test:

```
cmake -S omniagent-core -B omniagent-core/build -DCMAKE_BUILD_TYPE=Release
cmake --build omniagent-core/build --parallel
ctest --test-dir omniagent-core/build --output-on-failure
```

- **Set `timeout-minutes` from a measurement, not a guess.** Time the build and
  put the measured figure plus headroom in the workflow. Report the number.
- **Do not add a build cache in this brief.** A stale cache is a gate that
  tests something other than the current source. If the measured time is
  unacceptable, say so in `## Result` and leave caching to a decision.
- Do not add `continue-on-error` anywhere. A gate that cannot fail the run is
  not a gate.

## Build it locally first, under WSL

Windows is refused at configure time by design (`CMakeLists.txt:5`). Use the
local Ubuntu distribution. **A command over 600 seconds is backgrounded and
dies with the session**, so start the build in the background deliberately and
do other work while it runs rather than losing it at the 600-second mark.

Record the local build time and the `ctest` output. That log replaces the
twelve-day-old one as this code's current evidence.

## Mutation checks that must go red

This is the part that matters. A CI job that stays green while the code is
broken is worse than no job, because it is believed. Run each mutation locally
under WSL against the real build, restoring from a scratch copy outside the
repository each time — never `git checkout --` alone — and assert the target
string is present before replacing it.

| # | Mutation | Must go red |
| --- | --- | --- |
| M1 | Make the wiping store in `src/secure_heap.cpp` a no-op | `secure_heap` |
| M2 | Change one byte of `models/llama.cpp/include/llama.h` | the workflow's SHA256 step **and** the CMake fingerprint — report both, and which fired first |
| M3 | Reference `dlopen` from `tests/plugin_probe.cpp` or the test binary | `offline_imports` |
| M4 | Remove one refusal from `src/local_file.cpp`'s path validation — the `..` case, say | `core` |
| M5 | Remove a filesystem type from the `local_file.cpp` allowlist that the fixture root relies on | `core`, and this tells you which type the runner actually uses |
| M6 | Delete the `ctest` step from the workflow | **nothing locally** — which is the point: name what in the repository would notice, and if the answer is nothing, say so |

M1 and M4 touch `src/`, which this brief otherwise forbids. **Mutations are the
exception**: mutate, observe, restore from the scratch copy, and verify the
restore with a checksum. Nothing under `src/` or `include/` may appear in your
commit — prove it with `git show --stat`.

M6 is not a formality. The three Python gates are enforced by habit and by
`ci.yml`; a fourth gate in a second workflow file has nothing watching that it
still exists. Say plainly what protects it, even if the answer is "nothing yet".

## The claim-to-test map

`omniagent-core/README.md` makes a large number of security claims. Produce a
table in `## Result`: **claim, the README line it is on, the test that can fail
if it is untrue, and how you know that test covers it.** Start from the
"Verification" section, which already lists what the tests are meant to cover:
exact output over ten repetitions, forty concurrent requests, EOS, limits,
aborted prefill then successful reuse, concurrent unload, invalid
model/path/config, symlink/FIFO/log boundaries, and audit redaction — in a
231-line test file.

For every claim with no test behind it, choose one and say which:

- add a test that fails when the claim is untrue, or
- **strike the claim from the README.**

A claim with no run behind it does not stay in a public README. That is the
standard this whole project is built on, and the README's own honest limits
section — the paragraph beginning "This contract covers owned heap buffers" —
shows the author already knows the difference. Keep that paragraph.

Do not weaken a claim into vagueness to avoid testing it. Either it is checked
or it is gone.

## Gates before the commit

The three Python gates still apply, from the **main checkout**, because nothing
you touch should affect them:

```
.venv\Scripts\python.exe -m ruff check .
.venv\Scripts\python.exe -m mypy
.venv\Scripts\python.exe -m pytest
```

Full path, **no `-q` of your own**. Expect **633 passed**, unchanged — if the
number moved, you touched something you should not have.

Plus, in the worktree: `ctest --test-dir omniagent-core/build
--output-on-failure`, 4/4 passing, with the output pasted.

## The one thing that would make this wrong

**A green workflow that proves nothing.** The failure mode is a job that builds
successfully and runs zero tests, or runs them against a stale build directory,
or whose `ctest` step is skipped because a previous step soft-failed. That job
is then cited as "the core is gated" for months. M1 through M5 exist to show
each target can actually fail; M6 exists to admit what guards the gate itself.

The second way: fixing the code. If a mutation reveals that a README claim is
false about `src/`, that is a finding, not a task. Record it and stop — the
owner decides whether a security boundary changes.

## Commit

On `core-offline-runtime`, in the worktree. One commit:

```
git add .github/workflows/core.yml omniagent-core/README.md omniagent-core/tests
git commit -m "ci(core): a fourth gate that builds the native runtime and runs its tests"
```

`git show --stat` must list nothing under `omniagent-core/src/` or
`omniagent-core/include/`.

**Do not push.** This repository has two remotes and the branch exists on
`origin` only; the project manager pushes it.

## Result

<!-- Engineer: append here. The local build time, the ctest output, M1 through
M6 each with what went red and what stayed green, the claim-to-test table with
every untested claim resolved either way, the measured timeout-minutes, the
three Python gate results, the commit hash, and anything you refuse to claim. -->
