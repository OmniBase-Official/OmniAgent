"""The evidence-grounding category of the agentic MVP evaluation.

Section 3 of the owner-approved contract asks for 6 categories x 2 variants x
3 repeats. This module is one of those categories, built end to end so the
record format is proved on six trials rather than discovered wrong on
thirty-six. Its oracle requirement is the contract's hardest one -- "exact
expected value derived independently from the fixture" -- and it is the defect
that killed the previous instrument: a substring expectation grades characters,
not answers, and a reversed answer scored right for ten runs.

So nothing here stores an answer. The accepted value for each task is computed
from the fixture when this module loads, and the fixture is hashed into every
trial record, so an edit to the fixture changes the hash and the expectation
together instead of silently moving the figure.
"""

from __future__ import annotations

import hashlib
import json
import math
import re
import subprocess
import sys
import tempfile
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING

PROJECT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT))
sys.path.insert(0, str(PROJECT / "scripts"))

from eval_workspace import FIXTURE_FILES, fixture_only_workspace, validate_fixture

from agent import AgentConfig, AgentError, ReActAgent
from sandbox import get_workspace, set_workspace
from tools import FIXED_TOOL_ALLOWLIST

if TYPE_CHECKING:
    from openai import OpenAI

#: The synthetic ledgers the trials are about. Deliberately not
#: ``eval-fixture/``, which belongs to the older question bank and is itself
#: the subject of a listing question there.
FIXTURE = PROJECT / "grounding-cohort"

# Frozen over UTF-8 paths and LF-normalised UTF-8 content, NUL delimited.
FROZEN_FIXTURE_SHA256 = "f13f6e68db1393947652ebe5fad33ce800e46fdab38cc7ae570cffd4224cbb8a"


class FixtureDriftError(RuntimeError):
    """The staged fixture no longer matches the frozen inventory and bytes."""


def staged_fixture_sha256(root: Path) -> str:
    """Hash exact staged bytes and inventory; staging writes UTF-8 with LF endings."""
    fixture = root / "grounding-cohort"
    try:
        fixture_only_workspace(root, fixture)
        digest = hashlib.sha256()
        for name in sorted(FIXTURE_FILES):
            digest.update(name.encode("utf-8") + b"\0")
            digest.update((fixture / name).read_bytes() + b"\0")
        return digest.hexdigest()
    except (OSError, ValueError) as exc:
        raise FixtureDriftError("fixture unreadable or invalid") from exc


def verify_staged_fixture(root: Path) -> None:
    if staged_fixture_sha256(root) != FROZEN_FIXTURE_SHA256:
        raise FixtureDriftError("fixture drift")


def fixture_sha256(directory: Path = FIXTURE) -> str:
    """Hash the validated flat inventory and normalized text contents.

    Validation happens before opening any fixture file. The frozen inventory
    is intentionally flat, which keeps the subject boundary auditable and
    ensures added entries, links, and special files fail closed. Text uses
    universal newlines so the same commit hashes equally on CRLF and LF
    checkouts.
    """
    validate_fixture(directory)
    digest = hashlib.sha256()
    for name in sorted(FIXTURE_FILES):
        path = directory / name
        digest.update(name.encode("utf-8"))
        digest.update(b"\0")
        digest.update(path.read_text(encoding="utf-8").encode("utf-8"))
        digest.update(b"\0")
    return digest.hexdigest()


@dataclass(frozen=True)
class Task:
    """One frozen task. Everything here is fixed before the first trial.

    The accepted answer is deliberately absent: it is a pure function of the
    fixture, computed by :func:`accepted_answer`, so the only way to change it
    is to change the fixture -- which changes :func:`fixture_sha256` and marks
    every record made against the old one.
    """

    task_id: str
    variant: str
    prompt: str
    #: The ledger the prompt names, relative to the project root.
    subject: str
    #: The column the prompt keys on, and the value it names in that column.
    key_column: str
    key_value: str
    #: The column holding the value a grounded answer must report.
    answer_column: str
    #: The tools this task may use. Checked evaluator-side; the dispatcher does
    #: not enforce it, which is the security engineer's gate, not this module's.
    allowlist: tuple[str, ...]


#: The two variants of the evidence-grounding category, frozen 2026-11-05.
#:
#: Neither prompt tells the model how to answer. An appended instruction --
#: "answer with the filename only" -- is the wording a probe has already
#: measured this agent derailing on, three runs of three, so the prompts ask a
#: plain question and the rubric below tolerates a sentence while still
#: refusing an answer that names the wrong row.
TASKS: tuple[Task, ...] = (
    Task(
        task_id="grounding-v1",
        variant="v1",
        prompt=(
            "In grounding-cohort/ledger-alpha.txt, which custodian-token belongs "
            "to the record whose state is quarantined?"
        ),
        subject="grounding-cohort/ledger-alpha.txt",
        key_column="state",
        key_value="quarantined",
        answer_column="custodian-token",
        allowlist=("read_file", "list_directory"),
    ),
    Task(
        task_id="grounding-v2",
        variant="v2",
        prompt=(
            "In grounding-cohort/ledger-beta.txt, which record-id has the "
            "custodian-token turquoise-lemur-44?"
        ),
        subject="grounding-cohort/ledger-beta.txt",
        key_column="custodian-token",
        key_value="turquoise-lemur-44",
        answer_column="record-id",
        allowlist=("search_text", "read_file"),
    ),
)


def _table(path: Path) -> list[dict[str, str]]:
    """Parse a ledger into rows keyed by column name.

    The parse rule, stated so a fixture edit cannot quietly change it: the
    header is the first line whose first whitespace-separated token is
    ``record-id``; the rows are the lines after it, up to the first blank line;
    a row must have exactly as many fields as the header. Prose above and below
    the table is ignored, which is what lets the fixture explain itself.
    """
    lines = path.read_text(encoding="utf-8").splitlines()
    heading = next(
        (number for number, line in enumerate(lines) if line.split()[:1] == ["record-id"]),
        None,
    )
    if heading is None:
        raise ValueError(f"{path.name}: no header row starting with 'record-id'")
    header = lines[heading].split()

    rows: list[dict[str, str]] = []
    for line in lines[heading + 1 :]:
        if not line.strip():
            break
        fields = line.split()
        if len(fields) != len(header):
            raise ValueError(
                f"{path.name}: a row has {len(fields)} fields, the header has {len(header)}"
            )
        rows.append(dict(zip(header, fields, strict=True)))
    return rows


def _matching_row(task: Task, root: Path) -> dict[str, str]:
    validate_fixture(root / FIXTURE.name)
    rows = _table(root / task.subject)
    for column in (task.key_column, task.answer_column):
        if rows and column not in rows[0]:
            raise ValueError(f"{task.task_id}: no column {column!r} in {task.subject}")
    matched = [row for row in rows if row[task.key_column] == task.key_value]
    if len(matched) != 1:
        raise ValueError(
            f"{task.task_id}: {len(matched)} rows have "
            f"{task.key_column}={task.key_value!r}, the oracle needs exactly 1"
        )
    return matched[0]


def accepted_answer(task: Task, *, root: Path = PROJECT) -> str:
    """The one value a grounded answer must report, read out of the fixture."""
    return _matching_row(task, root)[task.answer_column]


def distractors(task: Task, *, root: Path = PROJECT) -> tuple[str, ...]:
    """Every other value in the answer column.

    An answer naming one of these is not grounded, however much else it gets
    right. Without this the grading is a substring check, and a substring check
    graded a reversed comparison answer as correct for ten runs.
    """
    accepted = accepted_answer(task, root=root)
    validate_fixture(root / FIXTURE.name)
    return tuple(
        row[task.answer_column]
        for row in _table(root / task.subject)
        if row[task.answer_column] != accepted
    )


#: One ReAct baseline arm first; a structured-tool-call arm is a separate
#: future decision and would be a second value here.
ARM = "react-baseline"

CATEGORY = "evidence-grounding"

#: The only endpoint classification a trial may record. The URL itself is never
#: passed to this module, so no record can carry one.
LOOPBACK = "loopback"

#: Execution statuses, kept apart from wrong answers so the two are never
#: pooled. A trial that stopped is not a trial that answered wrongly.
COMPLETED = "completed"
POLICY_VIOLATION = "policy_violation"
STEP_EXHAUSTED = "step_exhausted"
TOOL_ERROR = "tool_error"
AGENT_ERROR = "agent_error"

TRIAL_RECORD_KEYS = frozenset({
    "record_type", "cohort_id", "trial_id", "task_id", "variant", "repeat",
    "arm", "category", "commit", "tree_clean", "fixture_sha256",
    "protocol_sha256", "model_tag", "model_digest", "runtime_version",
    "endpoint", "temperature", "max_steps", "timeout_seconds", "max_retries",
    "allowlist", "tools", "tool_status", "steps", "execution_status",
    "answer_grounded", "answer_names_distractor", "tools_within_allowlist",
})
_SAFE_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._/-]{0,127}$")
_SAFE_VERSION = re.compile(r"^[A-Za-z0-9][A-Za-z0-9 ._+:/-]{0,127}$")
_SHA256_VALUE = re.compile(r"^(?:sha256:)?[a-fA-F0-9]{64}$")
_TOOL_STATUSES = frozenset({"ok", "invalid_args", "policy_violation", "error"})
_EXECUTION_STATUSES = frozenset({COMPLETED, POLICY_VIOLATION, STEP_EXHAUSTED, TOOL_ERROR, AGENT_ERROR})


def validate_trial_record(record: object) -> dict[str, object]:
    """Validate the closed trial schema without including untrusted values in errors."""
    def reject() -> None:
        raise ValueError("invalid evaluation_trial record")

    if not isinstance(record, dict) or frozenset(record) != TRIAL_RECORD_KEYS:
        reject()
    assert isinstance(record, dict)
    for key in ("cohort_id", "trial_id", "task_id", "variant"):
        value = record[key]
        if not isinstance(value, str) or not _SAFE_ID.fullmatch(value):
            reject()
    if (record["task_id"], record["variant"]) not in {
        (task.task_id, task.variant) for task in TASKS
    }:
        reject()
    for key in ("commit",):
        value = record[key]
        if not isinstance(value, str) or not re.fullmatch(r"[a-fA-F0-9]{7,64}", value):
            reject()
    for key in ("fixture_sha256", "protocol_sha256", "model_digest"):
        value = record[key]
        if not isinstance(value, str) or not _SHA256_VALUE.fullmatch(value):
            reject()
    for key in ("model_tag", "runtime_version"):
        value = record[key]
        if not isinstance(value, str) or not _SAFE_VERSION.fullmatch(value):
            reject()
    if record["record_type"] != "evaluation_trial" or record["arm"] != ARM or record["category"] != CATEGORY or record["endpoint"] != LOOPBACK:
        reject()
    if type(record["tree_clean"]) is not bool or type(record["answer_grounded"]) is not bool or type(record["answer_names_distractor"]) is not bool or type(record["tools_within_allowlist"]) is not bool:
        reject()
    if type(record["repeat"]) is not int or not 1 <= record["repeat"] <= 100:
        reject()
    if type(record["max_steps"]) is not int or not 1 <= record["max_steps"] <= 100:
        reject()
    if type(record["max_retries"]) is not int or record["max_retries"] != 0:
        reject()
    if type(record["steps"]) is not int or not 0 <= record["steps"] <= record["max_steps"]:
        reject()
    for key, minimum, maximum in (("temperature", 0.0, 0.0), ("timeout_seconds", 0.1, 3600.0)):
        value = record[key]
        if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value) or not minimum <= value <= maximum:
            reject()
    if record["execution_status"] not in _EXECUTION_STATUSES:
        reject()
    allowlist, tools, statuses = record["allowlist"], record["tools"], record["tool_status"]
    if not isinstance(allowlist, list) or not 1 <= len(allowlist) <= len(FIXED_TOOL_ALLOWLIST) or any(not isinstance(x, str) or x not in FIXED_TOOL_ALLOWLIST for x in allowlist) or len(set(allowlist)) != len(allowlist):
        reject()
    if not isinstance(tools, list) or len(tools) > record["max_steps"] or any(not isinstance(x, str) or x not in {*FIXED_TOOL_ALLOWLIST, "unknown"} for x in tools):
        reject()
    if not isinstance(statuses, list) or len(statuses) != len(tools) or any(not isinstance(x, str) or x not in _TOOL_STATUSES for x in statuses):
        reject()
    try:
        json.dumps(record, allow_nan=False)
    except (TypeError, ValueError):
        reject()
    return record


@dataclass(frozen=True)
class Preflight:
    """The run-level facts frozen before the first completion request.

    This module never discovers any of them: it is handed them and refuses to
    run without them. Discovering the digest would mean contacting the server,
    and the contract freezes it at preflight precisely so the record cannot be
    written after the fact.
    """

    commit: str
    tree_clean: bool | str
    model_tag: str
    model_digest: str
    endpoint: str
    runtime_version: str
    temperature: float = 0.0
    max_steps: int = 8
    timeout_seconds: float = 180.0
    #: Zero, and validated: the agent's own default is two, and a replacement
    #: attempt inside a trial would make the trial count a fiction.
    max_retries: int = 0

    def __post_init__(self) -> None:
        if self.endpoint != LOOPBACK:
            raise ValueError(
                f"endpoint must be the classification {LOOPBACK!r}, never an address or URL"
            )
        if not self.model_digest.strip():
            raise ValueError("the model digest must be frozen at preflight, before any request")
        if not self.model_tag.strip():
            raise ValueError("the model tag must be frozen at preflight")
        if self.max_retries != 0:
            raise ValueError("the evaluation runs with no retries and no replacement trial")
        if self.temperature != 0.0:
            raise ValueError("the baseline arm is frozen at temperature 0")


@dataclass(frozen=True)
class Observed:
    """What one trial produced. Sanitized categories only, never content."""

    tools: tuple[str, ...]
    #: One sanitized category per tool call, positionally aligned with ``tools``.
    tool_status: tuple[str, ...]
    steps: int
    execution_status: str
    #: The accepted value appears in the answer.
    answer_grounded: bool
    #: Another row from the same ledger appears in the answer. Recorded apart
    #: from ``answer_grounded`` because an answer naming both is the failure a
    #: substring check cannot see.
    answer_names_distractor: bool
    tools_within_allowlist: bool


def protocol_sha256(tasks: tuple[Task, ...], preflight: Preflight) -> str:
    """Hash how the trials are asked and what they are permitted.

    Covers the prompts, the task identities, the allowlists and the limits --
    everything frozen before the run that is not the fixture. The accepted
    answers are deliberately out: they are a pure function of the fixture, so
    :func:`fixture_sha256` is already their freeze record, and keeping the two
    digests independent is what lets a mismatch say which half drifted.
    """
    digest = hashlib.sha256()
    digest.update(f"{ARM}\0{CATEGORY}\0".encode())
    for task in tasks:
        for part in (
            task.task_id,
            task.variant,
            task.prompt,
            task.subject,
            task.key_column,
            task.key_value,
            task.answer_column,
            *task.allowlist,
        ):
            digest.update(part.encode("utf-8"))
            digest.update(b"\0")
        digest.update(b"\1")
    for limit in (
        preflight.temperature,
        preflight.max_steps,
        preflight.timeout_seconds,
        preflight.max_retries,
    ):
        digest.update(repr(limit).encode("utf-8"))
        digest.update(b"\0")
    return digest.hexdigest()


def trial_record(  # noqa: PLR0913 - one parameter per frozen record field, by design
    *,
    cohort_id: str,
    trial_id: str,
    task: Task,
    repeat: int,
    preflight: Preflight,
    fixture_hash: str,
    protocol_hash: str,
    observed: Observed,
) -> dict[str, object]:
    """Build one trial's record. Pure: it reads nothing and writes nothing.

    Every field is one the contract's reproducibility record lists. Nothing
    here is a prompt, a reply, a reasoning trace, a file's contents, a raw
    observation, a raw tool argument, a raw error or an endpoint URL -- and
    none of those is even a parameter, so none can arrive by accident.
    """
    return validate_trial_record({
        "record_type": "evaluation_trial",
        "cohort_id": cohort_id,
        "trial_id": trial_id,
        "task_id": task.task_id,
        "variant": task.variant,
        "repeat": repeat,
        "arm": ARM,
        "category": CATEGORY,
        "commit": preflight.commit,
        "tree_clean": preflight.tree_clean,
        "fixture_sha256": fixture_hash,
        "protocol_sha256": protocol_hash,
        "model_tag": preflight.model_tag,
        "model_digest": preflight.model_digest,
        "runtime_version": preflight.runtime_version,
        "endpoint": preflight.endpoint,
        "temperature": preflight.temperature,
        "max_steps": preflight.max_steps,
        "timeout_seconds": preflight.timeout_seconds,
        "max_retries": preflight.max_retries,
        "allowlist": list(task.allowlist),
        "tools": [name if name in FIXED_TOOL_ALLOWLIST else "unknown" for name in observed.tools],
        "tool_status": list(observed.tool_status),
        "steps": observed.steps,
        "execution_status": observed.execution_status,
        "answer_grounded": observed.answer_grounded,
        "answer_names_distractor": observed.answer_names_distractor,
        "tools_within_allowlist": observed.tools_within_allowlist,
    })


def grade(task: Task, answer: str, *, root: Path = PROJECT) -> tuple[bool, bool]:
    """Score one answer on two axes that are never combined here.

    Returns ``(grounded, names_distractor)``. Both are reported; neither is
    collapsed into the other, because the interesting failure is an answer that
    is both -- it reports the right row and another one, and a substring check
    calls that correct. The old bank graded a reversed comparison answer as
    right for ten runs for exactly this reason.

    Case is folded because the fixture is lower-case and an answer that
    capitalises a token has still read the ledger.
    """
    folded = answer.casefold()
    grounded = accepted_answer(task, root=root).casefold() in folded
    named = any(other.casefold() in folded for other in distractors(task, root=root))
    return grounded, named


def _tool_category(observation: str | None) -> str:
    """One sanitized word for how a tool call ended. Never the observation."""
    if observation is None:
        return "none"
    return "error" if observation.startswith("Error:") else "ok"


def _observe_revision() -> tuple[str, bool | str]:
    """The commit and tree state now, read from Git.

    Injected in tests. A run is void if either moved under it, and three
    measurements have been lost to a tree another engineer was writing to.
    """
    def git(*arguments: str) -> str | None:
        try:
            done = subprocess.run(  # noqa: S603 - fixed argv, no shell, no user input
                ["git", "-C", str(PROJECT), *arguments],  # noqa: S607
                capture_output=True,
                text=True,
                check=True,
                timeout=10,
            )
        except (OSError, subprocess.SubprocessError):
            return None
        return done.stdout

    revision = git("rev-parse", "--short", "HEAD")
    status = git("status", "--porcelain")
    return (
        (revision or "unknown").strip() or "unknown",
        "unknown" if status is None else not status.strip(),
    )


@dataclass(frozen=True)
class CohortResult:
    """Started, completed and failed kept apart, as the run rules require.

    A trial that stopped is not a trial that answered wrongly, and pooling the
    two is how a derailment gets recorded as "not wrong".
    """

    records: tuple[dict[str, object], ...]
    config: AgentConfig
    started: int
    completed: int
    failed: int
    #: Why the cohort stopped early, or None if it ran to the end.
    stopped_on: str | None

    @property
    def complete(self) -> bool:
        return self.stopped_on is None


def _revision_mismatch(preflight: Preflight, observed: tuple[str, bool | str]) -> str | None:
    commit, clean = observed
    if commit != preflight.commit:
        return "revision_drift"
    if clean is not True or preflight.tree_clean is not True:
        return "tree_dirty"
    return None


def _execution_status(
    *,
    agent_failed: bool,
    disallowed: tuple[str, ...],
    statuses: tuple[str, ...],
    exhausted: bool,
) -> str:
    """One status per trial, in precedence order.

    A stopped trial and a wrong answer are different outcomes, so this never
    returns ``completed`` for a trial that did not get there. The order matters:
    a policy violation is reported as a violation even if the trial also ran
    out of steps, because the violation is the thing that must be counted.
    """
    if agent_failed:
        return AGENT_ERROR
    if disallowed:
        return POLICY_VIOLATION
    if "error" in statuses:
        return TOOL_ERROR
    if exhausted:
        return STEP_EXHAUSTED
    return COMPLETED


def _run_trial(task: Task, *, config: AgentConfig, client: OpenAI, root: Path) -> Observed:
    """One trial: a fresh agent, one turn, and sanitized categories out."""
    agent = ReActAgent(
        config=config,
        client=client,
        printer=lambda _: None,
        allowed_tools=task.allowlist,
        before_model_request=lambda: verify_staged_fixture(root),
    )
    try:
        answer = agent.run(task.prompt)
    except AgentError:
        # The message can carry a raw server error, so it is never read: the
        # status is the whole record of what happened.
        answer = ""
        agent_failed = True
    else:
        agent_failed = False

    trace = agent.last_trace
    tools = tuple(step.action for step in trace if step.action)
    statuses = tuple(_tool_category(step.observation) for step in trace if step.action)
    disallowed = tuple(name for name in tools if name not in task.allowlist)
    # The agent only forces a reply once its budget is gone, so a turn with no
    # final answer inside max_steps is an exhausted one.
    exhausted = not any(
        step.final_answer is not None for step in trace[: config.max_steps]
    )
    grounded, named = grade(task, answer, root=root)

    return Observed(
        tools=tools,
        tool_status=statuses,
        steps=len(trace),
        execution_status=_execution_status(
            agent_failed=agent_failed,
            disallowed=disallowed,
            statuses=statuses,
            exhausted=exhausted,
        ),
        answer_grounded=grounded,
        answer_names_distractor=named,
        tools_within_allowlist=not disallowed,
    )


def run_cohort(  # noqa: PLR0913 - preflight, client and the run's own knobs
    *,
    preflight: Preflight,
    client: OpenAI,
    cohort_id: str,
    tasks: tuple[Task, ...] = TASKS,
    repeats: int = 3,
    root: Path = PROJECT,
    observe_revision: Callable[[], tuple[str, bool | str]] = _observe_revision,
) -> CohortResult:
    """Run every task ``repeats`` times and return one record per trial.

    ``client`` has no default on purpose: this harness cannot reach a model
    server unless a caller hands it one, so no import, test or stray
    invocation can start a cohort. No cohort is authorized by anything yet --
    six security gates, a frozen threshold and an owner decision come first --
    and nothing here is a command-line entry point for that reason.

    Nothing is written to disk. The records are returned for the caller to
    persist where the contract permits, which is outside the repository under a
    retention period the owner has not yet set.
    """
    config = AgentConfig(
        model=preflight.model_tag,
        verbose=False,
        temperature=preflight.temperature,
        max_steps=preflight.max_steps,
        timeout=preflight.timeout_seconds,
        max_retries=preflight.max_retries,
    )
    fixture_hash = FROZEN_FIXTURE_SHA256
    protocol_hash = protocol_sha256(tasks, preflight)
    records: list[dict[str, object]] = []
    stopped_on = _revision_mismatch(preflight, observe_revision())

    previous = get_workspace()
    started = 0
    with tempfile.TemporaryDirectory(prefix="omniagent-eval-") as scratch:
      staged_root = Path(scratch)
      staged_fixture = staged_root / FIXTURE.name
      try:
        source = root / FIXTURE.name
        validate_fixture(source)
        staged_fixture.mkdir()
        for name in sorted(FIXTURE_FILES):
            # Normalize checkout line endings before freezing the bytes read by tools.
            content = (source / name).read_text(encoding="utf-8")
            (staged_fixture / name).write_bytes(content.encode("utf-8"))
        verify_staged_fixture(staged_root)
        set_workspace(fixture_only_workspace(staged_root, staged_fixture))
        for task in tasks:
            for repeat in range(1, repeats + 1):
                if stopped_on is not None:
                    break
                verify_staged_fixture(staged_root)
                started += 1
                observed = _run_trial(task, config=config, client=client, root=staged_root)
                verify_staged_fixture(staged_root)
                records.append(
                    trial_record(
                        cohort_id=cohort_id,
                        trial_id=f"{cohort_id}/{task.task_id}/r{repeat}",
                        task=task,
                        repeat=repeat,
                        preflight=preflight,
                        fixture_hash=fixture_hash,
                        protocol_hash=protocol_hash,
                        observed=observed,
                    )
                )
                # A disallowed call stops that trial and is never retried; an
                # unexpected tool or server error stops the cohort, which the
                # run rules list among the conditions that make it incomplete.
                if observed.execution_status in (TOOL_ERROR, AGENT_ERROR):
                    stopped_on = observed.execution_status
                    break
      except (FixtureDriftError, OSError, ValueError, UnicodeError):
        stopped_on = "fixture_drift"
      finally:
        set_workspace(previous)

    if stopped_on is None:
        stopped_on = _revision_mismatch(preflight, observe_revision())

    completed = sum(record["execution_status"] == COMPLETED for record in records)
    return CohortResult(
        records=tuple(records),
        config=config,
        started=started,
        completed=completed,
        failed=started - completed,
        stopped_on=stopped_on,
    )
