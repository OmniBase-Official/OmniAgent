"""Behavioural tests for the ReAct loop itself.

M2's tests assert on what the loop *logs*. These assert on what it *does*: the
messages it sends, what it remembers between turns, how it handles a model that
will not cooperate, and where it gives up. Breaking the loop should turn one of
these red.
"""

from __future__ import annotations

from typing import Any

import pytest
from openai import APIConnectionError

from agent import AgentConfig, AgentError, ReActAgent
from tests.fakes import FakeOpenAI

FINAL = "Thought: done\nFinal Answer: {answer}"
CALL = "Thought: maths\nAction: calculate\nAction Input: {expression}"


def build(fake: FakeOpenAI, **overrides: Any) -> ReActAgent:
    # retry_backoff=0: the retry policy is tested by counting attempts, never by
    # making the suite wait for them.
    overrides.setdefault("retry_backoff", 0.0)
    config = AgentConfig(verbose=False, **overrides)
    return ReActAgent(config=config, client=fake.as_client(), printer=lambda _: None)


def sent_messages(fake: FakeOpenAI, call_index: int) -> list[dict[str, Any]]:
    return list(fake.calls[call_index]["messages"])


def roles(fake: FakeOpenAI, call_index: int) -> list[str]:
    return [message["role"] for message in sent_messages(fake, call_index)]


def contents(fake: FakeOpenAI, call_index: int) -> list[str]:
    return [str(message["content"]) for message in sent_messages(fake, call_index)]


# --------------------------------------------------------------------------- #
# what gets sent to the model
# --------------------------------------------------------------------------- #


def test_the_first_request_is_system_then_question() -> None:
    fake = FakeOpenAI(replies=[FINAL.format(answer="4")])
    build(fake).run("What is 2 + 2?")

    assert roles(fake, 0) == ["system", "user"]
    assert "OmniAgent" in contents(fake, 0)[0]
    assert contents(fake, 0)[1] == "What is 2 + 2?"


def test_the_system_prompt_covers_follow_up_questions() -> None:
    """Regression: on "Now divide that by 3" the model used to answer in prose.

    Fifteen turns of one collection run were lost this way - every follow-up in
    every multi-turn session. The model knew the answer and simply said it,
    arithmetic done in its head, no Thought and no Action.
    """
    fake = FakeOpenAI(replies=[FINAL.format(answer="4")])
    build(fake).run("hi")

    system = contents(fake, 0)[0]
    assert "follow-up" in system
    assert "Now divide that by 3" in system
    assert "WORKED EXAMPLE -- A FOLLOW-UP" in system


def test_the_system_prompt_lists_every_tool() -> None:
    fake = FakeOpenAI(replies=[FINAL.format(answer="4")])
    build(fake).run("hi")

    system = contents(fake, 0)[0]
    assert "calculate(expression: str)" in system
    assert "get_current_time()" in system


def test_an_observation_is_appended_as_a_user_message() -> None:
    fake = FakeOpenAI(replies=[CALL.format(expression="2 + 2"), FINAL.format(answer="4")])
    build(fake).run("What is 2 + 2?")

    assert roles(fake, 1) == ["system", "user", "assistant", "user"]
    assert contents(fake, 1)[2].startswith("Thought: maths")
    assert contents(fake, 1)[3] == "Observation: 2 + 2 = 4"


def test_the_stop_sequence_is_sent_so_the_model_cannot_invent_observations() -> None:
    fake = FakeOpenAI(replies=[FINAL.format(answer="4")])
    build(fake).run("What is 2 + 2?")

    assert fake.calls[0]["stop"] == ["\nObservation:", "Observation:"]


def test_model_and_temperature_are_passed_through() -> None:
    fake = FakeOpenAI(replies=[FINAL.format(answer="4")])
    build(fake, model="gemma2:2b", temperature=0.7).run("hi")

    assert fake.calls[0]["model"] == "gemma2:2b"
    assert fake.calls[0]["temperature"] == pytest.approx(0.7)


# --------------------------------------------------------------------------- #
# memory between turns
# --------------------------------------------------------------------------- #


def test_the_second_turn_sees_the_first_question_and_answer() -> None:
    fake = FakeOpenAI(replies=[FINAL.format(answer="4653"), FINAL.format(answer="1551")])
    agent = build(fake)
    agent.run("What is 99 * 47?")
    agent.run("Now divide that by 3")

    assert roles(fake, 1) == ["system", "user", "assistant", "user"]
    assert contents(fake, 1)[1] == "What is 99 * 47?"
    # Stored with the marker, so that every past turn shows the next one the
    # format it has to reply in.
    assert contents(fake, 1)[2] == "Final Answer: 4653"
    assert contents(fake, 1)[3] == "Now divide that by 3"


def test_the_scratchpad_does_not_leak_into_the_next_turn() -> None:
    """Only the question and the answer are remembered, not the working out."""
    fake = FakeOpenAI(
        replies=[
            CALL.format(expression="99 * 47"),
            FINAL.format(answer="4653"),
            FINAL.format(answer="1551"),
        ]
    )
    agent = build(fake)
    agent.run("What is 99 * 47?")
    agent.run("Now divide that by 3")

    # Index 0 is the system prompt, whose worked example legitimately contains
    # an Observation line; the leak would be in the messages after it.
    second_turn = contents(fake, 2)
    assert len(second_turn) == 4
    assert not any("Observation:" in message for message in second_turn[1:])
    assert not any("Action Input" in message for message in second_turn[1:])


def test_reset_forgets_the_conversation() -> None:
    fake = FakeOpenAI(replies=[FINAL.format(answer="4"), FINAL.format(answer="5")])
    agent = build(fake)
    agent.run("first")
    agent.reset()
    assert agent.history == []
    assert agent.last_trace == []

    agent.run("second")

    # The second turn starts clean: no remembered first question.
    assert roles(fake, 1) == ["system", "user"]
    assert contents(fake, 1)[1] == "second"


def test_the_answer_returned_is_the_answer_remembered() -> None:
    fake = FakeOpenAI(replies=[FINAL.format(answer="It is 4.")])
    agent = build(fake)

    assert agent.run("What is 2 + 2?") == "It is 4."
    # The caller gets the answer; the history keeps it in ReAct shape.
    assert agent.history[-1]["content"] == "Final Answer: It is 4."


# --------------------------------------------------------------------------- #
# the trace
# --------------------------------------------------------------------------- #


def test_the_trace_records_every_step() -> None:
    fake = FakeOpenAI(replies=[CALL.format(expression="2 + 2"), FINAL.format(answer="4")])
    agent = build(fake)
    agent.run("What is 2 + 2?")

    assert len(agent.last_trace) == 2
    first, second = agent.last_trace
    assert (first.action, first.action_input) == ("calculate", "2 + 2")
    assert first.observation == "2 + 2 = 4"
    assert second.final_answer == "4"


def test_the_trace_is_cleared_between_turns() -> None:
    fake = FakeOpenAI(
        replies=[
            CALL.format(expression="2 + 2"),
            FINAL.format(answer="4"),
            FINAL.format(answer="5"),
        ]
    )
    agent = build(fake)
    agent.run("first")
    agent.run("second")

    assert len(agent.last_trace) == 1


# --------------------------------------------------------------------------- #
# a model that will not cooperate
# --------------------------------------------------------------------------- #


def test_a_malformed_reply_gets_a_correction_not_a_crash() -> None:
    fake = FakeOpenAI(replies=["Sure, the answer is 4!", FINAL.format(answer="It is 4.")])
    agent = build(fake)

    assert agent.run("What is 2 + 2?") == "It is 4."

    nudge = contents(fake, 1)[-1]
    assert "did not follow the required format" in nudge
    assert "Final Answer:" in nudge


def test_a_thought_only_reply_counts_as_malformed() -> None:
    fake = FakeOpenAI(replies=["Thought: I am thinking.", FINAL.format(answer="4")])
    agent = build(fake)

    assert agent.run("What is 2 + 2?") == "4"
    assert "did not follow the required format" in contents(fake, 1)[-1]


def test_an_empty_reply_gets_a_correction() -> None:
    fake = FakeOpenAI(replies=["", FINAL.format(answer="4")])
    agent = build(fake)

    assert agent.run("What is 2 + 2?") == "4"
    assert "did not follow the required format" in contents(fake, 1)[-1]


def test_repeated_tool_errors_do_not_stop_the_loop() -> None:
    fake = FakeOpenAI(
        replies=[
            CALL.format(expression="1 / 0"),
            CALL.format(expression="2 +"),
            FINAL.format(answer="I could not compute that."),
        ]
    )
    agent = build(fake)

    assert agent.run("go") == "I could not compute that."
    observations = [step.observation for step in agent.last_trace[:2]]
    assert all(obs is not None and obs.startswith("Error:") for obs in observations)


# --------------------------------------------------------------------------- #
# the step budget
# --------------------------------------------------------------------------- #


def test_the_budget_caps_the_number_of_model_calls() -> None:
    loop = CALL.format(expression="1 + 1")
    fake = FakeOpenAI(replies=[loop, loop, FINAL.format(answer="2")])
    agent = build(fake, max_steps=2)

    assert agent.run("go") == "2"
    # Two budgeted steps, then one forced final answer.
    assert len(fake.calls) == 3


def test_the_forced_final_answer_drops_the_stop_sequence() -> None:
    """The model has to be able to write a long answer without being cut off."""
    loop = CALL.format(expression="1 + 1")
    fake = FakeOpenAI(replies=[loop, FINAL.format(answer="2")])
    build(fake, max_steps=1).run("go")

    assert fake.calls[0]["stop"] is not None
    assert fake.calls[-1]["stop"] is None


def test_the_forced_prompt_tells_the_model_to_stop_asking_for_tools() -> None:
    loop = CALL.format(expression="1 + 1")
    fake = FakeOpenAI(replies=[loop, FINAL.format(answer="2")])
    build(fake, max_steps=1).run("go")

    last = contents(fake, -1)[-1]
    assert "used all 1 available steps" in last
    # Case-insensitive: the clause moved into the middle of the sentence when
    # the prompt was given the question and told to use the Observations.
    assert "do not request another tool" in last.lower()


def test_a_stubborn_model_still_yields_something_usable() -> None:
    """If even the forced turn will not produce a Final Answer, use the text."""
    loop = CALL.format(expression="1 + 1")
    fake = FakeOpenAI(replies=[loop, "I really want to use another tool."])
    agent = build(fake, max_steps=1)

    assert agent.run("go") == "I really want to use another tool."


def test_a_silent_model_falls_back_to_an_explanation() -> None:
    loop = CALL.format(expression="1 + 1")
    fake = FakeOpenAI(replies=[loop, ""])
    agent = build(fake, max_steps=1)

    assert agent.run("go") == "I ran out of reasoning steps before reaching an answer."


def test_the_forced_answer_is_remembered_like_any_other() -> None:
    loop = CALL.format(expression="1 + 1")
    fake = FakeOpenAI(replies=[loop, FINAL.format(answer="2")])
    agent = build(fake, max_steps=1)
    agent.run("go")

    assert agent.history[-1]["content"] == "Final Answer: 2"


# --------------------------------------------------------------------------- #
# failures that must surface
# --------------------------------------------------------------------------- #


def test_a_dead_server_raises_rather_than_answering_wrongly() -> None:
    fake = FakeOpenAI(completion_error=APIConnectionError(request=None))  # type: ignore[arg-type]
    agent = build(fake)

    with pytest.raises(AgentError, match="Lost the connection"):
        agent.run("What is 2 + 2?")


def test_a_failed_turn_is_not_remembered() -> None:
    fake = FakeOpenAI(completion_error=APIConnectionError(request=None))  # type: ignore[arg-type]
    agent = build(fake)

    with pytest.raises(AgentError):
        agent.run("What is 2 + 2?")

    assert agent.history == []


def test_a_fabricated_fact_does_not_survive_a_format_violation() -> None:
    """A rejected reply must not leave its content standing as a premise.

    Asked for a line count, the fine-tune opened with "sandbox.py has 204
    lines." -- no Final Answer prefix, and the number invented before a single
    tool had run. Kept verbatim in the scratchpad it became the model's own
    premise: it went on repeating 204 for the rest of the turn, even after
    read_file had put the real 257 in front of it. The nudge already states the
    format in full, so the fabricated content has no job left to do.
    """
    fake = FakeOpenAI(
        replies=["sandbox.py has 204 lines.", FINAL.format(answer="257 lines.")]
    )

    assert build(fake).run("How many lines does sandbox.py have?") == "257 lines."

    resent = contents(fake, 1)
    assert not any("204" in text for text in resent), "the invented count came back"
    assert any("discarded" in text for text in resent), "nothing says it was dropped"


def test_the_forced_final_answer_restates_the_question() -> None:
    """Out of steps, the model answers the last thing it looked at.

    Measured: asked "What is 2 to the power of 11, minus 48?" with four
    questions behind it, the agent got 2 ** 11 - 48 = 2000 out of calculate at
    step 2, then drifted onto the previous question's file and spent the rest
    of the budget on it. The forced reply came back "`agent.py` contains 909
    lines of code" -- the most recent observation, not the question. The
    question was the oldest message in the scratchpad, behind eight steps of
    Thought, Action and Observation.

    Restating it here is not the change that was measured and reverted on
    2026-10-03. That one appended the question to every observation and cost
    two arithmetic answers on the held-out set. This reaches a prompt only once
    the step budget is gone, so a turn that ends normally never sees it.
    """
    loop = CALL.format(expression="1 + 1")
    fake = FakeOpenAI(replies=[loop, loop, FINAL.format(answer="2")])

    build(fake, max_steps=2).run("What is 2 to the power of 11, minus 48?")

    forced = str(fake.calls[-1]["messages"][-1]["content"])
    assert "out of steps" in forced.lower() or "all 2 available steps" in forced
    assert "What is 2 to the power of 11, minus 48?" in forced


def test_a_forced_reply_without_an_answer_is_not_handed_over_raw() -> None:
    """The second place raw protocol text reached the user as an answer.

    _answer_only cuts a Final Answer short at the next block, but a forced
    reply that never writes the marker at all skipped that entirely: the loop
    returned the reply verbatim. Told to read the Observations instead of
    recomputing, the model answered a question with

        Thought: The question asks for 2 to the power of 11 minus 48.
        Action: calculate

    in all three runs -- a tool request, at the step where tools are refused,
    printed as prose. The raw reply stays in Step.raw and in the log; what the
    caller gets is an admission.
    """
    loop = CALL.format(expression="1 + 1")
    protocol = "Thought: I will work it out\nAction: calculate\nAction Input: 1 + 1"
    fake = FakeOpenAI(replies=[loop, protocol])

    answer = build(fake, max_steps=1).run("What is 1 + 1?")

    assert "Action:" not in answer
    assert "Thought:" not in answer
    assert answer == "I ran out of reasoning steps before reaching an answer."


def test_a_remembered_answer_is_stored_in_the_shape_the_next_turn_must_use() -> None:
    """The history is what pulls a long session out of the ReAct format.

    Diagnosed with per-step logs on both settled drifts. Asked for
    2 ** 11 - 48 with four questions behind it the model opened with "2 to the
    power of 11 is 2048, and that minus 48 is 2000"; asked for the weather with
    seven behind it, "I don't have a built-in way to look up current weather
    conditions". Both are right -- the second is the honest answer the honesty
    axis wants -- and both were thrown away for want of a Final Answer prefix,
    after which the turn wandered onto the previous question's subject and
    answered that instead.

    The history was plain prose, so the longer it grew the harder it pulled
    towards replying conversationally. Stored with the marker, every past turn
    demonstrates the format instead of arguing against it. The answer handed
    back to the caller is unchanged.
    """
    fake = FakeOpenAI(replies=[FINAL.format(answer="4"), FINAL.format(answer="8")])
    agent = build(fake)

    assert agent.run("What is 2 + 2?") == "4"
    agent.run("And double it?")

    stored = [str(message["content"]) for message in agent.history]
    assert stored[1].startswith("Final Answer: ")
    assert "4" in stored[1]
    # And the second turn's prompt carries that shape in front of the model.
    second = [str(message["content"]) for message in sent_messages(fake, 1)]
    assert any(text.startswith("Final Answer: ") for text in second)
