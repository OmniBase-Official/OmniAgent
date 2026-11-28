import hashlib
import os
import subprocess
import sys
from pathlib import Path

import gitleaks_report as module
import pytest
from gitleaks_report import (
    MAX_CANONICAL,
    MAX_CAPTURE,
    MAX_PATH,
    MAX_REPORT,
    REDACTED_PATH,
    ScanError,
    StageError,
    capture,
    classify_docker_create_failure,
    contract_canary_scan,
    contract_clean_scan,
    contract_history_canary_scan,
    contract_mutant_scan,
    copy_scan_report,
    create_scan_container,
    fail_stage,
    parse_report,
    redact_report_template,
    render,
    report_error,
    safe_path,
    scanner_status_consistent,
    summary_count,
    verify_scan_summary,
)

HASH = "0123456789abcdef0123456789abcdef01234567"
VALID_REPORT_TEMPLATE = module.REPORT_TEMPLATE
ROW = f'R\t"fixture.txt"\t{HASH}\t1\n'.encode("ascii")
EXPECTED_COMMIT_COUNT = 270
EXPECTED_COLUMN_COUNT = 4
WINDOWS_SYMLINK_PRIVILEGE_ERROR = 1314


def expect_equal(actual: object, expected: object) -> None:
    if actual != expected:
        raise AssertionError(f"expected {expected!r}, got {actual!r}")


def git(repo: Path, *args: str) -> bytes:
    result = subprocess.run(  # noqa: S603 - controlled Git fixture argv.
        ["git", "-C", str(repo), *args],  # noqa: S607
        check=True,
        stdin=subprocess.DEVNULL,
        capture_output=True,
        timeout=10,
    )
    return result.stdout


def capture_git_for_test(args: list[str], timeout: int = 10) -> tuple[int, bytes, bytes]:
    result = subprocess.run(  # noqa: S603 - fixed Git fixture argv, shell=False.
        args,
        stdin=subprocess.DEVNULL,
        capture_output=True,
        timeout=timeout,
        check=False,
    )
    return result.returncode, result.stdout, result.stderr


def init_git_repo(repo: Path) -> None:
    subprocess.run(  # noqa: S603 - fixed Git fixture command.
        ["git", "init", "-q", str(repo)], check=True, timeout=10  # noqa: S607
    )
    git(repo, "config", "user.name", "Synthetic Fixture")
    git(repo, "config", "user.email", "fixture@example.invalid")
    git(repo, "branch", "-M", "main")


def commit_file(repo: Path, name: str, content: bytes, message: str) -> None:
    (repo / name).write_bytes(content)
    git(repo, "add", "--", name)
    git(repo, "commit", "-qm", message)


def test_scanner_summary_can_be_less_than_reachable_commits(tmp_path: Path) -> None:
    repo = tmp_path / "history"
    repo.mkdir()
    init_git_repo(repo)
    for index in range(4):
        commit_file(repo, f"fixture-{index}.txt", f"line {index}\n".encode(), "text commit")

    reachable = int(git(repo, "rev-list", "--all", "--count"))
    summary = b"INF 3 commits scanned\n"
    expect_equal(reachable > summary_count(summary), True)
    verify_scan_summary(b"", summary, module.CLEAN_STATUS)


def test_full_history_probe_fails_closed_on_shallow_or_git_errors(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    responses = iter(
        [
            (0, b"false\n", b""),
            (0, b"true\n", b""),
            (1, b"false\n", b""),
            (0, b"false\n", b"git failure"),
        ]
    )
    monkeypatch.setattr(module, "capture", lambda _args: next(responses))
    module.ensure_full_history(Path("synthetic"))
    for _ in range(3):
        with pytest.raises(ScanError):
            module.ensure_full_history(Path("synthetic"))


def test_git_stream_errors_fail_closed_without_echoing_raw_output(
    capsys: pytest.CaptureFixture[str],
) -> None:
    private = b"ERR [git] synthetic read failure with private-token"
    with pytest.raises(StageError) as caught:
        verify_scan_summary(b"", b"INF 2 commits scanned\n" + private, 0)

    expect_equal(caught.value.stage, "scan_git_stream")
    report_error(caught.value)
    diagnostic = capsys.readouterr().err
    expect_equal(diagnostic, "security scan failed stage=scan_git_stream\n")
    expect_equal(private.decode() in diagnostic, False)


@pytest.mark.parametrize("line_ending", [b"\n", b"\r\n"], ids=("lf", "crlf"))
def test_report_template_redacts_file_path_before_scanner_writes_report(
    tmp_path: Path, line_ending: bytes
) -> None:
    source = tmp_path / "source-template.tmpl"
    source.write_bytes(VALID_REPORT_TEMPLATE.replace(b"\n", line_ending))

    redacted = redact_report_template(source, tmp_path)

    expect_equal(redacted.read_bytes(), module.REDACTED_REPORT_TEMPLATE)
    expect_equal(b".File" in redacted.read_bytes(), False)


def test_report_template_rejects_hidden_file_access_in_comment(tmp_path: Path) -> None:
    source = tmp_path / "source-template.tmpl"
    source.write_bytes(
        b'{{- range . -}}\n'
        b'{{- /* .File */ printf "%s\\t%q\\t%s\\t%d\\n" .RuleID '
        b'index . "File" .Commit .StartLine -}}\n'
        b'{{- end -}}\n'
    )

    with pytest.raises(ScanError):
        redact_report_template(source, tmp_path)

    expect_equal((tmp_path / "redacted-report-template.tmpl").exists(), False)


@pytest.mark.parametrize(
    "template_bytes",
    [b"{{ .File }} {{ .File }}", b"missing file field", b"x" * (module.MAX_TEMPLATE + 1)],
    ids=("duplicate-path-field", "missing-path-field", "oversized-template"),
)
def test_report_template_rejects_ambiguous_or_oversized_input(
    tmp_path: Path, template_bytes: bytes
) -> None:
    source = tmp_path / "source-template.tmpl"
    source.write_bytes(template_bytes)

    with pytest.raises(ScanError):
        redact_report_template(source, tmp_path)

    expect_equal((tmp_path / "redacted-report-template.tmpl").exists(), False)


def test_scan_container_pins_full_history_and_archive_depth_zero(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    calls: list[list[str]] = []

    def record(args: list[str], _timeout: int = module.TIMEOUT) -> tuple[int, bytes, bytes]:
        calls.append(args)
        return 0, b"", b""

    monkeypatch.setattr(module, "capture", record)
    template = tmp_path / "template.tmpl"
    template.write_bytes(VALID_REPORT_TEMPLATE)
    create_scan_container(tmp_path, template, tmp_path, "synthetic", "docker")
    redacted_path = tmp_path / "redacted-report-template.tmpl"
    expect_equal(b".File" in redacted_path.read_bytes(), False)
    expect_equal("--log-opts=--all" in calls[0], True)
    expect_equal("--max-archive-depth=0" in calls[0], True)


def test_canary_contract_accepts_redacted_file_path(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    canary = b"synthetic-positive-control"
    monkeypatch.setattr(module, "make_repo", lambda *_args: tmp_path)
    monkeypatch.setattr(
        module,
        "scan",
        lambda *_args: (
            module.FINDINGS_STATUS,
            [("fixture-rule", REDACTED_PATH, HASH, 1)],
            b"INF 1 commits scanned\n",
            b"fixed-template-report",
        ),
    )

    contract_canary_scan(tmp_path, tmp_path / "template", canary)


def test_history_positive_control_targets_old_commit_and_redacts_output(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    canary = hashlib.sha256(b"historical synthetic finding").hexdigest().encode("ascii")
    old_commit: list[str] = []

    def scan_history(
        repo: Path, _template: Path
    ) -> tuple[int, list[tuple[str, str, str, int]], bytes, bytes]:
        head = git(repo, "rev-parse", "HEAD").decode("ascii").strip()
        expect_equal(head != old_commit[0], True)
        path_commit = git(
            repo,
            "log",
            "-1",
            "--format=%H",
            "--",
            "private-" + canary.decode("ascii") + ".txt",
        ).decode("ascii").strip()
        return module.FINDINGS_STATUS, [
            ("fixture-rule", REDACTED_PATH, old_commit[0], 1),
            ("fixture-rule", REDACTED_PATH, path_commit, 1),
        ], b"INF 2 commits scanned\n", b"REDACTED"

    original_make_repo = module.make_repo

    monkeypatch.setattr(module, "capture", capture_git_for_test)

    def make_historical_repo(root: Path, name: str, content: bytes) -> Path:
        repo = original_make_repo(root, name, content)
        old_commit.append(git(repo, "rev-parse", "HEAD").decode("ascii").strip())
        return repo

    monkeypatch.setattr(module, "make_repo", make_historical_repo)
    monkeypatch.setattr(module, "scan", scan_history)
    contract_history_canary_scan(tmp_path, tmp_path / "template", canary)


def test_history_control_fails_when_old_commit_is_not_found(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    canary = hashlib.sha256(b"historical missing finding").hexdigest().encode("ascii")
    monkeypatch.setattr(module, "capture", capture_git_for_test)
    monkeypatch.setattr(
        module,
        "scan",
        lambda *_args: (
            module.FINDINGS_STATUS,
            [
                ("fixture-rule", REDACTED_PATH, "a" * 40, 1),
                ("fixture-rule", REDACTED_PATH, "b" * 40, 1),
            ],
            b"INF 2 commits scanned\n",
            b"REDACTED",
        ),
    )
    with pytest.raises(StageError) as caught:
        contract_history_canary_scan(tmp_path, tmp_path / "template", canary)
    expect_equal(caught.value.stage, "contract_history_canary_scan")
    report_error(caught.value)
    expect_equal(
        capsys.readouterr().err,
        "security scan failed stage=contract_history_canary_scan\n",
    )


def create_symlink_or_skip(
    link: Path, target: Path, *, windows: bool = os.name == "nt"
) -> None:
    try:
        link.symlink_to(target)
    except OSError as exc:
        if windows and getattr(exc, "winerror", None) == WINDOWS_SYMLINK_PRIVILEGE_ERROR:
            pytest.skip("Windows symlink privilege is unavailable")
        raise


def test_symlink_setup_does_not_skip_unrelated_oserror(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    def fail_symlink(_path: Path, _target: Path) -> None:
        raise OSError("unexpected fixture failure")

    def fail_skip(reason: str) -> None:
        raise AssertionError(f"unexpected skip: {reason}")

    monkeypatch.setattr(Path, "symlink_to", fail_symlink)
    monkeypatch.setattr(pytest, "skip", fail_skip)
    with pytest.raises(OSError, match="unexpected fixture failure"):
        create_symlink_or_skip(tmp_path / "link", tmp_path / "target")


def test_symlink_setup_skips_windows_privilege_error(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    permission_error = OSError("symlink privilege unavailable")
    permission_error.winerror = WINDOWS_SYMLINK_PRIVILEGE_ERROR

    def fail_symlink(_path: Path, _target: Path) -> None:
        raise permission_error

    monkeypatch.setattr(Path, "symlink_to", fail_symlink)
    with pytest.raises(pytest.skip.Exception):
        create_symlink_or_skip(tmp_path / "link", tmp_path / "target", windows=True)


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


def test_empty_report_is_clean_but_absent_report_fails(tmp_path: Path) -> None:
    expect_equal(parse_report(b""), [])
    with pytest.raises(ScanError):
        copy_scan_report(tmp_path / "absent")


def test_summary_parser_accepts_timestamped_or_bare_and_rejects_malformed() -> None:
    nl = bytes((10,))
    expect_equal(summary_count(b"12:51AM INF 270 commits scanned" + nl), EXPECTED_COMMIT_COUNT)
    expect_equal(summary_count(b"INF 1 commits scanned." + nl), 1)
    invalid = [
        (b"no summary" + nl,),
        (b"junk INF 1 commits scanned." + nl,),
        (b"INF 1 commits scanned. trailing" + nl,),
        (b"INF 1\ncommits scanned\n",),
        (b"12:51AM INF 270 commits scanned" + nl + b"12:52AM INF 270 commits scanned" + nl,),
        (b"12:51AM INF 12345678901 commits scanned" + nl,),
    ]
    for (value,) in invalid:
        with pytest.raises(ScanError):
            summary_count(value)


def test_scan_container_configures_output_mount_and_logs(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    if not hasattr(module.os, "getuid"):
        monkeypatch.setattr(module.os, "getuid", lambda: 1234, raising=False)
        monkeypatch.setattr(module.os, "getgid", lambda: 5678, raising=False)

    captured: list[list[str]] = []

    def capture_command(args: list[str]) -> tuple[int, bytes, bytes]:
        captured.append(args)
        return 0, b"", b""

    monkeypatch.setattr(module, "capture", capture_command)
    output_dir = tmp_path / "output"
    output_dir.mkdir()
    output_dir.chmod(0o700)
    template = tmp_path / "template.tmpl"
    template.write_bytes(VALID_REPORT_TEMPLATE)
    create_scan_container(tmp_path, template, output_dir, "container", "docker")
    expect_equal((output_dir / "redacted-report-template.tmpl").exists(), True)
    expect_equal(captured[0].count("--no-color"), 1)
    expect_equal(f"{output_dir.resolve()}:/out:rw" in captured[0], True)
    expect_equal(any(arg.startswith("--tmpfs=/out") for arg in captured[0]), False)
    expect_equal(f"--ulimit=fsize={MAX_REPORT}:{MAX_REPORT}" in captured[0], True)
    expect_equal(f"--user={module.os.getuid()}:{module.os.getgid()}" in captured[0], True)


@pytest.mark.parametrize(
    ("stderr", "expected_reason"),
    [
        (b"Cannot connect to the Docker daemon", "daemon_unavailable"),
        (b"manifest unknown", "image_unavailable"),
        (b"invalid mount config", "volume_mount_failed"),
        (b"permission denied", "permission_denied"),
        (b"unknown flag", "invalid_options"),
        (b"no space left on device", "host_resource"),
        (b"unclassified diagnostic", "docker_rejected"),
    ],
)
def test_docker_create_failure_is_classified_without_echoing_output(
    stderr: bytes, expected_reason: str
) -> None:
    expect_equal(classify_docker_create_failure(stderr), expected_reason)


def test_scan_container_failure_reports_only_allowlisted_diagnostic(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    output_dir = tmp_path / "output"
    output_dir.mkdir()
    output_dir.chmod(0o700)
    template = tmp_path / "template.tmpl"
    template.write_bytes(VALID_REPORT_TEMPLATE)
    private_path = str(tmp_path / "private-scan-path")
    private_marker = "SYNTHETIC_PRIVATE_MARKER"
    monkeypatch.setattr(
        module,
        "capture",
        lambda _args: (
            125,
            b"",
            f"invalid mount config {private_path} {private_marker}".encode(),
        ),
    )

    with pytest.raises(StageError) as caught:
        create_scan_container(tmp_path, template, output_dir, "container", "docker")

    report_error(caught.value)
    captured = capsys.readouterr()
    expect_equal(captured.out, "")
    expect_equal(caught.value.stage, "scan_docker_create")
    expect_equal(
        captured.err,
        "security scan failed stage=scan_docker_create "
        "docker_create_status=125 docker_create_reason=volume_mount_failed\n",
    )
    expect_equal(private_path in captured.err, False)
    expect_equal(private_marker in captured.err, False)


@pytest.mark.parametrize(
    ("stdout", "stderr", "expected_metrics"),
    [
        (b"", b"", (0, 0, 0, None, 0, 0, False, False, False, False, False)),
        (b"commits scanned", b"", (1, 0, 0, None, 0, 1, False, False, False, False, False)),
        (b"", b"diagnostic only", (0, 0, 0, None, 0, 0, False, False, False, False, False)),
        (
            b"",
            b"INF 1 commits scanned\nINF 1 commits scanned\n",
            (0, 2, 2, None, 2, 2, True, False, True, False, False),
        ),
        (
            b"",
            b"INF 1 commits scanned unexpected\n",
            (0, 1, 0, None, 0, 1, True, False, True, False, True),
        ),
        (
            b"",
            b"INF 1 commits scanned..\n",
            (0, 1, 0, None, 0, 1, True, False, True, False, True),
        ),
        (
            b"",
            b"\x1b[31mINF 1 commits scanned\x1b[0m\n",
            (0, 1, 0, None, 0, 1, False, False, False, True, True),
        ),
    ],
    ids=(
        "no-output",
        "marker-without-regex-match",
        "marker-absent",
        "multiple",
        "suffix-content",
        "duplicate-period-suffix",
        "ansi-markers",
    ),
)
def test_summary_verification_reports_safe_numeric_diagnostics(
    stdout: bytes,
    stderr: bytes,
    expected_metrics: tuple[
        int, int, int, int | None, int, int, bool, bool, bool, bool, bool
    ],
    capsys: pytest.CaptureFixture[str],
) -> None:
    minimum = 1
    (
        stdout_markers,
        stderr_markers,
        matches,
        parsed,
        scanner_status,
        candidate_lines,
        inf_prefix,
        timestamp_prefix,
        numeric_prefix,
        ansi,
        suffix_content,
    ) = expected_metrics

    with pytest.raises(StageError) as caught:
        verify_scan_summary(stdout, stderr, scanner_status)

    expect_equal(caught.value.stage, "scan_commit_summary")
    expect_equal(
        caught.value.summary_diagnostics,
        (
            len(stdout),
            len(stderr),
            stdout_markers,
            stderr_markers,
            matches,
            minimum,
            parsed,
            scanner_status,
            candidate_lines,
            inf_prefix,
            timestamp_prefix,
            numeric_prefix,
            ansi,
            suffix_content,
        ),
    )
    report_error(caught.value)
    captured = capsys.readouterr()
    parsed_text = "none" if parsed is None else str(parsed)
    expect_equal(
        captured.err,
        f"security scan failed stage=scan_commit_summary stdout_bytes={len(stdout)} "
        f"stderr_bytes={len(stderr)} stdout_markers={stdout_markers} "
        f"stderr_markers={stderr_markers} summary_matches={matches} "
        f"minimum_commits={minimum} parsed_commits={parsed_text} "
        f"scanner_exit_status={scanner_status} candidate_lines={candidate_lines} "
        f"candidate_inf_prefix={int(inf_prefix)} "
        f"candidate_timestamp_prefix={int(timestamp_prefix)} "
        f"candidate_numeric_prefix={int(numeric_prefix)} candidate_ansi={int(ansi)} "
        f"candidate_suffix_content={int(suffix_content)}\n",
    )
    expect_equal(captured.out, "")


def test_summary_diagnostic_does_not_echo_stream_contents(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    private_path = str(tmp_path / "private-summary-path")
    canary = "ghp_" + hashlib.sha256(b"summary-diagnostic-canary").hexdigest()[:36]
    stdout = f"{private_path}:{canary}".encode()
    stderr = b"untrusted scanner output"

    with pytest.raises(StageError) as caught:
        verify_scan_summary(stdout, stderr, 0)

    report_error(caught.value)
    captured = capsys.readouterr()
    expect_equal(captured.out, "")
    expect_equal(private_path in captured.err, False)
    expect_equal(canary in captured.err, False)
    expect_equal(stderr.decode() in captured.err, False)


def test_summary_verification_accepts_positive_scanner_owned_count() -> None:
    verify_scan_summary(b"", b"12:51AM INF 1 commits scanned\n", 0)


def test_summary_verification_accepts_timestamped_positive_summary() -> None:
    verify_scan_summary(b"", b"12:51AM INF 2 commits scanned\n", 0)


def test_summary_verification_rejects_zero_count() -> None:
    with pytest.raises(StageError) as caught:
        verify_scan_summary(b"", b"INF 0 commits scanned\n", 0)
    expect_equal(caught.value.stage, "scan_commit_summary")


def test_summary_not_formed_across_stdout_stderr_boundary(
    capsys: pytest.CaptureFixture[str],
) -> None:
    stdout = b"INF "
    stderr = b"1 commits scanned\n"

    with pytest.raises(StageError) as caught:
        verify_scan_summary(stdout, stderr, 0)

    report_error(caught.value)
    captured = capsys.readouterr()
    expect_equal(captured.out, "")
    expect_equal(
        captured.err,
        "security scan failed stage=scan_commit_summary stdout_bytes=4 stderr_bytes=18 "
        "stdout_markers=0 stderr_markers=1 summary_matches=0 minimum_commits=1 "
        "parsed_commits=none scanner_exit_status=0 candidate_lines=1 "
        "candidate_inf_prefix=0 candidate_timestamp_prefix=0 candidate_numeric_prefix=0 "
        "candidate_ansi=0 candidate_suffix_content=0\n",
    )
    expect_equal(stdout.decode() in captured.err, False)
    expect_equal(stderr.decode() in captured.err, False)


def test_summary_diagnostic_bounds_accept_maximum_values() -> None:
    max_stream_matches = module.MAX_CAPTURE // module.MIN_SUMMARY_LINE_BYTES
    diagnostics = (
        module.MAX_CAPTURE,
        module.MAX_CAPTURE,
        max_stream_matches,
        max_stream_matches,
        2 * max_stream_matches,
        module.MAX_SUMMARY_COMMIT_COUNT,
        module.MAX_SUMMARY_COMMIT_COUNT,
        module.FINDINGS_STATUS,
        2 * max_stream_matches,
        True,
        True,
        True,
        True,
        True,
    )
    expect_equal(module.valid_summary_diagnostics(diagnostics), True)


@pytest.mark.parametrize(
    "field_index",
    range(module.SUMMARY_DIAGNOSTIC_FIELD_COUNT),
    ids=(
        "stdout-bytes",
        "stderr-bytes",
        "stdout-markers",
        "stderr-markers",
        "summary-matches",
        "expected-commits",
        "parsed-commits",
        "scanner-status",
        "candidate-lines",
        "inf-prefix",
        "timestamp-prefix",
        "numeric-prefix",
        "ansi",
        "suffix-content",
    ),
)
def test_oversized_summary_diagnostic_fields_fall_back_without_raising(
    field_index: int, capsys: pytest.CaptureFixture[str]
) -> None:
    fields: list[object] = [64, 64, 1, 0, 1, 1, 1, 0, 1, True, False, True, False, False]
    fields[field_index] = 10**5000
    error = StageError("scan_commit_summary", summary_diagnostics=tuple(fields))  # type: ignore[arg-type]

    report_error(error)

    captured = capsys.readouterr()
    expect_equal(captured.out, "")
    expect_equal(captured.err, "security scan failed stage=scan_commit_summary\n")


def test_malformed_summary_diagnostics_fall_back_without_raising(
    capsys: pytest.CaptureFixture[str],
) -> None:
    valid = (64, 64, 1, 0, 1, 1, 1, 0, 1, True, False, True, False, False)
    malformed: tuple[object, ...] = (
        None,
        [],
        valid[:-1],
        (True, *valid[1:]),
        (-1, *valid[1:]),
        (64, 64, 0, 0, 1, 1, 1, 0, 1, True, False, True, False, False),
        (64, 64, 1, 0, 1, 1, True, 0, 1, True, False, True, False, False),
        (*valid[:8], 0, *valid[9:]),
        (*valid[:8], 0, True, False, True, False, False),
        (64, 64, 1, 0, 0, 1, None, 0, 1, False, False, True, False, False),
        (*valid[:-1], 1),
    )
    for diagnostics in malformed:
        report_error(
            StageError("scan_commit_summary", summary_diagnostics=diagnostics)  # type: ignore[arg-type]
        )
        captured = capsys.readouterr()
        expect_equal(captured.out, "")
        expect_equal(captured.err, "security scan failed stage=scan_commit_summary\n")


def test_status_rows_consistency() -> None:
    row = ("R", "fixture.txt", HASH, 1)
    expect_equal(scanner_status_consistent(0, []), True)
    expect_equal(scanner_status_consistent(2, [row]), True)
    expect_equal(scanner_status_consistent(0, [row]), False)
    expect_equal(scanner_status_consistent(2, []), False)


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


def test_render_redacts_nested_untrusted_path_from_report_and_stdout(
    capsys: pytest.CaptureFixture[str],
) -> None:
    canary = "ghp_" + hashlib.sha256(b"omniagent-private-filename-canary").hexdigest()[:36]
    private_path = f"nested/π/segment/{canary}\x01\ncontrol"
    rows = [
        ("PrivateFinding", private_path, HASH, 3),
        ("IndependentPositiveControl", "src/normal.py", HASH, 8),
    ]

    report = render(rows)
    module.write_stdout(report)
    output = capsys.readouterr()

    expect_equal(canary.encode("ascii") in report, False)
    expect_equal(private_path.encode("utf-8") in report, False)
    expect_equal(canary in output.out, False)
    expect_equal(private_path in output.out, False)
    expect_equal(output.err, "")
    expect_equal(output.out.encode("ascii"), report)
    expect_equal(REDACTED_PATH.encode("ascii") in report, True)
    expect_equal(b"IndependentPositiveControl" in report, True)
    expect_equal(
        parse_report(report),
        [
            ("PrivateFinding", REDACTED_PATH, HASH, 3),
            ("IndependentPositiveControl", REDACTED_PATH, HASH, 8),
        ],
    )


def test_parse_report_retains_canonical_size_limit_after_redaction() -> None:
    path = "a/" + "b" * (MAX_PATH - 2)
    row = f'R\t"{path}"\t{HASH}\t1\n'.encode("ascii")
    report = row * (MAX_CANONICAL // len(row) + 1)

    expect_equal(len(report) < MAX_REPORT, True)
    with pytest.raises(ScanError):
        parse_report(report)


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


def test_stage_diagnostics_emit_only_allowlisted_ids(tmp_path: Path) -> None:
    script_dir = Path(__file__).resolve().parent
    canary = "ghp_" + hashlib.sha256(b"omniagent-gitleaks-contract").hexdigest()[:36]
    private_path = str(tmp_path / "private-report-path")
    stage_ids = (
        "contract_clean_repo_setup",
        "contract_clean_scan_execution",
        "contract_clean_assertions",
        "contract_canary_scan",
        "contract_history_canary_scan",
        "contract_mutant_scan",
        "contract_cli_validation",
        "scan_commit_summary",
        "scan_full_history",
        "scan_git_stream",
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

    invalid_summary = subprocess.run(  # noqa: S603 - fixed interpreter argv and controlled fixture.
        [
            sys.executable,
            "-c",
            (
                "import sys; import gitleaks_report as g; "
                "g.report_error(g.StageError(sys.argv[1], summary_diagnostics=(sys.argv[2], "
                "0, 0, 0, 0, 1, None, 0))); raise SystemExit(1)"
            ),
            "scan_commit_summary",
            canary,
        ],
        cwd=script_dir,
        capture_output=True,
        check=False,
    )
    expect_equal(invalid_summary.returncode, 1)
    invalid_diagnostic = invalid_summary.stderr.replace(b"\r\n", b"\n")
    expect_equal(invalid_diagnostic, b"security scan failed stage=scan_commit_summary\n")
    expect_equal(canary.encode() in invalid_diagnostic, False)

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
        ("full_history", "scan_full_history"),
        ("docker_create", "scan_docker_create"),
        ("docker_start", "scan_docker_start"),
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
    template = tmp_path / "template.tmpl"
    template.write_bytes(VALID_REPORT_TEMPLATE)
    private_path = str(tmp_path / "private-scan-path")
    injected = ScanError(f"{private_path}:{canary}:untrusted diagnostic")
    cleanup_called = False
    original_copy_scan_report = module.copy_scan_report
    monkeypatch.setattr(
        module, "ensure_full_history", lambda _repo: (_ for _ in ()).throw(injected)
        if phase == "full_history"
        else None,
    )

    def capture_for_phase(
        args: list[str], timeout: int = module.TIMEOUT
    ) -> tuple[int, bytes, bytes]:
        nonlocal cleanup_called
        del timeout
        if args[1] == "create":
            if phase == "docker_create":
                raise injected
            out_mount = next(arg for arg in args if arg.endswith(":/out:rw"))
            (Path(out_mount.removesuffix(":/out:rw")) / "report.tsv").write_bytes(b"")
            return 0, b"", b""
        if args[1] == "start":
            if phase == "docker_start":
                raise injected
            if phase == "summary":
                return 0, b"missing summary", b""
            return 0, b"12:51AM INF 1 commits scanned\n", b""
        if args[1] == "inspect":
            if phase == "docker_inspect":
                raise injected
            return 0, b"0\n", b""
        if args[1] == "rm":
            cleanup_called = True
            if phase == "cleanup":
                raise injected
            return 0, b"", b""
        raise AssertionError("unexpected synthetic command")

    def copy_for_phase(report: Path) -> bytes:
        if phase == "report_copy":
            fail_stage("scan_report_copy")
        return original_copy_scan_report(report)

    def parse_for_phase(_raw: bytes) -> list[tuple[str, str, str, int]]:
        if phase == "report_parse":
            raise injected
        return []

    monkeypatch.setattr(module, "capture", capture_for_phase)
    monkeypatch.setattr(module, "copy_scan_report", copy_for_phase)
    monkeypatch.setattr(module, "parse_report", parse_for_phase)
    with pytest.raises(StageError) as caught:
        module.scan(tmp_path, template)
    expect_equal(caught.value.stage, expected_stage)
    report_error(caught.value)
    captured = capsys.readouterr()
    expect_equal(captured.out, "")
    expect_equal(cleanup_called, phase not in {"full_history", "docker_create"})
    expected_diagnostic = (
        f"security scan failed stage=scan_commit_summary stdout_bytes={len(b'missing summary')} "
        "stderr_bytes=0 stdout_markers=0 stderr_markers=0 summary_matches=0 "
        "minimum_commits=1 parsed_commits=none scanner_exit_status=0 candidate_lines=0 "
        "candidate_inf_prefix=0 candidate_timestamp_prefix=0 candidate_numeric_prefix=0 "
        "candidate_ansi=0 candidate_suffix_content=0\n"
        if phase == "summary"
        else (
            "security scan failed stage=scan_docker_create "
            "docker_create_status=unknown docker_create_reason=capture_failed\n"
        )
        if phase == "docker_create"
        else f"security scan failed stage={expected_stage}\n"
    )
    expect_equal(captured.err, expected_diagnostic)
    expect_equal(canary in captured.err, False)
    expect_equal(private_path in captured.err, False)


def test_copy_scan_report_open_error_uses_fixed_stage(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    report = tmp_path / "report.tsv"
    report.write_bytes(b"fixture")

    def fail_open(*_args: object, **_kwargs: object) -> int:
        raise OSError("untrusted report open failure")

    monkeypatch.setattr(module.os, "open", fail_open)
    with pytest.raises(StageError) as caught:
        copy_scan_report(report)

    expect_equal(caught.value.stage, "scan_report_copy")
    report_error(caught.value)
    captured = capsys.readouterr()
    expect_equal(captured.out, "")
    expect_equal(captured.err, "security scan failed stage=scan_report_copy\n")


@pytest.mark.skipif(os.name != "posix", reason="RLIMIT_FSIZE fixture requires POSIX")
def test_stdout_capture_is_bounded() -> None:
    code = f"import sys; sys.stdout.buffer.write(b'x' * {MAX_CAPTURE + 2})"
    with pytest.raises(ScanError):
        capture([sys.executable, "-c", code])


def test_copy_scan_report_caps_size(tmp_path: Path) -> None:
    report = tmp_path / "report.tsv"
    report.write_bytes(b"x" * (300 * 1024))
    expect_equal(len(copy_scan_report(report)), 300 * 1024)

    report.write_bytes(b"x" * (MAX_REPORT + 1))
    with pytest.raises(ScanError):
        copy_scan_report(report)


def test_copy_scan_report_rejects_symlink(tmp_path: Path) -> None:
    target = tmp_path / "outside-report"
    target.write_bytes(b"private fixture")
    report = tmp_path / "report.tsv"
    create_symlink_or_skip(report, target)

    with pytest.raises(ScanError):
        copy_scan_report(report)


def test_copy_scan_report_rejects_symlink_swap(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    target = tmp_path / "outside-report"
    target.write_bytes(b"private fixture")
    report = tmp_path / "report.tsv"
    report.write_bytes(b"regular fixture")
    replacement = tmp_path / "replacement"
    create_symlink_or_skip(replacement, target)

    original_open = os.open
    swapped = False

    def swap_before_open(path: str | Path, flags: int, *args: object, **kwargs: object) -> int:
        nonlocal swapped
        if Path(path) == report:
            replacement.replace(report)
            swapped = True
        return original_open(path, flags, *args, **kwargs)  # type: ignore[arg-type]

    monkeypatch.setattr(module.os, "open", swap_before_open)
    with pytest.raises(ScanError):
        copy_scan_report(report)
    expect_equal(swapped, True)


@pytest.mark.parametrize(
    "case", ["redacted", "missing_redaction", "leaked_report", "leaked_output", "clean_status"]
)
def test_contract_mutant_scan_requires_redacted_positive_control(
    case: str, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    canary = hashlib.sha256(b"mutant contract fixture").hexdigest().encode("ascii")
    raw = b"R\tREDACTED\tfixture\t1\tREDACTED\tREDACTED\n"
    output = b""
    status = module.FINDINGS_STATUS
    if case == "missing_redaction":
        raw = b"R\tfixture\tfixture\t1\tvalue\tvalue\n"
    elif case == "leaked_report":
        raw = canary
    elif case == "leaked_output":
        output = canary
    elif case == "clean_status":
        status = module.CLEAN_STATUS

    def make_mutant_repo(root: Path, _name: str, _content: bytes) -> Path:
        return root / "mutant"

    def scan_mutant(
        _repo: Path, _template: Path, *, allow_invalid: bool = False
    ) -> tuple[int, list[tuple[str, str, str, int]], bytes, bytes]:
        expect_equal(allow_invalid, True)
        return status, [], output, raw

    monkeypatch.setattr(module, "make_repo", make_mutant_repo)
    monkeypatch.setattr(module, "scan", scan_mutant)

    if case == "redacted":
        mutant_raw, bad_report = contract_mutant_scan(tmp_path, tmp_path / "template", canary)
        expect_equal(b"REDACTED" in mutant_raw, True)
        expect_equal(canary in mutant_raw, False)
        expect_equal(bad_report.parent, tmp_path)
        return

    with pytest.raises(StageError) as caught:
        contract_mutant_scan(tmp_path, tmp_path / "template", canary)
    expect_equal(caught.value.stage, "contract_mutant_scan")
    report_error(caught.value)
    captured = capsys.readouterr()
    expect_equal(captured.out, "")
    expect_equal(captured.err, "security scan failed stage=contract_mutant_scan\n")
    expect_equal(canary.decode("ascii") in captured.err, False)
