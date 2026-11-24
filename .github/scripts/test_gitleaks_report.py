import hashlib
import os
import shutil
import subprocess
import sys
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


def capture_limit_diagnostic(stdout: bytes, stderr: bytes, limit: int) -> str:
    return (
        "security scan failed stage=scan_docker_start "
        f"stdout_bytes={len(stdout)} stderr_bytes={len(stderr)} limit={limit}"
    )


def expect_equal(actual: object, expected: object) -> None:
    if actual != expected:
        raise AssertionError(f"expected {expected!r}, got {actual!r}")


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


def test_scan_container_sets_exact_report_file_size_limit(
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
    args = captured[0]
    limit_index = args.index("--ulimit")
    expect_equal(args[limit_index + 1], f"fsize={MAX_REPORT}:{MAX_REPORT}")


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


@pytest.mark.skipif(
    shutil.which("docker") is None,
    reason="pinned-image integration requires Docker",
)
def test_scan_report_survives_container_exit(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    def portable_capture(
        args: list[str], timeout: int = module.TIMEOUT
    ) -> tuple[int, bytes, bytes]:
        if args[1] == "create":
            args = [*args[:2], "--env=NO_COLOR=1", *args[2:]]
        result = subprocess.run(  # noqa: S603 - controlled argv, synthetic fixture, shell=False.
            args,
            stdin=subprocess.DEVNULL,
            capture_output=True,
            timeout=timeout,
            check=False,
        )
        if len(result.stdout) > module.MAX_CAPTURE or len(result.stderr) > module.MAX_CAPTURE:
            pytest.fail(
                capture_limit_diagnostic(
                    result.stdout, result.stderr, module.MAX_CAPTURE
                ),
                pytrace=False,
            )
        return result.returncode, result.stdout, result.stderr

    monkeypatch.setattr(module, "capture", portable_capture)
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
        ("commit_count", "scan_commit_count"),
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
    monkeypatch.setattr(module, "count_commits", lambda _repo: (_ for _ in ()).throw(injected))
    if phase != "commit_count":
        monkeypatch.setattr(module, "count_commits", lambda _repo: 1)

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
