"""The workspace an evaluation may read: the questions' subjects, not their answers.

Both evaluations called ``set_workspace(Workspace.at(PROJECT))``, which handed
the agent a tree holding the answer key. Asked where 'budget' is used in
``agent.py``, the agent called ``search_text`` with path ``"."``; the
observation came back holding ``data/holdout-expects.txt:33: The word 'budget'
is used in the line "agent.budget.exhausted"``, and it answered that line
verbatim -- its own earlier answer out of a log, not a reading of ``agent.py``.

So every figure for a question the model could answer by searching was
collected in a workspace that contained the answer. Deleting the transcripts
does not fix it: the expectations also live in the evaluation scripts beside
each question, in the documents that explain the measurements, and in the
tests. The fix is that an evaluation runs against a workspace holding only
what its questions are about.

What stays readable is the set of files the questions ask about -- ``agent.py``,
``tests/fakes.py``, ``scripts/build_notebook.py``, ``sandbox.py``. What is
sealed is listed in :data:`ANSWER_KEY`, and ``tests/test_eval_workspace.py``
asserts the property rather than the list: no file reachable through this
workspace may contain a held-out question's text or its expected answer. That
way a transcript written by a future run cannot quietly reopen the leak.
"""

from __future__ import annotations

from pathlib import Path

from sandbox import Workspace

#: Paths, relative to the project root, that hold question texts or the strings
#: a question is scored against. Sealed from every file tool: unreadable, and
#: not named by ``list_directory`` either, since naming them tells the model
#: where to look next.
#:
#: ``models/`` holds no question subject and no answer, and is sealed only so a
#: ``search_text`` walk from the root does not spend its file budget inside a
#: vendored C++ tree.
ANSWER_KEY: tuple[str, ...] = (
    "data",
    "docs",
    "models",
    "NEXT_CHAT.md",
    # A build artifact holding a copy of README.md, which documents the log
    # event the 'budget' question is scored against. Found by measurement, not
    # by reading the tree: a sealed search still returned two matches from it.
    "omniagent.egg-info",
    "omniagent.toml",
    "scripts/eval_workspace.py",
    "scripts/holdout_eval.py",
    "scripts/session_eval.py",
    "tests/test_eval_scoring.py",
    "tests/test_eval_workspace.py",
    "tests/test_file_tools.py",
    "tests/test_holdout_questions.py",
    "tests/test_react_loop.py",
    "tests/test_session_eval.py",
)
#: Three of those are sealed for a reason worth stating. ``eval_workspace.py``,
#: ``tests/test_eval_workspace.py`` and ``tests/test_file_tools.py`` exist to
#: document this leak, so they quote the answer sentence the agent was observed
#: reading out of a transcript. A file whose purpose is to explain the key is
#: part of the key -- and the first version of the seal left all three readable,
#: which the invariant test caught.


def sealed_workspace(project: Path, *, also_deny: tuple[Path, ...] = ()) -> Workspace:
    """A workspace over ``project`` with the answer key out of reach.

    ``also_deny`` is for the run's own log file, which an evaluation must keep
    out of the agent's reach for the same reason: it is the conversation so
    far, and reading it back puts an earlier answer into the context.
    """
    denied = {(project / relative).resolve() for relative in ANSWER_KEY}
    denied.update(path.resolve() for path in also_deny)
    return Workspace.at(project, denied_paths=frozenset(denied))
