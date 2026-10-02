"""The OmniAgent ReAct engine.

A hand-rolled Reason + Act loop, no agent framework involved. The only
dependency is the ``openai`` client, pointed at a local Ollama server that
speaks the OpenAI-compatible API.

The loop is deliberately small and readable:

    1. Send the conversation (system prompt + scratchpad) to the model.
    2. Stop generation at "Observation:" so the model cannot invent tool output.
    3. Parse "Final Answer:" -> done, or "Action:"/"Action Input:" -> run a tool.
    4. Append the real Observation to the scratchpad and go back to step 1.
"""

from __future__ import annotations

import hashlib
import logging
import re
import time
from collections import Counter
from collections.abc import Callable, Iterable
from typing import Any, cast

from openai import APIConnectionError, APIStatusError, OpenAI
from openai.types.chat import ChatCompletion, ChatCompletionMessageParam
from pydantic import BaseModel, Field

import observability as obs
from tools import NO_ARG_INPUTS, TOOLS, describe_tools, run_tool, tool_names

_log = obs.get_logger("agent")

DEFAULT_BASE_URL = "http://localhost:11434/v1"
DEFAULT_API_KEY = "local-ollama"  # Ollama ignores it; the client demands one.
DEFAULT_MODEL = "qwen2.5:7b"

SYSTEM_PROMPT_TEMPLATE = """You are OmniAgent, a careful reasoning assistant that solves tasks by \
thinking step by step and calling tools.

AVAILABLE TOOLS
{tools}

RESPONSE FORMAT -- you MUST follow it exactly.

To use a tool, reply with exactly three lines and then STOP:

Thought: <why you need the tool, one short sentence>
Action: <exactly one of: {tool_names}>
Action Input: <the raw input for the tool, on ONE line, no quotes, no code fences>

The system will then run the tool and send you back a line starting with:

Observation: <the real result>

You may repeat the Thought / Action / Action Input cycle as many times as you \
need. When you have enough information, reply with exactly two lines:

Thought: <one short sentence explaining that you are done>
Final Answer: <the complete answer, written for the user>

HARD RULES
1. Never write an "Observation:" line yourself. The system writes it. Stop \
immediately after "Action Input:".
2. Emit at most ONE Action per reply.
3. Every reply must begin with "Thought:".
4. Every reply must contain either an "Action:" line or a "Final Answer:" line, \
never both.
5. Use "calculate" for EVERY arithmetic step, even easy ones. Do not compute in \
your head.
6. Use "get_current_time" whenever the answer depends on the current date, day \
or time. You have no other way of knowing it.
7. "Action Input" is the raw argument only -- write `2 + 2`, not \
`calculate(2 + 2)`. For a tool that takes no arguments, write `none`.
8. If an Observation starts with "Error:", read it, fix your input, and try \
again rather than giving up.
9. If the question needs no tool at all, answer immediately with Thought + \
Final Answer.
10. A short follow-up question is still a question. "Now divide that by 3" or \
"And README.md?" gets the same Thought/Action/Action Input treatment as anything \
else -- never a bare sentence, and never arithmetic done in your head just \
because the conversation has warmed up.

WORKED EXAMPLE

Question: What is 15% of 240, and what day is it today?
Thought: I need the percentage first, so I will use the calculator.
Action: calculate
Action Input: 240 * 0.15
Observation: 240 * 0.15 = 36
Thought: Now I need today's date.
Action: get_current_time
Action Input: none
Observation: Local time: 2026-01-05 09:12:44 (Monday, UTC+0700) | UTC: 2026-01-05 02:12:44
Thought: I have both pieces of information.
Final Answer: 15% of 240 is 36, and today is Monday, 5 January 2026.

WORKED EXAMPLE -- A FOLLOW-UP

Question: Now halve that percentage.
Thought: That refers to the 36 from before, and halving it is arithmetic, so I \
use the calculator.
Action: calculate
Action Input: 36 / 2
Observation: 36 / 2 = 18
Thought: I have the answer.
Final Answer: Half of 36 is 18.
"""

# Parsing patterns. DOTALL on the tail captures multi-line inputs/answers.
_FINAL_ANSWER_RE = re.compile(r"Final\s*Answer\s*:\s*(.*)", re.IGNORECASE | re.DOTALL)
_THOUGHT_RE = re.compile(
    r"Thought\s*:\s*(.*?)(?=\n\s*(?:Action|Final\s*Answer|Observation)\s*:|\Z)",
    re.IGNORECASE | re.DOTALL,
)
_ACTION_RE = re.compile(r"Action\s*:\s*([^\n]+)", re.IGNORECASE)
_ACTION_INPUT_RE = re.compile(
    r"Action\s*Input\s*:\s*(.*?)(?=\n\s*(?:Thought|Action|Observation|Final\s*Answer)\s*:|\Z)",
    re.IGNORECASE | re.DOTALL,
)
# "calculate(2 + 2)" written on the Action line instead of split across two lines.
_INLINE_CALL_RE = re.compile(r"^([A-Za-z_][A-Za-z0-9_]*)\s*\((.*)\)\s*$", re.DOTALL)

_BRACKET_PAIRS = {"()", "<>", "[]"}

#: Shortest string that can still be a quoted or bracketed wrapper.
_MIN_WRAPPED_LENGTH = 2

#: Ollama answers an unknown model tag with a 404.
_HTTP_NOT_FOUND = 404

#: Status codes worth trying again: the server is busy or briefly unwell, not
#: wrong. A 404 for a missing model tag will never fix itself, so it is absent.
_RETRYABLE_STATUS = frozenset({408, 409, 425, 429, 500, 502, 503, 504})


def _is_wrapped(value: str) -> bool:
    """True when the value is long enough to carry a matching pair of delimiters."""
    return len(value) >= _MIN_WRAPPED_LENGTH



# --------------------------------------------------------------------------- #
# message constructors
# --------------------------------------------------------------------------- #
# The OpenAI client types each role as its own TypedDict, so a plain
# {"role": ..., "content": ...} dict does not type-check. These three keep the
# call sites readable without scattering casts around.


#: Stands in for a tool output that had to be dropped to fit the window.
_ELIDED = "[earlier tool output omitted so that this request fits the context window]"

#: Marks the newest message when even that had to be cut back.
_CLIPPED = "\n[clipped to fit the context window]"

#: Characters per token. Crude on purpose: the point is to stay clear of the
#: limit, not to match the tokeniser, which we cannot run from here anyway.
_CHARS_PER_TOKEN = 4

#: Per-message overhead the chat format adds around the content.
_MESSAGE_OVERHEAD_TOKENS = 4


def _estimate_tokens(message: ChatCompletionMessageParam) -> int:
    content = message.get("content") or ""
    return len(str(content)) // _CHARS_PER_TOKEN + _MESSAGE_OVERHEAD_TOKENS


#: Stands in for a reply the loop threw away for breaking format. Short on
#: purpose: it has to carry no facts of its own.
_DISCARDED_REPLY = "(this reply was discarded: it did not follow the required format)"

#: Appended when one observation had to be shortened. Worded so it cannot be
#: mistaken for part of the tool's own output, and carrying no count of its
#: own: capped, a file read ended "34 of 258 lines shown" while the answer to
#: "how many lines does it have" sat 33 lines further up, so this note was
#: handing the model two wrong candidates at the moment it had to pick a
#: number. The full observation is in the log either way.
OBSERVATION_CAPPED_NOTE = "\n[observation capped: the rest of this output was not shown]"


def cap_observation(observation: str, max_tokens: int) -> str:
    """Shorten one observation so it cannot crowd out the rest of the prompt.

    The budget trimmer only acts once the whole prompt exceeds the window. An
    observation can sit far below that and still dominate: asked for a line
    count, the fine-tune read the whole 257-line file, and that one observation
    took 71% of a 5,091-token prompt against a 16,384-token window. Nothing was
    over budget, so nothing was trimmed -- and the model then continued the
    file's text instead of the format. One empty reply, one Thought lifted
    verbatim from the file's own docstring, and a call to get_current_time that
    nobody had asked for, whose result reached the final answer.

    The head is kept, because that is where a tool puts the summary line that
    often answers the question on its own.
    """
    limit = max_tokens * _CHARS_PER_TOKEN
    if len(observation) <= limit:
        return observation

    lines = observation.splitlines()
    kept: list[str] = []
    used = 0
    for line in lines:
        if used + len(line) + 1 > limit:
            break
        kept.append(line)
        used += len(line) + 1

    if not kept:
        # One unbroken line: a minified file, or a long error. Cut it anyway.
        return observation[:limit] + OBSERVATION_CAPPED_NOTE

    return "\n".join(kept) + OBSERVATION_CAPPED_NOTE


def _system(content: str) -> ChatCompletionMessageParam:
    return {"role": "system", "content": content}


def _user(content: str) -> ChatCompletionMessageParam:
    return {"role": "user", "content": content}


def _assistant(content: str) -> ChatCompletionMessageParam:
    return {"role": "assistant", "content": content}


class AgentConfig(BaseModel):
    """Runtime configuration for a single agent instance."""

    model: str = Field(default=DEFAULT_MODEL, description="Ollama model tag.")
    base_url: str = Field(default=DEFAULT_BASE_URL, description="Local OpenAI-compatible endpoint.")
    api_key: str = Field(default=DEFAULT_API_KEY, description="Placeholder; Ollama ignores it.")
    temperature: float = Field(default=0.1, ge=0.0, le=2.0)
    max_steps: int = Field(default=8, ge=1, le=50, description="Max ReAct iterations per question.")
    timeout: float = Field(default=180.0, gt=0, description="Per-request timeout in seconds.")
    verbose: bool = Field(default=True, description="Stream the reasoning trace to the console.")
    max_retries: int = Field(
        default=2,
        ge=0,
        le=10,
        description="Extra attempts after a transient model-server failure.",
    )
    retry_backoff: float = Field(
        default=1.0,
        ge=0.0,
        description="Seconds before the first retry; doubled for each attempt after it.",
    )
    max_repeated_actions: int = Field(
        default=2,
        ge=1,
        le=10,
        description="How often the same failing Action may repeat before the agent intervenes.",
    )
    context_window: int = Field(
        default=8192,
        ge=1024,
        description=(
            "Tokens the model has been configured for. The OpenAI API cannot be asked, "
            "so this is what the server was told -- for Ollama, the Modelfile's num_ctx."
        ),
    )
    reply_reserve: int = Field(
        default=512,
        ge=64,
        description="Tokens held back from the prompt so the reply has room.",
    )
    max_observation_tokens: int = Field(
        default=600,
        ge=64,
        description=(
            "Tokens any single tool observation may add to the prompt. Sized against "
            "the baseline prompt rather than the window: system prompt plus question "
            "measures about 1,400 tokens, so 600 keeps one observation a minority "
            "voice. The window is not the binding constraint -- share of prompt is."
        ),
    )


class Step(BaseModel):
    """One iteration of the loop, kept for inspection and testing."""

    thought: str = ""
    action: str | None = None
    action_input: str | None = None
    observation: str | None = None
    final_answer: str | None = None
    raw: str = ""


class AgentError(RuntimeError):
    """Raised when the loop cannot continue (e.g. the model is unreachable)."""


def model_is_installed(requested: str, available: Iterable[str]) -> bool:
    """Whether a model tag names one of the server's models.

    Ollama stores an untagged model as ``name:latest`` but accepts ``name``,
    so a plain string comparison refuses a model that is in fact installed --
    which is exactly what happens to a model you just built yourself.
    """
    wanted = requested.strip()
    if not wanted:
        return False
    candidates = {wanted, f"{wanted}:latest"}
    if wanted.endswith(":latest"):
        candidates.add(wanted.removesuffix(":latest"))
    return any(name in candidates for name in available)


def _parse(text: str) -> Step:
    """Turn one raw model reply into a structured :class:`Step`."""
    step = Step(raw=text)

    thought = _THOUGHT_RE.search(text)
    if thought:
        step.thought = thought.group(1).strip()

    final = _FINAL_ANSWER_RE.search(text)
    if final:
        step.final_answer = final.group(1).strip()
        return step

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

    step.action = name
    step.action_input = _clean_action_input(raw_input)
    return step


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


class ReActAgent:
    """A ReAct agent backed by a local Ollama model."""

    def __init__(
        self,
        config: AgentConfig | None = None,
        printer: Callable[[str], None] = print,
        client: OpenAI | None = None,
    ) -> None:
        """Build an agent.

        :param client: an already-built OpenAI client. Tests inject a fake one;
            leaving it out builds a client pointed at the configured local
            endpoint.
        """
        self.config = config or AgentConfig()
        self._print = printer
        self.client = client or OpenAI(
            base_url=self.config.base_url,
            api_key=self.config.api_key,
            timeout=self.config.timeout,
            max_retries=0,
        )
        self.system_prompt = SYSTEM_PROMPT_TEMPLATE.format(
            tools=describe_tools(), tool_names=tool_names()
        )
        # Long-term memory: only user questions and final answers, so the
        # scratchpad from an earlier turn never pollutes the next one.
        self.history: list[ChatCompletionMessageParam] = []
        self.last_trace: list[Step] = []
        self._turn = 0

        obs.event(
            "agent.created",
            logger=_log,
            # INFO, not DEBUG: this record carries the system prompt the dataset
            # exporter replays, so a log written at the default level has to
            # contain it or none of the run is usable for training.
            level=logging.INFO,
            # api_key is redacted by the formatter, which this proves.
            config=self.config.model_dump(),
            tools=list(TOOLS),
            # The exporter replays this verbatim as the system turn, and the
            # digest tells runs made with different prompts apart.
            system_prompt=self.system_prompt,
            system_prompt_sha256=hashlib.sha256(
                self.system_prompt.encode("utf-8")
            ).hexdigest(),
        )

    # -- public API -------------------------------------------------------- #

    def reset(self) -> None:
        """Forget the conversation history."""
        obs.event("agent.reset", logger=_log, level=logging.DEBUG, turns=self._turn)
        self.history.clear()
        self.last_trace.clear()

    def check_connection(self) -> list[str]:
        """Return the model tags the local server offers, or raise AgentError."""
        try:
            available = [m.id for m in self.client.models.list().data]
        except APIConnectionError as exc:
            obs.event(
                "agent.connection.unreachable",
                logger=_log,
                level=logging.ERROR,
                base_url=self.config.base_url,
                exc_info=True,
            )
            raise AgentError(
                f"Cannot reach a local model server at {self.config.base_url}. "
                "Is Ollama running? Start it with 'ollama serve'."
            ) from exc
        except APIStatusError as exc:
            obs.event(
                "agent.connection.error",
                logger=_log,
                level=logging.ERROR,
                base_url=self.config.base_url,
                status_code=exc.status_code,
                exc_info=True,
            )
            raise AgentError(
                f"Model server returned HTTP {exc.status_code}: {exc.message}"
            ) from exc

        obs.event(
            "agent.connection.ok",
            logger=_log,
            base_url=self.config.base_url,
            model=self.config.model,
            model_installed=model_is_installed(self.config.model, available),
            available=available,
        )
        return available

    def run(self, question: str) -> str:
        """Answer one question, running the ReAct loop until it settles."""
        self._turn += 1
        with obs.bind(turn=self._turn):
            return self._run_turn(question)

    def _run_turn(self, question: str) -> str:
        scratchpad: list[ChatCompletionMessageParam] = [_user(question)]
        self.last_trace = []
        attempts: Counter[tuple[str, str]] = Counter()
        started = time.perf_counter()
        obs.event(
            "agent.turn.start",
            logger=_log,
            question=question,
            max_steps=self.config.max_steps,
            history_messages=len(self.history),
        )

        for iteration in range(1, self.config.max_steps + 1):
            with obs.bind(step=iteration):
                reply = self._complete(scratchpad)
                step = _parse(reply)
                self.last_trace.append(step)
                self._trace(iteration, step)

                if step.final_answer is None and step.action is None:
                    # A reply that broke format is not kept verbatim. Asked for
                    # a line count, the model opened with "sandbox.py has 204
                    # lines." -- no Final Answer prefix, and the number invented
                    # before a single tool had run. Appended as-is it became the
                    # model's own premise, and it repeated 204 for the rest of
                    # the turn even after read_file put the real 257 in front of
                    # it. The turn is kept so the exchange still alternates; the
                    # content is not, because the nudge below states the format
                    # in full and the fabrication has no job left to do.
                    scratchpad.append(_assistant(_DISCARDED_REPLY))
                else:
                    scratchpad.append(_assistant(reply))

                if step.final_answer is not None:
                    obs.event(
                        "agent.step.final_answer",
                        logger=_log,
                        thought=step.thought,
                        answer=step.final_answer,
                    )
                    return self._finish(question, step.final_answer, started, iteration)

                if step.action is None:
                    # The model broke format. Tell it exactly what is missing.
                    obs.event(
                        "agent.format.violation",
                        logger=_log,
                        level=logging.WARNING,
                        reply=reply,
                    )
                    nudge = (
                        "Your last reply did not follow the required format. Reply with "
                        "either:\n"
                        "Thought: ...\nAction: <tool name>\nAction Input: <input>\n"
                        "or:\nThought: ...\nFinal Answer: <answer>"
                    )
                    scratchpad.append(_user(nudge))
                    step.observation = "(format correction sent)"
                    continue

                observation = self._invoke_tool(step)
                # The rut check below still sees the whole thing; only what the
                # model is asked to read again is capped.
                shown = cap_observation(observation, self.config.max_observation_tokens)
                scratchpad.append(_user(f"Observation: {shown}"))

                intervention = self._check_for_a_rut(step, observation, attempts)
                if intervention is not None:
                    scratchpad.append(_user(intervention))

        # Out of steps: ask for the best answer it can give from what it has.
        obs.event(
            "agent.budget.exhausted",
            logger=_log,
            level=logging.WARNING,
            max_steps=self.config.max_steps,
        )
        fallback = self._force_final_answer(scratchpad)
        return self._finish(question, fallback, started, self.config.max_steps)

    def _check_for_a_rut(
        self, step: Step, observation: str, attempts: Counter[tuple[str, str]]
    ) -> str | None:
        """Notice the model retrying an identical failing Action, and say so.

        Small models will happily send the same broken Action Input until the
        step budget runs out. Repeating the Observation does not help them --
        telling them it is a repeat does.

        A *succeeding* call repeated verbatim is a rut too, and used not to be
        caught. Asked which of two files was longer, both fine-tuned models read
        the same file nine times -- every read succeeded, so nothing intervened,
        and the whole step budget went on re-reading text already in the
        conversation. The threshold is higher for successes, because reading one
        file twice while working through a comparison is reasonable; a third
        identical call is not.
        """
        failed = observation.startswith("Error:")
        threshold = (
            self.config.max_repeated_actions if failed else self.config.max_repeated_actions + 1
        )

        signature = (step.action or "", step.action_input or "")
        attempts[signature] += 1
        count = attempts[signature]
        if count < threshold:
            return None

        obs.event(
            "agent.loop.repeated_action",
            logger=_log,
            level=logging.WARNING,
            tool=signature[0],
            tool_input=signature[1],
            attempts=count,
            failing=failed,
        )
        if failed:
            return (
                f"You have now tried {signature[0]} with exactly that input {count} times "
                "and it failed the same way each time. Do not send it again. Either fix "
                "the input based on the error, use a different tool, or give your "
                "Final Answer explaining what you could not do."
            )
        return (
            f"You have already called {signature[0]} with exactly that input {count} times "
            "and it succeeded every time -- the result is already above, so calling it "
            "again tells you nothing new. Use what you have: either a different tool, or "
            "your Final Answer."
        )

    def _invoke_tool(self, step: Step) -> str:
        """Run the tool a step asked for, logging the call and its result."""
        tool_name = step.action or ""
        obs.event(
            "agent.tool.call",
            logger=_log,
            tool=tool_name,
            tool_input=step.action_input or "",
            thought=step.thought,
        )

        started = time.perf_counter()
        observation = run_tool(tool_name, step.action_input or "")
        elapsed_ms = round((time.perf_counter() - started) * 1000, 2)

        step.observation = observation
        failed = observation.startswith("Error:")
        obs.event(
            "agent.tool.result",
            logger=_log,
            level=logging.WARNING if failed else logging.INFO,
            tool=tool_name,
            ok=not failed,
            observation=observation,
            elapsed_ms=elapsed_ms,
        )
        self._trace_observation(observation)
        return observation

    def _finish(self, question: str, answer: str, started: float, steps: int) -> str:
        obs.event(
            "agent.turn.end",
            logger=_log,
            answer=answer,
            steps_used=steps,
            elapsed_ms=round((time.perf_counter() - started) * 1000, 2),
        )
        return self._remember(question, answer)

    # -- internals --------------------------------------------------------- #

    def _messages(
        self, scratchpad: list[ChatCompletionMessageParam]
    ) -> list[ChatCompletionMessageParam]:
        return self._fit(_system(self.system_prompt), self.history, scratchpad)

    def _fit(
        self,
        system: ChatCompletionMessageParam,
        history: list[ChatCompletionMessageParam],
        scratchpad: list[ChatCompletionMessageParam],
    ) -> list[ChatCompletionMessageParam]:
        """Shrink the conversation so the server never has to.

        When a request exceeds the context window, Ollama drops tokens from the
        front -- which is where the system prompt lives. Asked how many lines a
        file had, a 7B model on a 4096-token context replied "The current date
        and time is Friday, 2 October 2026": the file read had filled the
        window, and the format instructions and the question had both been cut
        away with it.

        So the trimming happens here, where the parts can be told apart. What
        goes, in order: whole earlier turns, then the oldest tool output of this
        turn, then -- only if nothing else is left -- the tail of the newest
        message. The system prompt and the question are never dropped.
        """
        budget = self.config.context_window - self.config.reply_reserve
        kept_history = list(history)
        pad: list[dict[str, Any]] = [dict(message) for message in scratchpad]

        def assembled() -> list[dict[str, Any]]:
            return [dict(system), *(dict(m) for m in kept_history), *pad]

        def total() -> int:
            return sum(
                _estimate_tokens(cast("ChatCompletionMessageParam", m)) for m in assembled()
            )

        original = total()
        if original <= budget:
            return [system, *kept_history, *scratchpad]

        # 1. Earlier turns go first, oldest pair at a time: they are the least
        #    relevant thing in the request.
        while kept_history and total() > budget:
            del kept_history[: min(2, len(kept_history))]

        # 2. Then this turn's older tool output, keeping the question at index 0
        #    and the newest message intact.
        for index in range(1, max(1, len(pad) - 1)):
            if total() <= budget:
                break
            if len(str(pad[index].get("content", ""))) > len(_ELIDED):
                pad[index]["content"] = _ELIDED

        # 3. Last resort: shorten the newest message. Better a clipped
        #    observation than a request the server silently mangles.
        if total() > budget and pad:
            over = total() - budget
            content = str(pad[-1].get("content", ""))
            keep = max(0, len(content) - (over * _CHARS_PER_TOKEN) - len(_CLIPPED))
            if keep < len(content):
                pad[-1]["content"] = content[:keep] + _CLIPPED

        final = total()
        obs.event(
            "agent.context.trimmed",
            logger=_log,
            level=logging.WARNING,
            estimated_tokens_before=original,
            estimated_tokens_after=final,
            budget=budget,
            context_window=self.config.context_window,
            earlier_turns_dropped=len(history) - len(kept_history),
            still_over=final > budget,
        )
        return cast("list[ChatCompletionMessageParam]", assembled())

    def _complete(self, scratchpad: list[ChatCompletionMessageParam], stop: bool = True) -> str:
        messages = self._messages(scratchpad)
        obs.event(
            "agent.llm.request",
            logger=_log,
            model=self.config.model,
            temperature=self.config.temperature,
            message_count=len(messages),
            stop_enabled=stop,
        )

        started = time.perf_counter()
        response = self._create_with_retries(messages, stop=stop)
        elapsed_ms = round((time.perf_counter() - started) * 1000, 2)
        content = (response.choices[0].message.content or "").strip()
        usage = response.usage
        obs.event(
            "agent.llm.response",
            logger=_log,
            model=self.config.model,
            elapsed_ms=elapsed_ms,
            reply_chars=len(content),
            finish_reason=response.choices[0].finish_reason,
            prompt_tokens=usage.prompt_tokens if usage else None,
            completion_tokens=usage.completion_tokens if usage else None,
            reply=content,
        )
        return content

    def _create_with_retries(
        self, messages: list[ChatCompletionMessageParam], *, stop: bool
    ) -> ChatCompletion:
        """Call the model, retrying the failures that are worth retrying.

        A busy or still-loading Ollama is the normal case here -- the first
        request after an idle period routinely times out while the model is
        paged in. A 404 for a missing model tag is not retried, because no
        amount of waiting will create it.
        """
        attempts = self.config.max_retries + 1
        for attempt in range(1, attempts + 1):
            try:
                return self.client.chat.completions.create(
                    model=self.config.model,
                    messages=messages,
                    temperature=self.config.temperature,
                    stop=["\nObservation:", "Observation:"] if stop else None,
                )
            except APIConnectionError as exc:
                self._handle_attempt_failure(exc, attempt, attempts, retryable=True)
            except APIStatusError as exc:
                self._handle_attempt_failure(
                    exc, attempt, attempts, retryable=exc.status_code in _RETRYABLE_STATUS
                )

        raise AssertionError("unreachable: the retry loop either returns or raises")

    def _handle_attempt_failure(
        self,
        exc: APIConnectionError | APIStatusError,
        attempt: int,
        attempts: int,
        *,
        retryable: bool,
    ) -> None:
        """Log an attempt, then either sleep for the next one or give up."""
        status_code = exc.status_code if isinstance(exc, APIStatusError) else None

        if retryable and attempt < attempts:
            delay = self.config.retry_backoff * (2 ** (attempt - 1))
            obs.event(
                "agent.llm.retry",
                logger=_log,
                level=logging.WARNING,
                attempt=attempt,
                of=attempts,
                delay_seconds=round(delay, 3),
                status_code=status_code,
                reason=type(exc).__name__,
            )
            if delay:
                time.sleep(delay)
            return

        if isinstance(exc, APIConnectionError):
            obs.event(
                "agent.llm.unreachable",
                logger=_log,
                level=logging.ERROR,
                base_url=self.config.base_url,
                attempts=attempt,
                exc_info=True,
            )
            raise AgentError(
                f"Lost the connection to {self.config.base_url} after {attempt} "
                f"attempt{'s' if attempt > 1 else ''}. Is Ollama still running?"
            ) from exc

        obs.event(
            "agent.llm.error",
            logger=_log,
            level=logging.ERROR,
            status_code=status_code,
            model=self.config.model,
            attempts=attempt,
            retryable=retryable,
            exc_info=True,
        )
        hint = ""
        if status_code == _HTTP_NOT_FOUND:
            hint = f" Pull the model first: 'ollama pull {self.config.model}'."
        raise AgentError(f"Model server error (HTTP {status_code}).{hint}") from exc

    def _force_final_answer(self, scratchpad: list[ChatCompletionMessageParam]) -> str:
        scratchpad.append(
            _user(
                f"You have used all {self.config.max_steps} available steps. "
                "Reply now with 'Thought:' followed by 'Final Answer:' only, "
                "using what you already know. Do not request another tool."
            )
        )
        reply = self._complete(scratchpad, stop=False)
        step = _parse(reply)
        self.last_trace.append(step)
        if step.final_answer:
            return step.final_answer
        return reply or "I ran out of reasoning steps before reaching an answer."

    def _remember(self, question: str, answer: str) -> str:
        self.history.append(_user(question))
        self.history.append(_assistant(answer))
        return answer

    def _trace(self, iteration: int, step: Step) -> None:
        if not self.config.verbose:
            return
        self._print(f"\n  [step {iteration}]")
        if step.thought:
            self._print(f"  Thought      : {step.thought}")
        if step.action:
            self._print(f"  Action       : {step.action}")
            self._print(f"  Action Input : {step.action_input or '(none)'}")
        if not step.thought and not step.action and step.final_answer is None:
            self._print(f"  (unparsed reply) {step.raw[:200]}")

    def _trace_observation(self, observation: str) -> None:
        if self.config.verbose:
            # The same cap the prompt gets, from the same setting, so the trace
            # cannot disagree with what the model was actually given. One
            # read_file scrolled 257 numbered lines past a demo screen while
            # the model saw the first 35; the log keeps the whole observation.
            shown = cap_observation(observation, self.config.max_observation_tokens)
            self._print(f"  Observation  : {shown}")
