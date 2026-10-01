"""A fake OpenAI client, so the ReAct loop can be tested without a model.

The real client is only ever used for two things -- ``models.list()`` and
``chat.completions.create()`` -- so the fake implements exactly those, hands back
a scripted sequence of replies, and records what it was asked for.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, cast

from openai import OpenAI


@dataclass
class FakeUsage:
    prompt_tokens: int = 100
    completion_tokens: int = 20
    total_tokens: int = 120


@dataclass
class FakeMessage:
    content: str | None


@dataclass
class FakeChoice:
    message: FakeMessage
    finish_reason: str = "stop"


@dataclass
class FakeCompletion:
    choices: list[FakeChoice]
    usage: FakeUsage | None = field(default_factory=FakeUsage)


@dataclass
class FakeModel:
    id: str


@dataclass
class FakeModelList:
    data: list[FakeModel]


class FakeCompletions:
    """Plays back a script, one entry per call, and records the requests.

    A script entry is either a reply to return or an exception to raise, which
    is what lets a test say "fail twice, then succeed".
    """

    def __init__(self, script: list[str | Exception], error: Exception | None = None) -> None:
        self._script = list(script)
        self._error = error
        self.calls: list[dict[str, Any]] = []

    def create(self, **kwargs: Any) -> FakeCompletion:
        self.calls.append(kwargs)
        if self._error is not None:
            raise self._error
        if not self._script:
            raise AssertionError(
                f"the agent asked for reply #{len(self.calls)} but the script ran out"
            )
        entry = self._script.pop(0)
        if isinstance(entry, Exception):
            raise entry
        return FakeCompletion(choices=[FakeChoice(message=FakeMessage(entry))])


class FakeChat:
    def __init__(self, completions: FakeCompletions) -> None:
        self.completions = completions


class FakeModels:
    def __init__(self, models: list[str], error: Exception | None = None) -> None:
        self._models = models
        self._error = error

    def list(self) -> FakeModelList:
        if self._error is not None:
            raise self._error
        return FakeModelList(data=[FakeModel(id=name) for name in self._models])


class FakeOpenAI:
    """Stands in for :class:`openai.OpenAI` in tests."""

    def __init__(
        self,
        replies: list[str] | None = None,
        models: list[str] | None = None,
        completion_error: Exception | None = None,
        models_error: Exception | None = None,
        script: list[str | Exception] | None = None,
    ) -> None:
        """
        :param replies: successful replies, in order.
        :param script: replies and exceptions interleaved, for retry tests.
        :param completion_error: raised on every call, however many are made.
        """
        if script is not None and replies is not None:
            raise ValueError("pass either replies or script, not both")
        entries: list[str | Exception] = list(script or replies or [])
        self.completions = FakeCompletions(entries, error=completion_error)
        self.chat = FakeChat(self.completions)
        self.models = FakeModels(models if models is not None else ["qwen2.5:7b"], models_error)

    @property
    def calls(self) -> list[dict[str, Any]]:
        """Every ``chat.completions.create`` call the agent made."""
        return self.completions.calls

    def as_client(self) -> OpenAI:
        """Cast to the real client type for injection into ``ReActAgent``."""
        return cast("OpenAI", self)
