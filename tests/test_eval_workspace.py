"""The evaluation workspace must not contain the answers to its own questions.

These assert a property, not a list. A hand-written list of files to seal goes
stale the moment a run writes a new transcript, and the leak this closes was
discovered in a file that no list would have predicted: the agent searched
``.``, found its own earlier answer in ``data/holdout-expects.txt`` and read
it out verbatim. So the test walks the tree by the agent's own admission rules
and asserts that nothing reachable holds a held-out question's text.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

from eval_scoring import Question
from eval_workspace import ANSWER_KEY, LISTING_ONLY, sealed_workspace
from holdout_eval import SESSIONS_UNDER_TEST
from session_eval import WALK

from sandbox import _BINARY_SNIFF_BYTES, SandboxError, Workspace, get_workspace, set_workspace
from tools import list_directory, read_file, search_text

PROJECT = Path(__file__).resolve().parent.parent

#: How many bytes decide whether the tool treats a file as binary. Imported
#: rather than copied from its defining module, so this cannot drift from the
#: rule being mirrored.
#:
#: The first version of this test filtered by suffix instead, and that hole
#: hid a real carrier: ``omniagent.egg-info/PKG-INFO`` has no suffix at all,
#: holds a copy of README.md, and a sealed ``search_text`` returned two
#: matches out of it. ``search_text`` does not look at suffixes, so a test
#: that models reachability by suffix does not model reachability.
_SNIFF = _BINARY_SNIFF_BYTES

#: The sentence the agent was observed answering out of a transcript.
LEAKED_SENTENCE = "The word 'budget' is used in the line"


#: Where a distinctive expectation may legitimately appear, and why.
#:
#: Two different things get called a leak and only one is. A transcript
#: reading ``The word 'budget' is used in the line "agent.budget.exhausted"
#: within the system_prompt of agent.py`` is a sentence that answers the
#: question; ``obs.event("agent.budget.exhausted")`` in a file that emits that
#: log event is the codebase. The first has to be out of reach. The second
#: cannot be, and listing it here is the record that it was looked at.
#:
#: Measured, not assumed: the invariant below named every one of these.
#: ``agent.budget.exhausted`` occurs in **five** reachable files, so the
#: 'budget' question's expectation is not uniquely located in ``agent.py`` --
#: a ``search_text`` over ``.`` still returns four files that are not the
#: question's subject. Sealing the transcripts does not make that question
#: clean; it only stops the answer sentence coming back.
EXPECTATION_CARRIERS: dict[str, frozenset[str]] = {
    "agent.budget.exhausted": frozenset(
        {
            "agent.py",  # the question's subject: the fact being measured
            "README.md",  # the log event documented
            "export_dataset.py",  # the log event filtered
            "tests/test_agent_logging.py",  # the log event asserted
            "tests/test_export_dataset.py",  # the log event in a fixture
        }
    ),
    # Read out of the tree by holdout_eval._last_line, so the file it names is
    # the only place it can be: the expectation is a fact about that file.
    'print(f"wrote {OUT} with {len(CELLS)} cells")': frozenset({"scripts/build_notebook.py"}),
}

#: Below this length an expectation is a bare number -- "42", "1116", "500" --
#: which occurs all over a codebase for reasons that have nothing to do with
#: the question. Checking those would report noise, so the invariant covers
#: the expectations distinctive enough for a match to mean something.
_DISTINCTIVE = 12


def held_out_questions() -> list[Question]:
    """Every question either evaluation asks, as the model would see it."""
    return [*WALK, *(question for session in SESSIONS_UNDER_TEST for question in session)]


def held_out_texts() -> frozenset[str]:
    """The question texts. Banned from every reachable file, without exception.

    A file holding the question is the key-adjacency case: a transcript, an
    eval script, a documentation table. None of them has a reason to be
    readable during a run.
    """
    return frozenset(question.text for question in held_out_questions())


def held_out_expectations() -> frozenset[str]:
    """The expectations distinctive enough for a match to mean something.

    Texts alone were not enough. The first version of this test checked only
    them and passed while ``tests/test_file_tools.py`` -- written in the same
    session, to close this very leak -- held the answer sentence the agent had
    been observed reading out of a transcript. The seal had moved the leak
    rather than closing it, and only an expectation check found that.
    """
    return frozenset(
        question.expect
        for question in held_out_questions()
        if question.expect and len(question.expect) >= _DISTINCTIVE
    )


def reachable_files(workspace: Workspace) -> list[Path]:
    """The files the agent could actually open, by the workspace's own rules.

    Resolved the way ``search_text`` resolves each candidate it walks, so this
    enumerates what the tools admit rather than what the filesystem holds.
    Directories are pruned as the walk descends: resolving every path under
    ``.venv`` and ``models/`` and discarding it afterwards took 113 seconds.
    """
    found: list[Path] = []
    stack = [PROJECT]
    while stack:
        for child in stack.pop().iterdir():
            try:
                workspace.resolve(workspace.display(child))
            except (SandboxError, ValueError):
                continue  # hidden, denied or escaping: prune the whole branch
            if child.is_dir():
                stack.append(child)
            elif child.stat().st_size <= workspace.max_file_bytes and not _is_binary(child):
                found.append(child)
    return found


def _is_binary(path: Path) -> bool:
    """The tool's own test: a null byte in the first sniffed bytes."""
    with path.open("rb") as handle:
        return b"\0" in handle.read(_SNIFF)


@pytest.fixture
def sealed() -> Workspace:
    return sealed_workspace(PROJECT)


@pytest.fixture
def transcripts(tmp_path: Path) -> Workspace:
    """Exercise local transcripts without depending on ignored run artifacts."""
    data = tmp_path / "data"
    data.mkdir()
    (data / "collect-run.log").write_text("synthetic run log\n", encoding="utf-8")
    (data / "holdout-expects.txt").write_text(LEAKED_SENTENCE + "\n", encoding="utf-8")
    return sealed_workspace(tmp_path)


def test_no_reachable_file_holds_a_held_out_question(sealed: Workspace) -> None:
    """The property the whole seal exists for.

    A future run writing a new transcript under a sealed directory cannot
    reopen the leak; a run writing one somewhere else fails this immediately.
    """
    texts = held_out_texts()
    leaking: dict[str, list[str]] = {}
    for path in reachable_files(sealed):
        shown = sealed.display(path)
        blob = path.read_text("utf-8", errors="ignore")
        found = sorted(text for text in texts if text in blob)
        if found:
            leaking[shown] = found

    assert leaking == {}, f"these reachable files hold a question text: {leaking}"


def test_no_unreviewed_file_holds_an_expected_answer(sealed: Workspace) -> None:
    """An expectation may only sit where it has a reason to.

    This is the check that caught the seal moving the leak instead of closing
    it. A new file carrying an answer string fails here and forces the
    question of which kind of occurrence it is -- the codebase's own log event,
    or a sentence that answers the question.
    """
    expectations = held_out_expectations()
    unreviewed: dict[str, list[str]] = {}
    for path in reachable_files(sealed):
        shown = sealed.display(path)
        blob = path.read_text("utf-8", errors="ignore")
        found = sorted(
            expected
            for expected in expectations
            if expected in blob and shown not in EXPECTATION_CARRIERS.get(expected, frozenset())
        )
        if found:
            unreviewed[shown] = found

    assert unreviewed == {}, f"these reachable files hold an expected answer: {unreviewed}"


def test_the_budget_expectation_is_not_unique_to_its_subject(sealed: Workspace) -> None:
    """A measured fact about the question, recorded so it is not forgotten.

    ``agent.budget.exhausted`` is a log event this codebase emits, so it
    occurs in files that are not the question's subject. Sealing the
    transcripts stops the answer *sentence* coming back; it does not make the
    question uniquely answerable from ``agent.py``. If this ever drops to one
    carrier the question got stronger and the figure can be re-read.
    """
    carriers = EXPECTATION_CARRIERS["agent.budget.exhausted"]
    present = {
        sealed.display(path)
        for path in reachable_files(sealed)
        if "agent.budget.exhausted" in path.read_text("utf-8", errors="ignore")
    }

    assert present == set(carriers), f"the spread changed: {present ^ set(carriers)}"
    assert len(present) > 1, "if this is now unique to agent.py, re-read the 'budget' figure"


def test_the_questions_own_subjects_stay_readable(sealed: Workspace) -> None:
    """Sealing is worthless if it also seals what the questions ask about."""
    for subject in ("agent.py", "tests/fakes.py", "scripts/build_notebook.py", "sandbox.py"):
        assert sealed.resolve(subject).is_file(), f"{subject} became unreadable"


def test_search_text_no_longer_finds_the_leaked_answer(transcripts: Workspace) -> None:
    """Reproduce the observed leak with a synthetic transcript and the real tools."""
    original = get_workspace()
    set_workspace(Workspace.at(transcripts.root))
    try:
        leaky = search_text(LEAKED_SENTENCE, "data")
        assert "holdout" in leaky
        assert LEAKED_SENTENCE in leaky

        set_workspace(transcripts)
        observation = search_text(LEAKED_SENTENCE, "data")
    finally:
        set_workspace(original)

    assert "holdout" not in observation
    assert observation.startswith("No match")


def test_a_fully_sealed_directory_is_not_named_in_a_listing(sealed: Workspace) -> None:
    """`docs/` holds the demo script, question and answer in one table row."""
    original = get_workspace()
    set_workspace(sealed)
    try:
        observation = list_directory(".")
    finally:
        set_workspace(original)

    assert "docs/" not in observation
    assert "agent.py" in observation


def test_the_transcripts_directory_is_listable_but_not_readable(transcripts: Workspace) -> None:
    """What option A bought, asserted on the three tools separately.

    Sealing `data/` outright closed the leak and took the question with it.
    These are the two halves that have to hold at once: the listing answers
    "What is inside the data directory?", and nothing inside opens.
    """
    original = get_workspace()
    set_workspace(transcripts)
    try:
        listing = list_directory("data")
        read = read_file("data/holdout-expects.txt")
        searched = search_text(LEAKED_SENTENCE, "data")
    finally:
        set_workspace(original)

    assert "collect-run.log" in listing, "the question's expected answer is no longer listed"
    assert read.startswith("Error:")
    assert "not readable by the agent" in read
    assert "holdout" not in searched
    # Scoped to "data" rather than ".", and the reason is a measurement: a
    # search from the root costs 64 s on this tree because search_text
    # materialises every path under .venv and models/ before filtering any of
    # them. The code path is the same one; the invariant tests above cover the
    # root case by walking it with pruning instead.


def test_every_sealed_source_path_exists(sealed: Workspace) -> None:
    """Catch misspelled source paths; ignored local artifacts need not exist."""
    optional_artifacts = {"models", "data", "omniagent.egg-info"}
    missing = [
        relative
        for relative in (*ANSWER_KEY, *LISTING_ONLY)
        if relative not in optional_artifacts and not (PROJECT / relative).exists()
    ]

    assert missing == [], f"a sealed path is not there: {missing}"


@pytest.mark.parametrize("directory", ["models", "data", "omniagent.egg-info"])
def test_local_artifacts_created_after_sealing_stay_unreadable(
    tmp_path: Path, directory: str
) -> None:
    workspace = sealed_workspace(tmp_path)
    relative = f"{directory}/transcript.txt"
    with pytest.raises(SandboxError, match="not readable by the agent"):
        workspace.resolve(relative)

    (tmp_path / directory).mkdir()
    (tmp_path / relative).write_text(LEAKED_SENTENCE, encoding="utf-8")
    with pytest.raises(SandboxError, match="not readable by the agent"):
        workspace.read_text(relative)


def test_a_run_log_can_be_sealed_as_well(tmp_path: Path) -> None:
    """The run's own log is the conversation so far, and must not be readable."""
    log = PROJECT / "data" / "session-runs.jsonl"
    workspace = sealed_workspace(PROJECT, also_deny=(log,))

    with pytest.raises(SandboxError, match="not readable by the agent"):
        workspace.resolve("data/session-runs.jsonl")
