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

import re
from typing import Callable, Dict, List, Optional

from openai import APIConnectionError, APIStatusError, OpenAI
from pydantic import BaseModel, Field

from tools import describe_tools, run_tool, tool_names

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

_NO_ARG_INPUTS = {"", "none", "null", "n/a", "na", "-", "nothing", "()", "no input"}


class AgentConfig(BaseModel):
    """Runtime configuration for a single agent instance."""

    model: str = Field(default=DEFAULT_MODEL, description="Ollama model tag.")
    base_url: str = Field(default=DEFAULT_BASE_URL, description="Local OpenAI-compatible endpoint.")
    api_key: str = Field(default=DEFAULT_API_KEY, description="Placeholder; Ollama ignores it.")
    temperature: float = Field(default=0.1, ge=0.0, le=2.0)
    max_steps: int = Field(default=8, ge=1, le=50, description="Max ReAct iterations per question.")
    timeout: float = Field(default=180.0, gt=0, description="Per-request timeout in seconds.")
    verbose: bool = Field(default=True, description="Stream the reasoning trace to the console.")


class Step(BaseModel):
    """One iteration of the loop, kept for inspection and testing."""

    thought: str = ""
    action: Optional[str] = None
    action_input: Optional[str] = None
    observation: Optional[str] = None
    final_answer: Optional[str] = None
    raw: str = ""


class AgentError(RuntimeError):
    """Raised when the loop cannot continue (e.g. the model is unreachable)."""


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
    if len(value) >= 2 and value[0] == value[-1] and value[0] in "\"'":
        value = value[1:-1].strip()
    if value.lower() in _NO_ARG_INPUTS:
        return ""
    # Small models like to wrap the placeholder: "(none)", "<none>", "[none]".
    if len(value) >= 2 and value[0] + value[-1] in {"()", "<>", "[]"}:
        if value[1:-1].strip().lower() in _NO_ARG_INPUTS:
            return ""
    return value


class ReActAgent:
    """A ReAct agent backed by a local Ollama model."""

    def __init__(
        self,
        config: Optional[AgentConfig] = None,
        printer: Callable[[str], None] = print,
    ) -> None:
        self.config = config or AgentConfig()
        self._print = printer
        self.client = OpenAI(
            base_url=self.config.base_url,
            api_key=self.config.api_key,
            timeout=self.config.timeout,
            max_retries=1,
        )
        self.system_prompt = SYSTEM_PROMPT_TEMPLATE.format(
            tools=describe_tools(), tool_names=tool_names()
        )
        # Long-term memory: only user questions and final answers, so the
        # scratchpad from an earlier turn never pollutes the next one.
        self.history: List[Dict[str, str]] = []
        self.last_trace: List[Step] = []

    # -- public API -------------------------------------------------------- #

    def reset(self) -> None:
        """Forget the conversation history."""
        self.history.clear()
        self.last_trace.clear()

    def check_connection(self) -> List[str]:
        """Return the model tags the local server offers, or raise AgentError."""
        try:
            return [m.id for m in self.client.models.list().data]
        except APIConnectionError as exc:
            raise AgentError(
                f"Cannot reach a local model server at {self.config.base_url}. "
                "Is Ollama running? Start it with 'ollama serve'."
            ) from exc
        except APIStatusError as exc:
            raise AgentError(f"Model server returned HTTP {exc.status_code}: {exc.message}") from exc

    def run(self, question: str) -> str:
        """Answer one question, running the ReAct loop until it settles."""
        scratchpad: List[Dict[str, str]] = [{"role": "user", "content": question}]
        self.last_trace = []

        for iteration in range(1, self.config.max_steps + 1):
            reply = self._complete(scratchpad)
            step = _parse(reply)
            self.last_trace.append(step)
            self._trace(iteration, step)

            scratchpad.append({"role": "assistant", "content": reply})

            if step.final_answer is not None:
                return self._remember(question, step.final_answer)

            if step.action is None:
                # The model broke format. Tell it exactly what is missing.
                nudge = (
                    "Your last reply did not follow the required format. Reply with "
                    "either:\n"
                    "Thought: ...\nAction: <tool name>\nAction Input: <input>\n"
                    "or:\nThought: ...\nFinal Answer: <answer>"
                )
                scratchpad.append({"role": "user", "content": nudge})
                step.observation = "(format correction sent)"
                continue

            observation = run_tool(step.action, step.action_input or "")
            step.observation = observation
            self._trace_observation(observation)
            scratchpad.append({"role": "user", "content": f"Observation: {observation}"})

        # Out of steps: ask for the best answer it can give from what it has.
        fallback = self._force_final_answer(scratchpad)
        return self._remember(question, fallback)

    # -- internals --------------------------------------------------------- #

    def _messages(self, scratchpad: List[Dict[str, str]]) -> List[Dict[str, str]]:
        return [{"role": "system", "content": self.system_prompt}, *self.history, *scratchpad]

    def _complete(self, scratchpad: List[Dict[str, str]], stop: bool = True) -> str:
        try:
            response = self.client.chat.completions.create(
                model=self.config.model,
                messages=self._messages(scratchpad),
                temperature=self.config.temperature,
                stop=["\nObservation:", "Observation:"] if stop else None,
            )
        except APIConnectionError as exc:
            raise AgentError(
                f"Lost the connection to {self.config.base_url}. Is Ollama still running?"
            ) from exc
        except APIStatusError as exc:
            hint = ""
            if exc.status_code == 404:
                hint = f" Pull the model first: 'ollama pull {self.config.model}'."
            raise AgentError(f"Model server error (HTTP {exc.status_code}).{hint}") from exc

        content = response.choices[0].message.content or ""
        return content.strip()

    def _force_final_answer(self, scratchpad: List[Dict[str, str]]) -> str:
        scratchpad.append(
            {
                "role": "user",
                "content": (
                    f"You have used all {self.config.max_steps} available steps. "
                    "Reply now with 'Thought:' followed by 'Final Answer:' only, "
                    "using what you already know. Do not request another tool."
                ),
            }
        )
        reply = self._complete(scratchpad, stop=False)
        step = _parse(reply)
        self.last_trace.append(step)
        if step.final_answer:
            return step.final_answer
        return reply or "I ran out of reasoning steps before reaching an answer."

    def _remember(self, question: str, answer: str) -> str:
        self.history.append({"role": "user", "content": question})
        self.history.append({"role": "assistant", "content": answer})
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
            self._print(f"  Observation  : {observation}")
