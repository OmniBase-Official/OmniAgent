"""Parse model replies into structured ReAct steps."""

from __future__ import annotations

import re

from pydantic import BaseModel

from tool_input_values import NO_ARG_INPUTS

# Parsing patterns. DOTALL on the tail captures multi-line inputs/answers.
_FINAL_ANSWER_RE = re.compile(r"Final\s*Answer\s*:\s*(.*)", re.IGNORECASE | re.DOTALL)
_THOUGHT_RE = re.compile(
    r"Thought\s*:\s*(.*?)(?=\n\s*(?:Action|Final\s*Answer|Observation)\s*:|\Z)",
    re.IGNORECASE | re.DOTALL,
)
_ACTION_RE = re.compile(r"Action\s*:\s*([^\n]+)", re.IGNORECASE)

#: Lines that begin a new ReAct block, and therefore end a Final Answer. The
#: capture for the answer is DOTALL, so without this it runs to the end of the
#: reply: in a session where history had accumulated, the agent answered a
#: question with the raw text "Thought: I need to calculate 2480 * 15% and then
#: multiply that result by 3.\nAction: calculate" -- an earlier question's plan,
#: recycled, and shown to the user as prose.
_BLOCK_START_RE = re.compile(
    r"^[^\S\n]*(?:Thought|Action|Action\s*Input|Observation|Final\s*Answer)\s*:",
    re.IGNORECASE | re.MULTILINE,
)
_ACTION_INPUT_RE = re.compile(
    r"Action\s*Input\s*:\s*(.*?)(?=\n\s*(?:Thought|Action|Observation|Final\s*Answer)\s*:|\Z)",
    re.IGNORECASE | re.DOTALL,
)
# "calculate(2 + 2)" written on the Action line instead of split across two lines.
_INLINE_CALL_RE = re.compile(r"^([A-Za-z_][A-Za-z0-9_]*)\s*\((.*)\)\s*$", re.DOTALL)

_BRACKET_PAIRS = {"()", "<>", "[]"}

#: Shortest string that can still be a quoted or bracketed wrapper.
_MIN_WRAPPED_LENGTH = 2


class Step(BaseModel):
    """One iteration of the loop, kept for inspection and testing."""

    thought: str = ""
    action: str | None = None
    action_input: str | None = None
    observation: str | None = None
    final_answer: str | None = None
    raw: str = ""


def _is_wrapped(value: str) -> bool:
    """True when the value is long enough to carry a matching pair of delimiters."""
    return len(value) >= _MIN_WRAPPED_LENGTH


def parse_reply(text: str) -> Step:
    """Turn one raw model reply into a structured :class:`Step`."""
    step = Step(raw=text)

    thought = _THOUGHT_RE.search(text)
    if thought:
        step.thought = thought.group(1).strip()

    final = _FINAL_ANSWER_RE.search(text)
    if final:
        answer = _answer_only(final.group(1))
        if answer:
            step.final_answer = answer
            return step
        # A Final Answer marker followed straight by another block is not an
        # answer, so nothing is presented as one. Falling through honours what
        # the model was actually doing -- carrying on -- and a reply with no
        # Action either reaches the loop's format correction instead.

    action = _ACTION_RE.search(text)
    if not action:
        return step

    name = action.group(1).strip().strip("`*[] ").rstrip(".")
    raw_input_match = _ACTION_INPUT_RE.search(text)
    raw_input = raw_input_match.group(1) if raw_input_match else ""

    # Tolerate "Action: calculate(2 + 2)" by unpacking the call itself.
    inline = _INLINE_CALL_RE.match(name)
    if inline:
        name = inline.group(1)
        if not raw_input.strip():
            raw_input = inline.group(2)

    if _names_the_marker(name):
        # The model put the marker in the slot it has been taught to put a verb
        # in. Measured on the demo path: "Thought: I have found where 'budget'
        # is used in agent.py\nAction: Final Answer" dispatched a tool called
        # "Final Answer", logged tool.unknown, and spent a step on nothing.
        # With no Action Input there is no answer to take, so this falls
        # through to the loop's format correction rather than promoting the
        # Thought, which would be inventing one.
        answer = _answer_only(raw_input)
        if answer:
            step.final_answer = answer
        return step

    step.action = name
    step.action_input = _clean_action_input(raw_input)
    return step


def _names_the_marker(action: str) -> bool:
    """Whether an Action names the final-answer marker rather than a tool."""
    return "".join(c for c in action.lower() if c.isalnum()) == "finalanswer"


def _answer_only(captured: str) -> str:
    """The answer, cut before any further block the model wrote after it.

    A newline does not end an answer -- answers run to several lines -- but a
    line opening with Thought, Action, Observation or another Final Answer does.
    """
    nxt = _BLOCK_START_RE.search(captured)
    return (captured[: nxt.start()] if nxt else captured).strip()


def _clean_action_input(raw: str) -> str:
    """Strip the decorations small models like to add around tool arguments."""
    value = raw.strip()
    if value.startswith("```"):
        value = re.sub(r"^```[a-zA-Z0-9_+-]*\n?", "", value)
        value = re.sub(r"\n?```$", "", value).strip()
    value = value.strip("`").strip()
    if _is_wrapped(value) and value[0] in "\"'":
        value = value[1:-1].strip()
    if value.lower() in NO_ARG_INPUTS:
        return ""
    # Small models like to wrap the placeholder: "(none)", "<none>", "[none]".
    if (
        _is_wrapped(value)
        and value[0] + value[-1] in _BRACKET_PAIRS
        and value[1:-1].strip().lower() in NO_ARG_INPUTS
    ):
        return ""
    return value
