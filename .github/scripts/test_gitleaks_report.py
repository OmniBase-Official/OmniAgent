import hashlib
import os
import shutil
import stat
import subprocess
import sys
from enum import StrEnum
from pathlib import Path

import gitleaks_report as module
import pytest
from gitleaks_report import (
    MAX_CAPTURE,
    MAX_REPORT,
    ScanError,
    StageError,
    capture,
    contract_canary_scan,
    contract_clean_scan,
    contract_mutant_scan,
    copy_scan_report,
    docker_cp,
    fail_stage,
    make_repo,
    parse_report,
    render,
    report_error,
    safe_path,
    scanner_status_consistent,
    summary_count,
)

HASH = "0123456789abcdef0123456789abcdef01234567"
ROW = f'R\t"fixture.txt"\t{HASH}\t1\n'.encode("ascii")
EXPECTED_COMMIT_COUNT = 270
EXPECTED_COLUMN_COUNT = 4
EXPECTED_MERGE_PARENT_LINE_FIELDS = 3


def capture_limit_diagnostic(stdout: bytes, stderr: bytes, limit: int) -> str:
    return (
        "security scan failed stage=scan_docker_start "
        f"stdout_bytes={len(stdout)} stderr_bytes={len(stderr)} limit={limit}"
    )


class StartFailureCategory(StrEnum):
    PERMISSION_DENIED = "permission_denied"
    DUBIOUS_OWNERSHIP = "dubious_ownership"
    FILE_SIZE_LIMIT = "file_size_limit"
    OTHER = "other"


def classify_start_stderr(stderr: bytes) -> StartFailureCategory:
    diagnostic = stderr.lower()
    if b"permission denied" in diagnostic or b"operation not permitted" in diagnostic:
        return StartFailureCategory.PERMISSION_DENIED
    if b"dubious ownership" in diagnostic or b"safe.directory" in diagnostic:
        return StartFailureCategory.DUBIOUS_OWNERSHIP
    if (
        b"file too large" in diagnostic
        or b"file size limit" in diagnostic
        or b"sigxfsz" in diagnostic
    ):
        return StartFailureCategory.FILE_SIZE_LIMIT
    return StartFailureCategory.OTHER


def report_directory_metadata(report_dir: Path | None) -> str:
    if report_dir is None or os.name != "posix":
        return ""
    try:
        info = report_dir.lstat()
    except OSError:
        return ""
    if not stat.S_ISDIR(info.st_mode):
        return ""
    return (
        f" report_uid={info.st_uid} report_gid={info.st_gid}"
        f" report_mode_octal={stat.S_IMODE(info.st_mode):04o}"
    )


def start_status_diagnostic(
    exit_code: int,
    stdout: bytes,
    stderr: bytes,
    limit: int,
    report_dir: Path | None = None,
) -> str:
    return (
        "security scan failed stage=scan_docker_start "
        f"category={classify_start_stderr(stderr).value} exit_code={exit_code} "
        f"stdout_bytes={len(stdout)} stderr_bytes={len(stderr)} limit={limit}"
        f"{report_directory_metadata(report_dir)}"
    )


class PortableCapture:
    def __init__(self) -> None:
        self.report_dir: Path | None = None

    def __call__(
        self, args: list[str], timeout: int = module.TIMEOUT
    ) -> tuple[int, bytes, bytes]:
        if args[1] == "create":
            args = [*args[:2], "--env=NO_COLOR=1", *args[2:]]
            self.report_dir = report_dir_from_create_args(args)
        result = subprocess.run(  # noqa: S603 - controlled argv, synthetic fixture, shell=False.
            args,
            stdin=subprocess.DEVNULL,
            capture_output=True,
            timeout=timeout,
            check=False,
        )
        if args[1] == "start" and result.returncode not in (
            module.CLEAN_STATUS,
            module.FINDINGS_STATUS,
        ):
            pytest.fail(
                start_status_diagnostic(
                    result.returncode,
                    result.stdout,
                    result.stderr,
                    module.MAX_CAPTURE,
                    self.report_dir,
                ),
                pytrace=False,
            )
        if len(result.stdout) > module.MAX_CAPTURE or len(result.stderr) > module.MAX_CAPTURE:
            pytest.fail(
                capture_limit_diagnostic(result.stdout, result.stderr, module.MAX_CAPTURE),
                pytrace=False,
            )
        return result.returncode, result.stdout, result.stderr


def report_dir_from_create_args(args: list[str]) -> Path | None:
    mount_suffix = ":/out:rw"
    for index, arg in enumerate(args[:-1]):
        if arg == "--volume" and args[index + 1].endswith(mount_suffix):
            return Path(args[index + 1][: -len(mount_suffix)])
    return None


def expect_equal(actual: object, expected: object) -> None:
    if actual != expected:
        raise AssertionError(f"expected {expected!r}, got {actual!r}")


def make_history_fixture(root: Path, name: str) -> Path:
    repo = root / name
    repo.mkdir()
    (repo / ".gitleaksignore").write_bytes(b"")

    def git(*args: str) -> bytes:
        status, output, _ = module.capture(["git", "-C", str(repo), *args])
        if status != 0:
            raise AssertionError("synthetic git history setup failed")
        return output

    status, _, _ = module.capture(["git", "init", "-q", str(repo)])
    if status != 0:
        raise AssertionError("synthetic git history setup failed")
    git("config", "user.email", "fixture@example.invalid")
    git("config", "user.name", "Synthetic Fixture")
    git("branch", "-M", "main")

    (repo / "ordinary.txt").write_bytes(b"initial fixture\n")
    (repo / "delete-only.txt").write_bytes(b"delete-only fixture\n")
    git("add", "-A")
    git("commit", "-qm", "initial history fixture")

    (repo / "ordinary.txt").write_bytes(b"ordinary modification\n")
    git("add", "ordinary.txt")
    git("commit", "-qm", "ordinary commit")
    git("commit", "--allow-empty", "-qm", "empty commit")

    git("branch", "side")
    git("checkout", "-q", "side")
    (repo / "side.txt").write_bytes(b"side branch fixture\n")
    git("add", "side.txt")
    git("commit", "-qm", "side branch commit")

    git("checkout", "-q", "main")
    (repo / "main.txt").write_bytes(b"main branch fixture\n")
    git("add", "main.txt")
    git("commit", "-qm", "main branch commit")
    git("merge", "--no-ff", "-qm", "merge fixture", "side")

    git("rm", "-q", "delete-only.txt")
    git("commit", "-qm", "delete-only commit")
    return repo


def make_merge_resolution_fixture(root: Path, name: str, canary: bytes) -> Path:
    repo = root / name
    repo.mkdir()
    (repo / ".gitleaksignore").write_bytes(b"")

    def git(*args: str) -> bytes:
        status, output, _ = module.capture(["git", "-C", str(repo), *args])
        if status != 0:
            raise AssertionError("synthetic merge fixture setup failed")
        return output

    status, _, _ = module.capture(["git", "init", "-q", str(repo)])
    if status != 0:
        raise AssertionError("synthetic merge fixture setup failed")
    git("config", "user.email", "fixture@example.invalid")
    git("config", "user.name", "Synthetic Fixture")
    git("branch", "-M", "main")
    (repo / "fixture.txt").write_bytes(b"value=base\n")
    git("add", "fixture.txt")
    git("commit", "-qm", "merge base")
    base = git("rev-parse", "HEAD").strip().decode("ascii")

    git("checkout", "-q", "-b", "side", base)
    (repo / "fixture.txt").write_bytes(b"value=side-parent\n")
    git("add", "fixture.txt")
    git("commit", "-qm", "side parent")

    git("checkout", "-q", "main")
    (repo / "fixture.txt").write_bytes(b"value=main-parent\n")
    git("add", "fixture.txt")
    git("commit", "-qm", "main parent")
    merge_status, _, _ = module.capture(
        ["git", "-C", str(repo), "merge", "--no-ff", "--no-commit", "side"]
    )
    if merge_status == 0:
        raise AssertionError("synthetic merge fixture did not create a conflict")

    (repo / "fixture.txt").write_bytes(b"token=" + canary + b"\n")
    git("add", "fixture.txt")
    git("commit", "-qm", "resolution-only canary merge")
    parent_line = git("rev-list", "--parents", "-n", "1", "HEAD").strip()
    parents = parent_line.split()
    if len(parents) != EXPECTED_MERGE_PARENT_LINE_FIELDS:
        raise AssertionError("synthetic resolution commit is not a two-parent merge")
    for parent in parents[1:]:
        status, parent_file, _ = module.capture(
            ["git", "-C", str(repo), "show", f"{parent.decode('ascii')}:fixture.txt"]
        )
        if status != 0 or canary in parent_file:
            raise AssertionError("synthetic canary must be absent from both merge parents")
    status, merge_file, _ = module.capture(
        ["git", "-C", str(repo), "show", "HEAD:fixture.txt"]
    )
    if status != 0 or canary not in merge_file:
        raise AssertionError("synthetic canary must exist only in the merge result")
    return repo


def test_gitleaksignore_contains_only_approved_fixture_locations() -> None:
    expected = {
        "3576aebaf297c5e956ac9d9f0b80eb50a9af44af:tests/test_publish_dataset.py:generic-api-key:194",
        "3576aebaf297c5e956ac9d9f0b80eb50a9af44af:tests/test_publish_dataset.py:generic-api-key:200",
        "3576aebaf297c5e956ac9d9f0b80eb50a9af44af:tests/test_publish_dataset.py:generic-api-key:202",
        "3576aebaf297c5e956ac9d9f0b80eb50a9af44af:tests/test_validate_dataset.py:generic-api-key:126",
        "3576aebaf297c5e956ac9d9f0b80eb50a9af44af:tests/test_validate_dataset.py:generic-api-key:148",
        "3576aebaf297c5e956ac9d9f0b80eb50a9af44af:tests/test_validate_dataset.py:generic-api-key:161",
        "3576aebaf297c5e956ac9d9f0b80eb50a9af44af:tests/test_validate_dataset.py:generic-api-key:188",
        "8ebc04a8f548817e75834bb864659b357872a140:tests/test_validate_dataset.py:generic-api-key:168",
        "8ebc04a8f548817e75834bb864659b357872a140:tests/test_validate_dataset.py:generic-api-key:178",
    }
    allowlist = Path(__file__).resolve().parents[2] / ".gitleaksignore"
    actual = set(allowlist.read_text(encoding="ascii").splitlines())
    expect_equal(actual, expected)


def test_ascii_unicode_quote_round_trip() -> None:
    rows = parse_report(f'R\t"dir/quote\\"-caf\\u00e9.txt"\t{HASH}\t1\n'.encode())
    expect_equal(rows[0][1], 'dir/quote"-café.txt')


@pytest.mark.parametrize(
    "value",
    [
        "../escape",
        "/absolute",
        "dir\\escape",
        "x/\x1bname",
        "x/\u202ename",
    ],
)
def test_rejects_traversal_absolute_backslash_controls_and_bidi(value: str) -> None:
    expect_equal(safe_path(value), False)


def test_rejects_total_row_and_row_count_boundaries() -> None:
    with pytest.raises(ScanError):
        parse_report(b"x" * (MAX_REPORT + 1))
    with pytest.raises(ScanError):
        parse_report(b'R\t"' + b"x" * 16_384 + b'"\t' + HASH.encode() + b"\t1\n")
    with pytest.raises(ScanError):
        parse_report(ROW * 20_001)


def test_scan_report_read_rejects_non_regular_and_over_limit_files(tmp_path: Path) -> None:
    directory = tmp_path / "directory-report"
    directory.mkdir()
    with pytest.raises(ScanError):
        copy_scan_report(directory)

    oversized = tmp_path / "oversized-report"
    with oversized.open("wb") as stream:
        stream.truncate(MAX_REPORT + 1)
    with pytest.raises(ScanError):
        copy_scan_report(oversized)


@pytest.mark.skipif(os.name != "posix", reason="symlink no-follow check is POSIX-specific")
def test_scan_report_read_rejects_symlink(tmp_path: Path) -> None:
    target = tmp_path / "target-report"
    target.write_bytes(b"")
    link = tmp_path / "linked-report"
    link.symlink_to(target)
    with pytest.raises(ScanError):
        copy_scan_report(link)


@pytest.mark.parametrize(
    "raw",
    [
        b"\xff",
        ROW.replace(b"\n", b"\r\n"),
        b'R\t"unterminated\t' + HASH.encode() + b"\t1\n",
        b'R\t"fixture.txt"\t' + HASH.encode() + b"\n",
        b'R\t"fixture.txt"\t' + HASH.encode() + b"\t1\textra\n",
        b'R\t"fixture.txt"\tbad\t1\n',
        b'R\t"fixture.txt"\t' + HASH.encode() + b"\t0\n",
        b'R\t"fixture.txt"\t' + ("a" * 41).encode() + b"\t1\n",
        b'R\t"fixture.txt"\t' + ("a" * 63).encode() + b"\t1\n",
    ],
)
def test_rejects_malformed_encoding_crlf_quote_columns_hash_and_line(raw: bytes) -> None:
    with pytest.raises(ScanError):
        parse_report(raw)


@pytest.mark.skipif(os.name != "posix", reason="report copy contract uses POSIX file limits")
def test_empty_report_is_clean_but_absent_report_fails(tmp_path: Path) -> None:
    expect_equal(parse_report(b""), [])
    fake = tmp_path / "docker"
    fake.write_text("#!/usr/bin/env python3\nraise SystemExit(0)\n", encoding="utf-8")
    fake.chmod(0o700)
    with pytest.raises(ScanError):
        docker_cp("c", "/out/report.tsv", tmp_path / "absent", docker_bin=str(fake))


def test_summary_parser_accepts_timestamped_or_bare_and_rejects_malformed() -> None:
    nl = bytes((10,))
    expect_equal(summary_count(b"12:51AM INF 270 commits scanned" + nl), EXPECTED_COMMIT_COUNT)
    expect_equal(summary_count(b"INF 1 commits scanned." + nl), 1)
    invalid = [
        (b"no summary" + nl,),
        (b"junk INF 1 commits scanned." + nl,),
        (b"INF 1 commits scanned. trailing" + nl,),
        (b"12:51AM INF 270 commits scanned" + nl + b"12:52AM INF 270 commits scanned" + nl,),
        (b"12:51AM INF 12345678901 commits scanned" + nl,),
    ]
    for (value,) in invalid:
        with pytest.raises(ScanError):
            summary_count(value)


def test_status_rows_consistency() -> None:
    row = ("R", "fixture.txt", HASH, 1)
    expect_equal(scanner_status_consistent(0, []), True)
    expect_equal(scanner_status_consistent(2, [row]), True)
    expect_equal(scanner_status_consistent(0, [row]), False)
    expect_equal(scanner_status_consistent(2, []), False)


def test_scan_summary_requires_one_positive_parseable_count() -> None:
    module.verify_scan_summary(b"INF 1 commits scanned.\n")
    for invalid in (
        b"INF 0 commits scanned.\n",
        b"no summary\n",
        b"INF 1 commits scanned.\nINF 1 commits scanned.\n",
    ):
        with pytest.raises(StageError) as caught:
            module.verify_scan_summary(invalid)
        expect_equal(caught.value.stage, "scan_commit_summary")


def test_shallow_repository_is_rejected_before_container_creation(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(module, "capture", PortableCapture())
    repo = make_repo(tmp_path, "shallow-repo", b"synthetic shallow fixture\n")
    status, head, _ = module.capture(["git", "-C", str(repo), "rev-parse", "HEAD"])
    expect_equal(status, 0)
    expect_equal(head.endswith(b"\n"), True)
    (repo / ".git" / "shallow").write_bytes(head)

    def reject_docker(args: list[str], timeout: int = module.TIMEOUT) -> tuple[int, bytes, bytes]:
        del timeout
        if args[-1] != "--is-shallow-repository":
            raise AssertionError("container creation must not run for shallow repositories")
        return 0, b"true\n", b""

    monkeypatch.setattr(module, "capture", reject_docker)
    with pytest.raises(StageError) as caught:
        module.scan(repo, tmp_path / "template")
    expect_equal(caught.value.stage, "scan_repository_policy")


def test_scan_container_sets_exact_report_file_size_limit(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    captured: list[list[str]] = []

    def capture_args(args: list[str], timeout: int = module.TIMEOUT) -> tuple[int, bytes, bytes]:
        del timeout
        captured.append(args)
        return 0, b"", b""

    monkeypatch.setattr(module, "capture", capture_args)
    report_dir = tmp_path / "report"
    report_dir.mkdir()
    report_dir.chmod(0o700)
    module.create_scan_container(
        tmp_path, tmp_path / "template", report_dir, "scan", "docker"
    )
    args = captured[0]
    limit_index = args.index("--ulimit")
    expect_equal(args[limit_index + 1], f"fsize={MAX_REPORT}:{MAX_REPORT}")
    no_banner_index = args.index("--no-banner")
    expect_equal(args[no_banner_index + 1], "--no-color")
    expect_equal(
        "--log-opts=--full-history --all --diff-filter=tuxdb --diff-merges=first-parent" in args,
        True,
    )
    expect_equal("--gitleaks-ignore-path=/repo/.gitleaksignore" in args, True)


def test_scan_container_passes_available_report_directory_owner(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    captured: list[list[str]] = []

    def capture_args(args: list[str], timeout: int = module.TIMEOUT) -> tuple[int, bytes, bytes]:
        del timeout
        captured.append(args)
        return 0, b"", b""

    monkeypatch.setattr(module, "report_directory_owner", lambda _path: (1234, 5678))
    monkeypatch.setattr(module, "capture", capture_args)
    module.create_scan_container(
        tmp_path, tmp_path / "template", tmp_path / "report", "scan", "docker"
    )
    args = captured[0]
    user_index = args.index("--user")
    expect_equal(args[user_index + 1], "1234:5678")


def test_scan_container_omits_user_when_report_owner_is_unavailable(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    captured: list[list[str]] = []

    def capture_args(args: list[str], timeout: int = module.TIMEOUT) -> tuple[int, bytes, bytes]:
        del timeout
        captured.append(args)
        return 0, b"", b""

    monkeypatch.setattr(module, "report_directory_owner", lambda _path: None)
    monkeypatch.setattr(module, "capture", capture_args)
    module.create_scan_container(
        tmp_path, tmp_path / "template", tmp_path / "report", "scan", "docker"
    )
    expect_equal("--user" in captured[0], False)


def test_report_directory_owner_uses_posix_lstat_identity(tmp_path: Path) -> None:
    if os.name != "posix":
        pytest.skip("POSIX report-directory ownership metadata is unavailable")
    tmp_path.chmod(0o700)
    info = tmp_path.lstat()
    expect_equal(module.report_directory_owner(tmp_path), (info.st_uid, info.st_gid))


def test_report_directory_owner_rejects_symlink(tmp_path: Path) -> None:
    if os.name != "posix":
        pytest.skip("POSIX symlink ownership check")
    target = tmp_path / "target"
    target.mkdir()
    link = tmp_path / "link"
    link.symlink_to(target, target_is_directory=True)
    with pytest.raises(ScanError):
        module.report_directory_owner(link)


def test_report_directory_owner_omits_windows_identity(tmp_path: Path) -> None:
    expect_equal(module.report_directory_owner(tmp_path, platform_name="nt"), None)


@pytest.mark.skipif(os.name != "nt", reason="Windows container creation must omit --user")
def test_scan_container_omits_user_on_windows(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    captured: list[list[str]] = []

    def capture_args(args: list[str], timeout: int = module.TIMEOUT) -> tuple[int, bytes, bytes]:
        del timeout
        captured.append(args)
        return 0, b"", b""

    monkeypatch.setattr(module, "capture", capture_args)
    module.create_scan_container(
        tmp_path, tmp_path / "template", tmp_path / "report", "scan", "docker"
    )
    expect_equal("--user" in captured[0], False)


def test_capture_limit_diagnostic_contains_only_numeric_metadata() -> None:
    canary = b"ghp_synthetic_capture_canary"
    secret_content = b"private/path token=" + canary
    diagnostic = capture_limit_diagnostic(secret_content, secret_content, MAX_CAPTURE)
    expect_equal(
        diagnostic,
        f"security scan failed stage=scan_docker_start "
        f"stdout_bytes={len(secret_content)} stderr_bytes={len(secret_content)} "
        f"limit={MAX_CAPTURE}",
    )
    expect_equal(canary.decode("ascii") in diagnostic, False)
    expect_equal("private/path" in diagnostic, False)
    expect_equal(secret_content.decode("ascii") in diagnostic, False)


def test_portable_capture_enforces_cap_with_numeric_only_diagnostic(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    canary = b"ghp_synthetic_cap_guard_canary"
    private_path = b"private/path"
    argv = ["docker", "start", "--attach", private_path.decode(), canary.decode()]
    secret_content = b"argv=" + private_path + b" token=" + canary
    stdout = secret_content * (MAX_CAPTURE // len(secret_content) + 1)
    result = subprocess.CompletedProcess(argv, 0, stdout=stdout, stderr=b"")
    monkeypatch.setattr(subprocess, "run", lambda *_args, **_kwargs: result)

    with pytest.raises(pytest.fail.Exception) as caught:
        PortableCapture()(argv)

    diagnostic = str(caught.value)
    expect_equal(
        diagnostic,
        capture_limit_diagnostic(stdout, b"", MAX_CAPTURE),
    )
    expect_equal(canary.decode("ascii") in diagnostic, False)
    expect_equal(private_path.decode("ascii") in diagnostic, False)
    expect_equal(" ".join(argv) in diagnostic, False)
    expect_equal(secret_content.decode("ascii") in diagnostic, False)
    expect_equal(stdout.decode("ascii") in diagnostic, False)


@pytest.mark.parametrize(
    ("stderr", "expected_category"),
    [
        (
            b"permission denied private/path ghp_synthetic_permission_canary",
            StartFailureCategory.PERMISSION_DENIED,
        ),
        (
            b"detected dubious ownership private/path ghp_synthetic_owner_canary",
            StartFailureCategory.DUBIOUS_OWNERSHIP,
        ),
        (
            b"File too large private/path ghp_synthetic_limit_canary",
            StartFailureCategory.FILE_SIZE_LIMIT,
        ),
        (b"unknown private/path ghp_synthetic_other_canary", StartFailureCategory.OTHER),
    ],
)
def test_start_stderr_classification_is_allowlisted_and_sanitized(
    stderr: bytes, expected_category: StartFailureCategory
) -> None:
    diagnostic = start_status_diagnostic(153, b"", stderr, MAX_CAPTURE)
    expect_equal(classify_start_stderr(stderr), expected_category)
    expect_equal(f"category={expected_category.value}" in diagnostic, True)
    expect_equal("153" in diagnostic, True)
    expect_equal(str(len(stderr)) in diagnostic, True)
    expect_equal(stderr.decode("ascii") in diagnostic, False)
    expect_equal("private/path" in diagnostic, False)
    expect_equal("ghp_synthetic" in diagnostic, False)


def test_start_status_diagnostic_contains_only_safe_numeric_metadata(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    canary = b"ghp_synthetic_start_status_canary"
    secret_content = b"private/path token=" + canary
    args = ["docker", "start", "--attach", "synthetic-container"]
    result = subprocess.CompletedProcess(
        args, 153, stdout=b"", stderr=secret_content
    )

    def run_fake(command: list[str], **_kwargs: object) -> subprocess.CompletedProcess[bytes]:
        if command[1] == "create":
            return subprocess.CompletedProcess(command, 0, stdout=b"", stderr=b"")
        return result

    monkeypatch.setattr(subprocess, "run", run_fake)
    capture = PortableCapture()
    if os.name == "posix":
        tmp_path.chmod(0o700)
    capture(
        [
            "docker",
            "create",
            "--volume",
            f"{tmp_path.resolve()}:/out:rw",
            "synthetic-image",
        ]
    )
    with pytest.raises(pytest.fail.Exception) as caught:
        capture(args)
    diagnostic = str(caught.value)
    expect_equal(
        diagnostic,
        start_status_diagnostic(153, b"", secret_content, MAX_CAPTURE, tmp_path),
    )
    expect_equal(canary.decode("ascii") in diagnostic, False)
    expect_equal("private/path" in diagnostic, False)
    expect_equal("synthetic-container" in diagnostic, False)
    expect_equal(secret_content.decode("ascii") in diagnostic, False)
    if os.name == "posix":
        info = tmp_path.lstat()
        expect_equal(f"report_uid={info.st_uid}" in diagnostic, True)
        expect_equal(f"report_gid={info.st_gid}" in diagnostic, True)
        expect_equal(f"report_mode_octal={stat.S_IMODE(info.st_mode):04o}" in diagnostic, True)


@pytest.mark.skipif(
    shutil.which("docker") is None,
    reason="pinned-image integration requires Docker",
)
def test_scan_report_survives_container_exit(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(module, "capture", PortableCapture())
    canary = (
        "ghp_" + hashlib.sha256(b"omniagent-report-persistence-test").hexdigest()[:36]
    ).encode("ascii")
    repo = make_repo(tmp_path, "synthetic-canary-repo", b"token=" + canary + b"\n")
    template = Path(__file__).with_name("gitleaks-report.tmpl")
    status, rows, output, raw = module.scan(repo, template)
    expect_equal(status, module.FINDINGS_STATUS)
    expect_equal(len(rows), 1)
    expect_equal(summary_count(output), 1)
    expect_equal(parse_report(raw), rows)
    expect_equal(len(raw) > 0, True)
    expect_equal(canary in raw, False)
    expect_equal(canary in output, False)
    expect_equal(canary in module.render(rows), False)


@pytest.mark.skipif(
    shutil.which("docker") is None,
    reason="pinned-image synthetic Git history test requires Docker",
)
def test_history_with_merge_empty_and_delete_only_commits_scans_consistently(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(module, "capture", PortableCapture())
    repo = make_history_fixture(tmp_path, "synthetic-history-repo")
    graph_status, graph_count, _ = module.capture(
        ["git", "-C", str(repo), "rev-list", "--all", "--count"]
    )
    expect_equal((graph_status, graph_count), (0, b"7\n"))

    template = Path(__file__).with_name("gitleaks-report.tmpl")
    status, rows, output, raw = module.scan(repo, template)
    expect_equal(status, module.CLEAN_STATUS)
    expect_equal(rows, [])
    expect_equal(parse_report(raw), [])
    expect_equal(summary_count(output) > 0, True)


@pytest.mark.skipif(
    shutil.which("docker") is None,
    reason="pinned-image merge-resolution test requires Docker",
)
def test_merge_resolution_only_canary_is_detected_and_redacted(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(module, "capture", PortableCapture())
    canary = (
        "ghp_" + hashlib.sha256(b"omniagent-merge-resolution-canary").hexdigest()[:36]
    ).encode("ascii")
    repo = make_merge_resolution_fixture(tmp_path, "synthetic-merge-repo", canary)
    template = Path(__file__).with_name("gitleaks-report.tmpl")

    status, rows, output, raw = module.scan(repo, template)
    expect_equal(status, module.FINDINGS_STATUS)
    expect_equal(len(rows), 1)
    expect_equal(rows[0][1], "fixture.txt")
    expect_equal(rows[0][3], 1)
    expect_equal(canary in output, False)
    expect_equal(canary in raw, False)
    expect_equal(canary in module.render(rows), False)


@pytest.mark.skipif(
    shutil.which("docker") is None,
    reason="pinned-image exact ignore integration requires Docker",
)
def test_gitleaksignore_suppresses_only_exact_commit_path_rule_line(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(module, "capture", PortableCapture())
    first = hashlib.sha256(b"synthetic generic key first line").hexdigest()
    second = hashlib.sha256(b"synthetic generic key second line").hexdigest()
    content = f'api_key = "{first}"\napi_key = "{second}"\n'.encode("ascii")
    repo = module.make_repo(tmp_path, "synthetic-ignore-repo", content)
    status, commit_bytes, _ = module.capture(
        ["git", "-C", str(repo), "rev-parse", "HEAD"]
    )
    expect_equal(status, 0)
    commit = commit_bytes.strip().decode("ascii")
    ignore_file = repo / ".gitleaksignore"
    template = Path(__file__).with_name("gitleaks-report.tmpl")

    def scan_with(identifier: str) -> list[tuple[str, str, str, int]]:
        ignore_file.write_text(identifier + "\n", encoding="ascii", newline="")
        scan_status, rows, output, raw_report = module.scan(repo, template)
        expect_equal(scan_status, module.FINDINGS_STATUS)
        expect_equal(summary_count(output), 1)
        for value in (first.encode("ascii"), second.encode("ascii")):
            expect_equal(value in output, False)
            expect_equal(value in raw_report, False)
        return sorted(rows)

    exact = f"{commit}:fixture.txt:generic-api-key:1"
    expect_equal(
        scan_with(exact),
        [("generic-api-key", "fixture.txt", commit, 2)],
    )
    expect_equal(
        scan_with(f"{commit}:fixture.txt:generic-api-key:3"),
        [
            ("generic-api-key", "fixture.txt", commit, 1),
            ("generic-api-key", "fixture.txt", commit, 2),
        ],
    )
    other_commit = ("0" if commit[0] != "0" else "1") + commit[1:]
    expect_equal(
        scan_with(f"{other_commit}:fixture.txt:generic-api-key:1"),
        [
            ("generic-api-key", "fixture.txt", commit, 1),
            ("generic-api-key", "fixture.txt", commit, 2),
        ],
    )


def test_cli_clean_and_finding_exit_behavior_and_safe_output() -> None:
    script_dir = Path(__file__).resolve().parent
    canary = "ghp_" + hashlib.sha256(b"omniagent-gitleaks-contract").hexdigest()[:36]
    safe_row = ("GitleaksRule", "fixture.txt", HASH, 1)
    safe_row_repr = repr(safe_row)

    def command_for(scan_status: int) -> list[str]:
        code = (
            "import sys; import gitleaks_report as g; "
            f"g.scan=lambda *a, **k: ({scan_status}, "
            f"([{safe_row_repr}] if {scan_status} == 2 else []), "
            "b\x27\x27, b\x27\x27); "
            "sys.argv=['gitleaks_report.py','scan','unused','unused']; "
            "raise SystemExit(g.main())"
        )
        return ["-c", code]

    clean = subprocess.run(  # noqa: S603 - synthetic inline stub, fixed interpreter argv, shell=False.
        [sys.executable, *command_for(0)],
        cwd=script_dir,
        capture_output=True,
        check=False,
    )
    expect_equal((clean.returncode, clean.stdout, clean.stderr), (0, b"", b""))

    finding = subprocess.run(  # noqa: S603 - synthetic inline stub, fixed interpreter argv, shell=False.
        [sys.executable, *command_for(2)],
        cwd=script_dir,
        capture_output=True,
        check=False,
    )
    expected = render([safe_row])
    expect_equal(finding.returncode, 1)
    expect_equal(finding.stdout, expected)
    expect_equal(len(finding.stdout.rstrip(b"\n").split(b"\t")), EXPECTED_COLUMN_COUNT)
    expect_equal(canary.encode() in finding.stdout, False)
    expect_equal(canary.encode() in finding.stderr, False)


def test_actual_entrypoint_clean_and_invalid_reports(tmp_path: Path) -> None:
    helper = Path(__file__).with_name("gitleaks_report.py")
    empty = tmp_path / "empty.tsv"
    empty.write_bytes(b"")
    clean = subprocess.run(  # noqa: S603 - controlled local helper path and argv, shell=False.
        [sys.executable, str(helper), "validate", str(empty)],
        capture_output=True,
        check=False,
    )
    expect_equal((clean.returncode, clean.stdout, clean.stderr), (0, b"", b""))

    invalid = tmp_path / "invalid.tsv"
    invalid.write_bytes(b"bad schema\n")
    rejected = subprocess.run(  # noqa: S603 - controlled local helper path and argv, shell=False.
        [sys.executable, str(helper), "validate", str(invalid)],
        capture_output=True,
        check=False,
    )
    expect_equal(rejected.returncode, 1)
    expect_equal(rejected.stdout, b"")
    expect_equal(rejected.stderr.replace(b"\r\n", b"\n"), b"security scan failed\n")

    canary = (
        "ghp_" + hashlib.sha256(b"omniagent-validator-nondisclosure").hexdigest()[:36]
    ).encode("ascii")
    malformed_canary = tmp_path / "malformed-canary.tsv"
    malformed_canary.write_bytes(b'R\t"fixture.txt"\tinvalid\t1\t' + canary + b"\n")
    rejected_canary = subprocess.run(  # noqa: S603 - controlled local helper path and argv, shell=False.
        [sys.executable, str(helper), "validate", str(malformed_canary)],
        capture_output=True,
        check=False,
    )
    expect_equal(rejected_canary.returncode, 1)
    expect_equal(rejected_canary.stdout, b"")
    expect_equal(
        rejected_canary.stderr.replace(b"\r\n", b"\n"),
        b"security scan failed\n",
    )
    expect_equal(canary in rejected_canary.stdout, False)
    expect_equal(canary in rejected_canary.stderr, False)


def test_stage_diagnostics_emit_only_allowlisted_ids(tmp_path: Path) -> None:
    script_dir = Path(__file__).resolve().parent
    canary = "ghp_" + hashlib.sha256(b"omniagent-gitleaks-contract").hexdigest()[:36]
    private_path = str(tmp_path / "private-report-path")
    stage_ids = (
        "contract_clean_repo_setup",
        "contract_clean_scan_execution",
        "contract_clean_assertions",
        "contract_canary_scan",
        "contract_mutant_scan",
        "contract_cli_validation",
    )
    for stage_id in stage_ids:
        code = (
            "import sys; import gitleaks_report as g; "
            "g.report_error(g.StageError(sys.argv[1])); raise SystemExit(1)"
        )
        result = subprocess.run(  # noqa: S603 - fixed Python argv and stage allowlist; shell=False.
            [sys.executable, "-c", code, stage_id, private_path, canary],
            cwd=script_dir,
            capture_output=True,
            check=False,
        )
        expect_equal(result.returncode, 1)
        expect_equal(result.stdout, b"")
        diagnostic = result.stderr.replace(b"\r\n", b"\n")
        expect_equal(diagnostic, f"security scan failed stage={stage_id}\n".encode())
        expect_equal(private_path.encode() in diagnostic, False)
        expect_equal(canary.encode() in diagnostic, False)

    invalid_id = f"{private_path}:{canary}"
    with pytest.raises(ScanError) as rejected_stage:
        fail_stage(invalid_id)  # type: ignore[arg-type]
    expect_equal(type(rejected_stage.value), ScanError)
    code = (
        "import sys; import gitleaks_report as g; "
        "g.report_error(g.StageError(sys.argv[1])); raise SystemExit(1)"
    )
    rejected = subprocess.run(  # noqa: S603 - fixed Python argv, validates ID allowlist, shell=False.
        [sys.executable, "-c", code, invalid_id],
        cwd=script_dir,
        capture_output=True,
        check=False,
    )
    diagnostic = rejected.stderr.replace(b"\r\n", b"\n")
    if diagnostic != b"security scan failed\n":
        raise AssertionError("unallowlisted stage diagnostic was not generic")
    if invalid_id.encode() in diagnostic:
        raise AssertionError("unallowlisted stage identifier leaked")


@pytest.mark.parametrize(
    ("phase", "expected_stage"),
    [
        ("setup", "contract_clean_repo_setup"),
        ("scan", "contract_clean_scan_execution"),
        ("assertions", "contract_clean_assertions"),
    ],
)
def test_clean_contract_reports_only_isolated_phase_id(
    phase: str,
    expected_stage: str,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    canary = "ghp_" + hashlib.sha256(b"omniagent-stage-test-canary").hexdigest()[:36]
    injected = f"{tmp_path / 'private-path'}:{canary}"

    def make_repo_for_phase(*_: object) -> Path:
        if phase == "setup":
            raise ScanError(injected)
        return tmp_path

    def scan_for_phase(*_: object) -> tuple[int, list[tuple[str, str, str, int]], bytes, bytes]:
        if phase == "scan":
            raise ScanError(injected)
        return 2, [], b"", b""

    monkeypatch.setattr(module, "make_repo", make_repo_for_phase)
    monkeypatch.setattr(module, "scan", scan_for_phase)
    with pytest.raises(StageError) as caught:
        contract_clean_scan(tmp_path, tmp_path / "template")

    expect_equal(caught.value.stage, expected_stage)
    report_error(caught.value)
    captured = capsys.readouterr()
    expect_equal(captured.out, "")
    expect_equal(captured.err, f"security scan failed stage={expected_stage}\n")
    expect_equal(canary in captured.err, False)
    expect_equal(str(tmp_path / "private-path") in captured.err, False)


@pytest.mark.parametrize(
    "case",
    [
        ("clean", "scan_docker_create", "scan_docker_create"),
        ("clean", "untrusted/path", "contract_clean_scan_execution"),
        ("canary", "scan_docker_create", "scan_docker_create"),
        ("canary", "untrusted/path", "contract_canary_scan"),
        ("mutant", "scan_docker_create", "scan_docker_create"),
        ("mutant", "untrusted/path", "contract_mutant_scan"),
    ],
)
def test_contract_wrappers_preserve_only_allowlisted_nested_stages(
    case: tuple[str, str, str],
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    wrapper, nested_stage, expected_stage = case
    canary = "ghp_" + hashlib.sha256(b"omniagent-nested-stage-canary").hexdigest()[:36]
    private_path = str(tmp_path / "private-nested-path")
    injected = f"{private_path}:{canary}:nested diagnostic"

    def raise_nested_stage(*_args: object, **_kwargs: object) -> None:
        error = StageError(nested_stage)  # type: ignore[arg-type]
        error.args = (injected,)
        raise error

    monkeypatch.setattr(module, "make_repo", lambda *_args: tmp_path)
    monkeypatch.setattr(module, "scan", raise_nested_stage)

    def invoke_wrapper() -> None:
        if wrapper == "clean":
            contract_clean_scan(tmp_path, tmp_path / "template")
        elif wrapper == "canary":
            contract_canary_scan(tmp_path, tmp_path / "template", canary.encode())
        else:
            contract_mutant_scan(tmp_path, tmp_path / "mutant-template", canary.encode())

    with pytest.raises(StageError) as caught:
        invoke_wrapper()

    expect_equal(caught.value.stage, expected_stage)
    report_error(caught.value)
    captured = capsys.readouterr()
    expect_equal(captured.out, "")
    expect_equal(captured.err, f"security scan failed stage={expected_stage}\n")
    expect_equal(private_path in captured.err, False)
    expect_equal(canary in captured.err, False)


@pytest.mark.parametrize(
    ("phase", "expected_stage"),
    [
        ("repository_policy", "scan_repository_policy"),
        ("docker_create", "scan_docker_create"),
        ("docker_start", "scan_docker_start"),
        ("file_size_limit", "scan_docker_start"),
        ("docker_inspect", "scan_docker_inspect"),
        ("summary", "scan_commit_summary"),
        ("report_copy", "scan_report_copy"),
        ("report_parse", "scan_report_parse"),
        ("cleanup", "scan_container_cleanup"),
    ],
)
def test_scan_substep_failures_emit_only_fixed_stage_ids(
    phase: str,
    expected_stage: str,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    canary = "ghp_" + hashlib.sha256(b"omniagent-scan-stage-canary").hexdigest()[:36]
    private_path = str(tmp_path / "private-scan-path")
    injected = ScanError(f"{private_path}:{canary}:untrusted diagnostic")
    def verify_policy(_repo: Path) -> None:
        if phase == "repository_policy":
            raise injected

    monkeypatch.setattr(module, "verify_scan_repository", verify_policy)

    def capture_for_phase(
        args: list[str], timeout: int = module.TIMEOUT
    ) -> tuple[int, bytes, bytes]:
        del timeout
        if args[1] == "create":
            if phase == "docker_create":
                raise injected
            return 0, b"", b""
        if args[1] == "start":
            if phase == "docker_start":
                raise injected
            if phase == "file_size_limit":
                return 153, b"", b""
            if phase == "summary":
                return 0, b"missing summary", b""
            return 0, b"12:51AM INF 1 commits scanned\n", b""
        if args[1] == "inspect":
            if phase == "docker_inspect":
                raise injected
            return 0, b"0\n", b""
        if args[1] == "rm":
            if phase == "cleanup":
                raise injected
            return 0, b"", b""
        raise AssertionError("unexpected synthetic command")

    def parse_for_phase(_raw: bytes) -> list[tuple[str, str, str, int]]:
        if phase == "report_parse":
            raise injected
        return []

    monkeypatch.setattr(module, "capture", capture_for_phase)
    def copy_for_phase(report: Path) -> bytes:
        if phase == "report_copy":
            module.fail_stage("scan_report_copy")
        report.write_bytes(b"")
        return b""

    monkeypatch.setattr(module, "copy_scan_report", copy_for_phase)
    monkeypatch.setattr(module, "parse_report", parse_for_phase)
    with pytest.raises(StageError) as caught:
        module.scan(tmp_path, tmp_path / "template")
    expect_equal(caught.value.stage, expected_stage)
    report_error(caught.value)
    captured = capsys.readouterr()
    expect_equal(captured.out, "")
    expect_equal(captured.err, f"security scan failed stage={expected_stage}\n")
    expect_equal(canary in captured.err, False)
    expect_equal(private_path in captured.err, False)


@pytest.mark.skipif(os.name != "posix", reason="RLIMIT_FSIZE fixture requires POSIX")
def test_stdout_capture_is_bounded() -> None:
    code = f"import sys; sys.stdout.buffer.write(b'x' * {MAX_CAPTURE + 2})"
    with pytest.raises(ScanError):
        capture([sys.executable, "-c", code])


@pytest.mark.skipif(os.name != "posix", reason="RLIMIT_FSIZE fixture requires POSIX")
def test_docker_cp_allows_report_over_256k_and_rejects_over_8m(tmp_path: Path) -> None:
    payload = tmp_path / "payload"
    payload.write_bytes(b"x" * (300 * 1024))
    fake = tmp_path / "docker"
    fake.write_text(
        "#!/usr/bin/env python3\n"
        "import pathlib,sys\n"
        "if sys.argv[1] != 'cp': raise SystemExit(2)\n"
        "container, source = sys.argv[2].split(':', 1)\n"
        "if container != 'unused': raise SystemExit(3)\n"
        "src=pathlib.Path(source); dst=pathlib.Path(sys.argv[3])\n"
        "dst.write_bytes(src.read_bytes())\n",
        encoding="utf-8",
    )
    fake.chmod(0o700)
    dest = tmp_path / "copied-report"
    docker_cp("unused", str(payload), dest, docker_bin=str(fake))
    expect_equal(dest.stat().st_size, 300 * 1024)

    payload.write_bytes(b"x" * (MAX_REPORT + 1))
    with pytest.raises(ScanError):
        docker_cp("unused", str(payload), tmp_path / "too-large", docker_bin=str(fake))
