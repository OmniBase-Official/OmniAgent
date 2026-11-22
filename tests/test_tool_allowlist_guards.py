"""One test per guard that enforces the tool allowlist (contract gate 2).

The allowlist is enforced in several overlapping places, and two of them answer
with the *same* string. A test that only asserts "this was refused" therefore
cannot say which guard refused: delete any one guard and the others still refuse,
so the suite stays green. Each test below is built so that only ONE guard can
produce the result it asserts, and it asserts the cause (a spy proving the tool
body or the dispatcher was never reached, a different error string, a different
attribute), not merely the refusal.

====  ===========================  ==========================================
id    guard                        what only it can cause
====  ===========================  ==========================================
G2a   ``ReActAgent.__init__``      ``allowed_tools`` can never hold a name
      intersects with the fixed    outside the fixed allowlist
      allowlist
G2b   ``_invoke_tool`` permitted   ``run_tool`` is never *called* for a tool
                                   outside ``allowed_tools``
G2c   ``run_tool`` fixed check     a tool outside the fixed allowlist is
                                   refused as *unknown*, even when a caller
                                   names it in ``allowed_tools``
G2d   ``run_tool`` per-task check  a fixed-allowlist tool outside this task's
                                   subset is refused and its body never runs
G2e   run loop stop                the loop ends the turn with ``""`` and no
                                   Observation reaches the scratchpad
G2f   ``__init__`` capability      ``allowed_capabilities`` can never hold a
      intersection                 name outside the fixed capability set
G2g   config route                 the fast route refuses, naming the missing
      ``missing_capabilities``     capability, instead of running the tool
====  ===========================  ==========================================

Static throughout: the fake client never opens a socket, and nothing here may
contact a model server.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import replace
from typing import Any

import pytest

import agent as agent_module
from agent import AgentConfig, ReActAgent, Step
from tests.fakes import FakeOpenAI
from tools import FIXED_INTERNAL_CAPABILITY_ALLOWLIST, FIXED_TOOL_ALLOWLIST, TOOLS, run_tool

NOT_ALLOWED = "Error: tool is not allowed for this task."
UNKNOWN_TOOL = "there is no tool called"

ASK_READ_FILE = "Thought: look\nAction: read_file\nAction Input: pyproject.toml"
FINAL = "Thought: done\nFinal Answer: finished"


def build(
    fake: FakeOpenAI,
    allowed_tools: set[str] | frozenset[str] | None = None,
    allowed_capabilities: set[str] | frozenset[str] | None = None,
) -> ReActAgent:
    return ReActAgent(
        config=AgentConfig(verbose=False, retry_backoff=0.0),
        client=fake.as_client(),
        printer=lambda _: None,
        allowed_tools=allowed_tools,
        allowed_capabilities=allowed_capabilities,
    )


def spy_on_tool_body(
    monkeypatch: pytest.MonkeyPatch, name: str, calls: list[object]
) -> None:
    """Replace ``TOOLS[name].run`` with a recorder, so a test can see whether the
    body ran. The recorder returns a recognisable string, never the real result."""

    def body(args: object) -> str:
        calls.append(args)
        return "TOOL BODY RAN"

    monkeypatch.setitem(TOOLS, name, replace(TOOLS[name], run=body))


def spy_on_dispatcher(
    monkeypatch: pytest.MonkeyPatch, calls: list[str]
) -> Callable[..., str]:
    """Wrap ``agent.run_tool`` so a test can see whether the agent reached it."""
    real = run_tool

    def spy(name: str, tool_input: str, **kwargs: Any) -> str:
        calls.append(name)
        return real(name, tool_input, **kwargs)

    monkeypatch.setattr(agent_module, "run_tool", spy)
    return spy


# --------------------------------------------------------------------------- #
# G2a - the constructor can only narrow the fixed allowlist
# --------------------------------------------------------------------------- #


def test_g2a_constructor_drops_names_outside_the_fixed_allowlist() -> None:
    fake = FakeOpenAI(replies=[])
    invented = "delete_everything"
    assert invented not in FIXED_TOOL_ALLOWLIST
    assert invented not in TOOLS

    agent = build(fake, allowed_tools={"calculate", invented})

    assert agent.allowed_tools == frozenset({"calculate"})


def test_g2a_a_name_outside_the_fixed_allowlist_cannot_become_a_task_tool(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Behavioural face of G2a: a registered but unlisted tool stays unreachable.

    Without G2a the name survives into ``allowed_tools``, so ``_invoke_tool``
    (G2b) lets it through to ``run_tool``, where G2c refuses it as *unknown*. With
    G2a the name is gone and G2b itself answers "not allowed for this task" - a
    different string, so the two paths are told apart. ``_invoke_tool`` is called
    directly so that the run loop's stop (G2e) is not part of the result.
    """
    probe = replace(TOOLS["calculate"], name="probe_tool")
    monkeypatch.setitem(TOOLS, "probe_tool", probe)
    assert "probe_tool" not in FIXED_TOOL_ALLOWLIST
    agent = build(FakeOpenAI(replies=[]), allowed_tools={"calculate", "probe_tool"})
    step = Step(thought="t", action="probe_tool", action_input="1 + 1")

    observation = agent._invoke_tool(step)

    assert observation == NOT_ALLOWED


# --------------------------------------------------------------------------- #
# G2b - _invoke_tool does not even call the dispatcher for a disallowed tool
# --------------------------------------------------------------------------- #


def test_g2b_disallowed_tool_never_reaches_the_dispatcher(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """G2d would also refuse, with the same string - so the string is not the
    evidence. The evidence is that ``run_tool`` was never called at all."""
    dispatched: list[str] = []
    spy_on_dispatcher(monkeypatch, dispatched)
    agent = build(FakeOpenAI(replies=[]), allowed_tools={"calculate"})
    step = Step(thought="t", action="read_file", action_input="pyproject.toml")

    observation = agent._invoke_tool(step)

    assert observation == NOT_ALLOWED
    assert dispatched == []


def test_g2b_the_spy_does_see_a_permitted_tool(monkeypatch: pytest.MonkeyPatch) -> None:
    """Control for the test above: the spy is wired to the call that matters."""
    dispatched: list[str] = []
    spy_on_dispatcher(monkeypatch, dispatched)
    agent = build(FakeOpenAI(replies=[]), allowed_tools={"calculate"})
    step = Step(thought="t", action="calculate", action_input="2 + 2")

    observation = agent._invoke_tool(step)

    assert observation == "2 + 2 = 4"
    assert dispatched == ["calculate"]


# --------------------------------------------------------------------------- #
# G2c - run_tool refuses anything outside the fixed allowlist as unknown
# --------------------------------------------------------------------------- #


def test_g2c_a_tool_outside_the_fixed_allowlist_is_unknown_even_if_the_task_names_it(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The caller names the tool in ``allowed_tools``, so G2d has nothing to say.
    Only G2c stands between a registry entry and a run - and it answers
    "no tool called", which is how it is told apart from G2d."""
    calls: list[object] = []

    def body(args: object) -> str:
        calls.append(args)
        return "RAN"

    probe = replace(TOOLS["calculate"], name="probe_tool", run=body)
    monkeypatch.setitem(TOOLS, "probe_tool", probe)
    assert "probe_tool" not in FIXED_TOOL_ALLOWLIST

    result = run_tool("probe_tool", "1 + 1", allowed_tools={"probe_tool"})

    assert UNKNOWN_TOOL in result
    assert NOT_ALLOWED not in result
    assert calls == []


def test_g2c_rejection_does_not_leak_the_unlisted_tool_into_the_available_list(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setitem(TOOLS, "probe_tool", replace(TOOLS["calculate"], name="probe_tool"))

    result = run_tool("probe_tool", "1 + 1", allowed_tools={"probe_tool"})

    assert "probe_tool'" in result  # echoed once, as the name that was asked for
    available = result.rsplit("Available tools are:", 1)[1]
    assert "probe_tool" not in available


# --------------------------------------------------------------------------- #
# G2d - run_tool enforces the per-task subset when called directly
# --------------------------------------------------------------------------- #


def test_g2d_a_real_tool_outside_the_task_subset_is_refused_and_its_body_never_runs(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Called directly, so the agent's G2b/G2e are not in the path. ``read_file``
    is in the fixed allowlist, so G2c does not refuse it either: only G2d can."""
    calls: list[object] = []
    spy_on_tool_body(monkeypatch, "read_file", calls)

    result = run_tool("read_file", "pyproject.toml", allowed_tools={"calculate"})

    assert result == NOT_ALLOWED
    assert calls == []


def test_g2d_the_body_spy_does_see_a_tool_inside_the_task_subset(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Control for the test above: the spy catches a body that is allowed to run."""
    calls: list[object] = []
    spy_on_tool_body(monkeypatch, "read_file", calls)

    result = run_tool("read_file", "pyproject.toml", allowed_tools={"read_file"})

    assert result == "TOOL BODY RAN"
    assert len(calls) == 1


def test_g2d_an_empty_task_subset_refuses_every_tool(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[object] = []
    spy_on_tool_body(monkeypatch, "calculate", calls)

    result = run_tool("calculate", "2 + 2", allowed_tools=frozenset())

    assert result == NOT_ALLOWED
    assert calls == []


# --------------------------------------------------------------------------- #
# G2e - the run loop ends the turn when the model asks for a disallowed tool
# --------------------------------------------------------------------------- #


def test_g2e_a_disallowed_action_ends_the_turn_with_no_observation_in_the_scratchpad() -> None:
    """With G2e gone the refusal text becomes an Observation and the model is
    asked again; here the second scripted reply would then be a Final Answer."""
    fake = FakeOpenAI(replies=[ASK_READ_FILE, FINAL])
    agent = build(fake, allowed_tools={"calculate"})

    answer = agent.run("read pyproject.toml")

    assert answer == ""
    assert len(fake.calls) == 1, "the model was asked again after a disallowed action"
    seen = [str(m["content"]) for call in fake.calls for m in call["messages"]]
    assert not any(text.startswith("Observation:") for text in seen)
    assert [step.action for step in agent.last_trace] == ["read_file"]
    assert agent.last_trace[0].observation == NOT_ALLOWED


# --------------------------------------------------------------------------- #
# G2f - the constructor can only narrow the fixed capability set
# --------------------------------------------------------------------------- #


def test_g2f_constructor_drops_capabilities_outside_the_fixed_set() -> None:
    """``allowed_capabilities`` is only ever consulted by membership of the one
    real capability, so a stray name has no behavioural consequence today; the
    attribute is the only place the closed set shows. Pin it there."""
    fake = FakeOpenAI(replies=[])
    invented = "run_shell"
    assert invented not in FIXED_INTERNAL_CAPABILITY_ALLOWLIST

    agent = build(fake, allowed_capabilities={"inspect_default_model_cli", invented})

    assert agent.allowed_capabilities == frozenset({"inspect_default_model_cli"})


def test_g2f_a_scoped_task_gets_no_capabilities_unless_it_names_them() -> None:
    fake = FakeOpenAI(replies=[])

    agent = build(fake, allowed_tools={"calculate"})

    assert agent.allowed_capabilities == frozenset()


# --------------------------------------------------------------------------- #
# G2g - the config-inspection fast route fails closed on a missing capability
# --------------------------------------------------------------------------- #

CONFIG_QUESTION = "Trace the default model and CLI --model override precedence in config.resolve()."


@pytest.mark.parametrize(
    ("allowed_tools", "allowed_capabilities", "named"),
    [
        (set(FIXED_TOOL_ALLOWLIST) - {"inspect_config_precedence"},
         set(FIXED_INTERNAL_CAPABILITY_ALLOWLIST), "inspect_config_precedence"),
        (set(FIXED_TOOL_ALLOWLIST), set(), "inspect_default_model_cli"),
    ],
)
def test_g2g_fast_route_refuses_without_running_the_tool(
    monkeypatch: pytest.MonkeyPatch,
    allowed_tools: set[str],
    allowed_capabilities: set[str],
    named: str,
) -> None:
    """Remove the ``missing_capabilities`` check and the route runs the tool
    anyway: the body spy fires and the answer no longer names the capability."""
    calls: list[object] = []
    spy_on_tool_body(monkeypatch, "inspect_config_precedence", calls)
    fake = FakeOpenAI(replies=[])
    agent = build(fake, allowed_tools=allowed_tools, allowed_capabilities=allowed_capabilities)

    answer = agent.run(CONFIG_QUESTION)

    assert answer.startswith("Error: this task does not allow required inspection capabilities:")
    assert named in answer
    assert calls == []
    assert fake.calls == []

