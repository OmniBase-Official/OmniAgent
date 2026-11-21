[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)]
    [ValidateSet("Create", "Cleanup", "DiagnosticSelfTest")]
    [string]$Action,
    [ValidateSet("OMNIAGENT_PRIVATE_TEST_ROOT", "OMNIAGENT_PUBLISHER_STAGING_ROOT")]
    [string]$OutputVariable = "OMNIAGENT_PRIVATE_TEST_ROOT"
)
$ErrorActionPreference = "Stop"
$phase = "preflight"

$probeStatuses = @("accepted", "policy_rejected", "securefs_rejected", "module_missing", "probe_import_error", "probe_attribute_error", "probe_argument_error", "probe_type_error", "probe_value_error", "probe_os_error", "probe_exception")
$probeStages = @("import", "root_open", "capability_check", "ancestry_acl", "volume_query", "root_close", "serialize")
$ancestryRoles = @("volume", "program_data", "base", "root")

function ConvertFrom-SafeProbeOutput([string]$Output) {
    try {
        $result = ConvertFrom-Json -InputObject $Output -ErrorAction Stop
        if ($null -eq $result -or $result.status -isnot [string] -or $result.status -cnotin $probeStatuses) {
            return @{ status = "probe_exception"; stage = $null; ancestry = $null }
        }
        if ($result.stage -isnot [string] -or $result.stage -cnotin $probeStages) {
            return @{ status = "probe_exception"; stage = $null; ancestry = $null }
        }
        if ($result.status -cne "policy_rejected") {
            $keys = @($result.PSObject.Properties.Name | Sort-Object)
            if (($keys -join ",") -cne "stage,status") {
                return @{ status = "probe_exception"; stage = $null; ancestry = $null }
            }
            return @{ status = $result.status; stage = $result.stage; ancestry = $null }
        }
        $keys = @($result.PSObject.Properties.Name | Sort-Object)
        if (($keys -join ",") -cne "ancestry,stage,status" -or $null -eq $result.ancestry) {
            return @{ status = "probe_exception"; stage = $null; ancestry = $null }
        }
        $facts = @{}
        foreach ($role in $ancestryRoles) {
            $value = $result.ancestry.$role
            if ($value -isnot [bool]) {
                return @{ status = "probe_exception"; stage = $null; ancestry = $null }
            }
            $facts[$role] = $value
        }
        $ancestryKeys = @($result.ancestry.PSObject.Properties.Name | Sort-Object)
        if (($ancestryKeys -join ",") -cne (($ancestryRoles | Sort-Object) -join ",")) {
            return @{ status = "probe_exception"; stage = $null; ancestry = $null }
        }
        return @{ status = "policy_rejected"; stage = $result.stage; ancestry_policy_passed = $facts }
    } catch {
        return @{ status = "probe_exception"; stage = $null; ancestry = $null }
    }
}

function Get-SafeProbeFailureCategory([string]$Phase, [int]$ExitCode, [string]$Output) {
    if ($Phase -eq "probe-launch") { return "probe_launch_error" }
    if ($Phase -eq "environment-export") { return "environment_export_error" }
    if ($ExitCode -ne 0) { return "probe_exception" }
    return (ConvertFrom-SafeProbeOutput $Output).status
}

if ($Action -eq "DiagnosticSelfTest") {
    $valid = ConvertFrom-SafeProbeOutput '{"status":"policy_rejected","stage":"ancestry_acl","ancestry":{"volume":true,"program_data":true,"base":false,"root":true}}'
    $unknown = ConvertFrom-SafeProbeOutput '{"status":"secret-path-SENSITIVE_SENTINEL"}'
    $accepted = ConvertFrom-SafeProbeOutput '{"status":"accepted","stage":"capability_check"}'
    $extraField = ConvertFrom-SafeProbeOutput '{"status":"accepted","stage":"capability_check","raw":"SENSITIVE_SENTINEL"}'
    $securefsRejected = ConvertFrom-SafeProbeOutput '{"status":"securefs_rejected","stage":"root_open"}'
    $attributeError = ConvertFrom-SafeProbeOutput '{"status":"probe_attribute_error","stage":"ancestry_acl"}'
    $importError = ConvertFrom-SafeProbeOutput '{"status":"probe_import_error","stage":"import"}'
    $unknownStage = ConvertFrom-SafeProbeOutput '{"status":"probe_exception","stage":"SENSITIVE_SENTINEL"}'
    $statusCaseVariant = ConvertFrom-SafeProbeOutput '{"status":"ACCEPTED","stage":"capability_check"}'
    $stageCaseVariant = ConvertFrom-SafeProbeOutput '{"status":"accepted","stage":"CAPABILITY_CHECK"}'
    $empty = Get-SafeProbeFailureCategory "probe-result" 0 ""
    $nonzero = Get-SafeProbeFailureCategory "probe-result" 1 '{"status":"accepted"}'
    $launch = Get-SafeProbeFailureCategory "probe-launch" 1 "C:\\private\\SENSITIVE_SENTINEL"
    $export = Get-SafeProbeFailureCategory "environment-export" 1 "user=SENSITIVE_SENTINEL"
    $evidence = @{
        policy_rejected = ($valid.status -eq "policy_rejected")
        ancestry_roles_allowlisted = (($valid.ancestry_policy_passed.Keys | Sort-Object) -join ",") -eq "base,program_data,root,volume"
        ancestry_values_boolean = @($valid.ancestry_policy_passed.Values | Where-Object { $_ -isnot [bool] }).Count -eq 0
        unknown_status_fail_closed = ($unknown.status -eq "probe_exception")
        accepted_status_allowlisted = ($accepted.status -eq "accepted")
        unexpected_fields_fail_closed = ($extraField.status -eq "probe_exception")
        securefs_rejected_allowlisted = ($securefsRejected.status -eq "securefs_rejected")
        status_stage_allowlisted = ($attributeError.status -eq "probe_attribute_error" -and $attributeError.stage -eq "ancestry_acl" -and $importError.status -eq "probe_import_error" -and $importError.stage -eq "import")
        unknown_stage_fail_closed = ($unknownStage.status -eq "probe_exception" -and $null -eq $unknownStage.stage)
        case_variants_fail_closed = ($statusCaseVariant.status -eq "probe_exception" -and $stageCaseVariant.status -eq "probe_exception")
        empty_output_fails_closed = ($empty -eq "probe_exception")
        nonzero_exit_fails_closed = ($nonzero -eq "probe_exception")
        launch_error_allowlisted = ($launch -eq "probe_launch_error")
        export_error_allowlisted = ($export -eq "environment_export_error")
    }
    $evidenceOutput = $evidence | ConvertTo-Json -Compress
    $evidence.sensitive_sentinel_redacted = $evidenceOutput -notmatch "SENSITIVE_SENTINEL"
    $evidenceOutput = $evidence | ConvertTo-Json -Compress
    $evidenceOutput
    if ($evidence.Values -contains $false) { exit 1 }
    exit 0
}

function Get-SafeFailureCategory([System.Exception]$Exception) {
    $current = $Exception
    for ($depth = 0; $null -ne $current -and $depth -lt 5; $depth++) {
        if ($current -is [UnauthorizedAccessException]) { return "access_denied" }
        if ($current -is [Security.SecurityException]) { return "security_error" }
        if ($current -is [ArgumentException]) { return "invalid_argument" }
        if ($current -is [IO.IOException]) { return "io_error" }
        $current = $current.InnerException
    }
    return "other_error"
}

try {
    if ($env:GITHUB_RUN_ID -notmatch "^\d+$" -or $env:GITHUB_RUN_ATTEMPT -notmatch "^\d+$") {
        throw "Workflow run identity is unavailable."
    }
    $base = Join-Path $env:ProgramData "OmniAgent-CI"
    $root = Join-Path $base ("private-" + $env:GITHUB_RUN_ID + "-" + $env:GITHUB_RUN_ATTEMPT)
    $marker = Join-Path $root ".omniagent-private-test-root"
    $markerValue = $env:GITHUB_RUN_ID + ":" + $env:GITHUB_RUN_ATTEMPT

    if ($Action -eq "Create") {
        $phase = "base-check"
        if (Test-Path -LiteralPath $base) {
            $baseItem = Get-Item -LiteralPath $base -Force
            if (-not $baseItem.PSIsContainer -or ($baseItem.Attributes -band [IO.FileAttributes]::ReparsePoint) -ne 0) {
                throw "Private staging base is not a regular directory."
            }
        } else {
            $phase = "base-create"
            New-Item -ItemType Directory -Path $base | Out-Null
        }
        $phase = "root-create"
        if (Test-Path -LiteralPath $root) { throw "Private staging root already exists." }
        New-Item -ItemType Directory -Path $root | Out-Null
        [IO.File]::WriteAllText($marker, $markerValue, [Text.Encoding]::ASCII)

        $phase = "root-acl"
        $currentSid = [Security.Principal.WindowsIdentity]::GetCurrent().User
        if ($null -eq $currentSid) { throw "Current runner identity is unavailable." }
        $acl = [Security.AccessControl.DirectorySecurity]::new()
        $acl.SetAccessRuleProtection($true, $false)
        $acl.SetOwner($currentSid)
        $inheritance = [Security.AccessControl.InheritanceFlags]::ContainerInherit -bor [Security.AccessControl.InheritanceFlags]::ObjectInherit
        $trustedSids = @(
            $currentSid,
            [Security.Principal.SecurityIdentifier]::new("S-1-5-18"),
            [Security.Principal.SecurityIdentifier]::new("S-1-5-32-544")
        )
        foreach ($sid in $trustedSids) {
            $rule = [Security.AccessControl.FileSystemAccessRule]::new(
                $sid,
                [Security.AccessControl.FileSystemRights]::FullControl,
                $inheritance,
                [Security.AccessControl.PropagationFlags]::None,
                [Security.AccessControl.AccessControlType]::Allow
            )
            $acl.AddAccessRule($rule)
        }
        Set-Acl -LiteralPath $root -AclObject $acl
        Set-Item -Path ("Env:" + $OutputVariable) -Value $root

        $phase = "python-resolution"
        $python = Get-Command python.exe -ErrorAction SilentlyContinue
        if ($null -eq $python) {
            [Console]::Error.WriteLine("Private staging root failed [python-resolution/missing-python].")
            exit 1
        }
        $phase = "probe-launch"
        $probe = @'
import ctypes
import errno
import json
import os
import sys

result = {"status": "probe_exception"}
root = None
securefs_module = None
stage = "import"
try:
    import securefs as securefs_module
    stage = "root_open"
    root = securefs_module.SecureRoot(
        os.environ["OUTPUT_VARIABLE"], writable=True,
        _allow_safe_inherited_ancestors=True,
    )
    stage = "capability_check"
    if root.supports_private_staging():
        result = {"status": "accepted", "stage": stage}
    else:
        stage = "ancestry_acl"
        handles = root._pinned_handles
        if len(handles) != 4:
            raise OSError(errno.EIO, "unexpected ancestry handle count")
        role_handles = {
            "volume": handles[0],
            "program_data": handles[1],
            "base": handles[-2],
            "root": handles[-1],
        }
        ancestry = {
            role: bool(securefs_module._has_safe_parent_acl(
                handle, allow_safe_inherited=True
            ))
            for role, handle in role_handles.items()
        }
        stage = "volume_query"
        buffer = ctypes.create_string_buffer(1024)
        iosb = securefs_module._IOSB()
        status = securefs_module._nt.NtQueryVolumeInformationFile(
            root.handle, ctypes.byref(iosb), buffer, len(buffer), 5
        )
        if status < 0:
            raise OSError(errno.EIO, "volume capability probe failed")
        persistent = bool(
            ctypes.c_uint32.from_address(ctypes.addressof(buffer)).value
            & securefs_module._FILE_PERSISTENT_ACLS
        )
        ancestry["volume"] = ancestry["volume"] and persistent
        result = {"status": "policy_rejected", "stage": stage, "ancestry": ancestry}
except ModuleNotFoundError:
    result = {"status": "module_missing", "stage": stage}
except ImportError:
    result = {"status": "probe_import_error", "stage": stage}
except OSError as exc:
    if securefs_module is not None and isinstance(exc, securefs_module.SecureFSError):
        result = {"status": "securefs_rejected", "stage": stage}
    else:
        result = {"status": "probe_os_error", "stage": stage}
except ctypes.ArgumentError:
    result = {"status": "probe_argument_error", "stage": stage}
except AttributeError:
    result = {"status": "probe_attribute_error", "stage": stage}
except TypeError:
    result = {"status": "probe_type_error", "stage": stage}
except ValueError:
    result = {"status": "probe_value_error", "stage": stage}
except Exception:
    result = {"status": "probe_exception", "stage": stage}
finally:
    if root is not None:
        stage = "root_close"
        try:
            root.close()
        except Exception:
            result = {"status": "probe_exception", "stage": stage}
try:
    stage = "serialize"
    if "stage" not in result:
        result["stage"] = stage
    print(json.dumps(result, separators=(",", ":")))
except Exception:
    print('{"status":"probe_exception","stage":"serialize"}')
'@
        $probe = $probe.Replace("OUTPUT_VARIABLE", $OutputVariable)
        $previousErrorActionPreference = $ErrorActionPreference
        try {
            $ErrorActionPreference = "Continue"
            $probeOutput = @(& $python.Source -c $probe 2>$null)
            $probeExitCode = $LASTEXITCODE
        } catch {
            [Console]::Error.WriteLine("Private staging root failed [probe-launch/probe_launch_error].")
            exit 1
        } finally {
            $ErrorActionPreference = $previousErrorActionPreference
        }
        $phase = "probe-result"
        $probeText = $probeOutput -join "`n"
        $probeResult = ConvertFrom-SafeProbeOutput $probeText
        if ($probeExitCode -ne 0) { $probeResult = @{ status = "probe_exception"; ancestry_policy_passed = $null } }
        if ($probeResult.status -ne "accepted" -or $probeExitCode -ne 0) {
            $category = Get-SafeProbeFailureCategory "probe-result" $probeExitCode $probeText
            if ($category -eq "policy_rejected" -and $null -ne $probeResult.ancestry_policy_passed) {
                $facts = ($ancestryRoles | ForEach-Object { $_ + "_policy_passed=" + [string]$probeResult.ancestry_policy_passed[$_] }) -join ","
                [Console]::Error.WriteLine(("Private staging root failed [{0}/{1}] stage[{2}] ancestry[{3}]." -f $phase, $category, $probeResult.stage, $facts))
            } elseif ($null -ne $probeResult.stage) {
                [Console]::Error.WriteLine(("Private staging root failed [{0}/{1}] stage[{2}]." -f $phase, $category, $probeResult.stage))
            } else {
                [Console]::Error.WriteLine(("Private staging root failed [{0}/{1}]." -f $phase, $category))
            }
            exit 1
        }
        $phase = "environment-export"
        try {
            if (-not $env:GITHUB_ENV) { throw "Workflow environment file is unavailable." }
            [IO.File]::AppendAllText($env:GITHUB_ENV, ($OutputVariable + "=" + $root + "`n"), [Text.UTF8Encoding]::new($false))
        } catch {
            [Console]::Error.WriteLine("Private staging root failed [environment-export/environment_export_error].")
            exit 1
        }
        Write-Output "private_staging_root=accepted"
        exit 0
    }

    $phase = "cleanup"
    if (-not (Test-Path -LiteralPath $root -PathType Container)) { exit 0 }
    $item = Get-Item -LiteralPath $root -Force
    if (($item.Attributes -band [IO.FileAttributes]::ReparsePoint) -ne 0) { throw "Private staging cleanup refused a reparse point." }
    if (-not (Test-Path -LiteralPath $marker -PathType Leaf)) { throw "Private staging cleanup refused a missing marker." }
    $markerItem = Get-Item -LiteralPath $marker -Force
    if (($markerItem.Attributes -band [IO.FileAttributes]::ReparsePoint) -ne 0) { throw "Private staging cleanup refused a reparse marker." }
    if ((Get-Content -LiteralPath $marker -Raw) -cne $markerValue) { throw "Private staging cleanup refused an unexpected marker." }
    $baseFull = (Resolve-Path -LiteralPath $base).Path.TrimEnd("\") + "\"
    $rootFull = (Resolve-Path -LiteralPath $root).Path
    if (-not $rootFull.StartsWith($baseFull, [StringComparison]::OrdinalIgnoreCase)) { throw "Private staging cleanup refused an out-of-scope path." }
    Remove-Item -LiteralPath $rootFull -Recurse -Force
    Write-Output "private_staging_root=removed"
    exit 0
} catch {
    $category = Get-SafeFailureCategory $_.Exception
    [Console]::Error.WriteLine(("Private staging root failed [{0}/{1}]." -f $phase, $category))
    exit 1
}
