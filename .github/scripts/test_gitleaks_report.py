import hashlib
import os
import subprocess
import sys
from pathlib import Path
from typing import TypeVar

import pytest
from gitleaks_report import (
    MAX_CAPTURE,
    MAX_REPORT,
    ScanError,
    capture,
    docker_cp,
    parse_report,
    render,
    safe_path,
    scanner_status_consistent,
    summary_count,
)

HASH = "0123456789abcdef0123456789abcdef01234567"
ROW = f'R\t"fixture.txt"\t{HASH}\t1\n'.encode("ascii")
EXPECTED_COMMIT_COUNT = 270
EXPECTED_COLUMN_COUNT = 4
T = TypeVar("T")


def expect_equal(actual: T, expected: T) -> None:
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


def test_summary_parser_accepts_observed_log_prefix_and_rejects_missing_duplicate() -> None:
    nl = bytes((10,))
    expect_equal(summary_count(b"12:51AM INF 270 commits scanned" + nl), EXPECTED_COMMIT_COUNT)
    invalid = [
        (b"no summary" + nl,),
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
