# Brief 17 — PM verification: not merged, and the reason is a good one

**2026-11-05, against `main` at `c7e718f` with
`brief-17-wheel-completeness` (`ce07d50`) merged but not committed. The merge
was aborted; `main` is untouched and back at 658 passed.**

## The work is right. The test is wrong on `main`, which is where it has to live.

| Checked | Result |
| --- | --- |
| merge | clean, no conflicts, and `docs/pm/assignments-2026-11-04.md` survives (the branch is based on `108708c`, one commit behind `main`; a diff reads as a deletion, a merge does not) |
| `ruff` | clean |
| `mypy` | clean over **46** files (45 + the new test module) |
| `pytest` | **1 failed, 661 passed** |

The failure is `test_every_module_in_the_wheel_imports_from_the_unpacked_wheel`,
and **it is not the packaging**. The packaging fix is correct: the
completeness test passes, `dataset_provenance` is in `py-modules` and in
ruff's `known-first-party`, and every other new test passes.

## The defect, exactly

`tests/test_wheel_completeness.py:45` —
`PROJECT_ROOT = Path(__file__).resolve().parent.parent`, the checkout the test
file is sitting in.

The import child's canary, at `:73-84`, flags **any** loaded module whose
`__file__` resolves under that root:

```python
if resolved == root or root in resolved.parents:
    leaked.append(...)
```

**`.venv` lives at `D:/code-project/OmniAgent/.venv`, inside the repository
root.** So on `main` every third-party dependency the child imports —
`annotated_types`, `anyio`, `click`, `pydantic`, and the rest — resolves under
the root and the canary fires:

```
AssertionError: modules in the wheel that do not import from it:
agent: RESOLVED FROM THE CHECKOUT: annotated_types <- D:\code-project\OmniAgent\.venv\Lib\site-packages\annotated_types\__init__.py, anyio <- ...
```

**Why it passed for you and fails for me.** You ran it in your own worktree,
where there is no `.venv`. The interpreter is still the one in the main
checkout, so site-packages still resolve to
`D:/code-project/OmniAgent/.venv/...` — but that path is **not** under *your*
`PROJECT_ROOT`, so the canary stayed quiet. On `main` it is under the root,
and it fires. **The test passes everywhere except the place it has to run.**

Nothing about this is your fault in substance: the canary is a good idea, and
it is the part of the test I was most glad to see. It is the boundary that is
wrong, not the instinct.

## The fix is one condition, and you already compute both halves of it

`:112` already resolves `sysconfig`'s `purelib` and `platlib` to put them on
the child's `sys.path`. **Exclude anything under those two from the leak
check**, and the canary means what it says: loaded from the *source checkout*,
not loaded from the environment that happens to live inside it.

Please also consider — your call, say what you chose:

- whether the canary should test "under the source root **and not** under
  purelib/platlib", or "the module's file is one of the source files we know
  about". The first is cheaper and survives a layout change; the second is
  stricter and goes stale.
- a regression test for the canary itself. **It fired on the wrong thing and
  nothing caught that** — the same class of defect the whole brief is about.

## One more thing to decide, not a defect

**The suite went from 20.06 s to 33.12 s on this machine**, and the wheel
build is 6.38 s of setup plus 1.80 s in the import test. The brief asked for
the runtime and for a way to select it out; the Result gives the runtime.
**Add the marker.** A test that adds thirteen seconds to every run is a test
somebody deletes in six months, and this one is load-bearing: it is the
instrument that will prove the package move behaviour-free.

## What I have not verified yet

**I stopped at the failure.** Your Ma, Mb and Mc results are unchecked,
because a red suite makes them unreadable — I cannot tell a mutation that went
red for the right reason from one that went red because of the canary. I will
re-run all three when the fix lands.

## Two things in your report that are corrections to my brief, and both are right

1. **`-I` alone is not isolation.** The editable install's
   `__editable__.omniagent-0.1.0.pth` puts a finder on `sys.meta_path` that
   maps module names straight back at the checkout, and `-S` is needed as
   well. My own verification on 2026-11-04 used `-I` without `-S` and got the
   right answer **by luck**: that finder's `MAPPING` is generated from
   `py-modules`, which is exactly the list that was missing
   `dataset_provenance`. Any module that *was* in the list would have resolved
   from the checkout and my check would have passed while proving nothing.
   **You found a hole in the recipe I handed you, and it is the same hole the
   brief was written to close.**
2. **The base commit in the brief was wrong.** It said `05e99e8`; the brief
   file did not exist until `87a1297`. You branched from `108708c` and
   re-measured everything there rather than quoting me. Correct on both
   counts.

## Status

**Not merged.** Fix the canary boundary, add the marker, push to the same
branch, and tell me. I will re-run the gates, Ma, Mb and Mc, and merge.
