"""What prompt a dataset was collected under.

Every training example carries the system prompt in force when it was
recorded, so a dataset is only training data for the prompt it was collected
against. ``read_file``'s description changed in ``58bb801`` and
``data/dataset.jsonl`` predates it, which means the served model was trained
against a prompt it is no longer given. That was found by reading a commit
log. This module is how it gets found by a check instead.

The hash is the one the agent already writes into its ``agent.created``
event, so there is one fingerprint for the prompt and not two that can
disagree.
"""

from __future__ import annotations

import json
from hashlib import sha256
from pathlib import Path
from typing import Any

from agent import SYSTEM_PROMPT_TEMPLATE
from tools import describe_tools, tool_names

#: Appended to the dataset's own name, so the two travel together and a copy
#: that leaves the sidecar behind is detectably unprovenanced.
SIDECAR_SUFFIX = ".provenance.json"


class ProvenanceError(RuntimeError):
    """Raised when a dataset cannot say what prompt it was collected under."""


def render_system_prompt() -> str:
    """The prompt the agent builds, rendered the same way it builds it."""
    return SYSTEM_PROMPT_TEMPLATE.format(tools=describe_tools(), tool_names=tool_names())


def prompt_fingerprint() -> str:
    return sha256(render_system_prompt().encode("utf-8")).hexdigest()


def sidecar_path(dataset: Path) -> Path:
    return dataset.with_name(dataset.name + SIDECAR_SUFFIX)


def write_sidecar(dataset: Path) -> Path:
    """Record the current prompt beside ``dataset``, and say where it went."""
    lines = [line for line in dataset.read_text(encoding="utf-8").splitlines() if line.strip()]
    path = sidecar_path(dataset)
    path.write_text(
        json.dumps(
            {
                "dataset": dataset.name,
                "examples": len(lines),
                "system_prompt_sha256": prompt_fingerprint(),
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    return path


def read_sidecar(dataset: Path) -> dict[str, Any]:
    """The recorded provenance, or an error.

    A missing sidecar is never treated as agreement: a dataset that cannot
    say what prompt it was collected under has not been shown to match the
    prompt in force now.
    """
    path = sidecar_path(dataset)
    if not path.is_file():
        raise ProvenanceError(
            f"no provenance recorded for {dataset.name}: {path.name} is missing, so there is "
            "nothing to compare against the prompt in force now"
        )
    loaded: dict[str, Any] = json.loads(path.read_text(encoding="utf-8"))
    return loaded
