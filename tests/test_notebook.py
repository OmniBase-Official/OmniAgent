"""Structural checks on the training notebook.

The notebook cannot be executed here -- it wants a GPU and a real base model --
so these check what can be checked without running it: that it is valid
nbformat, that every code cell is syntactically valid Python, that the library
pins and API names match the ones `scripts/smoke_train.py` actually exercised,
and that the Modelfile cell produces the file `ollama create` accepts.
"""

from __future__ import annotations

import ast
import json
import os
import tempfile
from pathlib import Path
from typing import Any

import pytest

NOTEBOOK = Path(__file__).resolve().parent.parent / "notebooks" / "train_omniagent_lora.ipynb"


@pytest.fixture(scope="module")
def notebook() -> dict[str, Any]:
    data: dict[str, Any] = json.loads(NOTEBOOK.read_text(encoding="utf-8"))
    return data


def sources(notebook: dict[str, Any], kind: str = "code") -> list[str]:
    return [
        "".join(cell["source"]) for cell in notebook["cells"] if cell["cell_type"] == kind
    ]


def test_the_notebook_exists_and_is_valid_nbformat(notebook: dict[str, Any]) -> None:
    assert notebook["nbformat"] == 4
    assert notebook["cells"]
    for cell in notebook["cells"]:
        assert cell["cell_type"] in {"code", "markdown"}
        assert isinstance(cell["source"], list)


def test_every_code_cell_is_valid_python(notebook: dict[str, Any]) -> None:
    for index, source in enumerate(sources(notebook)):
        try:
            ast.parse(source)
        except SyntaxError as exc:
            pytest.fail(f"code cell {index} does not parse: {exc.msg} (line {exc.lineno})")


def test_the_notebook_ships_no_outputs(notebook: dict[str, Any]) -> None:
    """Saved outputs bloat the diff and can carry data from a real run."""
    for cell in notebook["cells"]:
        if cell["cell_type"] == "code":
            assert cell["outputs"] == []
            assert cell["execution_count"] is None


@pytest.mark.parametrize(
    "pin",
    ["transformers==5.17.0", "trl==1.13.0", "peft==0.21.0", "datasets==5.0.1"],
)
def test_the_library_versions_are_pinned(notebook: dict[str, Any], pin: str) -> None:
    """These exact versions are the ones the CPU smoke test ran against."""
    assert any(pin in source for source in sources(notebook))


def test_sentencepiece_is_installed_for_the_gguf_step(notebook: dict[str, Any]) -> None:
    """Discovered the hard way: convert_hf_to_gguf.py needs it for some tokenizers."""
    assert any("sentencepiece" in source for source in sources(notebook))


@pytest.mark.parametrize("name", ["max_length", "processing_class", "peft_config"])
def test_the_modern_trl_argument_names_are_used(notebook: dict[str, Any], name: str) -> None:
    assert any(name in source for source in sources(notebook))


@pytest.mark.parametrize("stale", ["max_seq_length", "tokenizer=tokenizer"])
def test_the_old_trl_argument_names_are_not_used(
    notebook: dict[str, Any], stale: str
) -> None:
    assert not any(stale in source for source in sources(notebook))


def test_the_gguf_step_clones_the_repo(notebook: dict[str, Any]) -> None:
    """convert_hf_to_gguf.py imports a package, so a single-file download fails."""
    gguf_cells = [s for s in sources(notebook) if "convert_hf_to_gguf" in s]

    assert gguf_cells
    assert any("git" in source and "clone" in source for source in gguf_cells)


def test_the_dataset_is_validated_before_the_model_loads(notebook: dict[str, Any]) -> None:
    code = sources(notebook)
    validate_at = next(i for i, s in enumerate(code) if "validate_file" in s)
    load_at = next(i for i, s in enumerate(code) if "AutoModelForCausalLM" in s)

    assert validate_at < load_at


def test_training_stops_when_the_dataset_is_refused(notebook: dict[str, Any]) -> None:
    validation = next(s for s in sources(notebook) if "validate_file" in s)

    assert "report.ok" in validation
    assert "SystemExit" in validation


def test_the_base_model_and_its_licence_are_called_out(notebook: dict[str, Any]) -> None:
    """Commercial intent makes the base model's licence a blocking question."""
    code = "\n".join(sources(notebook))
    prose = "\n".join(sources(notebook, "markdown"))

    assert "Qwen/Qwen2.5-1.5B-Instruct" in code
    assert "Apache-2.0" in prose
    assert "licence" in prose.lower() or "license" in prose.lower()


def test_the_modelfile_cell_writes_what_ollama_accepts(notebook: dict[str, Any]) -> None:
    """The f-string has to survive Go template braces; execute it and look."""
    cell = next(s for s in sources(notebook) if "modelfile" in s)

    cwd = Path.cwd()
    with tempfile.TemporaryDirectory() as scratch:
        os.chdir(scratch)
        try:
            namespace: dict[str, Any] = {"gguf_path": "model-f16.gguf", "Path": Path}
            exec(cell, namespace)  # noqa: S102 - executing our own notebook cell is the test
            written = Path("Modelfile").read_text(encoding="utf-8")
        finally:
            os.chdir(cwd)

    assert written.startswith("FROM ./model-f16.gguf")
    assert "{{ if .System }}" in written
    assert "{{ .Prompt }}" in written
    assert "{{ .Response }}" in written
    assert 'PARAMETER stop "<|im_end|>"' in written
    assert 'PARAMETER stop "Observation:"' in written
    # The f-string must not have leaked doubled braces into the template.
    assert "{{{{" not in written
