"""Tests for the pre-training dataset validator.

Its job is to refuse, so most of these check that it does.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from validate_dataset import check_shape, find_secrets, main, validate_file

SYSTEM = "You are OmniAgent."


def example(*turns: tuple[str, str]) -> dict[str, Any]:
    messages = [{"role": "system", "content": SYSTEM}]
    messages.extend({"role": role, "content": content} for role, content in turns)
    return {"messages": messages}


def clean(index: int = 0) -> dict[str, Any]:
    return example(
        ("user", f"What is {index} + 1?"),
        (
            "assistant",
            f"Thought: maths\nAction: calculate\nAction Input: {index} + 1",
        ),
        ("user", f"Observation: {index} + 1 = {index + 1}"),
        ("assistant", f"Thought: done\nFinal Answer: {index + 1}"),
    )


def write(path: Path, examples: list[dict[str, Any]]) -> Path:
    path.write_text(
        "\n".join(json.dumps(item) for item in examples) + "\n", encoding="utf-8"
    )
    return path


# --------------------------------------------------------------------------- #
# shape
# --------------------------------------------------------------------------- #


def test_a_clean_dataset_passes(tmp_path: Path) -> None:
    report = validate_file(write(tmp_path / "d.jsonl", [clean(i) for i in range(12)]))

    assert report.ok
    assert report.examples == 12
    assert report.actions["calculate"] == 12
    assert report.errors == []
    assert report.warnings == []


@pytest.mark.parametrize(
    ("messages", "fragment"),
    [
        ([], "non-empty list"),
        ("not a list", "non-empty list"),
        ([{"role": "user", "content": "hi"}], "must start with a system turn"),
        (
            [{"role": "system", "content": SYSTEM}, {"role": "user", "content": "hi"}],
            "must end with an assistant turn",
        ),
        (
            [
                {"role": "system", "content": SYSTEM},
                {"role": "user", "content": "hi"},
                {"role": "assistant", "content": "a"},
                {"role": "assistant", "content": "b"},
            ],
            "stop alternating",
        ),
        (
            [{"role": "system", "content": SYSTEM}, {"role": "wizard", "content": "hi"}],
            "has role 'wizard'",
        ),
        (
            [{"role": "system", "content": SYSTEM}, {"role": "user", "content": "   "}],
            "empty content",
        ),
        ([{"role": "system", "content": SYSTEM}, "not an object"], "not an object"),
    ],
)
def test_check_shape_rejects(messages: Any, fragment: str) -> None:
    problems = check_shape(messages, "line 1")

    assert problems
    assert any(fragment in problem for problem in problems)


def test_a_malformed_line_is_an_error(tmp_path: Path) -> None:
    path = tmp_path / "d.jsonl"
    path.write_text(json.dumps(clean()) + "\nnot json\n", encoding="utf-8")

    report = validate_file(path, min_examples=1)

    assert not report.ok
    assert any("not valid JSON" in error for error in report.errors)


def test_a_line_without_messages_is_an_error(tmp_path: Path) -> None:
    path = tmp_path / "d.jsonl"
    path.write_text(json.dumps({"text": "hello"}) + "\n", encoding="utf-8")

    report = validate_file(path)

    assert not report.ok
    assert any("missing a 'messages' key" in error for error in report.errors)


def test_an_empty_dataset_is_refused(tmp_path: Path) -> None:
    path = tmp_path / "d.jsonl"
    path.write_text("\n\n", encoding="utf-8")

    report = validate_file(path)

    assert not report.ok
    assert "the dataset is empty" in report.errors


def test_a_missing_dataset_is_refused(tmp_path: Path) -> None:
    report = validate_file(tmp_path / "nope.jsonl")

    assert not report.ok
    assert any("no such dataset" in error for error in report.errors)


# --------------------------------------------------------------------------- #
# secrets
# --------------------------------------------------------------------------- #


@pytest.mark.parametrize(
    ("text", "label"),
    [
        ("here is sk-abcdefghijklmnop1234567890", "OpenAI-style key"),
        ("AKIAIOSFODNN7EXAMPLE", "AWS access key"),
        ("ghp_abcdefghijklmnopqrstuvwxyz0123456789", "GitHub token"),
        ("xoxb-123456789012-abcdefghijkl", "Slack token"),
        ("-----BEGIN RSA PRIVATE KEY-----", "private key block"),
        ("Authorization: Bearer abcdefghijklmnopqrstuvwxyz", "bearer token"),
        ("API_KEY=supersecretvalue", "assigned secret"),
        ("password: hunter2hunter2", "assigned secret"),
    ],
)
def test_credentials_are_detected(text: str, label: str) -> None:
    assert label in find_secrets(text)


@pytest.mark.parametrize(
    "code_line",
    [
        "api_key=self.api_key,",
        "            api_key=self.config.api_key,",
        'api_key=os.getenv("OPENAI_API_KEY"),',
        "    api_key: str = Field(default=DEFAULT_API_KEY)",
        "api_key=settings.api_key",
    ],
)
def test_code_that_references_a_credential_is_not_a_finding(code_line: str) -> None:
    """Found by the validator refusing a real dataset.

    The agent had read agent.py and the line `api_key=self.api_key,` tripped the
    assignment pattern. OmniAgent's file tools read source for a living, and
    source is full of such lines; a validator that cries wolf on all of them
    gets ignored, which is worse than one that is slightly narrower. A value
    holding attribute access or a call is a reference, not a credential.
    """
    assert "assigned secret" not in find_secrets(code_line)


@pytest.mark.parametrize(
    "assignment",
    [
        "API_KEY=supersecretvalue",
        "OMNIAGENT_API_KEY=sk-do-not-log-this",
        "DB_PASSWORD=hunter2hunter2",
        "MY_SECRET: abcdefghijkl",
        'api_key = "sk-live-abcdefghijklmnop"',
    ],
)
def test_a_literal_assignment_is_still_a_finding(assignment: str) -> None:
    """The prefixed ones are the point.

    The pattern used to start with \b, which does not match inside
    OMNIAGENT_API_KEY or DB_PASSWORD because an underscore is a word character.
    Every prefixed environment-variable name slipped through unnoticed.
    """
    assert "assigned secret" in find_secrets(assignment)


def test_ordinary_text_is_not_flagged() -> None:
    for harmless in (
        "Thought: maths\nAction: calculate\nAction Input: 2 + 2",
        "Observation: 2 + 2 = 4",
        "The API key is stored in a password manager.",
        "Final Answer: 15% of 2400 is 360.",
    ):
        assert find_secrets(harmless) == []


def test_a_secret_anywhere_refuses_the_dataset(tmp_path: Path) -> None:
    """A model trained on a leaked key will reproduce it."""
    poisoned = clean()
    poisoned["messages"][3]["content"] = "Observation: API_KEY=sk-abcdefghijklmnop12345"

    report = validate_file(write(tmp_path / "d.jsonl", [clean(1), poisoned]), min_examples=1)

    assert not report.ok
    assert any("found in the user turn" in error for error in report.errors)


def test_a_secret_in_the_system_prompt_refuses_the_dataset(tmp_path: Path) -> None:
    poisoned = clean()
    poisoned["messages"][0]["content"] = "You are OmniAgent. Key: sk-abcdefghijklmnop12345"

    report = validate_file(write(tmp_path / "d.jsonl", [poisoned]), min_examples=1)

    assert not report.ok


# --------------------------------------------------------------------------- #
# warnings
# --------------------------------------------------------------------------- #


def test_too_few_examples_warns_but_passes(tmp_path: Path) -> None:
    report = validate_file(write(tmp_path / "d.jsonl", [clean(i) for i in range(3)]))

    assert report.ok
    assert any("only 3 examples" in warning for warning in report.warnings)


def test_duplicates_are_reported(tmp_path: Path) -> None:
    report = validate_file(
        write(tmp_path / "d.jsonl", [clean(0), clean(0), clean(1)]), min_examples=1
    )

    assert report.ok
    assert any("1 duplicate" in warning for warning in report.warnings)


def test_an_entirely_identical_dataset_warns(tmp_path: Path) -> None:
    report = validate_file(
        write(tmp_path / "d.jsonl", [clean(0)] * 12), min_examples=1
    )

    assert any("every example is identical" in warning for warning in report.warnings)


def test_a_dataset_with_no_tool_use_warns(tmp_path: Path) -> None:
    chatty = example(("user", "Hello"), ("assistant", "Thought: easy\nFinal Answer: Hi."))
    report = validate_file(write(tmp_path / "d.jsonl", [chatty] * 12), min_examples=1)

    assert any("will not teach tool use" in warning for warning in report.warnings)


# --------------------------------------------------------------------------- #
# the CLI
# --------------------------------------------------------------------------- #


def test_the_cli_succeeds_on_a_good_dataset(tmp_path: Path) -> None:
    path = write(tmp_path / "d.jsonl", [clean(i) for i in range(12)])
    assert main([str(path)]) == 0


def test_the_cli_fails_on_a_bad_dataset(tmp_path: Path) -> None:
    path = tmp_path / "d.jsonl"
    path.write_text(json.dumps({"messages": []}) + "\n", encoding="utf-8")
    assert main([str(path)]) == 1


def test_the_cli_honours_min_examples(tmp_path: Path) -> None:
    path = write(tmp_path / "d.jsonl", [clean(0)])
    assert main([str(path), "--min-examples", "100"]) == 0, "too few is a warning, not an error"


def test_the_report_names_what_it_found(tmp_path: Path) -> None:
    report = validate_file(write(tmp_path / "d.jsonl", [clean(i) for i in range(12)]))
    rendered = report.render()

    assert "examples   : 12" in rendered
    assert "calculate: 12" in rendered
    assert "verdict    : OK" in rendered
