import hashlib
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from gitleaks_report import (
    MAX_CAPTURE,
    MAX_REPORT,
    Failure,
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


class ParserTests(unittest.TestCase):
    def test_ascii_unicode_quote_round_trip(self):
        rows = parse_report(f'R\t"dir/quote\\\"-caf\\u00e9.txt"\t{HASH}\t1\n'.encode())
        self.assertEqual(rows[0][1], 'dir/quote"-café.txt')

    def test_rejects_traversal_absolute_backslash_controls_and_bidi(self):
        for value in ("../escape", "/absolute", "dir\\escape", "x/\x1bname", "x/\u202ename"):
            with self.subTest(value=repr(value)):
                self.assertFalse(safe_path(value))

    def test_rejects_total_row_and_row_count_boundaries(self):
        with self.assertRaises(Failure):
            parse_report(b"x" * (MAX_REPORT + 1))
        with self.assertRaises(Failure):
            parse_report(b"R\t\"" + b"x" * 16_384 + b"\"\t" + HASH.encode() + b"\t1\n")
        with self.assertRaises(Failure):
            parse_report(ROW * 20_001)

    def test_rejects_malformed_encoding_crlf_quote_columns_hash_and_line(self):
        invalid = (
            b"\xff",
            ROW.replace(b"\n", b"\r\n"),
            b'R\t"unterminated\t' + HASH.encode() + b"\t1\n",
            b'R\t"fixture.txt"\t' + HASH.encode() + b"\n",
            b'R\t"fixture.txt"\t' + HASH.encode() + b"\t1\textra\n",
            b'R\t"fixture.txt"\tbad\t1\n',
            b'R\t"fixture.txt"\t' + HASH.encode() + b"\t0\n",
            b'R\t"fixture.txt"\t' + ("a" * 41).encode() + b"\t1\n",
            b'R\t"fixture.txt"\t' + ("a" * 63).encode() + b"\t1\n",
        )
        for raw in invalid:
            with self.subTest(raw=raw[:20]), self.assertRaises(Failure):
                parse_report(raw)

    @unittest.skipUnless(os.name == "posix", "docker report copy contract uses POSIX file limits")
    def test_empty_report_is_clean_but_absent_report_fails(self):
        self.assertEqual(parse_report(b""), [])
        with tempfile.TemporaryDirectory(prefix="absent-report-") as td:
            fake = Path(td) / "docker"
            fake.write_text("#!/usr/bin/env python3\nraise SystemExit(0)\n", encoding="utf-8")
            fake.chmod(0o700)
            with self.assertRaises(Failure):
                docker_cp("c", "/out/report.tsv", Path(td) / "absent", docker_bin=str(fake))

    def test_summary_parser_accepts_observed_log_prefix_and_rejects_missing_duplicate(self):
        nl = bytes((10,))
        self.assertEqual(summary_count(b"12:51AM INF 270 commits scanned" + nl), 270)
        invalid = (
            b"no summary" + nl,
            b"12:51AM INF 270 commits scanned" + nl + b"12:52AM INF 270 commits scanned" + nl,
            b"12:51AM INF 12345678901 commits scanned" + nl,
        )
        for value in invalid:
            with self.subTest(value=value), self.assertRaises(Failure):
                summary_count(value)

    def test_status_rows_consistency(self):
        row = ("R", "fixture.txt", HASH, 1)
        self.assertTrue(scanner_status_consistent(0, []))
        self.assertTrue(scanner_status_consistent(2, [row]))
        self.assertFalse(scanner_status_consistent(0, [row]))
        self.assertFalse(scanner_status_consistent(2, []))

    def test_cli_clean_and_finding_exit_behavior_and_safe_output(self):
        script_dir = Path(__file__).resolve().parent
        canary = "ghp_" + hashlib.sha256(b"omniagent-gitleaks-contract").hexdigest()[:36]
        safe_row = ("GitleaksRule", "fixture.txt", HASH, 1)
        safe_row_repr = repr(safe_row)

        def command_for(scan_status):
            code = (
                "import sys; import gitleaks_report as g; "
                f"g.scan=lambda *a, **k: ({scan_status}, ([{safe_row_repr}] if {scan_status} == 2 else []), b'', b''); "
                "sys.argv=['gitleaks_report.py','scan','unused','unused']; "
                "raise SystemExit(g.main())"
            )
            return [sys.executable, "-c", code]

        clean = subprocess.run(command_for(0), cwd=script_dir, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False)
        self.assertEqual((clean.returncode, clean.stdout, clean.stderr), (0, b"", b""))

        finding = subprocess.run(command_for(2), cwd=script_dir, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False)
        expected = render([safe_row])
        self.assertEqual(finding.returncode, 1)
        self.assertEqual(finding.stdout, expected)
        self.assertEqual(len(finding.stdout.rstrip(b"\n").split(b"\t")), 4)
        self.assertNotIn(canary.encode(), finding.stdout)
        self.assertNotIn(canary.encode(), finding.stderr)

    def test_actual_entrypoint_clean_and_invalid_reports(self):
        helper = Path(__file__).with_name("gitleaks_report.py")
        with tempfile.TemporaryDirectory(prefix="entrypoint-report-") as td:
            root = Path(td)
            empty = root / "empty.tsv"
            empty.write_bytes(b"")
            clean = subprocess.run(
                [sys.executable, str(helper), "validate", str(empty)],
                stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False,
            )
            self.assertEqual((clean.returncode, clean.stdout, clean.stderr), (0, b"", b""))

            invalid = root / "invalid.tsv"
            invalid.write_bytes(b"bad schema\n")
            rejected = subprocess.run(
                [sys.executable, str(helper), "validate", str(invalid)],
                stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False,
            )
            self.assertEqual(rejected.returncode, 1)
            self.assertEqual(rejected.stdout, b"")
            self.assertEqual(rejected.stderr.replace(b"\r\n", b"\n"), b"security scan failed\n")

    @unittest.skipUnless(os.name == "posix", "RLIMIT_FSIZE fixture requires POSIX")
    def test_stdout_capture_is_bounded(self):
        code = "import sys; sys.stdout.buffer.write(b'x' * %d)" % (MAX_CAPTURE + 2)
        with self.assertRaises(Failure):
            capture([sys.executable, "-c", code])

    @unittest.skipUnless(os.name == "posix", "RLIMIT_FSIZE fixture requires POSIX")
    def test_docker_cp_allows_report_over_256k_and_rejects_over_8m(self):
        with tempfile.TemporaryDirectory(prefix="fake-docker-") as td:
            root = Path(td)
            payload = root / "payload"
            payload.write_bytes(b"x" * (300 * 1024))
            fake = root / "docker"
            fake.write_text(
                "#!/usr/bin/env python3\n"
                "import pathlib,sys\n"
                "assert sys.argv[1] == 'cp'\n"
                "container, source = sys.argv[2].split(':', 1)\n"
                "assert container == 'unused'\n"
                "src=pathlib.Path(source); dst=pathlib.Path(sys.argv[3])\n"
                "dst.write_bytes(src.read_bytes())\n",
                encoding="utf-8",
            )
            fake.chmod(0o700)
            dest = root / "copied-report"
            docker_cp("unused", str(payload), dest, docker_bin=str(fake))
            self.assertEqual(dest.stat().st_size, 300 * 1024)
            payload.write_bytes(b"x" * (MAX_REPORT + 1))
            with self.assertRaises(Failure):
                docker_cp("unused", str(payload), root / "too-large", docker_bin=str(fake))


if __name__ == "__main__":
    unittest.main()



