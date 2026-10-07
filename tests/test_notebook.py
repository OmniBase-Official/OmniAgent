"""Structural checks on the training notebook.

Running it needs a GPU, a 3 GB model download and twenty minutes, so the suite
checks what can be checked in milliseconds: that it is valid nbformat, that
every code cell is syntactically valid Python, that it still picks its loading
strategy from the hardware rather than assuming one, that it never uploads the
dataset anywhere, and that the Modelfile cell produces the file `ollama create`
accepts.

The notebook itself has been executed end to end on this project's own GPU; see
the README for what that run produced.
"""

from __future__ import annotations

import ast
import json
from pathlib import Path
from typing import Any

import pytest

NOTEBOOK = Path(__file__).resolve().parent.parent / "notebooks" / "train_omniagent_lora.ipynb"


@pytest.fixture(scope="module")
def notebook() -> dict[str, Any]:
    data: dict[str, Any] = json.loads(NOTEBOOK.read_text(encoding="utf-8"))
    return data


def joined(notebook: dict[str, Any], kind: str = "code") -> str:
    """Every cell of one kind, concatenated."""
    return chr(10).join(sources(notebook, kind))


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


def test_the_strategy_is_chosen_from_the_hardware(notebook: dict[str, Any]) -> None:
    """4 GB of VRAM needs 4-bit; a CPU needs fp32. Neither can be assumed."""
    code = joined(notebook)

    assert "torch.cuda.is_available()" in code
    assert "BitsAndBytesConfig" in code
    assert "load_in_4bit=True" in code
    assert "prepare_model_for_kbit_training" in code


def test_the_merge_happens_off_the_gpu(notebook: dict[str, Any]) -> None:
    """A 4-bit model cannot be merged into, and the card has no room anyway."""
    merge_cell = next(s for s in sources(notebook) if "merge_and_unload" in s)

    assert "PeftModel.from_pretrained" in merge_cell
    assert 'device_map="cpu"' in merge_cell
    assert "empty_cache" in merge_cell


def test_nothing_is_uploaded(notebook: dict[str, Any]) -> None:
    """The dataset holds the user's files. It stays on the machine that made it."""
    everything = joined(notebook) + joined(notebook, "markdown")

    for leak in ("google.colab", "files.download", "files.upload", "drive.mount"):
        assert leak not in everything, f"{leak} would move the dataset off this machine"


def test_the_notebook_registers_the_model_with_ollama(notebook: dict[str, Any]) -> None:
    """Local training means no download step: ollama create is a cell."""
    code = joined(notebook)

    assert '"ollama", "create"' in code


def test_the_notebook_finishes_by_running_the_agent(notebook: dict[str, Any]) -> None:
    """Did the pipeline finish is not the question. "Does the agent work" is."""
    code = joined(notebook)

    assert '"main.py"' in code
    assert '"--model"' in code


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


class _RecordingSubprocess:
    """Stands in for subprocess so the cell does not really build a model."""

    def __init__(self) -> None:
        self.calls: list[tuple[list[str], dict[str, Any]]] = []

    def run(self, args: list[str], **kwargs: Any) -> None:
        self.calls.append((list(args), kwargs))


def test_the_modelfile_cell_writes_what_ollama_accepts(
    notebook: dict[str, Any], tmp_path: Path
) -> None:
    """The f-string has to survive Go template braces; execute it and look."""
    cell = next(s for s in sources(notebook) if "modelfile" in s)
    recorder = _RecordingSubprocess()
    namespace: dict[str, Any] = {
        "gguf_path": tmp_path / "model-f16.gguf",
        "OUTPUT_DIR": tmp_path,
        "OUTPUT_NAME": "omniagent-test",
        "OLLAMA_NAME": "omniagent",
        "NUM_CTX": 16384,
        "Path": Path,
        "subprocess": recorder,
    }

    exec(cell, namespace)  # noqa: S102 - executing our own notebook cell is the test
    # Named for the run, so a second training does not overwrite the record of
    # how the first one was registered.
    written = (tmp_path / "Modelfile-omniagent-test").read_text(encoding="utf-8")

    assert written.startswith("FROM ./model-f16.gguf")
    assert "{{ if .System }}" in written
    assert "{{ .Prompt }}" in written
    assert "{{ .Response }}" in written
    assert 'PARAMETER stop "<|im_end|>"' in written
    assert 'PARAMETER stop "Observation:"' in written
    # The f-string must not have leaked doubled braces into the template.
    assert "{{{{" not in written


def test_the_modelfile_cell_registers_the_model(
    notebook: dict[str, Any], tmp_path: Path
) -> None:
    """It must run ollama create beside the GGUF, or the relative FROM breaks."""
    cell = next(s for s in sources(notebook) if "modelfile" in s)
    recorder = _RecordingSubprocess()
    exec(  # noqa: S102 - executing our own notebook cell is the test
        cell,
        {
            "gguf_path": tmp_path / "model-f16.gguf",
            "OUTPUT_DIR": tmp_path,
            "OUTPUT_NAME": "omniagent-test",
            "OLLAMA_NAME": "omniagent",
            "NUM_CTX": 16384,
            "Path": Path,
            "subprocess": recorder,
        },
    )

    assert len(recorder.calls) == 1
    args, kwargs = recorder.calls[0]
    assert args == ["ollama", "create", "omniagent", "-f", "Modelfile-omniagent-test"]
    assert kwargs["cwd"] == tmp_path
    assert kwargs["check"] is True


def test_a_run_can_be_named_without_editing_the_notebook(notebook: dict[str, Any]) -> None:
    """Three days before the demo, a retrain must not land on its model.

    Every path in the notebook derives from OUTPUT_NAME and the demo is pinned
    to the OLLAMA_NAME tag, so a second run with the defaults overwrites both
    the shipped files and the registered model. The defaults stay as they are,
    because this notebook is the record of how that model was built; a run that
    wants different names sets them in the environment instead.
    """
    settings = next(s for s in sources(notebook) if "BASE_MODEL" in s)

    for variable in ("OMNIAGENT_DATASET", "OMNIAGENT_OUTPUT_NAME", "OMNIAGENT_OLLAMA_NAME"):
        assert variable in settings, f"{variable} cannot be overridden"


def test_each_training_run_keeps_its_own_trainer_directory(notebook: dict[str, Any]) -> None:
    """models/runs/ was one directory for every run, so each overwrote the last."""
    training = next(s for s in sources(notebook) if "output_dir=" in s)

    assert 'OUTPUT_DIR / "runs" / OUTPUT_NAME' in training
