# Train and Deploy Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make a fine-tune's provenance durable and its promotion to the
`omniagent` tag conditional on the evaluations, so that no model is served
whose dataset was collected under a different system prompt.

**Architecture:** The pipeline already exists and already runs locally --
`models/omniagent-qwen2.5-1.5b-manifest.json` records a qlora-4bit run on an
RTX 3050 Laptop GPU, 109 examples, 3 epochs, 2026-10-02. What is missing is
memory and a gate. The dataset learns to record the system prompt it was
collected under, every run keeps its own directory instead of overwriting one
manifest, and `ollama create` moves out of a notebook cell into a script that
refuses to promote a model until the two evaluations pass.

**Tech Stack:** Python 3.12, transformers 5.17.0, trl 1.13.0, peft 0.21.0,
bitsandbytes 4-bit QLoRA, llama.cpp `convert_hf_to_gguf.py`, Ollama.

**Spec:** this document's Goal and Global Constraints, arguing from the
measured state in `NEXT_CHAT.md`. There is no separate spec; the facts the
plan rests on are the manifest above, the empty `models/runs/`, and the open
item in `NEXT_CHAT.md` recording that `read_file`'s description changed in
`58bb801` so the dataset no longer matches the prompt the model is served.

## Global Constraints

- **Local only.** Nothing leaves localhost, including the dataset. Training
  runs on this machine, not a hosted notebook.
- **No frameworks in the agent.** This plan touches training and deployment
  scripts only; `agent.py`'s hand-rolled loop is not in scope.
- **Three gates green before every commit:**
  `.venv/Scripts/python.exe -m ruff check . && .venv/Scripts/python.exe -m mypy && .venv/Scripts/python.exe -m pytest`
- **New scripts go in mypy's `files` list** in `pyproject.toml`. The
  evaluation scripts were outside it until 2026-10-04 and were clean only by
  luck.
- **Mutation-check every gate this plan adds.** Break the control, confirm a
  test goes red, restore from a `/tmp` copy and never with `git checkout --`.
- The agent already logs `system_prompt_sha256` in its `agent.created` event
  (`agent.py:467`). Reuse that hash; do not invent a second one.

## Review Focus

- **A dataset written before this plan** has no recorded prompt hash. Reading
  one must say so and stop, not treat a missing hash as a match.
- **A run directory half-written** because training crashed between the
  manifest and the weights: promotion must refuse it rather than serve a
  partial model.
- **An evaluation that errored** (19 errors and `0/0` happens when Ollama is
  down) must not read as "no failures, promote".
- **A promote run with Ollama not running** must fail with the connection
  error, not create a tag pointing at nothing.
- **Two runs in the same second** must not collide on one directory name.

---

### Task 1: The dataset records the prompt it was collected under

**Files:**
- Modify: `export_dataset.py` (add the sidecar write to its `main`)
- Create: `dataset_provenance.py`
- Test: `tests/test_dataset_provenance.py`

**Interfaces:**
- Consumes: `agent.SYSTEM_PROMPT_TEMPLATE`, `tools.describe_tools`,
  `tools.tool_names` — whatever `ReActAgent.__init__` already formats at
  `agent.py:445`.
- Produces: `render_system_prompt() -> str`,
  `prompt_fingerprint() -> str` (the sha256 hex digest of that string),
  `write_sidecar(dataset: Path) -> Path` (writes
  `<dataset>.provenance.json`), and
  `read_sidecar(dataset: Path) -> dict[str, str]` which raises
  `ProvenanceError` when the file is absent.

- [ ] **Step 1: Write the failing tests**

```python
def test_the_fingerprint_matches_the_prompt_the_agent_builds() -> None:
    agent = ReActAgent(config=AgentConfig(verbose=False), client=FakeOpenAI().as_client())
    assert prompt_fingerprint() == sha256(agent.system_prompt.encode("utf-8")).hexdigest()

def test_a_sidecar_records_the_fingerprint_and_the_example_count(tmp_path: Path) -> None:
    dataset = tmp_path / "dataset.jsonl"
    dataset.write_text('{"messages": []}\n', encoding="utf-8")
    write_sidecar(dataset)
    written = read_sidecar(dataset)
    assert written["system_prompt_sha256"] == prompt_fingerprint()
    assert written["examples"] == 1

def test_a_dataset_with_no_sidecar_is_an_error_not_a_match(tmp_path: Path) -> None:
    with pytest.raises(ProvenanceError, match="no provenance"):
        read_sidecar(tmp_path / "dataset.jsonl")
```

- [ ] **Step 2: Run them and watch them fail**

Run: `.venv/Scripts/python.exe -m pytest tests/test_dataset_provenance.py -v`
Expected: FAIL, `ModuleNotFoundError: dataset_provenance`

- [ ] **Step 3: Implement `dataset_provenance.py`**

`render_system_prompt()` must format the same template with the same
arguments as `agent.py:445`, so that the two cannot drift; import the
template rather than copying it.

- [ ] **Step 4: Call `write_sidecar` from `export_dataset.py`'s `main`**

After the dataset file is written, so a failed export leaves no sidecar.

- [ ] **Step 5: Add `dataset_provenance.py` to mypy's `files` list**

- [ ] **Step 6: Run the three gates**

Expected: all green, and the new tests pass.

- [ ] **Step 7: Mutation-check**

Make `read_sidecar` return `{}` for a missing file. Expected: the third test
goes red. Restore from `/tmp`.

- [ ] **Step 8: Commit**

```bash
git add dataset_provenance.py export_dataset.py tests/test_dataset_provenance.py pyproject.toml
git commit -m "feat: a dataset records the system prompt it was collected under"
```

---

### Task 2: Every training run keeps its own directory

**Files:**
- Modify: `scripts/build_notebook.py` (the manifest cell)
- Create: `scripts/run_dir.py`
- Test: `tests/test_run_dir.py`

**Interfaces:**
- Consumes: `dataset_provenance.read_sidecar` from Task 1.
- Produces: `new_run_dir(root: Path, when: datetime) -> Path` (creates
  `root/<when:%Y%m%dT%H%M%S>` and suffixes `-2`, `-3` on collision), and
  `write_manifest(run: Path, fields: Mapping[str, object]) -> Path`, which
  includes the dataset's `system_prompt_sha256` and raises `KeyError` if the
  caller omits `base_model`, `examples` or `strategy`.

- [ ] **Step 1: Write the failing tests**

```python
def test_a_run_directory_is_named_for_its_timestamp(tmp_path: Path) -> None:
    run = new_run_dir(tmp_path, datetime(2026, 10, 6, 7, 30, 0))
    assert run.name == "20261006T073000"

def test_two_runs_in_the_same_second_do_not_collide(tmp_path: Path) -> None:
    when = datetime(2026, 10, 6, 7, 30, 0)
    first, second = new_run_dir(tmp_path, when), new_run_dir(tmp_path, when)
    assert first != second
    assert second.name.endswith("-2")

def test_a_manifest_without_the_required_fields_is_refused(tmp_path: Path) -> None:
    with pytest.raises(KeyError):
        write_manifest(new_run_dir(tmp_path, datetime.now()), {"examples": 109})
```

- [ ] **Step 2: Run them and watch them fail**

Run: `.venv/Scripts/python.exe -m pytest tests/test_run_dir.py -v`
Expected: FAIL, `ModuleNotFoundError: run_dir`

- [ ] **Step 3: Implement `scripts/run_dir.py`**

- [ ] **Step 4: Rewrite the notebook's manifest cell to use it**

The cell writes into `models/runs/<timestamp>/manifest.json` and copies the
adapter there. `models/omniagent-qwen2.5-1.5b-manifest.json` stays as a
symlink or copy of the newest, so nothing that reads the old path breaks.
Regenerate with `python scripts/build_notebook.py`.

- [ ] **Step 5: Add `scripts/run_dir.py` to mypy's `files` list**

- [ ] **Step 6: Run the three gates, then `python scripts/build_notebook.py` and confirm the notebook is valid JSON**

Run: `.venv/Scripts/python.exe -c "import json,pathlib; json.loads(pathlib.Path('notebooks/train_omniagent_lora.ipynb').read_text(encoding='utf-8'))"`
Expected: no output, exit 0.

- [ ] **Step 7: Mutation-check**

Drop the collision suffix. Expected: the second test goes red.

- [ ] **Step 8: Commit**

```bash
git add scripts/run_dir.py scripts/build_notebook.py notebooks/train_omniagent_lora.ipynb tests/test_run_dir.py pyproject.toml
git commit -m "feat: each training run keeps its own directory"
```

---

### Task 3: Promotion is a script, and the evaluations gate it

**Files:**
- Create: `scripts/promote_model.py`
- Test: `tests/test_promote_model.py`

**Interfaces:**
- Consumes: `run_dir.write_manifest`'s output shape from Task 2,
  `dataset_provenance.prompt_fingerprint` from Task 1,
  `eval_scoring.Score`.
- Produces: `check_run(run: Path) -> list[str]` (the reasons a run may not be
  promoted, empty when it may), `check_scores(scores: Mapping[str, Score], floor: Mapping[str, int]) -> list[str]`,
  and `main(argv: list[str] | None = None) -> int`, invoked as
  `python scripts/promote_model.py models/runs/<timestamp> --tag omniagent`.

- [ ] **Step 1: Write the failing tests**

```python
def test_a_run_whose_prompt_hash_differs_is_refused(tmp_path: Path) -> None:
    run = _run_dir(tmp_path, system_prompt_sha256="0" * 64)
    assert "collected under a different system prompt" in " ".join(check_run(run))

def test_a_run_missing_its_weights_is_refused(tmp_path: Path) -> None:
    run = _run_dir(tmp_path, weights=False)
    assert any("gguf" in reason for reason in check_run(run))

def test_an_evaluation_that_errored_is_not_a_pass() -> None:
    scored = {"holdout": Score(correct=0, checkable=0, errors=["connection lost"])}
    assert check_scores(scored, {"correct": 12}) != []

def test_a_score_below_the_floor_is_refused() -> None:
    scored = {"holdout": Score(correct=11, checkable=16)}
    assert any("12" in reason for reason in check_scores(scored, {"correct": 12}))

def test_a_run_that_passes_everything_has_no_reasons(tmp_path: Path) -> None:
    assert check_run(_run_dir(tmp_path)) == []

def test_a_stopped_ollama_fails_loudly_rather_than_tagging_nothing(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr("promote_model._ollama_create", _raise(OSError("connection refused")))
    with pytest.raises(OSError):
        main([str(_run_dir(tmp_path)), "--tag", "omniagent"])
```

`_run_dir` and `_raise` are helpers the implementer writes: the first builds a
run directory whose manifest, weights and Modelfile are all present and whose
prompt hash matches, with keyword arguments to spoil one thing at a time; the
second returns a callable that raises what it is given.

- [ ] **Step 2: Run them and watch them fail**

Run: `.venv/Scripts/python.exe -m pytest tests/test_promote_model.py -v`
Expected: FAIL, `ModuleNotFoundError: promote_model`

- [ ] **Step 3: Implement `check_run` and `check_scores`**

Both return reasons rather than raising, so `main` can print every problem at
once instead of the first. An empty `checkable` or a non-empty `errors` is a
refusal, not a pass.

- [ ] **Step 4: Implement `main`**

It runs `ollama create <tag> -f <run>/Modelfile` only when both check
functions return empty, prints every reason and returns 1 otherwise, and
writes the promoted tag and the run's timestamp into
`models/promoted.json`. It does not catch the connection error from a stopped
Ollama: that failure should be visible.

- [ ] **Step 5: Add `scripts/promote_model.py` to mypy's `files` list**

- [ ] **Step 6: Run the three gates**

- [ ] **Step 7: Mutation-check**

Make `check_scores` ignore `errors`. Expected: the errored-evaluation test
goes red. Restore from `/tmp`.

- [ ] **Step 8: Commit**

```bash
git add scripts/promote_model.py tests/test_promote_model.py pyproject.toml
git commit -m "feat: promotion refuses a run the evaluations have not passed"
```

---

### Task 4: The Colab framing goes

**Files:**
- Modify: `scripts/smoke_train.py` (the module docstring)
- Modify: `scripts/build_notebook.py` (the one Colab mention)
- Modify: `README.md` (the training section, if it says Colab)
- Test: `tests/test_local_only.py`

**Interfaces:** none; this is documentation that contradicts the manifest.

- [ ] **Step 1: Write the failing test**

```python
@pytest.mark.parametrize("path", ["scripts/smoke_train.py", "scripts/build_notebook.py", "README.md"])
def test_nothing_tells_the_reader_to_train_on_a_hosted_notebook(path: str) -> None:
    """The manifest records an RTX 3050 Laptop GPU, and standard 1 says local only."""
    assert "colab" not in (REPO_ROOT / path).read_text(encoding="utf-8").lower()
```

- [ ] **Step 2: Run it and watch it fail**

Run: `.venv/Scripts/python.exe -m pytest tests/test_local_only.py -v`
Expected: FAIL on at least `scripts/smoke_train.py`.

- [ ] **Step 3: Rewrite the three mentions**

`smoke_train.py`'s docstring says the notebook targets a local GPU with a real
base model, which a CPU cannot exercise. Keep what it says about catching a
transformers/trl/peft API change before a twenty-minute run.

- [ ] **Step 4: Regenerate the notebook and run the three gates**

Run: `.venv/Scripts/python.exe scripts/build_notebook.py && .venv/Scripts/python.exe -m pytest`
Expected: notebook regenerated, all green.

- [ ] **Step 5: Commit**

```bash
git add scripts/smoke_train.py scripts/build_notebook.py README.md notebooks/train_omniagent_lora.ipynb tests/test_local_only.py
git commit -m "docs: the notebook trains locally, which is what the manifest records"
```

---

## After the plan

Collect a fresh dataset under the current system prompt, train, and promote
through Task 3's script. The first promotion will refuse the existing
`data/dataset.jsonl`, which is the point: `read_file`'s description changed in
`58bb801` and the dataset predates it.
