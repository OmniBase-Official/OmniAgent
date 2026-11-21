"""Opt-in end-to-end publisher checks across two Windows user SIDs."""

from __future__ import annotations

import csv
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import time
from pathlib import Path
from typing import TypedDict

import pytest

PROJECT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT / "scripts"))

import publish_dataset  # noqa: E402, I001
import publisher_root  # noqa: E402
from dataset_provenance import write_sidecar  # noqa: E402
from publish_dataset import PublishError  # noqa: E402

_CONFIG_ENV = "OMNIAGENT_WINDOWS_ACL_CONFIG"
_ADMINISTRATORS_SID = "S-1-5-32-544"
_PRIVILEGED_GROUP_SIDS = {
    "S-1-5-32-547",  # Power Users
    "S-1-5-32-548",  # Account Operators
    "S-1-5-32-549",  # Server Operators
    "S-1-5-32-550",  # Print Operators
    "S-1-5-32-551",  # Backup Operators
    "S-1-5-32-552",  # Replicator
    "S-1-5-32-569",  # Cryptographic Operators
}
_SENSITIVE_PRIVILEGES = {
    "SeAssignPrimaryTokenPrivilege",
    "SeBackupPrivilege",
    "SeCreateTokenPrivilege",
    "SeDebugPrivilege",
    "SeImpersonatePrivilege",
    "SeLoadDriverPrivilege",
    "SeManageVolumePrivilege",
    "SeRestorePrivilege",
    "SeSecurityPrivilege",
    "SeTakeOwnershipPrivilege",
    "SeTcbPrivilege",
}
_MAX_PROBE_TIMEOUT_SECONDS = 300


class WindowsACLTestConfig(TypedDict):
    publisher_sid: str
    peer_sid: str
    destination_parent: str
    unsafe_ancestor_root: str
    unsafe_ancestor_destination_parent: str
    unsafe_delete_child_parent: str
    unsafe_delete_child_control_path: str
    unsafe_delete_child_result_path: str
    unsafe_write_dac_parent: str
    unsafe_write_dac_result_path: str
    unsafe_write_owner_parent: str
    unsafe_write_owner_control_path: str
    unsafe_write_owner_result_path: str
    unsafe_generic_all_parent: str
    unsafe_generic_all_control_path: str
    unsafe_generic_all_result_path: str
    ready_path: str
    release_path: str
    publisher_evidence_path: str
    result_path: str
    probe_timeout_seconds: int


def _configuration() -> WindowsACLTestConfig:
    if os.name != "nt":
        pytest.skip("cross-SID publisher validation requires Windows")
    config_path = os.environ.get(_CONFIG_ENV)
    if not config_path:
        pytest.skip("set OMNIAGENT_WINDOWS_ACL_CONFIG from the validation harness")
    try:
        raw: object = json.loads(Path(config_path).read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ValueError("Windows ACL validation config must contain valid JSON") from exc
    if not isinstance(raw, dict):
        raise TypeError("Windows ACL validation config must be a JSON object")
    expected_keys = {
        "publisher_sid",
        "peer_sid",
        "destination_parent",
        "unsafe_ancestor_root",
        "unsafe_ancestor_destination_parent",
        "unsafe_delete_child_parent",
        "unsafe_delete_child_control_path",
        "unsafe_delete_child_result_path",
        "unsafe_write_dac_parent",
        "unsafe_write_dac_result_path",
        "unsafe_write_owner_parent",
        "unsafe_write_owner_control_path",
        "unsafe_write_owner_result_path",
        "unsafe_generic_all_parent",
        "unsafe_generic_all_control_path",
        "unsafe_generic_all_result_path",
        "ready_path",
        "release_path",
        "publisher_evidence_path",
        "result_path",
        "probe_timeout_seconds",
    }
    if set(raw) != expected_keys:
        raise ValueError("Windows ACL validation config has unexpected or missing keys")

    def require_string(key: str) -> str:
        value = raw.get(key)
        if not isinstance(value, str) or not value:
            raise ValueError(
                f"Windows ACL validation config field {key} must be a non-empty string"
            )
        return value

    timeout = raw.get("probe_timeout_seconds")
    if (
        isinstance(timeout, bool)
        or not isinstance(timeout, int)
        or not 1 <= timeout <= _MAX_PROBE_TIMEOUT_SECONDS
    ):
        raise ValueError("Windows ACL validation probe timeout must be between 1 and 300 seconds")

    return WindowsACLTestConfig(
        publisher_sid=require_string("publisher_sid"),
        peer_sid=require_string("peer_sid"),
        destination_parent=require_string("destination_parent"),
        unsafe_ancestor_root=require_string("unsafe_ancestor_root"),
        unsafe_ancestor_destination_parent=require_string("unsafe_ancestor_destination_parent"),
        unsafe_delete_child_parent=require_string("unsafe_delete_child_parent"),
        unsafe_delete_child_control_path=require_string("unsafe_delete_child_control_path"),
        unsafe_delete_child_result_path=require_string("unsafe_delete_child_result_path"),
        unsafe_write_dac_parent=require_string("unsafe_write_dac_parent"),
        unsafe_write_dac_result_path=require_string("unsafe_write_dac_result_path"),
        unsafe_write_owner_parent=require_string("unsafe_write_owner_parent"),
        unsafe_write_owner_control_path=require_string("unsafe_write_owner_control_path"),
        unsafe_write_owner_result_path=require_string("unsafe_write_owner_result_path"),
        unsafe_generic_all_parent=require_string("unsafe_generic_all_parent"),
        unsafe_generic_all_control_path=require_string("unsafe_generic_all_control_path"),
        unsafe_generic_all_result_path=require_string("unsafe_generic_all_result_path"),
        ready_path=require_string("ready_path"),
        release_path=require_string("release_path"),
        publisher_evidence_path=require_string("publisher_evidence_path"),
        result_path=require_string("result_path"),
        probe_timeout_seconds=timeout,
    )


def _token_snapshot() -> tuple[str, set[str], list[str]]:
    whoami = Path(os.environ["SYSTEMROOT"]) / "System32" / "whoami.exe"
    user = subprocess.run(  # noqa: S603 - fixed Windows system executable
        [str(whoami), "/user", "/fo", "csv", "/nh"],
        capture_output=True,
        text=True,
        check=True,
        timeout=10,
    )
    user_sids = re.findall(r"S-1-\d+(?:-\d+)+", user.stdout)
    if len(user_sids) != 1:
        raise AssertionError("could not identify the current Windows token SID")
    groups = subprocess.run(  # noqa: S603 - fixed Windows system executable
        [str(whoami), "/groups", "/fo", "csv", "/nh"],
        capture_output=True,
        text=True,
        check=True,
        timeout=10,
    )
    privileges = subprocess.run(  # noqa: S603 - fixed Windows system executable
        [str(whoami), "/priv", "/fo", "csv", "/nh"],
        capture_output=True,
        text=True,
        check=True,
        timeout=10,
    )
    privilege_rows = [line.strip() for line in privileges.stdout.splitlines() if line.strip()]
    return (
        user_sids[0],
        set(re.findall(r"S-1-\d+(?:-\d+)+", groups.stdout)),
        privilege_rows,
    )


def _assert_standard_token(groups: set[str], privileges: list[str], label: str) -> None:
    forbidden_groups = _PRIVILEGED_GROUP_SIDS | {_ADMINISTRATORS_SID}
    if groups & forbidden_groups:
        raise AssertionError(f"{label} token has privileged group membership")
    rows = list(csv.reader(privileges))
    if not rows or any(len(row) < 3 for row in rows):
        raise AssertionError(f"{label} token privileges could not be parsed")
    enabled_sensitive = {
        row[0].strip()
        for row in rows
        if row[0].strip() in _SENSITIVE_PRIVILEGES and row[-1].strip().casefold() == "enabled"
    }
    if enabled_sensitive:
        raise AssertionError(f"{label} token has an enabled sensitive privilege")


def _dataset(path: Path) -> Path:
    source = path / "source"
    source.mkdir()
    dataset = source / "dataset.jsonl"
    example = json.dumps(
        {
            "messages": [
                {"role": "system", "content": "Synthetic publisher ACL test."},
                {"role": "user", "content": "Synthetic input."},
                {"role": "assistant", "content": "Synthetic output."},
            ]
        }
    )
    dataset.write_text(example + "\n", encoding="utf-8")
    write_sidecar(dataset)
    return dataset


def _record_result(config: WindowsACLTestConfig, result: dict[str, bool]) -> None:
    path = Path(config["result_path"])
    current: dict[str, bool] = {}
    if path.exists():
        current = json.loads(path.read_text(encoding="utf-8"))
    current.update(result)
    path.write_text(json.dumps(current), encoding="utf-8")


def test_publisher_staging_denies_a_distinct_sid(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    config = _configuration()
    current_sid, group_sids, privileges = _token_snapshot()
    publisher_sid = config["publisher_sid"]
    peer_sid = config["peer_sid"]

    assert current_sid == publisher_sid
    assert publisher_sid != peer_sid
    _assert_standard_token(group_sids, privileges, "publisher")

    destination_parent = Path(config["destination_parent"])
    ready_path = Path(config["ready_path"])
    release_path = Path(config["release_path"])
    publisher_evidence_path = Path(config["publisher_evidence_path"])
    assert destination_parent.is_dir()
    monkeypatch.setattr(publisher_root, "_known_local_data_root", lambda: destination_parent)
    monkeypatch.setattr(publisher_root, "_APP_DIRECTORY", "OmniAgent")
    profile = publisher_root.PublisherRoot.provision_local_user()
    destination = profile.path / "published"
    publisher_evidence_path.write_text(
        json.dumps(
            {
                "user_sid": current_sid,
                "group_sids": sorted(group_sids),
                "privileges": privileges,
            }
        ),
        encoding="utf-8",
    )
    dataset = _dataset(tmp_path)

    def pause_after_payload(phase: str) -> None:
        if phase != "first-payload":
            return
        stages = list(profile.path.glob(f"{publish_dataset._STAGING_PREFIX}*"))
        assert len(stages) == 1, "expected exactly one private staging directory"
        staged_payload = stages[0] / dataset.name
        assert staged_payload.is_file(), "expected the staged payload before peer access"
        ready_path.write_text(
            json.dumps(
                {
                    "stage_path": str(stages[0]),
                    "payload_path": str(staged_payload),
                    "payload_sha256": hashlib.sha256(staged_payload.read_bytes()).hexdigest(),
                }
            ),
            encoding="utf-8",
        )
        deadline = time.monotonic() + int(config.get("probe_timeout_seconds", 90))
        while not release_path.exists() and time.monotonic() < deadline:
            time.sleep(0.1)
        if not release_path.exists():
            raise TimeoutError("the cross-SID probe did not release the publisher")

    monkeypatch.setattr(publish_dataset, "_publish_checkpoint", pause_after_payload)
    try:
        publish_dataset.publish_to_root(dataset, profile, "published", teacher="synthetic-acl-test")
        assert publish_dataset.verify_from_root(profile, "published") == []
        assert (destination / dataset.name).read_bytes() == dataset.read_bytes()
        assert not list(profile.path.glob(f"{publish_dataset._STAGING_PREFIX}*"))
        _record_result(config, {"publish_success": True, "safe_profile": True})
    finally:
        profile.close()


def test_foreign_parent_delete_child_and_write_dac_are_rejected_before_publish(
    tmp_path: Path,
) -> None:
    config = _configuration()
    current_sid, groups, privileges = _token_snapshot()
    assert current_sid == config["publisher_sid"]
    _assert_standard_token(groups, privileges, "publisher")

    controls = Path(config["unsafe_delete_child_result_path"])
    assert controls.is_file(), "peer DELETE_CHILD negative control did not run"
    control = json.loads(controls.read_text(encoding="utf-8"))
    assert control.get("peer_deleted_child") is True
    assert not Path(config["unsafe_delete_child_control_path"]).exists()
    write_dac_controls = Path(config["unsafe_write_dac_result_path"])
    assert write_dac_controls.is_file(), "peer WRITE_DAC negative control did not run"
    write_dac_control = json.loads(write_dac_controls.read_text(encoding="utf-8"))
    assert write_dac_control.get("peer_changed_dacl") is True
    write_owner_result = Path(config["unsafe_write_owner_result_path"])
    assert write_owner_result.is_file(), "peer WRITE_OWNER negative control did not run"
    write_owner_control = json.loads(write_owner_result.read_text(encoding="utf-8"))
    assert write_owner_control.get("peer_changed_owner") is True
    assert write_owner_control.get("owner_sid") == config["peer_sid"]
    generic_all_result = Path(config["unsafe_generic_all_result_path"])
    assert generic_all_result.is_file(), "peer GENERIC_ALL negative control did not run"
    generic_all_control = json.loads(generic_all_result.read_text(encoding="utf-8"))
    assert generic_all_control.get("peer_created_file") is True
    assert generic_all_control.get("generic_all_ace_verified") is True
    assert not Path(config["unsafe_generic_all_control_path"]).exists()

    cases = (
        (Path(config["unsafe_delete_child_parent"]), "delete-child"),
        (Path(config["unsafe_write_dac_parent"]), "write-dac"),
        (Path(config["unsafe_write_owner_parent"]), "write-owner"),
        (Path(config["unsafe_generic_all_parent"]), "generic-all"),
        (Path(config["unsafe_ancestor_destination_parent"]), "ancestor-delete-child"),
    )
    dataset = _dataset(tmp_path)
    for parent, label in cases:
        assert parent.is_dir()
        before = sorted(path.name for path in parent.iterdir())
        root = publish_dataset.SecureRoot(parent, writable=True)
        try:
            assert not root.supports_private_staging(), f"unsafe {label} parent was accepted"
        finally:
            root.close()

        destination = parent / "must-not-be-created"
        with pytest.raises(PublishError, match="cannot enforce private staging"):
            publish_dataset.publish(dataset, destination, teacher="synthetic-acl-test")
        assert not destination.exists()
        assert sorted(path.name for path in parent.iterdir()) == before
    unsafe_ancestor = Path(config["unsafe_ancestor_root"])
    nested_parent = Path(config["unsafe_ancestor_destination_parent"])
    assert nested_parent.parent == unsafe_ancestor


def test_promotion_failure_leaves_no_destination_or_staging(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    config = _configuration()
    current_sid, group_sids, privileges = _token_snapshot()
    assert current_sid == str(config["publisher_sid"])
    _assert_standard_token(group_sids, privileges, "publisher")

    destination_parent = Path(str(config["destination_parent"]))
    monkeypatch.setattr(publisher_root, "_known_local_data_root", lambda: destination_parent)
    monkeypatch.setattr(publisher_root, "_APP_DIRECTORY", "OmniAgent")
    profile = publisher_root.PublisherRoot.provision_local_user()
    destination = profile.path / "promotion-failure"
    dataset = _dataset(tmp_path)

    def fail_promotion(self: object, handle: int, stage_name: str, name: str) -> None:
        raise OSError("injected Windows promotion failure")

    monkeypatch.setattr(publish_dataset.SecureRoot, "rename_noreplace", fail_promotion)
    try:
        with pytest.raises(PublishError, match="atomic publication failed"):
            publish_dataset.publish_to_root(
                dataset, profile, "promotion-failure", teacher="synthetic-acl-test"
            )

        assert not destination.exists()
        assert not list(profile.path.glob(f"{publish_dataset._STAGING_PREFIX}*"))
        _record_result(config, {"promotion_failure": True})
    finally:
        profile.close()


@pytest.mark.skipif(os.name != "nt", reason="sanitized PowerShell diagnostics require Windows")
def test_windows_identity_diagnostics_are_allowlisted_and_redacted() -> None:
    powershell = shutil.which("powershell") or shutil.which("pwsh")
    assert powershell is not None, "PowerShell is required for Windows diagnostics validation"
    script = PROJECT / "scripts" / "validate_windows_publish_acl.ps1"
    completed = subprocess.run(  # noqa: S603 - fixed repository-owned PowerShell validation script
        [
            powershell,
            "-NoProfile",
            "-NonInteractive",
            "-ExecutionPolicy",
            "Bypass",
            "-File",
            str(script),
            "-RepositoryRoot",
            str(PROJECT),
            "-DiagnosticSelfTest",
        ],
        capture_output=True,
        text=True,
        check=True,
        timeout=20,
    )
    evidence = json.loads(completed.stdout)
    assert evidence == {
        "privilege": {
            "exception_type": "Win32Exception",
            "exception_chain": "Win32Exception",
            "error_category": "privilege_not_held",
            "powershell_category": "permission_denied",
        },
        "access_denied": {
            "exception_type": "Win32Exception",
            "exception_chain": "Win32Exception",
            "error_category": "access_denied",
            "powershell_category": "not_specified",
        },
        "hresult_access_denied": {
            "exception_type": "OtherException",
            "exception_chain": "OtherException",
            "error_category": "access_denied",
            "powershell_category": "not_specified",
        },
        "unsupported": {
            "exception_type": "Win32Exception",
            "exception_chain": "Win32Exception",
            "error_category": "unsupported",
            "powershell_category": "not_specified",
        },
        "unknown": {
            "exception_type": "InvalidOperationException",
            "exception_chain": "InvalidOperationException",
            "error_category": "unclassified",
            "powershell_category": "not_specified",
        },
        "wrapped": {
            "exception_type": "PowerShellRuntimeException",
            "exception_chain": "PowerShellRuntimeException>InvalidOperationException",
            "error_category": "unclassified",
            "powershell_category": "permission_denied",
        },
        "cim_access_denied": "access_denied",
        "cim_unknown": None,
        "cim_status_access_denied": "access_denied",
        "cim_status_unknown": None,
        "ownership_description_one": "OmniAgent-0123456789abcdef0123456789abcdef",
        "ownership_description_two": "OmniAgent-fedcba9876543210fedcba9876543210",
        "ownership_description_too_long_rejected": True,
    }
    assert len(evidence["ownership_description_one"]) <= 48
    assert evidence["ownership_description_one"] != evidence["ownership_description_two"]
    assert "SENSITIVE_SENTINEL" not in completed.stdout
    assert "SENSITIVE_SENTINEL" not in completed.stderr


@pytest.mark.skipif(os.name != "nt", reason="PowerShell diagnostics require Windows")
def test_private_root_diagnostics_are_allowlisted_and_redacted() -> None:
    powershell = shutil.which("powershell") or shutil.which("pwsh")
    assert powershell is not None, "PowerShell is required for private-root diagnostics validation"
    script = PROJECT / "scripts" / "prepare_windows_private_test_root.ps1"
    completed = subprocess.run(  # noqa: S603 - fixed repository-owned PowerShell self-test
        [
            powershell,
            "-NoProfile",
            "-NonInteractive",
            "-File",
            str(script),
            "-Action",
            "DiagnosticSelfTest",
        ],
        capture_output=True,
        text=True,
        check=True,
        timeout=20,
    )
    evidence = json.loads(completed.stdout)
    assert evidence == {
        "policy_rejected": True,
        "ancestry_roles_allowlisted": True,
        "ancestry_values_boolean": True,
        "unknown_status_fail_closed": True,
        "accepted_status_allowlisted": True,
        "unexpected_fields_fail_closed": True,
        "securefs_rejected_allowlisted": True,
        "status_stage_allowlisted": True,
        "unknown_stage_fail_closed": True,
        "case_variants_fail_closed": True,
        "empty_output_fails_closed": True,
        "nonzero_exit_fails_closed": True,
        "launch_error_allowlisted": True,
        "export_error_allowlisted": True,
        "sensitive_sentinel_redacted": True,
    }
    assert "SENSITIVE_SENTINEL" not in completed.stdout
    assert "SENSITIVE_SENTINEL" not in completed.stderr
