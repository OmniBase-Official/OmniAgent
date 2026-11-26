"""Private rule text must never reach a commit (brief 44, owner ruling 42).

The owner's rule files (AGENTS.md, CLAUDE.md, CODEX.md, CURSOR.md) hold private rules.
Both remotes are public. On the main checkout the files are untracked and hidden only by
``.git/info/exclude``, which is local to that clone and not versioned: remove those lines
before the files are overwritten with sanitized text and ``git add -A`` stages the
private rules. This guard goes red in three states and stays green otherwise:

1. a rule file is TRACKED and holds a private marker;
2. a rule file is present, untracked and NOT ignored (what ``git add -A`` stages) and holds
   a private marker;
3. any tracked text file holds a secret-shaped string or an e-mail address that is not on
   the allowlist.

A rule file that is present and ignored is the safe state and stays green.

The check is a function of a repository root, so the tests drive it against throwaway git
repositories. Tracked content is read from the INDEX (what a commit would carry), never from
the working tree. Only paths, line numbers and marker indexes are ever reported: no matched
text, and no content of any rule file.

Secret-shaped samples are assembled from pieces so this file holds none itself.
Static: read-only git on throwaway repositories, no model, no socket.
"""

from __future__ import annotations

import hashlib
import os
import re
import shutil
import subprocess
from pathlib import Path, PurePosixPath

import pytest

PROJECT = Path(__file__).resolve().parent.parent
GIT = shutil.which("git")

#: The rule files by name, at any depth (the root and docs/ are the ones that exist today).
RULE_FILES = frozenset({"agents.md", "claude.md", "codex.md", "cursor.md"})

#: Four generic header phrases from the private files, matched without case and with any
#: run of whitespace collapsed. Phrases, not private text: a hash of normalised lines would
#: leak less and survive a reworded header, but could not be read or reviewed by anyone who
#: does not hold the private files, and a changed line would silently stop matching. The
#: owner approves this list before merge.
MARKERS = (
    "STANDING RULES (owner-issued",
    "ADDENDUM 3 TO THE ROUTING PROTOCOL",
    "QUALITY PUSH RULE (owner",
    "Autonomous Hybrid Model Routing Protocol",
)

#: name -> pattern. Boundaries and minimum lengths keep ordinary words ("task-based",
#: "sk-" inside "disk-usage") and the short fake keys in the tests from matching. A PEM key
#: counts only with a real line break and a base64 body after the header: the header alone
#: (a fixture, or a pattern in a scanner) is not a secret.
SECRET_PATTERNS = (
    ("github token", re.compile(r"\bgh[pousr]_[A-Za-z0-9]{36,}")),
    ("github fine-grained token", re.compile(r"\bgithub_pat_[A-Za-z0-9_]{40,}")),
    ("sk- key", re.compile(r"\bsk-[A-Za-z0-9_-]{32,}")),
    ("aws access key", re.compile(r"\b(?:AKIA|ASIA)[0-9A-Z]{16}\b")),
    ("slack token", re.compile(r"\bxox[abprs]-[0-9A-Za-z-]{10,}")),
    ("google api key", re.compile(r"\bAIza[0-9A-Za-z_-]{35}\b")),
    ("huggingface token", re.compile(r"\bhf_[A-Za-z0-9]{34,}")),
    (
        "pem private key",
        re.compile(
            r"-----BEGIN (?:[A-Z0-9]+ )*PRIVATE KEY-----[\r\n]+"
            r"(?:[A-Za-z-]+: [^\r\n]*[\r\n]+)*[A-Za-z0-9+/=]{16,}"
        ),
    ),
)

#: SHA-256 of the three fake secrets that tests/test_validate_dataset.py feeds the dataset
#: validator on purpose (hashed, so no secret-shaped text sits in this file): the AWS
#: documentation example key, a GitHub-token-shaped alphabet sequence, a Slack-shaped
#: sample. Allowed by exact value, not by path: a different string in the same file is
#: still flagged.
KNOWN_FAKES = frozenset(
    {
        "1a5d44a2dca19669d72edf4c4f1c27c4c1ca4b4408fbb17f6ce4ad452d78ddb3",
        "03aafb028d538b06c4341bf8cf2a692a3c6d1f36e34e0e0b376f407c6117a246",
        "7dd866a2f4ffbca0f2d07b59771645fb1933c031d61e55d8e270382d26246def",
    }
)

EMAIL = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9-]+(?:\.[A-Za-z0-9-]+)*\.[A-Za-z]{2,}")

#: Any address at the first domain (GitHub's commit-identity relay); the other two are used on
#: purpose: noreply@anthropic.com is the commit trailer's address, and 11434@evil.example is
#: the port and host of an SSRF-style URL (user-info form) in docs/pm/brief-14 and in
#: tests/test_endpoint_policy.py, on a reserved .example name. Nothing else is allowed.
EMAIL_DOMAIN_ALLOWED = "users.noreply.github.com"
EMAIL_ADDRESSES_ALLOWED = frozenset({"noreply@anthropic.com", "11434@evil.example"})

ADVICE = (
    "Private rule text or a secret would reach a commit and both remotes are public. "
    "Do not stage it: unstage it (git rm --cached), keep the rule files ignored until the "
    "sanitized text replaces them, and remove the secret. Found: {found}"
)


def _git_env() -> dict[str, str]:
    """The environment without GIT_*: a git hook exports GIT_DIR, which would make
    ``git -C <root>`` answer about the hook's repository instead of *root*."""
    return {key: value for key, value in os.environ.items() if not key.startswith("GIT_")}


def run_git(root: Path, *args: str, stdin: bytes | None = None) -> bytes:
    assert GIT is not None, "git is required for this test and was not found on PATH"
    done = subprocess.run(  # noqa: S603 - controlled argv; shell=False; read-only git
        [GIT, "-C", str(root), *args],
        input=stdin,
        capture_output=True,
        env=_git_env(),
        check=False,
        timeout=60,
    )
    assert done.returncode == 0, f"git {args[0]} failed with exit code {done.returncode}"
    return done.stdout


def _squash(text: str) -> str:
    return " ".join(text.casefold().split())


def _is_rule_file(path: str) -> bool:
    return PurePosixPath(path).name.casefold() in RULE_FILES


def marker_indexes(data: bytes) -> list[int]:
    text = _squash(data.decode("utf-8", "replace"))
    return [index for index, marker in enumerate(MARKERS) if _squash(marker) in text]


def _tracked_blobs(root: Path) -> dict[str, bytes]:
    """The index content of every tracked file: what the next commit would carry."""
    entries = [entry for entry in run_git(root, "ls-files", "-s", "-z").split(b"\0") if entry]
    files = []
    for entry in entries:
        meta, _, raw_path = entry.partition(b"\t")
        mode, sha, _stage = meta.split()
        if mode != b"160000":  # a submodule is a commit, not a blob
            files.append((raw_path.decode("utf-8", "replace"), sha))
    if not files:
        return {}
    output = run_git(root, "cat-file", "--batch", stdin=b"\n".join(sha for _, sha in files) + b"\n")
    blobs: dict[str, bytes] = {}
    position = 0
    for path, _sha in files:
        header_end = output.index(b"\n", position)
        _, kind, size = output[position:header_end].split()
        assert kind == b"blob", f"{path}: not a blob"
        start = header_end + 1
        blobs[path] = output[start : start + int(size)]
        position = start + int(size) + 1
    return blobs


def _line(text: str, offset: int) -> int:
    return text.count("\n", 0, offset) + 1


def _email_allowed(address: str) -> bool:
    folded = address.casefold()
    return folded.endswith("@" + EMAIL_DOMAIN_ALLOWED) or folded in EMAIL_ADDRESSES_ALLOWED


def find_violations(root: Path) -> list[str]:
    """Paths and positions only. A root that is not a git work tree has nothing to leak
    through git, so it reports none; a git failure inside one is an error, never a pass."""
    if not (root / ".git").exists():
        return []
    blobs = _tracked_blobs(root)
    found = [
        f"{path}: tracked rule file holds private marker {index}"
        for path, data in blobs.items()
        if _is_rule_file(path)
        for index in marker_indexes(data)
    ]
    untracked = run_git(root, "ls-files", "-z", "--others", "--exclude-standard")
    for raw in untracked.split(b"\0"):
        path = raw.decode("utf-8", "replace")
        if path and _is_rule_file(path):
            found += [
                f"{path}: present, untracked and not ignored (git add -A would stage it), "
                f"holds private marker {index}"
                for index in marker_indexes((root / path).read_bytes())
            ]
    for path, data in blobs.items():
        if b"\0" in data[:8000]:
            continue
        text = data.decode("utf-8", "replace")
        found += [
            f"{path}:{_line(text, hit.start())}: secret-shaped string ({name})"
            for name, pattern in SECRET_PATTERNS
            for hit in pattern.finditer(text)
            if hashlib.sha256(hit.group().encode()).hexdigest() not in KNOWN_FAKES
        ]
        found += [
            f"{path}:{_line(text, hit.start())}: e-mail address not on the allowlist"
            for hit in EMAIL.finditer(text)
            if not _email_allowed(hit.group())
        ]
    return sorted(found)


# --------------------------------------------------------------------------- #
# throwaway repositories
# --------------------------------------------------------------------------- #

HERE = "owner private text below: "

#: The approved phrases again, typed out, so that dropping one from MARKERS fails a test
#: instead of quietly shrinking the list the tests are built from.
APPROVED = (
    "STANDING RULES (owner-issued",
    "ADDENDUM 3 TO THE ROUTING PROTOCOL",
    "QUALITY PUSH RULE (owner",
    "Autonomous Hybrid Model Routing Protocol",
)


def make_repo(root: Path) -> Path:
    root.mkdir()
    run_git(root, "init", "-q")
    empty = root.parent / (root.name + ".excludes")
    empty.write_text("", encoding="utf-8")
    run_git(root, "config", "core.excludesFile", str(empty))
    return root


def put(repo: Path, name: str, text: str | bytes, *, add: bool = True) -> None:
    target = repo / name
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(text if isinstance(text, bytes) else text.encode("utf-8"))
    if add:
        run_git(repo, "add", "-f", "--", name)


def private(index: int = 0) -> str:
    return f"intro\n{HERE}{APPROVED[index]} and more\nend\n"


@pytest.fixture
def repo(tmp_path: Path) -> Path:
    return make_repo(tmp_path / "repo")


#: The four names at the root and under docs/, the same names in another case and another
#: directory (a case-insensitive file system cannot hold both spellings side by side), and a
#: hidden directory. A name, not a place, makes a file a rule file.
RULE_PATHS = [
    "AGENTS.md", "CLAUDE.md", "CODEX.md", "CURSOR.md",
    "docs/AGENTS.md", "docs/CLAUDE.md", "docs/CODEX.md", "docs/CURSOR.md",
    "lower/agents.md", "mixed/Claude.MD", ".claude/CLAUDE.md",
]  # fmt: skip


# --------------------------------------------------------------------------- #
# states 1 and 2: a rule file with a private marker
# --------------------------------------------------------------------------- #


def test_a_tracked_rule_file_with_a_marker_is_found_at_every_path(repo: Path) -> None:
    for name in RULE_PATHS:
        put(repo, name, private())

    assert find_violations(repo) == sorted(
        f"{name}: tracked rule file holds private marker 0" for name in RULE_PATHS
    )


def test_an_untracked_unignored_rule_file_with_a_marker_is_found_at_every_path(
    repo: Path,
) -> None:
    for name in RULE_PATHS:
        put(repo, name, private(), add=False)

    assert find_violations(repo) == sorted(
        f"{name}: present, untracked and not ignored (git add -A would stage it), "
        "holds private marker 0"
        for name in RULE_PATHS
    )


def test_each_marker_alone_is_enough_in_both_states(repo: Path) -> None:
    for index in range(len(APPROVED)):
        put(repo, f"tracked{index}/CLAUDE.md", private(index))
        put(repo, f"loose{index}/AGENTS.md", private(index), add=False)

    found = find_violations(repo)

    for name in ("CLAUDE.md", "AGENTS.md"):
        assert [line[-1] for line in found if f"/{name}" in line] == ["0", "1", "2", "3"]


def test_a_failure_names_the_file_and_the_marker_number_never_the_text(repo: Path) -> None:
    put(repo, "CLAUDE.md", private(2))
    put(repo, "docs/CODEX.md", private(3), add=False)

    message = ADVICE.format(found=find_violations(repo))

    assert "CLAUDE.md" in message
    assert "marker 2" in message
    assert "marker 3" in message
    assert all(marker not in message for marker in APPROVED)
    assert HERE not in message


def test_a_marker_is_matched_through_case_and_spacing_changes(repo: Path) -> None:
    put(repo, "CLAUDE.md", "standing   rules (OWNER-ISSUED 2026)\n")

    assert find_violations(repo) == ["CLAUDE.md: tracked rule file holds private marker 0"]


def test_a_sanitized_tracked_rule_file_is_fine(repo: Path) -> None:
    put(repo, "AGENTS.md", "# Rules\nRun the three gates before every commit.\n")
    put(repo, "docs/CLAUDE.md", "Notes for contributors.\n", add=False)

    assert find_violations(repo) == []


def test_a_present_rule_file_that_is_ignored_stays_green_through_the_exclude_file(
    repo: Path,
) -> None:
    put(repo, "CLAUDE.md", private(), add=False)
    exclude = repo / ".git" / "info" / "exclude"
    exclude.parent.mkdir(exist_ok=True)
    exclude.write_text("CLAUDE.md\n", encoding="utf-8")

    assert find_violations(repo) == []


def test_a_present_rule_file_that_is_ignored_stays_green_through_gitignore(repo: Path) -> None:
    put(repo, ".gitignore", "AGENTS.md\ndocs/CODEX.md\n")
    put(repo, "AGENTS.md", private(), add=False)
    put(repo, "docs/CODEX.md", private(1), add=False)

    assert find_violations(repo) == []


def test_removing_the_exclude_line_turns_the_hidden_file_red(repo: Path) -> None:
    """The exact hazard: the same file, the same content, one line removed."""
    exclude = repo / ".git" / "info" / "exclude"
    exclude.parent.mkdir(exist_ok=True)
    exclude.write_text("CLAUDE.md\n", encoding="utf-8")
    put(repo, "CLAUDE.md", private(), add=False)
    assert find_violations(repo) == []

    exclude.write_text("", encoding="utf-8")

    assert len(find_violations(repo)) == 1


def test_ignoring_a_file_does_not_hide_it_once_it_is_tracked(repo: Path) -> None:
    put(repo, ".gitignore", "CLAUDE.md\n")
    put(repo, "CLAUDE.md", private())

    assert find_violations(repo) == ["CLAUDE.md: tracked rule file holds private marker 0"]


def test_the_index_is_read_not_the_working_tree(repo: Path) -> None:
    """A staged private file whose working copy was sanitized afterwards is still staged."""
    put(repo, "CLAUDE.md", private())
    (repo / "CLAUDE.md").write_text("sanitized\n", encoding="utf-8")

    assert find_violations(repo) == ["CLAUDE.md: tracked rule file holds private marker 0"]


def test_a_marker_outside_a_rule_file_is_not_this_guards_business(repo: Path) -> None:
    """Known limit, pinned so it is a decision and not a surprise: the name is the scope."""
    put(repo, "docs/pm/notes.md", private())

    assert find_violations(repo) == []


# --------------------------------------------------------------------------- #
# state 3: secrets and e-mail addresses in any tracked text file
# --------------------------------------------------------------------------- #

BODY = "QUJDREVGR0hJSktMTU5PUFFSU1RVVldYWVo="
SECRETS = {
    "github token": "gh" + "p_" + "A1b2" * 9,
    "github fine-grained token": "github" + "_pat_" + "Z9" * 30,
    "sk- key": "s" + "k-" + "Ab1" * 12,
    "aws access key": "AK" + "IA" + "ABCDEFGHIJKLMNOP",
    "slack token": "xo" + "xb-" + "1234567890-abcdefghij",
    "google api key": "AI" + "za" + "A" * 35,
    "huggingface token": "h" + "f_" + "a" * 34,
    "pem private key": "-----BEGIN " + "RSA PRIVATE KEY-----\n" + BODY + "\n",
}


def test_a_secret_shaped_string_in_a_tracked_file_is_found_by_line(repo: Path) -> None:
    for number, name in enumerate(SECRETS):
        put(repo, f"src/settings{number}.py", f"first\nsecond\nvalue = '{SECRETS[name]}'\n")

    found = find_violations(repo)

    assert found == [
        f"src/settings{number}.py:3: secret-shaped string ({name})"
        for number, name in enumerate(SECRETS)
    ]
    assert not any(secret in ADVICE.format(found=found) for secret in SECRETS.values())


#: Text that looks a little like a secret and is not one.
ORDINARY = [
    "the task-based approach to the long-running jobs of the evening",
    "ask-me-anything-about-the-very-long-name-of-this-thing-please",
    "gh" + "p_short and " + "AK" + "IA" + "TOOSHORT",
    "hf" + "_token_name_is_not_a_token and " + "sk-" + "short",
    "-----BEGIN " + "PRIVATE KEY-----\\n",
    '("-----BEGIN ' + 'RSA PRIVATE KEY-----", "private key block")',
]


def test_ordinary_text_and_header_only_fixtures_are_not_secrets(repo: Path) -> None:
    for number, text in enumerate(ORDINARY):
        put(repo, f"docs/notes{number}.md", text + "\n")

    assert find_violations(repo) == []


def test_an_encrypted_pem_key_is_found(repo: Path) -> None:
    key = "-----BEGIN " + "RSA PRIVATE KEY-----\nProc-Type: 4,ENCRYPTED\nDEK-Info: AES\n\n" + BODY
    put(repo, "key.txt", key + "\n")

    assert find_violations(repo) == ["key.txt:1: secret-shaped string (pem private key)"]


def test_a_known_fake_is_allowed_by_value_but_not_by_file(repo: Path) -> None:
    fake = "AK" + "IA" + "IOSFODNN7EXAMPLE"
    put(repo, "tests/test_validate_dataset.py", f'("{fake}", "AWS access key")\n')
    assert find_violations(repo) == []

    put(repo, "tests/test_validate_dataset.py", f'("{SECRETS["aws access key"]}", "x")\n')

    assert find_violations(repo) == [
        "tests/test_validate_dataset.py:1: secret-shaped string (aws access key)"
    ]


def test_a_secret_in_an_untracked_file_is_not_this_guards_business(repo: Path) -> None:
    """Known limit, pinned: state 3 reads what is tracked, because that is what is pushed."""
    put(repo, "scratch.txt", SECRETS["sk- key"], add=False)

    assert find_violations(repo) == []


def test_a_binary_blob_is_not_scanned(repo: Path) -> None:
    """Known limit, pinned: a NUL in the first 8,000 bytes marks a blob as not text."""
    put(repo, "blob.bin", b"\0" + SECRETS["sk- key"].encode())

    assert find_violations(repo) == []


ADDRESSES_ALLOWED = [
    "12345+someone@users.noreply.github.com",
    "Someone@Users.Noreply.GitHub.com",
    "noreply@anthropic.com",
    "11434@evil.example",
]
#: Joined at run time: written out, they would be flagged in this very file once it is tracked.
ADDRESSES_FLAGGED = [
    "@".join(pair)
    for pair in (
        ("t", "example.com"),
        ("someone", "gmail.com"),
        ("noreply", "github.com"),
        ("x", "evil.example"),
        ("a", "users.noreply.github.com.evil.org"),
        ("someone", "fake-users.noreply.github.com"),
    )
]


def test_the_allowlisted_addresses_are_not_flagged(repo: Path) -> None:
    for number, address in enumerate(ADDRESSES_ALLOWED):
        put(repo, f"docs/notes{number}.md", f"contact {address} about it\n")

    assert find_violations(repo) == []


def test_any_other_address_is_flagged_by_line(repo: Path) -> None:
    for number, address in enumerate(ADDRESSES_FLAGGED):
        put(repo, f"docs/notes{number}.md", f"first\ncontact {address} about it\n")

    found = find_violations(repo)

    assert found == [
        f"docs/notes{number}.md:2: e-mail address not on the allowlist"
        for number in range(len(ADDRESSES_FLAGGED))
    ]
    assert not any(address in ADVICE.format(found=found) for address in ADDRESSES_FLAGGED)


# --------------------------------------------------------------------------- #
# the harness itself
# --------------------------------------------------------------------------- #


def test_inherited_git_variables_do_not_redirect_the_check(
    repo: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A pre-push hook exports GIT_DIR. The check must still read the repository it was given."""
    put(repo, "CLAUDE.md", private())
    other = make_repo(tmp_path / "other")
    put(other, "README.md", "clean\n")
    monkeypatch.setenv("GIT_DIR", str(other / ".git"))
    monkeypatch.setenv("GIT_WORK_TREE", str(other))
    monkeypatch.setenv("GIT_INDEX_FILE", str(other / ".git" / "index"))

    assert find_violations(repo) == ["CLAUDE.md: tracked rule file holds private marker 0"]


def test_a_directory_that_is_not_a_repository_reports_nothing(tmp_path: Path) -> None:
    (tmp_path / "CLAUDE.md").write_text(private(), encoding="utf-8")

    assert find_violations(tmp_path) == []


def test_an_empty_repository_reports_nothing(repo: Path) -> None:
    assert find_violations(repo) == []


# --------------------------------------------------------------------------- #
# the real checkout
# --------------------------------------------------------------------------- #


def test_the_real_checkout_tracks_no_private_rule_text_and_no_secret() -> None:
    found = find_violations(PROJECT)

    assert found == [], ADVICE.format(found=found)
