"""The evidence-grounding category: a derived oracle and a record that carries no answers.

One category, built end to end, so the record format is proved before
thirty-six trials are spent on it. Every test here runs on an injected fake
client; nothing in this module may reach a model server.
"""

from __future__ import annotations

import inspect
import json
import shutil
import sys
from collections.abc import Callable
from dataclasses import replace
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

import grounding_cohort
import pytest
from eval_workspace import sealed_workspace
from grounding_cohort import (
    ARM,
    FIXTURE,
    SEALED_FROM_TRIALS,
    TASKS,
    Observed,
    Preflight,
    Task,
    accepted_answer,
    distractors,
    fixture_sha256,
    protocol_sha256,
    run_cohort,
    trial_record,
)

import agent as agent_module
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
    """Content alone is not the fixture: its inventory is part of it."""
    copy = _copy_fixture(tmp_path)
    before = fixture_sha256(copy)

    (copy / "ledger-gamma.txt").write_text("another ledger\n", encoding="utf-8")

    assert fixture_sha256(copy) != before


def test_the_fixture_hash_changes_when_a_file_is_renamed(tmp_path: Path) -> None:
    copy = _copy_fixture(tmp_path)
    before = fixture_sha256(copy)

    (copy / "ledger-beta.txt").rename(copy / "ledger-delta.txt")

    assert fixture_sha256(copy) != before


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


def test_the_trial_record_carries_every_field_the_contract_lists() -> None:
    """Me's test. Drop any field named here and this fails.

    The contract's reproducibility record, asserted as an exact dictionary so a
    missing field cannot pass as an absent one. The clean-tree field is in here
    because a run record once carried the commit and not the tree, and a void
    run pooled with ten good ones for want of it.
    """
    record = trial_record(
        cohort_id="cohort-fixture",
        trial_id="cohort-fixture/grounding-v1/r1",
        task=TASKS[0],
        repeat=1,
        preflight=_preflight(),
        fixture_hash="f" * 64,
        protocol_hash="e" * 64,
        observed=_observed(),
    )

    assert record == {
        "cohort_id": "cohort-fixture",
        "trial_id": "cohort-fixture/grounding-v1/r1",
        "task_id": "grounding-v1",
        "variant": "v1",
        "repeat": 1,
        "arm": ARM,
        "category": "evidence-grounding",
        "commit": "87a1297",
        "tree_clean": True,
        "fixture_sha256": "f" * 64,
        "protocol_sha256": "e" * 64,
        "model_tag": "omniagent-v2",
        "model_digest": "sha256:" + "0" * 64,
        "runtime_version": "ollama 0.0.0-fixture",
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


def test_the_trial_record_carries_no_prompt_answer_content_or_url() -> None:
    """Mc's test. Add the prompt to the record and this fails.

    Checked over the serialised record rather than its keys, so a forbidden
    value smuggled inside an allowed field fails too.
    """
    record = trial_record(
        cohort_id="cohort-fixture",
        trial_id="cohort-fixture/grounding-v2/r3",
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


def test_a_disallowed_tool_request_is_recorded_as_a_policy_violation() -> None:
    """Recorded, not retried, and never pooled with a wrong answer.

    This proves the evaluator notices. It does not prove the dispatcher
    refuses: there is no per-task allowlist in the dispatcher, so the call did
    run. That gate is the security engineer's, not this module's.
    """
    task = TASKS[0]
    fake = FakeOpenAI(
        replies=[
            "Thought: arithmetic instead\nAction: calculate\nAction Input: 2+2",
            _answer_step(f"The value is {accepted_answer(task)}."),
        ]
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
    assert len(fake.calls) == 2, "a violated trial must not be run again"


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


def test_the_category_seals_exactly_the_two_files_that_define_it() -> None:
    """Derived from the modules, so an empty or wrong seal list cannot pass.

    The first version of the test below only looped over
    ``SEALED_FROM_TRIALS``, which made an empty tuple assert nothing at all. A
    mutation emptying it stayed green, so the set is pinned here against the
    files the interpreter actually loaded this category from.
    """
    assert set(SEALED_FROM_TRIALS) == {
        Path(inspect.getfile(grounding_cohort)).resolve(),
        Path(__file__).resolve(),
    }


def test_the_trial_workspace_opens_the_fixture_and_seals_this_category() -> None:
    """The fixture is the subject, so it must open. The tasks must not.

    ``sealed_workspace`` is imported, never edited: the paths this category has
    to add are passed through its own ``also_deny`` hatch, so the answer-key
    seal three briefs have routed around stays untouched.
    """
    workspace = sealed_workspace(FIXTURE.parent, also_deny=SEALED_FROM_TRIALS)

    assert SEALED_FROM_TRIALS, "an empty seal list would make the loop below vacuous"
    for task in TASKS:
        assert workspace.resolve(task.subject).is_file()
    for sealed_path in SEALED_FROM_TRIALS:
        with pytest.raises(SandboxError, match="not readable by the agent"):
            workspace.resolve(workspace.display(sealed_path))
