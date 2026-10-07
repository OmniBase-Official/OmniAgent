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



def dataset_fingerprint(dataset: Path) -> str:
    """The digest of the system prompt the dataset itself carries.

    Measured, not claimed. Every example records the prompt in force when the
    turn was logged, and the exporter replays it verbatim as the system turn,
    so the fingerprint can be read out of the file rather than asserted about
    whichever checkout the file happens to be sitting in.

    This is what makes this module's stated purpose reachable. Hashing the
    prompt the code renders today stamps today's fingerprint onto a dataset of
    any age, which cannot detect the one thing worth detecting: data collected
    under a prompt that no longer exists. On the real files the difference is
    the whole point -- ``data/dataset.jsonl`` carries ``ee43a4af...`` in all
    109 of its examples while the live prompt is ``36397f37...``.

    A dataset mixing two prompts is refused rather than reduced to one of
    them: a pooled collection is training data for neither.
    """
    seen: set[str] = set()
    for number, line in enumerate(dataset.read_text(encoding="utf-8").splitlines(), start=1):
        if not line.strip():
            continue
        messages = json.loads(line).get("messages", [])
        prompts = [m["content"] for m in messages if m.get("role") == "system"]
        if not prompts:
            raise ProvenanceError(
                f"{dataset.name} line {number} has no system turn, so it cannot say "
                "which prompt it was collected under"
            )
        seen.update(sha256(prompt.encode("utf-8")).hexdigest() for prompt in prompts)

    if not seen:
        raise ProvenanceError(f"{dataset.name} is empty, so it has no prompt to fingerprint")
    if len(seen) > 1:
        raise ProvenanceError(
            f"{dataset.name} mixes {len(seen)} distinct system prompts "
            f"({', '.join(sorted(h[:12] for h in seen))}), so it is training data for "
            "none of them"
        )
    return seen.pop()


def sidecar_path(dataset: Path) -> Path:
    return dataset.with_name(dataset.name + SIDECAR_SUFFIX)


def write_sidecar(dataset: Path) -> Path:
    """Record beside ``dataset`` which prompt it carries, and say where it went.

    ``system_prompt_sha256`` is the dataset's **own** fingerprint, read out of
    its examples. ``live_prompt_sha256`` is what the code renders now, and
    ``matches_live_prompt`` is the comparison between them -- the question this
    module was written to answer, and the one an earlier version of this
    function could not, because it recorded the live prompt as though it were
    the data's own.
    """
    lines = [line for line in dataset.read_text(encoding="utf-8").splitlines() if line.strip()]
    recorded = dataset_fingerprint(dataset)
    live = prompt_fingerprint()
    path = sidecar_path(dataset)
    path.write_text(
        json.dumps(
            {
                "dataset": dataset.name,
                "examples": len(lines),
                "system_prompt_sha256": recorded,
                "live_prompt_sha256": live,
                "matches_live_prompt": recorded == live,
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
