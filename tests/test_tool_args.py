"""Tests for the typed tool layer: schemas, parsing, and the errors a model sees.

The point of the layer is that a 7B model gets told exactly what it did wrong,
so most of these assert on the text of the Observation, not just that it failed.
"""

from __future__ import annotations

import json
from typing import Any

import pytest
from pydantic import Field

from tools import (
    TOOLS,
    CalculateArgs,
    NoArgs,
    Tool,
    ToolArgs,
    ToolArgumentError,
    describe_tools,
    parse_tool_args,
    run_tool,
)


class TwoFieldArgs(ToolArgs):
    city: str = Field(description="Where to look.")
    units: str = Field(default="metric", description="metric or imperial.")


TWO_FIELD_TOOL: Tool[TwoFieldArgs] = Tool(
    name="fake_weather",
    description="A stand-in for a future multi-argument tool.",
    args_model=TwoFieldArgs,
    run=lambda args: f"{args.city}/{args.units}",
    example='{"city": "Bangkok", "units": "metric"}',
)


# --------------------------------------------------------------------------- #
# signatures are derived, not hand-written
# --------------------------------------------------------------------------- #


def test_signature_comes_from_the_schema() -> None:
    assert TOOLS["calculate"].signature == "calculate(expression: str)"
    assert TOOLS["get_current_time"].signature == "get_current_time()"
    assert TWO_FIELD_TOOL.signature == "fake_weather(city: str, units: str)"


def test_the_prompt_catalogue_documents_every_field() -> None:
    rendered = describe_tools()
    assert "calculate(expression: str)" in rendered
    assert "expression (str, required)" in rendered
    # A tool with no fields gets no Arguments block.
    assert "get_current_time()" in rendered


def test_adding_a_field_changes_the_prompt_automatically() -> None:
    """The prompt is generated, so it cannot drift away from the schema."""
    assert TWO_FIELD_TOOL.signature in _describe(TWO_FIELD_TOOL)
    assert "city (str, required)" in _describe(TWO_FIELD_TOOL)
    assert "units (str, optional)" in _describe(TWO_FIELD_TOOL)


def _describe(tool: Tool[Any]) -> str:
    original = dict(TOOLS)
    TOOLS.clear()
    TOOLS[tool.name] = tool
    try:
        return describe_tools()
    finally:
        TOOLS.clear()
        TOOLS.update(original)


# --------------------------------------------------------------------------- #
# the three input shapes
# --------------------------------------------------------------------------- #


def test_a_bare_value_fills_a_single_field() -> None:
    args = parse_tool_args(TOOLS["calculate"], "2 + 2")
    assert isinstance(args, CalculateArgs)
    assert args.expression == "2 + 2"


def test_a_json_object_is_accepted() -> None:
    args = parse_tool_args(TOOLS["calculate"], '{"expression": "2 + 2"}')
    assert isinstance(args, CalculateArgs)
    assert args.expression == "2 + 2"


def test_json_reaches_a_multi_field_tool() -> None:
    args = parse_tool_args(TWO_FIELD_TOOL, '{"city": "Bangkok"}')
    assert isinstance(args, TwoFieldArgs)
    assert (args.city, args.units) == ("Bangkok", "metric")


@pytest.mark.parametrize("raw", ["", "   ", "none"])
def test_a_no_arg_tool_accepts_anything(raw: str) -> None:
    assert isinstance(parse_tool_args(TOOLS["get_current_time"], raw), NoArgs)


# --------------------------------------------------------------------------- #
# validation errors a model can act on
# --------------------------------------------------------------------------- #


def test_an_empty_expression_is_rejected_with_the_field_name() -> None:
    observation = run_tool("calculate", "")
    assert observation.startswith("Error: invalid arguments for calculate(expression: str)")
    assert "expression" in observation


def test_an_over_long_expression_is_rejected_by_the_schema() -> None:
    observation = run_tool("calculate", "1+" * 400)
    assert observation.startswith("Error: invalid arguments")
    assert "at most 500 characters" in observation


def test_an_invented_field_name_is_rejected_rather_than_ignored() -> None:
    observation = run_tool("calculate", json.dumps({"formula": "2 + 2"}))
    assert observation.startswith("Error: invalid arguments")
    assert "formula" in observation
    assert "expression" in observation, "the error should name the field that was expected"


def test_a_missing_required_field_names_it() -> None:
    with pytest.raises(ToolArgumentError, match="city"):
        parse_tool_args(TWO_FIELD_TOOL, '{"units": "metric"}')


def test_a_multi_field_tool_rejects_a_bare_value_and_asks_for_json() -> None:
    with pytest.raises(ToolArgumentError, match="JSON object"):
        parse_tool_args(TWO_FIELD_TOOL, "Bangkok")


def test_malformed_json_is_reported_as_an_argument_error() -> None:
    observation = run_tool("calculate", '{"expression": "2 + 2"')
    assert observation.startswith("Error: invalid arguments")


def test_the_error_tells_a_single_field_tool_what_to_send() -> None:
    observation = run_tool("calculate", "")
    assert "the expression itself on one line" in observation


# --------------------------------------------------------------------------- #
# dispatch still protects the loop
# --------------------------------------------------------------------------- #


def test_a_validation_failure_never_reaches_the_tool() -> None:
    def explode(_args: CalculateArgs) -> str:
        raise AssertionError("the tool must not run with invalid arguments")

    original = TOOLS["calculate"]
    TOOLS["calculate"] = Tool(
        name="calculate",
        description=original.description,
        args_model=CalculateArgs,
        run=explode,
        example=original.example,
    )
    try:
        assert run_tool("calculate", "").startswith("Error: invalid arguments")
    finally:
        TOOLS["calculate"] = original


def test_valid_arguments_still_reach_the_tool() -> None:
    assert run_tool("calculate", "6 * 7").endswith("= 42")
    assert run_tool("calculate", '{"expression": "6 * 7"}').endswith("= 42")
