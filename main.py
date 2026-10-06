"""OmniAgent CLI entry point.

Starts an interactive REPL (or answers a single question with --ask) backed by
the local ReAct loop in ``agent.py``. Nothing here talks to the internet: every
request goes to the Ollama server on localhost.
"""

from __future__ import annotations

import argparse
import logging
import os
import sys
from pathlib import Path

import observability as obs
from agent import (
    DEFAULT_BASE_URL,
    DEFAULT_MODEL,
    AgentError,
    ReActAgent,
    model_is_installed,
)
from config import DEFAULT_CONFIG_NAME, LOG_LEVELS, ConfigError, render, resolve
from sandbox import SandboxError, set_workspace, without_own_transcripts
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
    """Parse the command line.

    Every setting defaults to None so that an unused flag does not outrank the
    config file; config.resolve() applies the real defaults.
    """
    parser = argparse.ArgumentParser(
        prog="omniagent",
        description="A local-only ReAct agent running on Ollama.",
    )
    parser.add_argument("--ask", metavar="QUESTION", help="Answer one question and exit.")
    parser.add_argument(
        "--config", type=Path, help=f"Config file to read (default: ./{DEFAULT_CONFIG_NAME})."
    )
    parser.add_argument("--profile", help="Named [profile.NAME] section to apply.")
    parser.add_argument(
        "--print-config",
        action="store_true",
        help="Show every resolved setting and where it came from, then exit.",
    )

    settings = parser.add_argument_group("settings (override the config file)")
    settings.add_argument("--model", help=f"Ollama model tag (default: {DEFAULT_MODEL}).")
    settings.add_argument(
        "--base-url", help=f"OpenAI-compatible endpoint (default: {DEFAULT_BASE_URL})."
    )
    settings.add_argument("--max-steps", type=int, help="Max ReAct iterations (default: 8).")
    settings.add_argument(
        "--temperature", type=float, help="Sampling temperature (default: 0.1)."
    )
    settings.add_argument(
        "--max-retries", type=int, help="Retries after a transient failure (default: 2)."
    )
    settings.add_argument(
        "--timeout", type=float, help="Per-request timeout in seconds (default: 180)."
    )
    settings.add_argument(
        "--workspace", type=Path, help="Directory the file tools may read inside."
    )
    settings.add_argument(
        "--log-file", type=Path, help="Append structured JSON-lines logs to this file."
    )
    settings.add_argument(
        "--log-level", choices=LOG_LEVELS, help="Minimum level for the log (default: INFO)."
    )
    settings.add_argument(
        "--log-console",
        action="store_true",
        default=None,
        help="Also stream the JSON logs to stderr (stdout keeps the readable trace).",
    )
    settings.add_argument(
        "--quiet",
        action="store_true",
        default=None,
        help="Hide the Thought/Action/Observation trace.",
    )
    return parser.parse_args(argv)


def cli_settings(args: argparse.Namespace) -> dict[str, object]:
    """The settings the user actually passed, as config.resolve() wants them."""
    supplied: dict[str, object] = {
        name: getattr(args, name)
        for name in (
            "model",
            "base_url",
            "max_steps",
            "temperature",
            "max_retries",
            "timeout",
            "workspace",
            "log_file",
            "log_level",
            "log_console",
        )
        if getattr(args, name) is not None
    }
    if args.quiet is not None:
        supplied["verbose"] = not args.quiet
    return supplied


def preflight(agent: ReActAgent) -> bool:
    """Verify the local server is up and the requested model is present."""
    try:
        available = agent.check_connection()
    except AgentError as exc:
        print(Style.red(f"[!] {exc}"))
        return False

    print(Style.dim(f"    endpoint : {agent.config.base_url}"))
    print(Style.dim(f"    model    : {agent.config.model}"))

    if available and not model_is_installed(agent.config.model, available):
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
    except KeyboardInterrupt:
        # A local 7B model can think for a long time; Ctrl-C during a step
        # should drop back to the prompt, not print a traceback.
        obs.event("cli.interrupted", level=logging.WARNING, question=question)
        print(Style.dim("\n(cancelled)"))
        return 130
    except AgentError as exc:
        obs.event("cli.aborted", level=logging.ERROR, reason=str(exc), exc_info=True)
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

    try:
        settings, sources = resolve(
            cli_settings(args), config_path=args.config, profile=args.profile
        )
    except ConfigError as exc:
        print(Style.red(f"[!] {exc}"))
        return 2

    if args.print_config:
        print(render(settings, sources))
        return 0

    # Structured logging must be live before the agent is built, so that even
    # construction and preflight end up in the log.
    session_id = obs.configure(
        level=settings.log_level,
        log_file=settings.log_file,
        console=settings.log_console,
    )

    try:
        # Not just the active log: any earlier transcript replays an earlier
        # conversation into the context and into the dataset just as well.
        # Asked where 'budget' was used in agent.py, the agent answered a
        # sentence it found in a previous run's transcript, verbatim.
        workspace = without_own_transcripts(settings.workspace, settings.log_file)
    except SandboxError as exc:
        print(Style.red(f"[!] {exc}"))
        return 1
    set_workspace(workspace)

    agent = ReActAgent(
        config=settings.agent_config(), printer=lambda text: print(Style.dim(text))
    )

    print(Style.cyan(BANNER))
    if args.profile:
        print(Style.dim(f"    profile  : {args.profile}"))
    print(Style.dim(f"    workspace: {workspace.root}"))
    if settings.log_file is not None or settings.log_console:
        print(Style.dim(f"    session  : {session_id}"))
        if settings.log_file is not None:
            print(Style.dim(f"    log      : {settings.log_file}"))
    if not preflight(agent):
        return 1

    if args.ask:
        return answer(agent, args.ask)
    return repl(agent)


if __name__ == "__main__":
    raise SystemExit(main())
