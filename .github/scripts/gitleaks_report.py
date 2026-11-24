from __future__ import annotations

import ast
import hashlib
import json
import os
import re
import stat
import subprocess
import sys
import tempfile
import unicodedata
import uuid
from pathlib import Path
from typing import Literal, NoReturn

try:
    import resource
except ImportError:  # pragma: no cover - CI and publisher runner are POSIX.
    resource = None

IMAGE = (
    "ghcr.io/gitleaks/gitleaks:v8.30.1@sha256:"
    "b109bc5f8f76a38196a3e413704fc5b9e3c32360bce4e4b603bd6f45b3721dbb"
)
MAX_CAPTURE = 256 * 1024
MAX_REPORT = 8 * 1024 * 1024
MAX_ROWS = 20_000
MAX_ROW = 16 * 1024
MAX_PATH = 4096
MAX_CANONICAL = 1024 * 1024
TIMEOUT = 120
FIELDS = ("RuleID", "File", "Commit", "StartLine")
SUMMARY = re.compile(
    rb"(?m)^(?:[0-9]{1,2}:[0-9]{2}(?:AM|PM)\s+)?INF\s+([0-9]{1,10})\s+commits scanned\.?\s*$"
)
HASH = re.compile(r"^(?:[0-9a-f]{40}|[0-9a-f]{64})\Z")
GENERIC = "security scan failed"
CLEAN_STATUS = 0
FINDINGS_STATUS = 2
CLI_EXIT_FAILURE = 1
REPORT_FIELD_COUNT = 4
MAX_LINE_NUMBER = 2**31 - 1
CLI_SCAN_ARGC = 4
CLI_CONTRACT_ARGC = 4
CLI_VALIDATE_ARGC = 3
StageId = Literal[
    "contract_clean_repo_setup",
    "contract_clean_scan_execution",
    "contract_clean_assertions",
    "scan_repository_policy",
    "scan_docker_create",
    "scan_docker_start",
    "scan_docker_inspect",
    "scan_commit_summary",
    "scan_report_copy",
    "scan_report_parse",
    "scan_container_cleanup",
    "contract_canary_scan",
    "contract_mutant_scan",
    "contract_cli_validation",
]
ALLOWED_STAGE_IDS = frozenset(
    {
        "contract_clean_repo_setup",
        "contract_clean_scan_execution",
        "contract_clean_assertions",
        "scan_repository_policy",
        "scan_docker_create",
        "scan_docker_start",
        "scan_docker_inspect",
        "scan_commit_summary",
        "scan_report_copy",
        "scan_report_parse",
        "scan_container_cleanup",
        "contract_canary_scan",
        "contract_mutant_scan",
        "contract_cli_validation",
    }
)
FindingRow = tuple[str, str, str, int]
ScanResult = tuple[int, list[FindingRow], bytes, bytes]


class ScanError(Exception):
    pass


def fail() -> NoReturn:
    raise ScanError(GENERIC)


class StageError(ScanError):
    def __init__(self, stage: StageId) -> None:
        super().__init__(GENERIC)
        self.stage = stage


def fail_stage(stage: StageId) -> NoReturn:
    if stage not in ALLOWED_STAGE_IDS:
        fail()
    raise StageError(stage)


def preserve_or_fallback(error: StageError, fallback: StageId) -> NoReturn:
    if error.stage in ALLOWED_STAGE_IDS:
        raise error
    fail_stage(fallback)


def report_error(error: ScanError) -> None:
    sys.stdout.buffer.write(b"")
    if isinstance(error, StageError) and error.stage in ALLOWED_STAGE_IDS:
        sys.stderr.write(f"{GENERIC} stage={error.stage}\n")
        return
    sys.stderr.write(GENERIC + "\n")


def set_fsize(limit: int) -> None:
    if resource is None:
        raise OSError("POSIX file-size limits are required")
    resource.setrlimit(resource.RLIMIT_FSIZE, (limit, limit))


def capture(args: list[str], timeout: int = TIMEOUT) -> tuple[int, bytes, bytes]:
    """Capture diagnostics to private files and reject output above 256 KiB."""
    with tempfile.TemporaryDirectory(prefix="omni-capture-") as td:
        root = Path(td)
        root.chmod(0o700)
        out_path, err_path = root / "out", root / "err"
        try:
            with out_path.open("wb") as out, err_path.open("wb") as err:
                result = subprocess.run(  # noqa: S603 - controlled argv; shell=False.
                    args,
                    stdin=subprocess.DEVNULL,
                    stdout=out,
                    stderr=err,
                    timeout=timeout,
                    check=False,
                    preexec_fn=lambda: set_fsize(MAX_CAPTURE + 1),
                )
            if out_path.stat().st_size > MAX_CAPTURE or err_path.stat().st_size > MAX_CAPTURE:
                fail()
            return result.returncode, out_path.read_bytes(), err_path.read_bytes()
        except (OSError, subprocess.TimeoutExpired):
            fail()


def docker_cp(container: str, source: str, destination: Path, docker_bin: str = "docker") -> None:
    """Copy report with an 8 MiB file cap; Docker diagnostics are discarded."""
    if resource is None:
        fail()
    try:
        result = subprocess.run(  # noqa: S603 - controlled argv; shell=False.
            [docker_bin, "cp", f"{container}:{source}", str(destination)],
            stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            timeout=TIMEOUT,
            check=False,
            preexec_fn=lambda: set_fsize(MAX_REPORT),
        )
        if result.returncode != 0 or not destination.is_file():
            fail()
        if destination.stat().st_size > MAX_REPORT:
            fail()
    except (OSError, subprocess.TimeoutExpired):
        fail()


def safe_path(value: str) -> bool:
    try:
        encoded = value.encode("utf-8", "strict")
    except UnicodeError:
        return False
    if not value or len(encoded) > MAX_PATH or value.startswith("/"):
        return False
    if "\\" in value or ":" in value:
        return False
    if any(part in ("", ".", "..") for part in value.split("/")):
        return False
    return not any(unicodedata.category(c) in {"Cc", "Cf", "Cs", "Zl", "Zp"} for c in value)


def render(rows: list[tuple[str, str, str, int]]) -> bytes:
    output = bytearray()
    for rule, path, commit, line in rows:
        output.extend(
            f"{rule}\t{json.dumps(path, ensure_ascii=True)}\t{commit}\t{line}\n".encode("ascii")
        )
        if len(output) > MAX_CANONICAL:
            fail()
    return bytes(output)


def parse_row(line: str) -> FindingRow:
    if not line or len(line.encode("utf-8")) > MAX_ROW:
        fail()
    fields = line.split("\t")
    if len(fields) != REPORT_FIELD_COUNT:
        fail()
    rule, quoted, commit, number = fields
    if not re.fullmatch(r"[A-Za-z0-9_.-]{1,128}", rule) or not HASH.fullmatch(commit):
        fail()
    try:
        path = ast.literal_eval(quoted)
    except (SyntaxError, ValueError):
        fail()
    if not isinstance(path, str) or not safe_path(path):
        fail()
    if not number.isascii() or not number.isdecimal():
        fail()
    line_no = int(number)
    if not 1 <= line_no <= MAX_LINE_NUMBER:
        fail()
    return rule, path, commit, line_no


def parse_report(raw: bytes) -> list[FindingRow]:
    if len(raw) > MAX_REPORT:
        fail()
    try:
        text = raw.decode("utf-8", "strict")
    except UnicodeError:
        fail()
    if "\r" in text:
        fail()
    if not text:
        return []
    lines = text.split("\n")
    if lines[-1] == "":
        lines.pop()
    if len(lines) > MAX_ROWS:
        fail()
    rows = [parse_row(line) for line in lines]
    if len(render(rows)) > MAX_CANONICAL:
        fail()
    return rows


def verify_scan_repository(repo: Path) -> None:
    status, output, _ = capture(
        ["git", "-C", str(repo), "rev-parse", "--is-shallow-repository"]
    )
    if status != CLEAN_STATUS or output != b"false\n":
        fail()


def summary_count(output: bytes) -> int:
    found = SUMMARY.findall(output)
    if len(found) != 1:
        fail()
    try:
        return int(found[0])
    except ValueError:
        fail()


def scanner_status_consistent(status: int, rows: list[tuple[str, str, str, int]]) -> bool:
    return (status == CLEAN_STATUS and not rows) or (status == FINDINGS_STATUS and bool(rows))


def report_directory_owner(
    report_dir: Path, *, platform_name: str | None = None
) -> tuple[int, int] | None:
    if (os.name if platform_name is None else platform_name) != "posix":
        return None
    try:
        info = report_dir.lstat()
        uid, gid = info.st_uid, info.st_gid
    except (OSError, AttributeError):
        fail()
    if not stat.S_ISDIR(info.st_mode):
        fail()
    if not isinstance(uid, int) or isinstance(uid, bool):
        fail()
    if not isinstance(gid, int) or isinstance(gid, bool):
        fail()
    return uid, gid


def create_scan_container(
    repo: Path, template: Path, report_dir: Path, name: str, docker_bin: str
) -> None:
    try:
        owner = report_directory_owner(report_dir)
    except Exception:  # noqa: BLE001 - report only a fixed scan stage identifier.
        fail_stage("scan_docker_create")
    user_args = [] if owner is None else ["--user", f"{owner[0]}:{owner[1]}"]
    args = [
        docker_bin,
        "create",
        "--name",
        name,
        "--network=none",
        "--read-only",
        "--cap-drop=ALL",
        "--security-opt=no-new-privileges",
        "--memory=512m",
        "--cpus=1",
        "--pids-limit=64",
        *user_args,
        "--ulimit",
        f"fsize={MAX_REPORT}:{MAX_REPORT}",
        "--volume",
        f"{report_dir.resolve()}:/out:rw",
        "--volume",
        f"{repo.resolve()}:/repo:ro",
        "--volume",
        f"{template.resolve()}:/template.tmpl:ro",
        IMAGE,
        "git",
        "--redact=100",
        "--no-banner",
        "--no-color",
        "--exit-code=2",
        "--report-format=template",
        "--report-template=/template.tmpl",
        "--report-path=/out/report.tsv",
        "--gitleaks-ignore-path=/repo/.gitleaksignore",
        "--log-opts=--full-history --all --diff-filter=tuxdb --diff-merges=first-parent",
        "/repo",
    ]
    try:
        status, _, _ = capture(args)
        if status != CLEAN_STATUS:
            fail()
    except Exception:  # noqa: BLE001 - report only a fixed scan stage identifier.
        fail_stage("scan_docker_create")


def start_scan_container(docker_bin: str, name: str) -> tuple[int, bytes, bytes]:
    try:
        status, stdout, stderr = capture([docker_bin, "start", "--attach", name])
        if status not in (CLEAN_STATUS, FINDINGS_STATUS):
            fail()
    except Exception:  # noqa: BLE001 - report only a fixed scan stage identifier.
        fail_stage("scan_docker_start")
    else:
        return status, stdout, stderr


def inspect_scan_container(docker_bin: str, name: str, start_status: int) -> int:
    try:
        status, output, _ = capture(
            [docker_bin, "inspect", "--format", "{{.State.ExitCode}}", name]
        )
        if status != CLEAN_STATUS or not output.endswith(b"\n"):
            fail()
        scan_status = int(output.decode("ascii").strip())
        if scan_status not in (CLEAN_STATUS, FINDINGS_STATUS) or start_status != scan_status:
            fail()
    except Exception:  # noqa: BLE001 - report only a fixed scan stage identifier.
        fail_stage("scan_docker_inspect")
    else:
        return scan_status


def verify_scan_summary(output: bytes) -> None:
    try:
        if summary_count(output) < 1:
            fail()
    except Exception:  # noqa: BLE001 - report only a fixed scan stage identifier.
        fail_stage("scan_commit_summary")


def copy_scan_report(report: Path) -> bytes:
    try:
        info = report.lstat()
        if not stat.S_ISREG(info.st_mode) or info.st_size > MAX_REPORT:
            fail()
        flags = os.O_RDONLY
        if hasattr(os, "O_NOFOLLOW"):
            flags |= os.O_NOFOLLOW
        fd = os.open(report, flags)
        try:
            opened = os.fstat(fd)
            if not stat.S_ISREG(opened.st_mode) or opened.st_size > MAX_REPORT:
                fail()
            with os.fdopen(fd, "rb", closefd=False) as source:
                raw = source.read(MAX_REPORT + 1)
            if len(raw) > MAX_REPORT:
                fail()
            return raw
        finally:
            os.close(fd)
    except Exception:  # noqa: BLE001 - report only a fixed scan stage identifier.
        fail_stage("scan_report_copy")


def parse_scan_report(raw: bytes, scan_status: int, allow_invalid: bool) -> list[FindingRow] | None:
    try:
        rows = parse_report(raw)
    except ScanError:
        if allow_invalid:
            return None
        fail_stage("scan_report_parse")
    except Exception:  # noqa: BLE001 - report only a fixed scan stage identifier.
        fail_stage("scan_report_parse")
    try:
        if not scanner_status_consistent(scan_status, rows):
            fail()
    except Exception:  # noqa: BLE001 - report only a fixed scan stage identifier.
        fail_stage("scan_report_parse")
    else:
        return rows


def cleanup_scan_container(docker_bin: str, name: str) -> None:
    try:
        status, _, _ = capture([docker_bin, "rm", "-f", name])
        if status != CLEAN_STATUS:
            fail()
    except Exception:  # noqa: BLE001 - report only a fixed scan stage identifier.
        fail_stage("scan_container_cleanup")


def scan(
    repo: Path, template: Path, *, docker_bin: str = "docker", allow_invalid: bool = False
) -> tuple[int, list[tuple[str, str, str, int]], bytes, bytes]:
    try:
        verify_scan_repository(repo)
    except Exception:  # noqa: BLE001 - report only a fixed scan stage identifier.
        fail_stage("scan_repository_policy")
    name = "omni-gitleaks-" + uuid.uuid4().hex
    with tempfile.TemporaryDirectory(prefix="omni-report-") as td:
        root = Path(td)
        root.chmod(0o700)
        report = root / "report.tsv"
        create_scan_container(repo, template, root, name, docker_bin)
        try:
            start_status, stdout, stderr = start_scan_container(docker_bin, name)
            scan_status = inspect_scan_container(docker_bin, name, start_status)
            output = stdout + b"\n" + stderr
            verify_scan_summary(output)
            raw = copy_scan_report(report)
            rows = parse_scan_report(raw, scan_status, allow_invalid)
            if rows is None:
                return scan_status, [], stdout + stderr, raw
            return scan_status, rows, stdout + stderr, raw
        finally:
            cleanup_scan_container(docker_bin, name)


def validate_report(path: Path) -> bytes:
    try:
        raw = path.read_bytes()
    except OSError:
        fail()
    rows = parse_report(raw)
    return render(rows)


def make_repo(root: Path, name: str, content: bytes) -> Path:
    repo = root / name
    repo.mkdir()
    (repo / ".gitleaksignore").write_bytes(b"")
    commands = [
        ["git", "init", "-q", str(repo)],
        ["git", "-C", str(repo), "config", "user.email", "fixture@example.invalid"],
        ["git", "-C", str(repo), "config", "user.name", "Synthetic Fixture"],
    ]
    for command in commands:
        status, _, _ = capture(command)
        if status != CLEAN_STATUS:
            fail()
    (repo / "fixture.txt").write_bytes(content)
    for command in (
        ["git", "-C", str(repo), "add", "fixture.txt"],
        ["git", "-C", str(repo), "commit", "-qm", "synthetic fixture"],
    ):
        status, _, _ = capture(command)
        if status != CLEAN_STATUS:
            fail()
    return repo


def assert_clean_scan(
    status: int,
    rows: list[FindingRow],
    output: bytes,
    raw: bytes,
) -> None:
    if (
        status != CLEAN_STATUS
        or rows
        or parse_report(raw)
        or summary_count(output) < 1
        or b"finding" in output.lower()
        or b"secret" in output.lower()
    ):
        fail()


def contract_clean_scan(root: Path, template: Path) -> None:
    try:
        clean = make_repo(root, "clean", b"ordinary fixture text\n")
    except StageError as error:
        preserve_or_fallback(error, "contract_clean_repo_setup")
    except Exception:  # noqa: BLE001 - map every phase failure to a fixed, non-sensitive stage ID.
        fail_stage("contract_clean_repo_setup")

    try:
        status, rows, output, raw = scan(clean, template)
    except StageError as error:
        preserve_or_fallback(error, "contract_clean_scan_execution")
    except Exception:  # noqa: BLE001 - map every phase failure to a fixed, non-sensitive stage ID.
        fail_stage("contract_clean_scan_execution")

    try:
        assert_clean_scan(status, rows, output, raw)
    except StageError as error:
        preserve_or_fallback(error, "contract_clean_assertions")
    except Exception:  # noqa: BLE001 - map every phase failure to a fixed, non-sensitive stage ID.
        fail_stage("contract_clean_assertions")


def contract_canary_scan(root: Path, template: Path, canary: bytes) -> None:
    try:
        positive = make_repo(root, "positive", b"token=" + canary + b"\n")
        status, rows, output, raw = scan(positive, template)
        if (
            status != FINDINGS_STATUS
            or len(rows) != 1
            or canary in output
            or canary in raw
            or canary in render(rows)
        ):
            fail()
        if rows[0][1] != "fixture.txt" or rows[0][3] != 1:
            fail()
        if FIELDS != ("RuleID", "File", "Commit", "StartLine"):
            fail()
        if render(rows).splitlines()[0].decode("ascii").count(chr(9)) != REPORT_FIELD_COUNT - 1:
            fail()
    except StageError as error:
        preserve_or_fallback(error, "contract_canary_scan")
    except Exception:  # noqa: BLE001 - map phase failures to a fixed, non-sensitive stage ID.
        fail_stage("contract_canary_scan")


def contract_mutant_scan(root: Path, template: Path, canary: bytes) -> None:
    try:
        mutant_repo = make_repo(root, "mutant", b"token=" + canary + b"\n")
        mutant_status, _, mutant_output, mutant_raw = scan(
            mutant_repo, template, allow_invalid=True
        )
        if (
            mutant_status != FINDINGS_STATUS
            or not mutant_raw
            or canary in mutant_raw
            or canary in mutant_output
        ):
            fail()
        try:
            parse_report(mutant_raw)
        except ScanError:
            return
        fail()
    except StageError as error:
        preserve_or_fallback(error, "contract_mutant_scan")
    except Exception:  # noqa: BLE001 - map phase failures to a fixed, non-sensitive stage ID.
        fail_stage("contract_mutant_scan")


def contract(template: Path, mutant_template: Path) -> None:
    with tempfile.TemporaryDirectory(prefix="omni-contract-") as td:
        root = Path(td)
        root.chmod(0o700)
        contract_clean_scan(root, template)

        canary = ("ghp_" + hashlib.sha256(b"omniagent-gitleaks-contract").hexdigest()[:36]).encode(
            "ascii"
        )
        contract_canary_scan(root, template, canary)
        contract_mutant_scan(root, mutant_template, canary)
        bad = root / "malformed-report.tsv"
        bad.write_bytes(b'R\t"fixture.txt"\tinvalid\t1\t' + canary + b"\n")
        code = [sys.executable, str(Path(__file__).resolve()), "validate", str(bad)]
        try:
            proc_status, proc_out, proc_err = capture(code)
            if (
                proc_status == CLEAN_STATUS
                or proc_out
                or canary in proc_out
                or canary in proc_err
                or proc_err != (GENERIC + "\n").encode()
            ):
                fail()
        except ScanError:
            fail_stage("contract_cli_validation")


def main() -> int:
    if len(sys.argv) == CLI_SCAN_ARGC and sys.argv[1] == "scan":
        status, rows, _, _ = scan(Path(sys.argv[2]), Path(sys.argv[3]))
        if status not in (CLEAN_STATUS, FINDINGS_STATUS) or not scanner_status_consistent(
            status, rows
        ):
            fail()
        write_stdout(render(rows))
        return CLI_EXIT_FAILURE if status == FINDINGS_STATUS else CLEAN_STATUS
    if len(sys.argv) == CLI_CONTRACT_ARGC and sys.argv[1] == "contract":
        contract(Path(sys.argv[2]), Path(sys.argv[3]))
        return CLEAN_STATUS
    if len(sys.argv) == CLI_VALIDATE_ARGC and sys.argv[1] == "validate":
        write_stdout(validate_report(Path(sys.argv[2])))
        return CLEAN_STATUS
    fail()


def write_stdout(data: bytes) -> None:
    if len(data) > MAX_CANONICAL:
        fail()
    sys.stdout.buffer.write(data)
    sys.stdout.buffer.flush()


if __name__ == "__main__":
    try:
        exit_code = main()
    except StageError as error:
        report_error(error)
        exit_code = CLI_EXIT_FAILURE
    except ScanError as error:
        report_error(error)
        exit_code = CLI_EXIT_FAILURE
    except Exception:  # noqa: BLE001 - CLI boundary emits only generic errors.
        sys.stdout.buffer.write(b"")
        sys.stderr.write(GENERIC + "\n")
        exit_code = CLI_EXIT_FAILURE
    raise SystemExit(exit_code)
