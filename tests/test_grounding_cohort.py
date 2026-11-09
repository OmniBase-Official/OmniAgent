"""The evidence-grounding category: a derived oracle and a record that carries no answers.

One category, built end to end, so the record format is proved before
thirty-six trials are spent on it. Every test here runs on an injected fake
client; nothing in this module may reach a model server.
"""

from __future__ import annotations

import json
import secrets as secrets_module
import shutil
import subprocess
import sys
from collections.abc import Callable
from dataclasses import replace
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

import grounding_cohort as cohort_module
import pytest
from eval_workspace import fixture_only_workspace
from grounding_cohort import (
    ARM,
    FIXTURE,
    TASKS,
    Observed,
    Preflight,
    Task,
    _opaque_identifier,
    accepted_answer,
    distractors,
    fixture_sha256,
    protocol_sha256,
    run_cohort,
    trial_record,
)

import agent as agent_module
import tools as tools_module
from sandbox import SandboxError, get_workspace
from tests.fakes import FakeOpenAI


def _copy_fixture(destination: Path) -> Path:
    """A writable copy, so a mutation test never edits the real fixture."""
    copy = destination / FIXTURE.name
    shutil.copytree(FIXTURE, copy)
    return copy


# --------------------------------------------------------------------------- #
# the fixture hash
# --------------------------------------------------------------------------- #


def test_the_fixture_hash_changes_when_any_fixture_byte_changes(tmp_path: Path) -> None:
    copy = _copy_fixture(tmp_path)
    before = fixture_sha256(copy)

    ledger = copy / "ledger-alpha.txt"
    ledger.write_text(ledger.read_text(encoding="utf-8") + "trailing\n", encoding="utf-8")

    assert fixture_sha256(copy) != before


def test_the_fixture_hash_changes_when_a_file_is_added(tmp_path: Path) -> None:
    """An expanded inventory is drift, and is rejected before it is hashed."""
    copy = _copy_fixture(tmp_path)
    (copy / "ledger-gamma.txt").write_text("another ledger\n", encoding="utf-8")

    with pytest.raises(ValueError, match="fixture inventory"):
        fixture_sha256(copy)


def test_the_fixture_hash_changes_when_a_file_is_renamed(tmp_path: Path) -> None:
    copy = _copy_fixture(tmp_path)
    (copy / "ledger-beta.txt").rename(copy / "ledger-delta.txt")

    with pytest.raises(ValueError, match="fixture inventory"):
        fixture_sha256(copy)


def test_fixture_hash_rejects_links_before_opening_fixture_files(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    copy = _copy_fixture(tmp_path)
    target = copy / "ledger-alpha.txt"
    target.unlink()
    outside = tmp_path / "outside.txt"
    outside.write_text("OUTSIDE_CANARY", encoding="utf-8")
    try:
        target.symlink_to(outside)
    except OSError as exc:
        if sys.platform == "win32":
            pytest.skip(f"Windows symlink privilege or Developer Mode unavailable: {exc}")
        raise

    def fail_if_read(*_args: Any, **_kwargs: Any) -> str:
        pytest.fail("fixture files must not be read before link validation")

    monkeypatch.setattr(Path, "read_text", fail_if_read)
    with pytest.raises(ValueError, match="links and reparse points"):
        fixture_sha256(copy)


def test_the_fixture_hash_ignores_the_line_ending_the_checkout_happens_to_use(
    tmp_path: Path,
) -> None:
    """This repository has core.autocrlf=true and no .gitattributes.

    The same commit therefore yields CRLF bytes on this machine and LF bytes on
    a Linux checkout. A hash over raw bytes would report fixture drift that is
    only a checkout difference, so the digest is taken over text with newlines
    normalised -- the same view the oracle reads the fixture through.
    """
    crlf = tmp_path / "crlf"
    lf = tmp_path / "lf"
    crlf.mkdir()
    lf.mkdir()
    for source in sorted(FIXTURE.iterdir()):
        text = source.read_text(encoding="utf-8")
        (crlf / source.name).write_bytes(text.replace("\n", "\r\n").encode("utf-8"))
        (lf / source.name).write_bytes(text.encode("utf-8"))

    assert fixture_sha256(crlf) == fixture_sha256(lf)


def test_the_real_fixture_hashes_to_the_same_value_twice() -> None:
    assert fixture_sha256(FIXTURE) == fixture_sha256(FIXTURE)


# --------------------------------------------------------------------------- #
# the oracle: derived at load time, never stored
# --------------------------------------------------------------------------- #


def test_every_task_derives_its_accepted_answer_from_the_fixture(tmp_path: Path) -> None:
    """Ma's test. Edit the ledger and the accepted answer follows it.

    A written-down answer is wrong the moment the fixture is edited, and the
    figure then falls for a reason that is not the model.
    """
    copy = _copy_fixture(tmp_path)
    for task in TASKS:
        before = accepted_answer(task, root=tmp_path)
        subject = tmp_path / task.subject
        subject.write_text(
            subject.read_text(encoding="utf-8").replace(before, "relabelled-token-01"),
            encoding="utf-8",
        )

        assert accepted_answer(task, root=tmp_path) == "relabelled-token-01"
        assert accepted_answer(task, root=tmp_path) != before
    assert copy.is_dir()


def test_the_oracle_refuses_a_fixture_with_two_matching_rows(tmp_path: Path) -> None:
    """``sorted(...)[0]`` quietly picking one is how an oracle starts lying."""
    _copy_fixture(tmp_path)
    task = TASKS[0]
    subject = tmp_path / task.subject
    rows = subject.read_text(encoding="utf-8")
    subject.write_text(rows.replace("asset-7734    amber-pangolin-77      active",
                                    "asset-7734    amber-pangolin-77      quarantined"),
                       encoding="utf-8")

    with pytest.raises(ValueError, match="2 rows"):
        accepted_answer(task, root=tmp_path)


def test_the_oracle_refuses_a_fixture_with_no_matching_row(tmp_path: Path) -> None:
    _copy_fixture(tmp_path)
    task = TASKS[0]
    subject = tmp_path / task.subject
    subject.write_text(
        subject.read_text(encoding="utf-8").replace("quarantined", "active"),
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="0 rows"):
        accepted_answer(task, root=tmp_path)


def test_the_oracle_refuses_a_fixture_whose_column_was_renamed(tmp_path: Path) -> None:
    _copy_fixture(tmp_path)
    task = TASKS[0]
    subject = tmp_path / task.subject
    subject.write_text(
        subject.read_text(encoding="utf-8").replace("custodian-token", "holder-token"),
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="column"):
        accepted_answer(task, root=tmp_path)


def test_the_distractors_are_the_other_values_in_the_same_column() -> None:
    """What makes the grading an answer check instead of a character check.

    The old bank scored a comparison by whether a filename appeared, so an
    answer naming both files scored right whichever way round it was. Here an
    answer that also names another ledger row fails.
    """
    for task in TASKS:
        accepted = accepted_answer(task)
        others = distractors(task)

        assert accepted not in others
        assert len(others) >= 4
        assert all(other and other != accepted for other in others)


def test_no_accepted_answer_is_written_down_in_this_category_source() -> None:
    """The second way this brief could be wrong: an oracle that stores its answer."""
    sources = {
        "scripts/grounding_cohort.py": (FIXTURE.parent / "scripts" / "grounding_cohort.py"),
        "tests/test_grounding_cohort.py": Path(__file__).resolve(),
    }
    carried: dict[str, list[str]] = {}
    for shown, path in sources.items():
        blob = path.read_text(encoding="utf-8")
        found = sorted(
            accepted_answer(task) for task in TASKS if accepted_answer(task) in blob
        )
        if found:
            carried[shown] = found

    assert carried == {}, f"an accepted answer is written down here: {carried}"


# --------------------------------------------------------------------------- #
# the trial record
# --------------------------------------------------------------------------- #


def _preflight(**overrides: object) -> Preflight:
    """The frozen run-level facts. A real run gets these from preflight."""
    values: dict[str, object] = {
        "commit": "87a1297",
        "tree_clean": True,
        "model_tag": "omniagent-v2",
        "model_digest": "sha256:" + "0" * 64,
        "endpoint": "loopback",
        "runtime_version": "ollama 0.0.0-fixture",
    }
    values.update(overrides)
    return Preflight(**values)  # type: ignore[arg-type]


def _observed(**overrides: object) -> Observed:
    values: dict[str, object] = {
        "tools": ("read_file",),
        "tool_status": ("ok",),
        "steps": 2,
        "execution_status": "completed",
        "answer_grounded": True,
        "answer_names_distractor": False,
        "tools_within_allowlist": True,
    }
    values.update(overrides)
    return Observed(**values)  # type: ignore[arg-type]


_RECORD_KEY = b"test-record-key-that-is-at-least-32-bytes"


def test_the_trial_record_carries_every_field_the_contract_lists(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Me's test. Drop any field named here and this fails.

    The contract's reproducibility record, asserted as an exact dictionary so a
    missing field cannot pass as an absent one. The clean-tree field is in here
    because a run record once carried the commit and not the tree, and a void
    run pooled with ten good ones for want of it.
    """
    monkeypatch.setattr(secrets_module, "token_bytes", lambda _: _RECORD_KEY)
    cohort_hmac = _opaque_identifier("cohort-fixture", _RECORD_KEY)
    record = trial_record(
        cohort_id="cohort-fixture",
        task=TASKS[0],
        repeat=1,
        preflight=_preflight(),
        fixture_hash="f" * 64,
        protocol_hash="e" * 64,
        observed=_observed(),
    )

    assert record == {
        "record_type": "evaluation_trial",
        "cohort_id_hmac_sha256": cohort_hmac,
        "trial_id": f"{cohort_hmac}/grounding-v1/r1",
        "task_id": "grounding-v1",
        "variant": "v1",
        "repeat": 1,
        "arm": ARM,
        "category": "evidence-grounding",
        "commit": "87a1297",
        "tree_clean": True,
        "fixture_sha256": "f" * 64,
        "protocol_sha256": "e" * 64,
        "model_tag_hmac_sha256": _opaque_identifier("omniagent-v2", _RECORD_KEY),
        "model_digest_hmac_sha256": _opaque_identifier(
            "sha256:" + "0" * 64, _RECORD_KEY
        ),
        "runtime_version_hmac_sha256": _opaque_identifier(
            "ollama 0.0.0-fixture", _RECORD_KEY
        ),
        "endpoint": "loopback",
        "temperature": 0.0,
        "max_steps": 8,
        "timeout_seconds": 180.0,
        "max_retries": 0,
        "allowlist": ["read_file", "list_directory"],
        "tools": ["read_file"],
        "tool_status": ["ok"],
        "steps": 2,
        "execution_status": "completed",
        "answer_grounded": True,
        "answer_names_distractor": False,
        "tools_within_allowlist": True,
    }


@pytest.mark.parametrize(
    "field",
    [
        "cohort_id",
        "task_id",
        "variant",
        "prompt",
        "subject",
        "key_column",
        "key_value",
        "answer_column",
        "commit",
        "tree_clean",
        "model_tag",
        "model_digest",
        "runtime_version",
        "endpoint",
        "fixture_sha256",
        "protocol_sha256",
        "allowlist",
        "tool_status",
        "execution_status",
    ],
)
def test_record_canary_rejection_matrix(  # noqa: PLR0912
    field: str,
) -> None:
    canary = "RAW SECRET\nCANARY"
    cohort_id = "cohort-fixture"
    task = TASKS[0]
    preflight = _preflight()
    observed = _observed()
    fixture_hash = "f" * 64
    protocol_hash = "e" * 64

    if field == "cohort_id":
        cohort_id = canary
    elif field == "task_id":
        task = replace(task, task_id=canary)
    elif field == "variant":
        task = replace(task, variant=canary)
    elif field == "prompt":
        task = replace(task, prompt=canary)
    elif field == "subject":
        task = replace(task, subject=canary)
    elif field == "key_column":
        task = replace(task, key_column=canary)
    elif field == "key_value":
        task = replace(task, key_value=canary)
    elif field == "answer_column":
        task = replace(task, answer_column=canary)
    elif field == "allowlist":
        task = replace(task, allowlist=(canary,))
    elif field == "commit":
        preflight = _preflight(commit=canary)
    elif field == "tree_clean":
        preflight = _preflight(tree_clean=canary)
    elif field == "model_tag":
        preflight = _preflight(model_tag=canary)
    elif field == "model_digest":
        preflight = _preflight(model_digest=canary)
    elif field == "runtime_version":
        preflight = _preflight(runtime_version=canary)
    elif field == "endpoint":
        object.__setattr__(preflight, "endpoint", canary)
    elif field == "fixture_sha256":
        fixture_hash = canary
    elif field == "protocol_sha256":
        protocol_hash = canary
    elif field == "tool_status":
        observed = _observed(tool_status=(canary,))
    else:
        observed = _observed(execution_status=canary)

    with pytest.raises(
        ValueError, match="evaluation trial record violates the approved schema"
    ) as error:
        trial_record(
            cohort_id=cohort_id,
            task=task,
            repeat=1,
            preflight=preflight,
            fixture_hash=fixture_hash,
            protocol_hash=protocol_hash,
            observed=observed,
        )

    assert canary not in str(error.value)


@pytest.mark.parametrize(
    "field",
    ["prompt", "subject", "key_column", "key_value", "answer_column"],
)
def test_run_cohort_rejects_noncanonical_task_before_model_request(
    field: str,
) -> None:
    task = TASKS[0]
    if field == "prompt":
        task = replace(task, prompt="token-abc123")
    elif field == "subject":
        task = replace(task, subject="token-abc123")
    elif field == "key_column":
        task = replace(task, key_column="token-abc123")
    elif field == "key_value":
        task = replace(task, key_value="token-abc123")
    else:
        task = replace(task, answer_column="token-abc123")
    fake = FakeOpenAI(replies=["Final Answer: must not run"])

    with pytest.raises(
        ValueError, match="evaluation trial record violates the approved schema"
    ):
        run_cohort(
            preflight=_preflight(),
            client=fake.as_client(),
            cohort_id="canonical-task-check",
            tasks=(task,),
            repeats=1,
            observe_revision=_fixed_revision(),
        )

    assert fake.calls == []


@pytest.mark.parametrize(
    "repeats",
    [0, -1, cohort_module._MAX_REPEATS + 1, True],
)
def test_run_cohort_rejects_invalid_repeat_count_before_model_request(
    repeats: int,
) -> None:
    fake = FakeOpenAI(replies=["Final Answer: must not run"])

    with pytest.raises(
        ValueError, match="evaluation trial record violates the approved schema"
    ):
        run_cohort(
            preflight=_preflight(),
            client=fake.as_client(),
            cohort_id="repeat-bound-check",
            tasks=(TASKS[0],),
            repeats=repeats,
            observe_revision=_fixed_revision(),
        )

    assert fake.calls == []


@pytest.mark.parametrize(
    "tasks",
    [(), (TASKS[0], TASKS[0])],
    ids=["empty", "duplicate-task-id"],
)
def test_run_cohort_rejects_empty_or_duplicate_task_inventory_before_model_request(
    tasks: tuple[Task, ...],
) -> None:
    fake = FakeOpenAI(replies=["Final Answer: must not run"])

    with pytest.raises(
        ValueError, match="evaluation trial record violates the approved schema"
    ):
        run_cohort(
            preflight=_preflight(),
            client=fake.as_client(),
            cohort_id="inventory-check",
            tasks=tasks,
            repeats=1,
            observe_revision=_fixed_revision(),
        )

    assert fake.calls == []


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("commit", "bad commit canary"),
        ("tree_clean", 1),
        ("model_tag", "RAW SECRET\nCANARY"),
        ("model_digest", "bad digest canary"),
        ("runtime_version", "bad runtime\ncanary"),
        ("max_steps", 0),
        ("timeout_seconds", 0),
    ],
)
def test_run_cohort_rejects_invalid_preflight_before_model_request(
    field: str, value: object
) -> None:
    fake = FakeOpenAI(replies=["Final Answer: must not run"])

    with pytest.raises(
        ValueError, match="evaluation trial record violates the approved schema"
    ):
        run_cohort(
            preflight=_preflight(**{field: value}),
            client=fake.as_client(),
            cohort_id="preflight-check",
            tasks=(TASKS[0],),
            repeats=1,
            observe_revision=_fixed_revision(),
        )

    assert fake.calls == []


def test_trial_record_accepts_only_bounded_identifier_formats() -> None:
    cohort_id = "review-run-7"
    preflight = _preflight(
        commit="a" * 40,
        model_tag="omniagent-v2:latest",
        runtime_version="ollama 0.12.3",
    )
    record = trial_record(
        cohort_id=cohort_id,
        task=TASKS[0],
        repeat=1,
        preflight=preflight,
        fixture_hash="f" * 64,
        protocol_hash="e" * 64,
        observed=_observed(),
    )

    trial_id = record["trial_id"]
    assert isinstance(trial_id, str)
    assert trial_id.split("/")[0] == record["cohort_id_hmac_sha256"]
    assert record["commit"] == "a" * 40
    assert "omniagent-v2:latest" not in json.dumps(record)
    assert "ollama 0.12.3" not in json.dumps(record)


def test_trial_record_pseudonymizes_well_formed_caller_identifiers() -> None:
    cohort_id = "private-run-identifier-123"
    model_tag = "token-abc123"
    runtime_version = "ollama 0.12.3 secret456"
    model_digest = "sha256:" + "a" * 64
    preflight = _preflight(
        model_tag=model_tag,
        model_digest=model_digest,
        runtime_version=runtime_version,
    )
    record = trial_record(
        cohort_id=cohort_id,
        task=TASKS[0],
        repeat=1,
        preflight=preflight,
        fixture_hash="f" * 64,
        protocol_hash="e" * 64,
        observed=_observed(),
    )

    serialized = json.dumps(record)
    for raw_value in (cohort_id, model_tag, model_digest, runtime_version):
        assert raw_value not in serialized
    trial_id = record["trial_id"]
    model_digest_hmac = record["model_digest_hmac_sha256"]
    assert isinstance(trial_id, str)
    assert isinstance(model_digest_hmac, str)
    assert trial_id.split("/")[0] == record["cohort_id_hmac_sha256"]
    assert len(model_digest_hmac) == 64


def test_trial_record_normalizes_untrusted_tool_name_in_serialized_output() -> None:
    canary = "RAW_SECRET_CANARY"
    cohort_id = "cohort-fixture"
    record = trial_record(
        cohort_id=cohort_id,
        task=TASKS[0],
        repeat=1,
        preflight=_preflight(),
        fixture_hash="f" * 64,
        protocol_hash="e" * 64,
        observed=_observed(tools=(canary,)),
    )
    serialized = json.dumps(record)

    assert record["tools"] == ["unknown"]
    assert canary not in serialized


def test_the_trial_record_carries_no_prompt_answer_content_or_url() -> None:
    """Mc's test. Add the prompt to the record and this fails.

    Checked over the serialised record rather than its keys, so a forbidden
    value smuggled inside an allowed field fails too.
    """
    record = trial_record(
        cohort_id="cohort-fixture",
        task=TASKS[1],
        repeat=3,
        preflight=_preflight(),
        fixture_hash=fixture_sha256(),
        protocol_hash=protocol_sha256(TASKS, _preflight()),
        observed=_observed(tools=("search_text",)),
    )
    blob = json.dumps(record)

    for task in TASKS:
        assert task.prompt not in blob
        assert accepted_answer(task) not in blob
        for distractor in distractors(task):
            assert distractor not in blob
    assert "http" not in blob
    assert "localhost" not in blob
    assert "11434" not in blob
    assert not {
        "prompt",
        "question",
        "system_prompt",
        "reasoning",
        "thought",
        "reply",
        "answer",
        "observation",
        "action_input",
        "error",
        "base_url",
        "url",
        "endpoint_url",
        "expect",
        "expected",
    } & record.keys()


def test_the_record_can_never_be_handed_an_endpoint_url() -> None:
    """The record cannot leak a URL because it is never given one."""
    with pytest.raises(ValueError, match="loopback"):
        _preflight(endpoint="http://localhost:11434/v1")
    with pytest.raises(ValueError, match="loopback"):
        _preflight(endpoint="127.0.0.1:11434")


def test_a_run_without_a_frozen_model_digest_is_refused() -> None:
    """The contract freezes the digest at preflight, before any request."""
    with pytest.raises(ValueError, match="digest"):
        _preflight(model_digest="")


def test_the_evaluation_refuses_a_retry_policy_above_zero() -> None:
    """No automatic retries and no replacement trial, per the run rules.

    The agent's own default is two, which is why this is asserted rather than
    assumed.
    """
    with pytest.raises(ValueError, match="retr"):
        _preflight(max_retries=1)


def test_the_protocol_hash_moves_when_a_prompt_moves() -> None:
    reworded = (
        replace(TASKS[0], prompt=TASKS[0].prompt + " Answer with the token only."),
        TASKS[1],
    )

    assert protocol_sha256(reworded, _preflight()) != protocol_sha256(TASKS, _preflight())


def test_the_protocol_hash_moves_when_an_allowlist_or_a_limit_moves() -> None:
    widened = (replace(TASKS[0], allowlist=("read_file", "search_text")), TASKS[1])

    assert protocol_sha256(widened, _preflight()) != protocol_sha256(TASKS, _preflight())
    assert protocol_sha256(TASKS, _preflight(max_steps=6)) != protocol_sha256(
        TASKS, _preflight()
    )


def test_the_protocol_hash_does_not_carry_the_accepted_answers() -> None:
    """The fixture hash freezes the answers; the protocol hash freezes the asking.

    Keeping them apart is what lets a record say which of the two drifted.
    """
    digest = protocol_sha256(TASKS, _preflight())

    for task in TASKS:
        assert accepted_answer(task) not in digest
    assert digest != fixture_sha256()


# --------------------------------------------------------------------------- #
# the six trials, on an injected fake client
# --------------------------------------------------------------------------- #


def _read_step(task: Task) -> str:
    return f"Thought: I will open the ledger\nAction: read_file\nAction Input: {task.subject}"


def _answer_step(text: str) -> str:
    return f"Thought: the ledger says so\nFinal Answer: {text}"


def _grounded_script(repeats: int = 3) -> list[str]:
    """Two replies per trial: one tool call, then an answer that is grounded.

    The answer text is derived from the fixture here too. A test that writes
    the expected value down is the same defect as an oracle that stores it.
    """
    script: list[str] = []
    for task in TASKS:
        for _ in range(repeats):
            script.append(_read_step(task))
            script.append(_answer_step(f"The value is {accepted_answer(task)}."))
    return script


def _fixed_revision(
    commit: str = "87a1297", clean: bool | str = True
) -> Callable[[], tuple[str, bool | str]]:
    def observe() -> tuple[str, bool | str]:
        return commit, clean

    return observe


def test_six_trials_are_recorded_individually_never_averaged() -> None:
    """Md's test. Collapse the repeats into one row and this fails.

    Three repeats of a temperature-0 model is not determinism insurance: this
    project measured one question answered correctly 1 time in 10 on one day
    and 6 in 10 two days later with unchanged text. A mean would have reported
    both as the same number.
    """
    fake = FakeOpenAI(replies=_grounded_script())

    result = run_cohort(
        preflight=_preflight(),
        client=fake.as_client(),
        cohort_id="c1",
        observe_revision=_fixed_revision(),
    )

    assert len(result.records) == 6
    assert all(record["record_type"] == "evaluation_trial" for record in result.records)
    assert [(r["task_id"], r["repeat"]) for r in result.records] == [
        ("grounding-v1", 1),
        ("grounding-v1", 2),
        ("grounding-v1", 3),
        ("grounding-v2", 1),
        ("grounding-v2", 2),
        ("grounding-v2", 3),
    ]
    assert len({str(r["trial_id"]) for r in result.records}) == 6


def test_a_grounded_answer_is_scored_grounded() -> None:
    fake = FakeOpenAI(replies=_grounded_script())

    result = run_cohort(
        preflight=_preflight(),
        client=fake.as_client(),
        cohort_id="c1",
        observe_revision=_fixed_revision(),
    )

    for record in result.records:
        assert record["answer_grounded"] is True
        assert record["answer_names_distractor"] is False
        assert record["tools_within_allowlist"] is True
        assert record["execution_status"] == "completed"
        assert record["tools"] == ["read_file"]
        assert record["tool_status"] == ["ok"]


def test_an_answer_naming_another_ledger_row_is_not_clean() -> None:
    """The defect that killed the old instrument, asserted directly.

    A substring expectation graded a reversed comparison answer as correct for
    ten runs, because the answer named both files. Here an answer that names
    the accepted value *and* another row fails on its own axis.
    """
    task = TASKS[0]
    both = f"It is {accepted_answer(task)}, or possibly {distractors(task)[0]}."
    fake = FakeOpenAI(replies=[_read_step(task), _answer_step(both)])

    result = run_cohort(
        preflight=_preflight(),
        client=fake.as_client(),
        cohort_id="c1",
        tasks=(task,),
        repeats=1,
        observe_revision=_fixed_revision(),
    )

    assert result.records[0]["answer_grounded"] is True
    assert result.records[0]["answer_names_distractor"] is True


def test_an_answer_naming_the_wrong_row_is_not_grounded() -> None:
    task = TASKS[0]
    wrong = f"It is {distractors(task)[0]}."
    fake = FakeOpenAI(replies=[_read_step(task), _answer_step(wrong)])

    result = run_cohort(
        preflight=_preflight(),
        client=fake.as_client(),
        cohort_id="c1",
        tasks=(task,),
        repeats=1,
        observe_revision=_fixed_revision(),
    )

    assert result.records[0]["answer_grounded"] is False
    assert result.records[0]["answer_names_distractor"] is True


def test_a_disallowed_tool_request_is_rejected_before_dispatch(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Reject before Tool.run, stop the trial, and do not issue another request."""
    task = TASKS[0]
    fake = FakeOpenAI(
        replies=[
            "Thought: arithmetic instead\nAction: calculate\nAction Input: 2+2",
            _answer_step(f"The value is {accepted_answer(task)}."),
        ]
    )
    calculate = tools_module.TOOLS["calculate"]
    dispatched: list[Any] = []

    def count_dispatch(args: Any) -> str:
        dispatched.append(args)
        return calculate.run(args)

    monkeypatch.setitem(
        tools_module.TOOLS,
        "calculate",
        replace(calculate, run=count_dispatch),
    )

    result = run_cohort(
        preflight=_preflight(),
        client=fake.as_client(),
        cohort_id="c1",
        tasks=(task,),
        repeats=1,
        observe_revision=_fixed_revision(),
    )

    record = result.records[0]
    assert record["execution_status"] == "policy_violation"
    assert record["tools_within_allowlist"] is False
    assert record["tools"] == ["calculate"]
    assert result.failed == 1
    assert result.completed == 0
    assert len(fake.calls) == 1, "a policy violation must stop before another model request"
    assert dispatched == [], "a task-disallowed tool must not execute"


def test_the_cohort_never_constructs_a_real_client(monkeypatch: pytest.MonkeyPatch) -> None:
    """No test here may reach a model server, and this is what proves it."""
    def explode(*_: object, **__: object) -> object:
        raise AssertionError("the cohort built a real client")

    monkeypatch.setattr(agent_module, "OpenAI", explode)
    fake = FakeOpenAI(replies=_grounded_script())

    result = run_cohort(
        preflight=_preflight(),
        client=fake.as_client(),
        cohort_id="c1",
        observe_revision=_fixed_revision(),
    )

    assert len(result.records) == 6
    assert len(fake.calls) == 12


def test_the_cohort_runs_the_agent_with_no_retries_and_nothing_printed() -> None:
    """The agent's own defaults are two retries and verbose on."""
    fake = FakeOpenAI(replies=_grounded_script(repeats=1))

    result = run_cohort(
        preflight=_preflight(),
        client=fake.as_client(),
        cohort_id="c1",
        repeats=1,
        observe_revision=_fixed_revision(),
    )

    assert result.config.max_retries == 0
    assert result.config.verbose is False
    assert result.config.temperature == 0.0
    assert result.config.max_steps == 8


def test_the_cohort_is_incomplete_when_the_revision_moved_under_it() -> None:
    """Three measurements have been lost to a tree someone else was writing to."""
    fake = FakeOpenAI(replies=_grounded_script())

    result = run_cohort(
        preflight=_preflight(commit="87a1297"),
        client=fake.as_client(),
        cohort_id="c1",
        observe_revision=_fixed_revision(commit="deadbee"),
    )

    assert result.stopped_on == "revision_drift"
    assert result.complete is False


def test_the_cohort_is_incomplete_when_the_tree_stopped_being_clean() -> None:
    fake = FakeOpenAI(replies=_grounded_script())

    result = run_cohort(
        preflight=_preflight(tree_clean=True),
        client=fake.as_client(),
        cohort_id="c1",
        observe_revision=_fixed_revision(clean=False),
    )

    assert result.stopped_on == "tree_dirty"
    assert result.complete is False


def test_a_finished_cohort_reports_started_completed_and_failed_separately() -> None:
    fake = FakeOpenAI(replies=_grounded_script())

    result = run_cohort(
        preflight=_preflight(),
        client=fake.as_client(),
        cohort_id="c1",
        observe_revision=_fixed_revision(),
    )

    assert (result.started, result.completed, result.failed) == (6, 6, 0)
    assert result.complete is True
    assert result.stopped_on is None


def test_the_cohort_leaves_the_workspace_it_found() -> None:
    before = get_workspace()
    fake = FakeOpenAI(replies=_grounded_script(repeats=1))

    run_cohort(
        preflight=_preflight(),
        client=fake.as_client(),
        cohort_id="c1",
        repeats=1,
        observe_revision=_fixed_revision(),
    )

    assert get_workspace() is before


def test_the_trial_workspace_exposes_only_the_synthetic_fixture(tmp_path: Path) -> None:
    fixture = _copy_fixture(tmp_path)
    (tmp_path / "agent.py").write_text("CODE_CANARY", encoding="utf-8")
    (tmp_path / "outside-canary.txt").write_text("WORKSPACE_CANARY", encoding="utf-8")
    with pytest.raises(ValueError, match="staging inventory"):
        fixture_only_workspace(tmp_path, fixture)
    stage = tmp_path / "stage"
    stage.mkdir()
    shutil.copytree(fixture, stage / fixture.name)
    workspace = fixture_only_workspace(stage, stage / fixture.name)

    assert workspace.list_dir(".") == ["grounding-cohort/"]
    for task in TASKS:
        assert workspace.resolve(task.subject).is_file()
    for sealed_path in (tmp_path / "agent.py", tmp_path / "outside-canary.txt"):
        with pytest.raises(SandboxError):
            workspace.resolve(str(sealed_path))


@pytest.mark.parametrize("change", ["extra", "missing", "modified", "directory"])
def test_invalid_fixture_stops_before_model_request(tmp_path: Path, change: str) -> None:
    fixture = _copy_fixture(tmp_path)
    target = fixture / "ledger-alpha.txt"
    if change == "extra":
        (fixture / "unexpected.txt").write_text("unexpected", encoding="utf-8")
    elif change == "missing":
        target.unlink()
    elif change == "modified":
        target.write_text("changed", encoding="utf-8")
    else:
        target.unlink()
        target.mkdir()
    fake = FakeOpenAI(replies=["Final Answer: should not run"])
    result = run_cohort(preflight=_preflight(), client=fake.as_client(), cohort_id="c",
                        root=tmp_path, observe_revision=_fixed_revision())
    assert result.stopped_on == "fixture_drift"
    assert not result.complete
    assert fake.calls == []


@pytest.mark.parametrize("internal", [False, True])
def test_fixture_symlink_is_rejected_before_model_request(tmp_path: Path, internal: bool) -> None:
    fixture = _copy_fixture(tmp_path)
    target = fixture / "ledger-alpha.txt"
    target.unlink()
    outside = tmp_path / "outside.txt"
    outside.write_text("OUTSIDE_CANARY", encoding="utf-8")
    try:
        target.symlink_to(fixture / "ledger-beta.txt" if internal else outside)
    except OSError as exc:
        if sys.platform == "win32":
            pytest.skip(f"Windows symlink privilege or Developer Mode unavailable: {exc}")
        raise
    fake = FakeOpenAI(replies=["Final Answer: should not run"])
    result = run_cohort(preflight=_preflight(), client=fake.as_client(), cohort_id="c",
                        root=tmp_path, observe_revision=_fixed_revision())
    assert result.stopped_on == "fixture_drift"
    assert not fake.calls


@pytest.mark.skipif(sys.platform != "win32", reason="Windows junctions require Windows")
def test_fixture_junction_is_rejected_before_model_request(tmp_path: Path) -> None:
    fixture = _copy_fixture(tmp_path)
    outside = tmp_path / "outside"
    fixture.rename(outside)
    result = subprocess.run(  # noqa: S603 - fixed command and pytest-owned paths
        ["cmd", "/c", "mklink", "/J", str(fixture), str(outside)],  # noqa: S607
        capture_output=True, text=True, check=False,
    )
    assert result.returncode == 0, f"junction creation failed: {result.stdout} {result.stderr}"
    fake = FakeOpenAI(replies=["Final Answer: should not run"])
    outcome = run_cohort(preflight=_preflight(), client=fake.as_client(), cohort_id="c",
                         root=tmp_path, observe_revision=_fixed_revision())
    assert outcome.stopped_on == "fixture_drift"
    assert not fake.calls


def test_fixture_drift_between_requests_stops_without_second_request(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fake = FakeOpenAI(replies=[_read_step(TASKS[0]), _answer_step("answer")])
    original = fake.completions.create

    def mutate_after_request(**kwargs: Any) -> Any:
        reply = original(**kwargs)
        (get_workspace().root / TASKS[0].subject).write_text("changed", encoding="utf-8")
        return reply

    monkeypatch.setattr(fake.completions, "create", mutate_after_request)
    result = run_cohort(preflight=_preflight(), client=fake.as_client(), cohort_id="c",
                        tasks=(TASKS[0],), repeats=2, observe_revision=_fixed_revision())
    assert result.stopped_on == "fixture_drift"
    assert (result.started, result.completed, result.failed) == (1, 0, 1)
    assert len(fake.calls) == 1


def test_trial_record_drops_untrusted_tool_name() -> None:
    fake = FakeOpenAI(replies=[
        "Thought: THOUGHT_CANARY\nAction: RAW_TOOL_CANARY\nAction Input: ARGUMENT_CANARY"
    ])
    result = run_cohort(preflight=_preflight(), client=fake.as_client(), cohort_id="c",
                        tasks=(TASKS[0],), repeats=1, observe_revision=_fixed_revision())
    blob = json.dumps(result.records)
    assert "RAW_TOOL_CANARY" not in blob
    assert "THOUGHT_CANARY" not in blob
    assert "ARGUMENT_CANARY" not in blob
    assert result.records[0]["tools"] == ["unknown"]
    assert result.records[0]["execution_status"] == "policy_violation"


@pytest.mark.parametrize("change", ["modify", "remove"])
def test_drift_after_final_response_stops_without_success_record(
    monkeypatch: pytest.MonkeyPatch, change: str,
) -> None:
    fake = FakeOpenAI(replies=[_read_step(TASKS[0]), _answer_step("answer")])
    original = fake.completions.create

    def mutate_after_final(**kwargs: Any) -> Any:
        reply = original(**kwargs)
        if len(fake.calls) == 2:
            path = get_workspace().root / FIXTURE.name / "README.txt"
            if change == "remove":
                path.unlink()
            else:
                path.write_text("changed", encoding="utf-8")
        return reply

    monkeypatch.setattr(fake.completions, "create", mutate_after_final)
    result = run_cohort(preflight=_preflight(), client=fake.as_client(), cohort_id="c",
                        tasks=(TASKS[0],), repeats=2, observe_revision=_fixed_revision())
    assert result.stopped_on == "fixture_drift"
    assert not result.complete
    assert result.records == ()
    assert len(fake.calls) == 2


def test_drift_after_last_trial_record_marks_cohort_incomplete(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fake = FakeOpenAI(replies=[_answer_step(f"The value is {accepted_answer(TASKS[0])}.")])
    original = cohort_module.trial_record

    def record_then_mutate(**kwargs: Any) -> dict[str, object]:
        record = original(**kwargs)
        (get_workspace().root / FIXTURE.name / "README.txt").write_text(
            "changed", encoding="utf-8"
        )
        return record

    monkeypatch.setattr(cohort_module, "trial_record", record_then_mutate)
    result = run_cohort(
        preflight=_preflight(),
        client=fake.as_client(),
        cohort_id="last-trial-drift",
        tasks=(TASKS[0],),
        repeats=1,
        observe_revision=_fixed_revision(),
    )

    assert result.stopped_on == "fixture_drift"
    assert not result.complete
    assert len(result.records) == 1
    assert len(fake.calls) == 1


def test_drift_between_trials_stops_before_next_trial(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fake = FakeOpenAI(replies=[_read_step(TASKS[0]), _answer_step("answer")])
    original = cohort_module.trial_record

    def record_then_mutate(**kwargs: Any) -> dict[str, object]:
        record = original(**kwargs)
        (get_workspace().root / FIXTURE.name / "README.txt").write_text(
            "changed", encoding="utf-8"
        )
        return record

    monkeypatch.setattr(cohort_module, "trial_record", record_then_mutate)
    result = run_cohort(preflight=_preflight(), client=fake.as_client(), cohort_id="c",
                        tasks=(TASKS[0],), repeats=2, observe_revision=_fixed_revision())
    assert result.stopped_on == "fixture_drift"
    assert not result.complete
    assert len(result.records) == 1
    assert len(fake.calls) == 2
