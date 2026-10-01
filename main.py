"""OmniAgent CLI entry point.

Starts an interactive REPL (or answers a single question with --ask) backed by
the local ReAct loop in ``agent.py``. Nothing here talks to the internet: every
request goes to the Ollama server on localhost.
"""

from __future__ import annotations

import argparse
import os
import sys

from agent import (
    DEFAULT_BASE_URL,
    DEFAULT_MODEL,
    AgentConfig,
    AgentError,
    ReActAgent,
)
from tools import TOOLS

BANNER = r"""
  ___                  _    _                 _
 / _ \ _ __ ___  _ __ (_)  / \   __ _  ___ _ __ | |_
| | | | '_ ` _ \| '_ \| | / _ \ / _` |/ _ \ '_ \| __|
| |_| | | | | | | | | | |/ ___ \ (_| |  __/ | | | |_
 \___/|_| |_| |_|_| |_|_/_/   \_\__, |\___|_| |_|\__|
                                |___/
  local-only ReAct agent  -  no cloud, no framework
"""

HELP_TEXT = """
Commands:
  /help     show this help
  /tools    list the tools the agent can call
  /reset    clear the conversation history
  /quit     exit (also: /exit, or Ctrl-C)

Anything else is sent to the agent as a question.
"""


class Style:
    """ANSI colours, disabled when the output is not an interactive terminal."""

    enabled = sys.stdout.isatty() and os.environ.get("NO_COLOR") is None

    @classmethod
    def _wrap(cls, code: str, text: str) -> str:
        return f"\033[{code}m{text}\033[0m" if cls.enabled else text

    @classmethod
    def dim(cls, text: str) -> str:
        return cls._wrap("2", text)

    @classmethod
    def cyan(cls, text: str) -> str:
        return cls._wrap("36", text)

    @classmethod
    def green(cls, text: str) -> str:
        return cls._wrap("32", text)

    @classmethod
    def red(cls, text: str) -> str:
        return cls._wrap("31", text)

    @classmethod
    def bold(cls, text: str) -> str:
        return cls._wrap("1", text)


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="omniagent",
        description="A local-only ReAct agent running on Ollama.",
    )
    parser.add_argument(
        "--model",
        default=os.environ.get("OMNIAGENT_MODEL", DEFAULT_MODEL),
        help=f"Ollama model tag (default: {DEFAULT_MODEL}).",
    )
    parser.add_argument(
        "--base-url",
        default=os.environ.get("OMNIAGENT_BASE_URL", DEFAULT_BASE_URL),
        help=f"OpenAI-compatible endpoint (default: {DEFAULT_BASE_URL}).",
    )
    parser.add_argument(
        "--max-steps", type=int, default=8, help="Max ReAct iterations (default: 8)."
    )
    parser.add_argument(
        "--temperature", type=float, default=0.1, help="Sampling temperature (default: 0.1)."
    )
    parser.add_argument(
        "--quiet", action="store_true", help="Hide the Thought/Action/Observation trace."
    )
    parser.add_argument("--ask", metavar="QUESTION", help="Answer one question and exit.")
    return parser.parse_args(argv)


def preflight(agent: ReActAgent) -> bool:
    """Verify the local server is up and the requested model is present."""
    try:
        available = agent.check_connection()
    except AgentError as exc:
        print(Style.red(f"[!] {exc}"))
        return False

    print(Style.dim(f"    endpoint : {agent.config.base_url}"))
    print(Style.dim(f"    model    : {agent.config.model}"))

    if available and agent.config.model not in available:
        print(
            Style.red(
                f"[!] Model '{agent.config.model}' is not installed on this Ollama server."
            )
        )
        print(Style.dim(f"    installed: {', '.join(available) or '(none)'}"))
        print(Style.dim(f"    fix      : ollama pull {agent.config.model}"))
        return False
    return True


def answer(agent: ReActAgent, question: str) -> int:
    try:
        result = agent.run(question)
    except AgentError as exc:
        print(Style.red(f"\n[!] {exc}"))
        return 1
    print(Style.green("\nOmniAgent: ") + result + "\n")
    return 0


def repl(agent: ReActAgent) -> int:
    print(Style.dim(HELP_TEXT))
    while True:
        try:
            user_input = input(Style.cyan("You > ")).strip()
        except (EOFError, KeyboardInterrupt):
            print(Style.dim("\nBye."))
            return 0

        if not user_input:
            continue

        command = user_input.lower()
        if command in {"/quit", "/exit", "quit", "exit"}:
            print(Style.dim("Bye."))
            return 0
        if command == "/help":
            print(Style.dim(HELP_TEXT))
            continue
        if command == "/tools":
            for tool in TOOLS.values():
                print(f"  {Style.bold(tool.signature)}\n    {tool.description}")
            print()
            continue
        if command == "/reset":
            agent.reset()
            print(Style.dim("History cleared."))
            continue

        answer(agent, user_input)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)

    # Keep the box-drawing banner and any non-ASCII output readable on Windows.
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8", errors="replace")

    config = AgentConfig(
        model=args.model,
        base_url=args.base_url,
        max_steps=args.max_steps,
        temperature=args.temperature,
        verbose=not args.quiet,
    )
    agent = ReActAgent(config=config, printer=lambda text: print(Style.dim(text)))

    print(Style.cyan(BANNER))
    if not preflight(agent):
        return 1

    if args.ask:
        return answer(agent, args.ask)
    return repl(agent)


if __name__ == "__main__":
    raise SystemExit(main())
