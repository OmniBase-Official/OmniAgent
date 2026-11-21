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

$probeStatuses = @("accepted", "policy_rejected", "securefs_rejected", "module_missing", "probe_import_error", "probe_attribute_error", "probe_argument_error", "probe_type_error", "probe_value_error", "probe_os_error", "probe_bootstrap_error", "probe_output_overflow", "probe_timeout", "probe_exception")
$probeStages = @("bootstrap", "import", "root_open", "capability_check", "ancestry_acl", "volume_query", "root_close", "serialize")
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
    return (Resolve-SafeProbeResult $ExitCode $Output).status
}

function Resolve-SafeProbeResult([int]$ExitCode, [string]$Output, [bool]$TimedOut = $false, [bool]$OutputOverflow = $false) {
    $parsed = ConvertFrom-SafeProbeOutput $Output
    if ($TimedOut) { return @{ status = "probe_timeout"; stage = "bootstrap"; ancestry_policy_passed = $null } }
    if ($OutputOverflow) { return @{ status = "probe_output_overflow"; stage = "bootstrap"; ancestry_policy_passed = $null } }
    if ($ExitCode -ne 0) {
        $outcome = "output_invalid"
        if ([string]::IsNullOrWhiteSpace($Output)) {
            $outcome = "output_missing"
        } elseif ($parsed.status -in $probeStatuses -and $parsed.stage -is [string] -and $parsed.stage -in $probeStages) {
            $outcome = "output_valid"
        }
        return @{ status = "probe_nonzero_exit"; stage = $parsed.stage; output_outcome = $outcome; ancestry_policy_passed = $null }
    }
    return $parsed
}

function Format-SafeNonzeroProbeFailure($Result) {
    $outcomes = @("output_missing", "output_invalid", "output_valid")
    $stages = $probeStages
    $outcome = "output_invalid"
    if ($Result.output_outcome -in $outcomes) { $outcome = $Result.output_outcome }
    if ($Result.stage -is [string] -and $Result.stage -in $stages) {
        return ("Private staging root failed [probe-result/probe_nonzero_exit] output[{0}] stage[{1}]." -f $outcome, $Result.stage)
    }
    return ("Private staging root failed [probe-result/probe_nonzero_exit] output[{0}]." -f $outcome)
}

function New-SafeProbeBootstrap([string]$ProbeSource) {
    $encoded = [Convert]::ToBase64String([Text.Encoding]::UTF8.GetBytes($ProbeSource))
    $bootstrap = @'
import base64
import json
try:
    source = base64.b64decode("PROBE_SOURCE_BASE64", validate=True).decode("utf-8")
    code = compile(source, "<omniagent-private-root-probe>", "exec")
    exec(code, {"__name__": "__main__"})
except BaseException:
    print('{"status":"probe_bootstrap_error","stage":"bootstrap"}')
'@
    return $bootstrap.Replace("PROBE_SOURCE_BASE64", $encoded)
}

function Invoke-SafePythonProbe([string]$PythonPath, [string]$ProbeSource, [int]$TimeoutMilliseconds = 30000, [int]$MaximumOutputBytes = 4096) {
    if ($ProbeSource.Length -gt 65536) {
        return @{ ExitCode = 1; Output = '{"status":"probe_bootstrap_error","stage":"bootstrap"}'; TimedOut = $false }
    }
    try {
        if ($null -eq ("OmniAgent.PrivateProbeProcess" -as [type])) {
            Add-Type -TypeDefinition @'
using System;
using System.Diagnostics;
using System.IO;
using System.Text;
using System.Threading.Tasks;

namespace OmniAgent {
    public sealed class PrivateProbeResult {
        public int ExitCode;
        public string Output;
        public bool TimedOut;
        public bool Overflow;
    }

    internal sealed class CappedCaptureStream : Stream {
        private readonly MemoryStream captured = new MemoryStream();
        private readonly int maximum;
        public bool Dropped { get; private set; }
        public CappedCaptureStream(int maximumBytes) { maximum = maximumBytes; }
        public override bool CanRead { get { return false; } }
        public override bool CanSeek { get { return false; } }
        public override bool CanWrite { get { return true; } }
        public override long Length { get { return captured.Length; } }
        public override long Position { get { throw new NotSupportedException(); } set { throw new NotSupportedException(); } }
        public override void Flush() { }
        public override int Read(byte[] buffer, int offset, int count) { throw new NotSupportedException(); }
        public override long Seek(long offset, SeekOrigin origin) { throw new NotSupportedException(); }
        public override void SetLength(long value) { throw new NotSupportedException(); }
        public override void Write(byte[] buffer, int offset, int count) {
            int remaining = maximum - (int)captured.Length;
            if (remaining > 0) captured.Write(buffer, offset, Math.Min(remaining, count));
            if (count > remaining) Dropped = true;
        }
        public string GetCapturedText() { return Encoding.UTF8.GetString(captured.ToArray()); }
    }

    public static class PrivateProbeProcess {
        public static PrivateProbeResult Run(string executable, string source, int timeoutMilliseconds, int maximumOutputBytes) {
            Stopwatch deadline = Stopwatch.StartNew();
            using (Process process = new Process()) {
                process.StartInfo = new ProcessStartInfo {
                    FileName = executable,
                    Arguments = "-",
                    UseShellExecute = false,
                    CreateNoWindow = true,
                    RedirectStandardInput = true,
                    RedirectStandardOutput = true,
                    RedirectStandardError = true
                };
                if (!process.Start()) return new PrivateProbeResult { ExitCode = 1, Output = "", TimedOut = false };
                using (CappedCaptureStream stdout = new CappedCaptureStream(maximumOutputBytes)) {
                    Task stdoutDrain = process.StandardOutput.BaseStream.CopyToAsync(stdout);
                    Task stderrDrain = process.StandardError.BaseStream.CopyToAsync(Stream.Null);
                    Task stdinWrite = process.StandardInput.WriteAsync(source);
                    int remaining = timeoutMilliseconds - (int)deadline.ElapsedMilliseconds;
                    if (remaining <= 0 || !stdinWrite.Wait(Math.Max(0, remaining))) {
                        try { process.Kill(); } catch { }
                        if (process.WaitForExit(1000)) Task.WaitAll(new Task[] { stdoutDrain, stderrDrain }, 1000);
                        return new PrivateProbeResult { ExitCode = 1, Output = "", TimedOut = true };
                    }
                    stdinWrite.GetAwaiter().GetResult();
                    process.StandardInput.Close();
                    remaining = timeoutMilliseconds - (int)deadline.ElapsedMilliseconds;
                    if (remaining <= 0 || !process.WaitForExit(Math.Max(0, remaining))) {
                        try { process.Kill(); } catch { }
                        if (process.WaitForExit(1000)) Task.WaitAll(new Task[] { stdoutDrain, stderrDrain }, 1000);
                        return new PrivateProbeResult { ExitCode = 1, Output = "", TimedOut = true };
                    }
                    remaining = timeoutMilliseconds - (int)deadline.ElapsedMilliseconds;
                    if (remaining <= 0 || !Task.WaitAll(new Task[] { stdoutDrain, stderrDrain }, Math.Max(0, remaining)))
                        return new PrivateProbeResult { ExitCode = 1, Output = "", TimedOut = true };
                    if (stdout.Dropped) return new PrivateProbeResult { ExitCode = 1, Output = "", TimedOut = false, Overflow = true };
                    return new PrivateProbeResult {
                        ExitCode = process.ExitCode,
                        Output = stdout.GetCapturedText().TrimEnd('\r', '\n'),
                        TimedOut = false,
                        Overflow = false
                    };
                }
            }
        }
    }
}
'@ -ErrorAction Stop | Out-Null
        }
        $result = [OmniAgent.PrivateProbeProcess]::Run($PythonPath, $ProbeSource, $TimeoutMilliseconds, $MaximumOutputBytes)
        if ($result.TimedOut) { return @{ ExitCode = 1; Output = ""; TimedOut = $true; OutputOverflow = $false } }
        if ($result.Overflow) { return @{ ExitCode = 1; Output = ""; TimedOut = $false; OutputOverflow = $true } }
        return @{ ExitCode = $result.ExitCode; Output = $result.Output; TimedOut = $false; OutputOverflow = $false }
    } catch {
        return @{ ExitCode = 1; Output = '{"status":"probe_bootstrap_error","stage":"bootstrap"}'; TimedOut = $false; OutputOverflow = $false }
    }
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
    $nonzero = Resolve-SafeProbeResult 1 '{"status":"accepted","stage":"capability_check"}'
    $nonzeroMalformed = Resolve-SafeProbeResult 1 '{"status":"accepted","stage":"SENSITIVE_SENTINEL","raw":"SENSITIVE_SENTINEL"}'
    $nonzeroMissing = Resolve-SafeProbeResult 1 " `t "
    $nonzeroInvalid = Resolve-SafeProbeResult 1 '{"status":"accepted","stage":"root_open","raw":"SENSITIVE_SENTINEL"}'
    $nonzeroMessage = Format-SafeNonzeroProbeFailure $nonzero
    $testPython = Get-Command python.exe -ErrorAction SilentlyContinue
    $bootstrapValid = $false
    $bootstrapFailure = $false
    $bootstrapRedacted = $false
    $bootstrapNonzero = $false
    $bootstrapTimeout = $false
    $bootstrapStdoutBounded = $false
    $bootstrapStderrDiscarded = $false
    if ($null -ne $testPython) {
        $validSource = 'import json; print(json.dumps({"status":"accepted","stage":"capability_check"},separators=(",",":")))'
        $validBootstrapSource = New-SafeProbeBootstrap $validSource
        $validInvocation = Invoke-SafePythonProbe -PythonPath $testPython.Source -ProbeSource $validBootstrapSource
        $validResult = Resolve-SafeProbeResult $validInvocation.ExitCode $validInvocation.Output
        $invalidSource = 'if True print("SENSITIVE_SENTINEL")'
        $invalidBootstrapSource = New-SafeProbeBootstrap $invalidSource
        $invalidInvocation = Invoke-SafePythonProbe -PythonPath $testPython.Source -ProbeSource $invalidBootstrapSource
        $invalidResult = Resolve-SafeProbeResult $invalidInvocation.ExitCode $invalidInvocation.Output
        $nonzeroSource = 'import os; print("{" + chr(34) + "status" + chr(34) + ":" + chr(34) + "accepted" + chr(34) + "," + chr(34) + "stage" + chr(34) + ":" + chr(34) + "capability_check" + chr(34) + "}", flush=True); os._exit(7)'
        $nonzeroInvocation = Invoke-SafePythonProbe -PythonPath $testPython.Source -ProbeSource (New-SafeProbeBootstrap $nonzeroSource)
        $nonzeroResult = Resolve-SafeProbeResult $nonzeroInvocation.ExitCode $nonzeroInvocation.Output
        $timeoutSource = New-SafeProbeBootstrap 'import time; time.sleep(10)'
        $timeoutInvocation = Invoke-SafePythonProbe -PythonPath $testPython.Source -ProbeSource $timeoutSource -TimeoutMilliseconds 100
        $timeoutResult = Resolve-SafeProbeResult $timeoutInvocation.ExitCode $timeoutInvocation.Output $timeoutInvocation.TimedOut $timeoutInvocation.OutputOverflow
        $largeStdoutSource = New-SafeProbeBootstrap 'import os; os.write(1, b"x" * 100000)'
        $largeStdoutInvocation = Invoke-SafePythonProbe -PythonPath $testPython.Source -ProbeSource $largeStdoutSource -TimeoutMilliseconds 5000 -MaximumOutputBytes 256
        $overflowSource = New-SafeProbeBootstrap 'import os; print("{" + chr(34) + "status" + chr(34) + ":" + chr(34) + "accepted" + chr(34) + "," + chr(34) + "stage" + chr(34) + ":" + chr(34) + "capability_check" + chr(34) + "}", end=""); os.write(1, b" " * 5000)'
        $overflowInvocation = Invoke-SafePythonProbe -PythonPath $testPython.Source -ProbeSource $overflowSource -TimeoutMilliseconds 5000 -MaximumOutputBytes 256
        $overflowResult = Resolve-SafeProbeResult $overflowInvocation.ExitCode $overflowInvocation.Output $overflowInvocation.TimedOut $overflowInvocation.OutputOverflow
        $bootstrapStdoutBounded = ($largeStdoutInvocation.Output.Length -le 256 -and $largeStdoutInvocation.OutputOverflow)
        $largeStderrSource = New-SafeProbeBootstrap 'import os; os.write(2, b"SENSITIVE_SENTINEL" * 100000); print("{" + chr(34) + "status" + chr(34) + ":" + chr(34) + "accepted" + chr(34) + "," + chr(34) + "stage" + chr(34) + ":" + chr(34) + "capability_check" + chr(34) + "}", flush=True)'
        $largeStderrInvocation = Invoke-SafePythonProbe -PythonPath $testPython.Source -ProbeSource $largeStderrSource -TimeoutMilliseconds 5000
        $bootstrapStderrDiscarded = ($largeStderrInvocation.ExitCode -eq 0 -and $largeStderrInvocation.Output -ceq '{"status":"accepted","stage":"capability_check"}' -and $largeStderrInvocation.Output -notmatch "SENSITIVE_SENTINEL")
        $bootstrapValid = ($validInvocation.ExitCode -eq 0 -and $validInvocation.Output -ceq '{"status":"accepted","stage":"capability_check"}' -and $validResult.status -eq "accepted" -and $validResult.stage -eq "capability_check")
        $bootstrapFailure = ($invalidInvocation.ExitCode -eq 0 -and $invalidInvocation.Output -ceq '{"status":"probe_bootstrap_error","stage":"bootstrap"}' -and $invalidResult.status -eq "probe_bootstrap_error" -and $invalidResult.stage -eq "bootstrap")
        $bootstrapRedacted = ($invalidInvocation.Output -notmatch "SENSITIVE_SENTINEL")
        $bootstrapNonzero = ($nonzeroResult.status -eq "probe_nonzero_exit" -and $nonzeroResult.stage -eq "capability_check" -and $nonzeroResult.output_outcome -eq "output_valid" -and $null -eq $nonzeroResult.ancestry_policy_passed)
        $bootstrapTimeout = ($timeoutResult.status -eq "probe_timeout" -and $timeoutResult.stage -eq "bootstrap" -and $null -eq $timeoutResult.ancestry_policy_passed)
        $bootstrapOverflow = ($overflowResult.status -eq "probe_output_overflow" -and $overflowResult.stage -eq "bootstrap" -and $null -eq $overflowResult.ancestry_policy_passed -and $overflowInvocation.Output -eq "")
    }
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
        nonzero_exit_status_allowlisted = ($nonzero.status -eq "probe_nonzero_exit" -and $nonzero.stage -eq "capability_check" -and $null -eq $nonzero.ancestry_policy_passed)
        nonzero_output_valid_token = ($nonzero.output_outcome -eq "output_valid")
        nonzero_output_missing_token = ($nonzeroMissing.output_outcome -eq "output_missing" -and $null -eq $nonzeroMissing.stage)
        nonzero_output_invalid_token = ($nonzeroInvalid.output_outcome -eq "output_invalid" -and $null -eq $nonzeroInvalid.stage)
        malformed_nonzero_stage_cleared = ($nonzeroMalformed.status -eq "probe_nonzero_exit" -and $null -eq $nonzeroMalformed.stage -and $null -eq $nonzeroMalformed.ancestry_policy_passed)
        nonzero_output_redacted = (($nonzero | ConvertTo-Json -Compress) -notmatch "SENSITIVE_SENTINEL" -and ($nonzeroMalformed | ConvertTo-Json -Compress) -notmatch "SENSITIVE_SENTINEL" -and ($nonzeroInvalid | ConvertTo-Json -Compress) -notmatch "SENSITIVE_SENTINEL")
        nonzero_message_uses_fixed_tokens = ($nonzeroMessage -eq "Private staging root failed [probe-result/probe_nonzero_exit] output[output_valid] stage[capability_check]." -and $nonzeroMessage -notmatch "SENSITIVE_SENTINEL")
        python_bootstrap_valid_probe = $bootstrapValid
        python_bootstrap_syntax_failure_sanitized = $bootstrapFailure
        python_bootstrap_output_redacted = $bootstrapRedacted
        python_bootstrap_nonzero_exit_classified = $bootstrapNonzero
        python_bootstrap_timeout_bounded = $bootstrapTimeout
        python_bootstrap_stdout_bounded = $bootstrapStdoutBounded
        python_bootstrap_valid_json_overflow_rejected = $bootstrapOverflow
        python_bootstrap_stderr_discarded = $bootstrapStderrDiscarded
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
        $probe = New-SafeProbeBootstrap $probe
        $previousErrorActionPreference = $ErrorActionPreference
        try {
            $ErrorActionPreference = "Continue"
            $probeInvocation = Invoke-SafePythonProbe $python.Source $probe
            $probeOutput = $probeInvocation.Output
            $probeExitCode = $probeInvocation.ExitCode
        } catch {
            [Console]::Error.WriteLine("Private staging root failed [probe-launch/probe_launch_error].")
            exit 1
        } finally {
            $ErrorActionPreference = $previousErrorActionPreference
        }
        $phase = "probe-result"
        $probeText = $probeOutput
        $probeResult = Resolve-SafeProbeResult $probeExitCode $probeText $probeInvocation.TimedOut $probeInvocation.OutputOverflow
        if ($probeResult.status -ne "accepted" -or $probeExitCode -ne 0) {
            $category = $probeResult.status
            if ($category -eq "probe_nonzero_exit") {
                [Console]::Error.WriteLine((Format-SafeNonzeroProbeFailure $probeResult))
            } elseif ($category -eq "policy_rejected" -and $null -ne $probeResult.ancestry_policy_passed) {
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
