[CmdletBinding()]
param(
    [string]$RepositoryRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path,
    [string]$ExpectedCommit = $env:GITHUB_SHA,
    [string]$EvidencePath,
    [switch]$ProbeOnly,
    [string]$RunnerTempPath,
    [string]$RunRoot,
    [string]$ControlRoot,
    [string]$PeerOutputRoot,
    [string]$RunId,
    [ValidateSet("stage", "delete-child-control", "write-dac-control", "write-owner-control", "generic-all-control", "ancestor-rename")]
    [string]$ProbeMode = "stage",
    [string]$ProbeTarget,
    [string]$ProbePayloadPath,
    [string]$ExpectedSid,
    [string]$ProbeEvidencePath
)
$ErrorActionPreference = "Stop"

function Get-ControlledErrorCategory([System.Exception]$Exception) {
    if ($Exception -is [UnauthorizedAccessException]) { return "access_denied" }
    if ($Exception -is [Security.SecurityException]) { return "security_error" }
    if ($Exception -is [IO.IOException]) { return "io_error" }
    if ($Exception -is [ArgumentException]) { return "invalid_argument" }
    if ($Exception -is [InvalidOperationException]) { return "invalid_operation" }
    return "other_error"
}

function Get-SanitizedPathAclFact([string]$Role, [string]$Path) {
    $fact = [ordered]@{
        category = $Role
        exists = $false
        is_directory = $null
        is_reparse_point = $null
        acl_readable = $false
        inheritance_protected = $null
        error_category = $null
    }
    if (-not $Path) { return $fact }
    try {
        if (-not (Test-Path -LiteralPath $Path)) { return $fact }
        $item = Get-Item -LiteralPath $Path -Force -ErrorAction Stop
        $fact.exists = $true
        $fact.is_directory = [bool]$item.PSIsContainer
        $fact.is_reparse_point = [bool]($item.Attributes -band [IO.FileAttributes]::ReparsePoint)
        $acl = Get-Acl -LiteralPath $Path -ErrorAction Stop
        $fact.acl_readable = $true
        $fact.inheritance_protected = [bool]$acl.AreAccessRulesProtected
    } catch {
        $fact.error_category = Get-ControlledErrorCategory $_.Exception
    }
    return $fact
}

function Get-TokenEvidence {
    $identity = [Security.Principal.WindowsIdentity]::GetCurrent()
    $whoami = Join-Path $env:SYSTEMROOT "System32\whoami.exe"
    return @{
        user_sid = $identity.User.Value
        group_sids = @($identity.Groups | ForEach-Object { $_.Value })
        privileges = @(& $whoami /priv /fo csv /nh)
    }
}

function Assert-StandardToken([hashtable]$Token) {
    $forbiddenGroups = @(
        "S-1-5-32-544", "S-1-5-32-547", "S-1-5-32-548", "S-1-5-32-549",
        "S-1-5-32-550", "S-1-5-32-551", "S-1-5-32-552", "S-1-5-32-569"
    )
    if (@($Token.group_sids | Where-Object { $_ -in $forbiddenGroups }).Count -gt 0) {
        throw "A validation account has privileged group membership."
    }
    $sensitivePrivileges = @(
        "SeAssignPrimaryTokenPrivilege", "SeBackupPrivilege", "SeCreateTokenPrivilege",
        "SeDebugPrivilege", "SeImpersonatePrivilege", "SeLoadDriverPrivilege",
        "SeManageVolumePrivilege", "SeRestorePrivilege", "SeSecurityPrivilege",
        "SeTakeOwnershipPrivilege", "SeTcbPrivilege"
    )
    $rows = @($Token.privileges | ConvertFrom-Csv -Header @("Name", "Description", "State"))
    if ($rows.Count -eq 0 -or @($rows | Where-Object { -not $_.Name -or -not $_.State }).Count -gt 0) {
        throw "Token privileges could not be parsed."
    }
    foreach ($row in $rows) {
        if ($row.Name -in $sensitivePrivileges -and $row.State -notmatch "(?i)^disabled$") {
            throw "A validation account has an enabled or unknown sensitive privilege."
        }
    }
}

function Assert-Within {
    param([string]$Path, [string]$Root)
    $fullPath = [IO.Path]::GetFullPath($Path)
    $prefix = [IO.Path]::GetFullPath($Root).TrimEnd("\") + "\"
    if (-not $fullPath.StartsWith($prefix, [StringComparison]::OrdinalIgnoreCase)) {
        throw "Path is outside the allowed run directory."
    }
    return $fullPath
}

function Write-NewJson {
    param([string]$Path, [object]$Value)
    $stream = [IO.File]::Open($Path, [IO.FileMode]::CreateNew, [IO.FileAccess]::Write, [IO.FileShare]::None)
    try {
        $bytes = [Text.UTF8Encoding]::new($false).GetBytes((ConvertTo-Json -InputObject $Value -Depth 8))
        $stream.Write($bytes, 0, $bytes.Length)
        $stream.Flush()
    } finally { $stream.Dispose() }
}

function Get-PublisherOnlyDirectoryAcl {
    param([string]$Path, [string]$PublisherSid)
    $acl = Get-Acl -LiteralPath $Path
    $ownerSid = ([Security.Principal.NTAccount]::new($acl.Owner)).Translate([Security.Principal.SecurityIdentifier]).Value
    $allowedSids = @("S-1-5-18", "S-1-5-32-544", $PublisherSid)
    $actualSids = @(
        $acl.Access | ForEach-Object {
            try { $_.IdentityReference.Translate([Security.Principal.SecurityIdentifier]).Value }
            catch { throw "Destination ACL contains an unresolvable identity." }
        } | Sort-Object -Unique
    )
    if ($ownerSid -ne $PublisherSid -or
        $acl.AreAccessRulesProtected -ne $true -or
        @($acl.Access | Where-Object { $_.IsInherited -or $_.AccessControlType -ne "Allow" }).Count -gt 0 -or
        @($actualSids | Where-Object { $_ -notin $allowedSids }).Count -gt 0 -or
        $actualSids -notcontains $PublisherSid -or
        $actualSids -notcontains "S-1-5-18" -or
        $actualSids -notcontains "S-1-5-32-544") {
        throw "Destination parent DACL is not protected and publisher-only."
    }
    return @{
        sddl = $acl.Sddl
        allowed_sids = $actualSids
        inheritance_protected = $acl.AreAccessRulesProtected
    }
}

function Set-ExplicitAcl {
    param([string]$Path, [string[]]$AccessRules, [string]$OwnerSid)
    & icacls.exe $Path /inheritance:r /grant:r @AccessRules | Out-Null
    if ($LASTEXITCODE -ne 0) { throw "Could not apply an explicit validation ACL." }
    if ($OwnerSid) {
        & icacls.exe $Path /setowner ("*" + $OwnerSid) | Out-Null
        if ($LASTEXITCODE -ne 0) { throw "Could not set the validation directory owner." }
        $ownerName = (Get-Acl -LiteralPath $Path).Owner
        $actualOwner = ([Security.Principal.NTAccount]::new($ownerName)).Translate([Security.Principal.SecurityIdentifier]).Value
        if ($actualOwner -ne $OwnerSid) { throw "Validation directory owner did not match." }
    }
}

function Set-UnsafeParentAcl {
    param(
        [string]$Path,
        [string]$PublisherSid,
        [string]$PeerSid,
        [Security.AccessControl.FileSystemRights]$PeerRights
    )
    New-Item -ItemType Directory -Path $Path | Out-Null
    $acl = Get-Acl -LiteralPath $Path
    $acl.SetAccessRuleProtection($true, $false)
    $acl.SetOwner([Security.Principal.SecurityIdentifier]::new($PublisherSid))
    $inherit = [Security.AccessControl.InheritanceFlags]::ObjectInherit -bor [Security.AccessControl.InheritanceFlags]::ContainerInherit
    $publisherRule = [Security.AccessControl.FileSystemAccessRule]::new(
        [Security.Principal.SecurityIdentifier]::new($PublisherSid),
        [Security.AccessControl.FileSystemRights]::Modify,
        $inherit,
        [Security.AccessControl.PropagationFlags]::None,
        [Security.AccessControl.AccessControlType]::Allow
    )
    $systemRule = [Security.AccessControl.FileSystemAccessRule]::new(
        [Security.Principal.SecurityIdentifier]::new("S-1-5-18"),
        [Security.AccessControl.FileSystemRights]::FullControl,
        $inherit,
        [Security.AccessControl.PropagationFlags]::None,
        [Security.AccessControl.AccessControlType]::Allow
    )
    $adminsRule = [Security.AccessControl.FileSystemAccessRule]::new(
        [Security.Principal.SecurityIdentifier]::new("S-1-5-32-544"),
        [Security.AccessControl.FileSystemRights]::FullControl,
        $inherit,
        [Security.AccessControl.PropagationFlags]::None,
        [Security.AccessControl.AccessControlType]::Allow
    )
    $peerRule = [Security.AccessControl.FileSystemAccessRule]::new(
        [Security.Principal.SecurityIdentifier]::new($PeerSid),
        ([Security.AccessControl.FileSystemRights]::ReadAndExecute -bor $PeerRights),
        [Security.AccessControl.InheritanceFlags]::None,
        [Security.AccessControl.PropagationFlags]::None,
        [Security.AccessControl.AccessControlType]::Allow
    )
    $acl.AddAccessRule($systemRule)
    $acl.AddAccessRule($adminsRule)
    $acl.AddAccessRule($publisherRule)
    $acl.AddAccessRule($peerRule)
    Set-Acl -LiteralPath $Path -AclObject $acl
    $readback = Get-Acl -LiteralPath $Path
    if (-not $readback.AreAccessRulesProtected -or
        -not ($readback.Access | Where-Object {
            $_.IdentityReference.Translate([Security.Principal.SecurityIdentifier]).Value -eq $PeerSid -and
            $_.AccessControlType -eq [Security.AccessControl.AccessControlType]::Allow -and
            ($_.FileSystemRights -band $PeerRights) -eq $PeerRights
        })) {
        throw "Could not verify the intentionally unsafe peer rights."
    }
}

function Set-GenericAllParentAcl {
    param([string]$Path, [string]$PublisherSid, [string]$PeerSid)
    New-Item -ItemType Directory -Path $Path | Out-Null
    $acl = Get-Acl -LiteralPath $Path
    $sddl = "D:P(A;OICI;FA;;;S-1-5-18)(A;OICI;FA;;;S-1-5-32-544)(A;OICI;M;;;$PublisherSid)(A;;GA;;;$PeerSid)"
    $acl.SetSecurityDescriptorSddlForm($sddl, [Security.AccessControl.AccessControlSections]::Access)
    Set-Acl -LiteralPath $Path -AclObject $acl
    $readback = Get-Acl -LiteralPath $Path
    if (-not $readback.AreAccessRulesProtected -or $readback.Sddl -notmatch ("GA;;;" + [regex]::Escape($PeerSid) + "\)")) {
        throw "Could not verify a peer GENERIC_ALL ACE."
    }
}

function Invoke-PeerProbe {
    param([string]$Mode, [string]$Target, [string]$OutputPath, [string]$ExpectedPeerSid)
    $arguments = '-NoProfile -ExecutionPolicy Bypass -File "' + $PSCommandPath + '"' +
        ' -ProbeOnly -ProbeMode ' + $Mode + ' -RunnerTempPath "' + $runnerTemp + '"' +
        ' -RunRoot "' + $runRoot + '" -ControlRoot "' + $controlRoot + '"' +
        ' -PeerOutputRoot "' + $peerOutputRoot + '" -RunId "' + $runId + '"' +
        ' -ProbeTarget "' + $Target + '" -ExpectedSid "' + $ExpectedPeerSid + '"' +
        ' -ProbeEvidencePath "' + $OutputPath + '"'
    $process = Start-Process -FilePath (Join-Path $PSHOME "powershell.exe") `
        -Credential $peerCredential -ArgumentList $arguments -PassThru -Wait `
        -RedirectStandardOutput (Join-Path $runRoot ("peer-" + $Mode + ".stdout.txt")) `
        -RedirectStandardError (Join-Path $runRoot ("peer-" + $Mode + ".stderr.txt"))
    if ($process.ExitCode -ne 0) { throw "Peer $Mode negative control failed with exit code $($process.ExitCode)." }
}

function Add-PeerAncestorRenameRights {
    param([string]$Path, [string]$PeerSid)
    $acl = Get-Acl -LiteralPath $Path
    $rights = [Security.AccessControl.FileSystemRights]::ReadAndExecute -bor
        [Security.AccessControl.FileSystemRights]::DeleteSubdirectoriesAndFiles
    $rule = [Security.AccessControl.FileSystemAccessRule]::new(
        [Security.Principal.SecurityIdentifier]::new($PeerSid),
        $rights,
        [Security.AccessControl.InheritanceFlags]::None,
        [Security.AccessControl.PropagationFlags]::None,
        [Security.AccessControl.AccessControlType]::Allow
    )
    $acl.AddAccessRule($rule)
    Set-Acl -LiteralPath $Path -AclObject $acl
}

if ($ProbeOnly) {
    $runnerTemp = (Resolve-Path -LiteralPath $RunnerTempPath).Path
    $runRoot = Assert-Within -Path $RunRoot -Root $runnerTemp
    $marker = Join-Path $runRoot ".omniagent-acl-run"
    if (-not (Test-Path -LiteralPath $marker -PathType Leaf) -or (Get-Content -LiteralPath $marker -Raw) -cne $RunId) {
        throw "Probe run marker did not match."
    }
    $controlRoot = Assert-Within -Path $ControlRoot -Root $runRoot
    if ((Split-Path -Leaf $controlRoot) -ne "control") { throw "Probe control directory is invalid." }
    $peerOutputRoot = Assert-Within -Path $PeerOutputRoot -Root $runRoot
    if ((Split-Path -Leaf $peerOutputRoot) -ne "peer-output") { throw "Peer output directory is invalid." }
    $probeOutput = Assert-Within -Path $ProbeEvidencePath -Root $peerOutputRoot
    if (Test-Path -LiteralPath $probeOutput) { throw "Probe evidence already exists." }

    $token = Get-TokenEvidence
    if ($token.user_sid -ne $ExpectedSid) { exit 31 }
    Assert-StandardToken $token

    if ($ProbeMode -eq "delete-child-control") {
        $unsafeRoot = Assert-Within -Path (Join-Path $runRoot "unsafe-delete-child") -Root $runRoot
        $controlFile = Assert-Within -Path $ProbeTarget -Root $unsafeRoot
        if ((Split-Path -Parent $controlFile) -ne $unsafeRoot -or (Split-Path -Leaf $controlFile) -ne "control.txt") { throw "Negative-control file is invalid." }
        [IO.File]::Delete($controlFile)
        if (Test-Path -LiteralPath $controlFile) { throw "Peer could not delete the DELETE_CHILD control file." }
        Write-NewJson -Path $probeOutput -Value @{ peer_sid = $token.user_sid; peer_deleted_child = $true }
        exit 0
    }

    if ($ProbeMode -eq "write-dac-control") {
        $unsafeRoot = Assert-Within -Path (Join-Path $runRoot "unsafe-write-dac") -Root $runRoot
        $controlFile = Assert-Within -Path $ProbeTarget -Root $unsafeRoot
        if ((Split-Path -Parent $controlFile) -ne $unsafeRoot -or (Split-Path -Leaf $controlFile) -ne "control.txt") { throw "WRITE_DAC control target is invalid." }
        $acl = Get-Acl -LiteralPath $unsafeRoot
        $peerSid = [Security.Principal.SecurityIdentifier]::new($token.user_sid)
        $rule = [Security.AccessControl.FileSystemAccessRule]::new(
            $peerSid,
            [Security.AccessControl.FileSystemRights]::FullControl,
            [Security.AccessControl.InheritanceFlags]::None,
            [Security.AccessControl.PropagationFlags]::None,
            [Security.AccessControl.AccessControlType]::Allow
        )
        $acl.AddAccessRule($rule)
        Set-Acl -LiteralPath $unsafeRoot -AclObject $acl
        $actual = Get-Acl -LiteralPath $unsafeRoot
        $canChangeDacl = @($actual.Access | Where-Object {
            $_.IdentityReference.Translate([Security.Principal.SecurityIdentifier]).Value -eq $token.user_sid -and
            $_.AccessControlType -eq [Security.AccessControl.AccessControlType]::Allow -and
            ($_.FileSystemRights -band [Security.AccessControl.FileSystemRights]::ChangePermissions)
        }).Count -gt 0
        if (-not $canChangeDacl) { throw "Peer WRITE_DAC negative control did not take effect." }
        Write-NewJson -Path $probeOutput -Value @{ peer_sid = $token.user_sid; peer_changed_dacl = $true }
        exit 0
    }

    if ($ProbeMode -eq "write-owner-control") {
        $unsafeRoot = Assert-Within -Path (Join-Path $runRoot "unsafe-write-owner") -Root $runRoot
        $controlFile = Assert-Within -Path $ProbeTarget -Root $unsafeRoot
        if ((Split-Path -Parent $controlFile) -ne $unsafeRoot -or (Split-Path -Leaf $controlFile) -ne "control.txt") { throw "WRITE_OWNER control target is invalid." }
        $acl = Get-Acl -LiteralPath $unsafeRoot
        $acl.SetOwner([Security.Principal.SecurityIdentifier]::new($token.user_sid))
        Set-Acl -LiteralPath $unsafeRoot -AclObject $acl
        $actualOwner = (Get-Acl -LiteralPath $unsafeRoot).Owner
        $actualOwnerSid = ([Security.Principal.NTAccount]::new($actualOwner)).Translate([Security.Principal.SecurityIdentifier]).Value
        if ($actualOwnerSid -ne $token.user_sid) { throw "Peer WRITE_OWNER negative control did not take effect." }
        Write-NewJson -Path $probeOutput -Value @{ peer_sid = $token.user_sid; owner_sid = $actualOwnerSid; peer_changed_owner = $true }
        exit 0
    }

    if ($ProbeMode -eq "generic-all-control") {
        $unsafeRoot = Assert-Within -Path (Join-Path $runRoot "unsafe-generic-all") -Root $runRoot
        $controlFile = Assert-Within -Path $ProbeTarget -Root $unsafeRoot
        if ((Split-Path -Parent $controlFile) -ne $unsafeRoot -or (Split-Path -Leaf $controlFile) -ne "control.txt") { throw "GENERIC_ALL control target is invalid." }
        $readback = Get-Acl -LiteralPath $unsafeRoot
        if ($readback.Sddl -notmatch ("GA;;;" + [regex]::Escape($token.user_sid) + "\)")) { throw "GENERIC_ALL ACE was not present for peer." }
        $file = [IO.File]::Open($controlFile, [IO.FileMode]::OpenOrCreate, [IO.FileAccess]::Write, [IO.FileShare]::None)
        try { $file.WriteByte(0x47); $file.Flush() } finally { $file.Dispose() }
        [IO.File]::Delete($controlFile)
        Write-NewJson -Path $probeOutput -Value @{ peer_sid = $token.user_sid; generic_all_ace_verified = $true; peer_created_file = $true }
        exit 0
    }

    if ($ProbeMode -eq "ancestor-rename") {
        $ancestor = Assert-Within -Path $ProbeTarget -Root (Join-Path $runRoot "private-data")
        if ((Split-Path -Leaf $ancestor) -ne "destination") { throw "Ancestor rename target is invalid." }
        $renameTarget = $ancestor + ".peer-renamed"
        try {
            [IO.Directory]::Move($ancestor, $renameTarget)
            [IO.Directory]::Move($renameTarget, $ancestor)
            Write-NewJson -Path $probeOutput -Value @{ peer_sid = $token.user_sid; ancestor_rename_denied = $false }
            exit 32
        } catch [UnauthorizedAccessException] {
            Write-NewJson -Path $probeOutput -Value @{ peer_sid = $token.user_sid; ancestor_rename_denied = $true; denial = "access-denied" }
            exit 0
        } catch [IO.IOException] {
            $win32 = $_.Exception.HResult -band 0xffff
            if ($win32 -notin @(5, 32)) { throw }
            Write-NewJson -Path $probeOutput -Value @{ peer_sid = $token.user_sid; ancestor_rename_denied = $true; denial = "sharing-or-access-denied" }
            exit 0
        }
    }

    $stagePath = Assert-Within -Path $ProbeTarget -Root (Join-Path $runRoot "private-data\destination")
    if ((Split-Path -Leaf $stagePath) -notlike ".omniagent-publish-*") { throw "Probe target is not a stage directory." }
    $payloadPath = Assert-Within -Path $ProbePayloadPath -Root $stagePath
    if ((Split-Path -Parent $payloadPath) -ne $stagePath -or (Split-Path -Leaf $payloadPath) -ne "dataset.jsonl") {
        throw "Probe payload is outside the expected staged dataset."
    }
    $destinationParent = Join-Path $runRoot "private-data\destination"
    $destinationListingDenied = $false
    try { [void][IO.Directory]::GetFileSystemEntries($destinationParent) }
    catch [UnauthorizedAccessException] { $destinationListingDenied = $true }
    $destinationCanary = Join-Path $destinationParent ("UNAUTHORIZED_PARENT_PROBE_" + [Guid]::NewGuid().ToString("N"))
    $destinationCanaryCreated = $false
    $destinationWriteDenied = $false
    $destinationCanaryCleanupError = $null
    try {
        $file = [IO.File]::Open($destinationCanary, [IO.FileMode]::CreateNew, [IO.FileAccess]::Write, [IO.FileShare]::None)
        $destinationCanaryCreated = $true
        $file.Dispose()
    } catch [UnauthorizedAccessException] { $destinationWriteDenied = $true }
    catch [IO.IOException] { if (($_.Exception.HResult -band 0xffff) -eq 5) { $destinationWriteDenied = $true } else { throw } }
    if ($destinationCanaryCreated) {
        try {
            Remove-Item -LiteralPath $destinationCanary -Force -ErrorAction Stop
            if (Test-Path -LiteralPath $destinationCanary) { throw "destination canary remains" }
        } catch { $destinationCanaryCleanupError = $_.Exception.GetType().Name }
    }
    $listDenied = $false
    try { [void][IO.Directory]::GetFileSystemEntries($stagePath) }
    catch [UnauthorizedAccessException] { $listDenied = $true }
    $readDenied = $false
    try { [void][IO.File]::ReadAllBytes($payloadPath) }
    catch [UnauthorizedAccessException] { $readDenied = $true }
    catch [IO.IOException] { if (($_.Exception.HResult -band 0xffff) -eq 5) { $readDenied = $true } else { throw } }
    $canary = Join-Path $stagePath ("UNAUTHORIZED_PROBE_" + [Guid]::NewGuid().ToString("N"))
    $canaryCreated = $false
    $writeDenied = $false
    $canaryCleanupError = $null
    try {
        $file = [IO.File]::Open($canary, [IO.FileMode]::CreateNew, [IO.FileAccess]::Write, [IO.FileShare]::None)
        $canaryCreated = $true
        $file.Dispose()
    } catch [UnauthorizedAccessException] { $writeDenied = $true }
    catch [IO.IOException] { if (($_.Exception.HResult -band 0xffff) -eq 5) { $writeDenied = $true } else { throw } }
    if ($canaryCreated) {
        try {
            Remove-Item -LiteralPath $canary -Force -ErrorAction Stop
            if (Test-Path -LiteralPath $canary) { throw "probe canary remains" }
        } catch { $canaryCleanupError = $_.Exception.GetType().Name }
    }
    $renameDenied = $false
    $renameTarget = $stagePath + ".peer-renamed"
    try {
        [IO.Directory]::Move($stagePath, $renameTarget)
    } catch [UnauthorizedAccessException] {
        $renameDenied = $true
    } catch [IO.IOException] {
        if (($_.Exception.HResult -band 0xffff) -eq 5) { $renameDenied = $true } else { throw }
    }
    if (-not $renameDenied -and (Test-Path -LiteralPath $renameTarget)) {
        Write-NewJson -Path $probeOutput -Value @{ peer_sid = $token.user_sid; stage_rename_denied = $false; stage_delete_denied = $false }
        exit 32
    }
    $deleteDenied = $false
    try {
        [IO.Directory]::Delete($stagePath, $true)
    } catch [UnauthorizedAccessException] {
        $deleteDenied = $true
    } catch [IO.IOException] {
        if (($_.Exception.HResult -band 0xffff) -eq 5) { $deleteDenied = $true } else { throw }
    }
    Write-NewJson -Path $probeOutput -Value @{
        peer_sid = $token.user_sid
        peer_group_sids = $token.group_sids
        peer_privileges = $token.privileges
        destination_listing_denied = $destinationListingDenied
        destination_create_denied = $destinationWriteDenied
        destination_canary_was_created = $destinationCanaryCreated
        destination_canary_cleanup_error = $destinationCanaryCleanupError
        stage_listing_denied = $listDenied
        payload_read_denied = $readDenied
        stage_create_denied = $writeDenied
        stage_rename_denied = $renameDenied
        stage_delete_denied = $deleteDenied
        stage_probe_boundary = "Denial was observed at the staged path; publisher-only ancestors may enforce it, and the stage DACL was not independently verified."
        canary_was_created = $canaryCreated
        canary_cleanup_error = $canaryCleanupError
    }
    if (-not $destinationListingDenied -or -not $destinationWriteDenied -or $destinationCanaryCreated -or $destinationCanaryCleanupError -or
        -not $listDenied -or -not $readDenied -or -not $writeDenied -or $canaryCreated -or $canaryCleanupError -or
        -not $renameDenied -or -not $deleteDenied) { exit 32 }
    exit 0
}

if ($env:GITHUB_ACTIONS -ne "true" -or $env:GITHUB_REPOSITORY -ne "OmniBase-Official/OmniAgent") {
    throw "Privileged validation is restricted to this repository on an ephemeral GitHub runner."
}
$sameRepositoryPullRequest = $false
if ($env:GITHUB_EVENT_NAME -eq "pull_request") {
    if (-not $env:GITHUB_EVENT_PATH -or -not (Test-Path -LiteralPath $env:GITHUB_EVENT_PATH)) {
        throw "Pull request event metadata is unavailable."
    }
    $event = Get-Content -LiteralPath $env:GITHUB_EVENT_PATH -Raw | ConvertFrom-Json
    $sameRepositoryPullRequest =
        $event.pull_request.base.ref -eq "main" -and
        $event.pull_request.head.repo.full_name -eq $env:GITHUB_REPOSITORY
    if (-not $sameRepositoryPullRequest) { throw "Only same-repository pull requests targeting main may run this harness." }
} elseif ($env:GITHUB_EVENT_NAME -eq "workflow_dispatch") {
    if ($env:GITHUB_REF -notin @("refs/heads/codex/scale-security-hardening-20261113", "refs/heads/codex/security-scans-validation-20261120")) {
        throw "Manual validation is restricted to the trusted feature ref."
    }
} else {
    throw "Unsupported event for privileged publisher validation."
}
if (-not $ExpectedCommit -or $ExpectedCommit -ne $env:GITHUB_SHA) { throw "Commit must match GITHUB_SHA." }
$admin = [Security.Principal.WindowsPrincipal]::new([Security.Principal.WindowsIdentity]::GetCurrent())
if (-not $admin.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)) {
    throw "The ephemeral runner must be elevated to create temporary standard users."
}
if (-not (Get-Command New-LocalUser -ErrorAction SilentlyContinue)) { throw "LocalAccounts module is unavailable." }

$repository = (Resolve-Path -LiteralPath $RepositoryRoot).Path
$runnerTemp = (Resolve-Path -LiteralPath $env:RUNNER_TEMP).Path
$tempPrefix = $runnerTemp.TrimEnd("\") + "\"
$head = (& git.exe -C $repository rev-parse HEAD).Trim()
if ($LASTEXITCODE -ne 0 -or $head -ne $ExpectedCommit) { throw "Checked-out HEAD does not match GITHUB_SHA." }
$tree = (& git.exe -C $repository rev-parse "HEAD^{tree}").Trim()
if ($LASTEXITCODE -ne 0) { throw "Could not read the checked-out tree hash." }
if (-not $EvidencePath) { $EvidencePath = Join-Path $runnerTemp ("publisher-acl-" + $env:GITHUB_RUN_ID + ".json") }
$evidenceFull = Assert-Within -Path $EvidencePath -Root $runnerTemp
$evidenceStream = [IO.File]::Open($evidenceFull, [IO.FileMode]::CreateNew, [IO.FileAccess]::Write, [IO.FileShare]::None)

$runId = [Guid]::NewGuid().ToString("N")
$runRoot = Join-Path $runnerTemp ("omniagent-acl-" + $runId)
$marker = Join-Path $runRoot ".omniagent-acl-run"
$controlRoot = Join-Path $runRoot "control"
$publisherStatus = Join-Path $runRoot "publisher-status"
$peerOutputRoot = Join-Path $runRoot "peer-output"
$readyPath = Join-Path $publisherStatus "stage-ready.json"
$releasePath = Join-Path $controlRoot "release-publisher"
$publisherEvidencePath = Join-Path $publisherStatus "publisher-token.json"
$peerEvidencePath = Join-Path $peerOutputRoot "peer-token.json"
$unsafeDeleteChildParent = Join-Path $runRoot "unsafe-delete-child"
$unsafeDeleteChildControlPath = Join-Path $unsafeDeleteChildParent "control.txt"
$unsafeDeleteChildResultPath = Join-Path $peerOutputRoot "delete-child-control.json"
$unsafeWriteDacParent = Join-Path $runRoot "unsafe-write-dac"
$unsafeWriteDacControlPath = Join-Path $unsafeWriteDacParent "control.txt"
$unsafeWriteDacResultPath = Join-Path $peerOutputRoot "write-dac-control.json"
$unsafeWriteOwnerParent = Join-Path $runRoot "unsafe-write-owner"
$unsafeWriteOwnerControlPath = Join-Path $unsafeWriteOwnerParent "control.txt"
$unsafeWriteOwnerResultPath = Join-Path $peerOutputRoot "write-owner-control.json"
$unsafeGenericAllParent = Join-Path $runRoot "unsafe-generic-all"
$unsafeGenericAllControlPath = Join-Path $unsafeGenericAllParent "control.txt"
$unsafeGenericAllResultPath = Join-Path $peerOutputRoot "generic-all-control.json"
$unsafeAncestorRoot = Join-Path $runRoot "unsafe-ancestor"
$unsafeAncestorDestinationParent = Join-Path $unsafeAncestorRoot "destination"
$resultPath = Join-Path $publisherStatus "test-results.json"
$privateData = Join-Path $runRoot "private-data"
$destinationParent = Join-Path $privateData "destination"
$destinationAclEvidence = $null
$publisherName = "oapub" + $runId.Substring(0, 8)
$peerName = "oapeer" + $runId.Substring(8, 8)
$usersToClean = @()
$cleanupErrors = @()
$publisherProcess = $null
$publisherEvidence = $null
$peerEvidence = $null
$testResults = @{}
$probeExitCode = $null
$failureClass = $null
$failurePhase = "preflight"
$identitySubphase = "not-started"
$localAppData = $null

function New-RandomCredential([string]$Name) {
    $random = New-Object byte[] 32
    $generator = [Security.Cryptography.RandomNumberGenerator]::Create()
    try {
        $generator.GetBytes($random)
        $text = "Aa1!" + [Convert]::ToBase64String($random)
        $secure = ConvertTo-SecureString $text -AsPlainText -Force
        $text = $null
        return [PSCredential]::new("$env:COMPUTERNAME\$Name", $secure)
    } finally {
        $generator.Dispose()
        [Array]::Clear($random, 0, $random.Length)
    }
}

try {
    $localAppData = [Environment]::GetFolderPath([Environment+SpecialFolder]::LocalApplicationData)
    $failurePhase = "directory-setup"
    New-Item -ItemType Directory -Path $runRoot | Out-Null
    [IO.File]::WriteAllText($marker, $runId, [Text.Encoding]::ASCII)
    New-Item -ItemType Directory -Path $controlRoot | Out-Null
    New-Item -ItemType Directory -Path $publisherStatus | Out-Null
    New-Item -ItemType Directory -Path $peerOutputRoot | Out-Null
    New-Item -ItemType Directory -Path $privateData | Out-Null
    New-Item -ItemType Directory -Path $destinationParent | Out-Null
    $failurePhase = "identity-setup"
    $identitySubphase = "publisher-credential"
    $publisherCredential = New-RandomCredential $publisherName
    $identitySubphase = "peer-credential"
    $peerCredential = New-RandomCredential $peerName
    $ownerDescription = "OmniAgent ACL validation run " + $runId
    $identitySubphase = "account-collision-check"
    if ((Get-LocalUser -Name $publisherName -ErrorAction SilentlyContinue) -or
        (Get-LocalUser -Name $peerName -ErrorAction SilentlyContinue)) {
        throw "A generated temporary username already exists."
    }
    $usersToClean += [pscustomobject]@{ Name = $publisherName; Marker = $ownerDescription; Sid = $null }
    $identitySubphase = "publisher-account-create"
    New-LocalUser -Name $publisherName -Password $publisherCredential.Password -Description $ownerDescription -AccountNeverExpires -PasswordNeverExpires -UserMayNotChangePassword | Out-Null
    $identitySubphase = "publisher-account-readback"
    $publisherAccount = Get-LocalUser -Name $publisherName
    if ($publisherAccount.Description -ne $ownerDescription) { throw "Publisher ownership marker mismatch." }
    $identitySubphase = "publisher-sid-capture"
    $usersToClean[0].Sid = $publisherAccount.SID.Value

    $usersToClean += [pscustomobject]@{ Name = $peerName; Marker = $ownerDescription; Sid = $null }
    $identitySubphase = "peer-account-create"
    New-LocalUser -Name $peerName -Password $peerCredential.Password -Description $ownerDescription -AccountNeverExpires -PasswordNeverExpires -UserMayNotChangePassword | Out-Null
    $identitySubphase = "peer-account-readback"
    $peerAccount = Get-LocalUser -Name $peerName
    if ($peerAccount.Description -ne $ownerDescription) { throw "Peer ownership marker mismatch." }
    $identitySubphase = "peer-sid-capture"
    $usersToClean[1].Sid = $peerAccount.SID.Value
    $publisherSid = $publisherAccount.SID.Value
    $peerSid = $peerAccount.SID.Value
    $identitySubphase = "sid-distinctness-check"
    if ($publisherSid -eq $peerSid) { throw "Temporary users did not receive distinct SIDs." }
    $identitySubphase = "admin-membership-check"
    $adminSids = @(Get-LocalGroupMember -Group "Administrators" | ForEach-Object { $_.SID.Value })
    if ($adminSids -contains $publisherSid -or $adminSids -contains $peerSid) { throw "Temporary accounts must be standard users." }
    $identitySubphase = "complete"

    $failurePhase = "acl-setup"
    $systemFull = "*S-1-5-18:(OI)(CI)F"
    $adminsFull = "*S-1-5-32-544:(OI)(CI)F"
    $publisherRead = "*{0}:(OI)(CI)RX" -f $publisherSid
    $peerRead = "*{0}:(RX)" -f $peerSid
    $publisherModify = "*{0}:(OI)(CI)M" -f $publisherSid
    $peerModify = "*{0}:(OI)(CI)M" -f $peerSid
    $peerMarkerRead = "*{0}:R" -f $peerSid
    $publisherMarkerRead = "*{0}:R" -f $publisherSid
    Set-ExplicitAcl -Path $runRoot -AccessRules @($systemFull, $adminsFull, $publisherRead, $peerRead)
    Set-ExplicitAcl -Path $privateData -AccessRules @($systemFull, $adminsFull, $publisherModify)
    Set-ExplicitAcl -Path $controlRoot -AccessRules @($systemFull, $adminsFull, $publisherRead)
    Set-ExplicitAcl -Path $publisherStatus -AccessRules @($systemFull, $adminsFull, $publisherModify)
    Set-ExplicitAcl -Path $peerOutputRoot -AccessRules @($systemFull, $adminsFull, $peerModify, $publisherRead)
    $destinationPublisherAce = "*{0}:(OI)(CI)M" -f $publisherSid
    Set-ExplicitAcl -Path $destinationParent -AccessRules @($systemFull, $adminsFull, $destinationPublisherAce) -OwnerSid $publisherSid
    Set-ExplicitAcl -Path $marker -AccessRules @("*S-1-5-18:F", "*S-1-5-32-544:F", $peerMarkerRead, $publisherMarkerRead)
    $destinationAclEvidence = Get-PublisherOnlyDirectoryAcl -Path $destinationParent -PublisherSid $publisherSid

    $failurePhase = "negative-controls"
    Set-UnsafeParentAcl -Path $unsafeDeleteChildParent -PublisherSid $publisherSid -PeerSid $peerSid -PeerRights ([Security.AccessControl.FileSystemRights]::DeleteSubdirectoriesAndFiles)
    Set-Content -LiteralPath $unsafeDeleteChildControlPath -Value "negative-control" -Encoding ascii
    Set-UnsafeParentAcl -Path $unsafeWriteDacParent -PublisherSid $publisherSid -PeerSid $peerSid -PeerRights ([Security.AccessControl.FileSystemRights]::ChangePermissions)
    Set-Content -LiteralPath $unsafeWriteDacControlPath -Value "negative-control" -Encoding ascii
    Set-UnsafeParentAcl -Path $unsafeWriteOwnerParent -PublisherSid $publisherSid -PeerSid $peerSid -PeerRights ([Security.AccessControl.FileSystemRights]::TakeOwnership)
    Set-Content -LiteralPath $unsafeWriteOwnerControlPath -Value "negative-control" -Encoding ascii
    Set-GenericAllParentAcl -Path $unsafeGenericAllParent -PublisherSid $publisherSid -PeerSid $peerSid
    Set-Content -LiteralPath $unsafeGenericAllControlPath -Value "negative-control" -Encoding ascii
    Set-UnsafeParentAcl -Path $unsafeAncestorRoot -PublisherSid $publisherSid -PeerSid $peerSid -PeerRights ([Security.AccessControl.FileSystemRights]::DeleteSubdirectoriesAndFiles)
    New-Item -ItemType Directory -Path $unsafeAncestorDestinationParent | Out-Null
    Set-ExplicitAcl -Path $unsafeAncestorDestinationParent -AccessRules @($systemFull, $adminsFull, $destinationPublisherAce) -OwnerSid $publisherSid
    Invoke-PeerProbe -Mode "delete-child-control" -Target $unsafeDeleteChildControlPath -OutputPath $unsafeDeleteChildResultPath -ExpectedPeerSid $peerSid
    Invoke-PeerProbe -Mode "write-dac-control" -Target $unsafeWriteDacControlPath -OutputPath $unsafeWriteDacResultPath -ExpectedPeerSid $peerSid
    Invoke-PeerProbe -Mode "write-owner-control" -Target $unsafeWriteOwnerControlPath -OutputPath $unsafeWriteOwnerResultPath -ExpectedPeerSid $peerSid
    Invoke-PeerProbe -Mode "generic-all-control" -Target $unsafeGenericAllControlPath -OutputPath $unsafeGenericAllResultPath -ExpectedPeerSid $peerSid

    $failurePhase = "publisher-setup"
    $configPath = Join-Path $controlRoot "test-config.json"
    $config = [ordered]@{
        publisher_sid = $publisherSid
        peer_sid = $peerSid
        destination_parent = $destinationParent
        unsafe_ancestor_root = $unsafeAncestorRoot
        unsafe_ancestor_destination_parent = $unsafeAncestorDestinationParent
        unsafe_delete_child_parent = $unsafeDeleteChildParent
        unsafe_delete_child_control_path = $unsafeDeleteChildControlPath
        unsafe_delete_child_result_path = $unsafeDeleteChildResultPath
        unsafe_write_dac_parent = $unsafeWriteDacParent
        unsafe_write_dac_result_path = $unsafeWriteDacResultPath
        unsafe_write_owner_parent = $unsafeWriteOwnerParent
        unsafe_write_owner_control_path = $unsafeWriteOwnerControlPath
        unsafe_write_owner_result_path = $unsafeWriteOwnerResultPath
        unsafe_generic_all_parent = $unsafeGenericAllParent
        unsafe_generic_all_control_path = $unsafeGenericAllControlPath
        unsafe_generic_all_result_path = $unsafeGenericAllResultPath
        ready_path = $readyPath
        release_path = $releasePath
        publisher_evidence_path = $publisherEvidencePath
        result_path = $resultPath
        probe_timeout_seconds = 90
    } | ConvertTo-Json -Depth 4
    [IO.File]::WriteAllText($configPath, $config, [Text.UTF8Encoding]::new($false))

    $python = (Get-Command python.exe -ErrorAction Stop).Source
    $commandFile = Join-Path $runRoot "run-publisher-tests.cmd"
    $pytestTemp = Join-Path $privateData "pytest-temp"
    $batch = [string[]]@(
        "@echo off"
        ('set "OMNIAGENT_WINDOWS_ACL_CONFIG=' + $configPath + '"')
        'set "PYTHONDONTWRITEBYTECODE=1"'
        ('cd /d "' + $repository + '"')
        ('"' + $python + '" -m pytest -q tests/test_windows_publish_acl.py -p no:cacheprovider --basetemp="' + $pytestTemp + '"')
        'exit /b %ERRORLEVEL%'
    )
    Set-Content -LiteralPath $commandFile -Value $batch -Encoding ascii
    $publisherProcess = Start-Process -FilePath $env:ComSpec -Credential $publisherCredential -WorkingDirectory $repository -ArgumentList ('/d /c "' + $commandFile + '"') -PassThru -RedirectStandardOutput (Join-Path $runRoot "publisher.stdout.txt") -RedirectStandardError (Join-Path $runRoot "publisher.stderr.txt")

    $failurePhase = "publisher-wait"
    $deadline = [DateTime]::UtcNow.AddMinutes(4)
    while (-not $publisherProcess.HasExited -and [DateTime]::UtcNow -lt $deadline) {
        $publisherProcess.Refresh()
        if (Test-Path -LiteralPath $readyPath -PathType Leaf) {
            $failurePhase = "peer-probe"
            $ready = Get-Content -LiteralPath $readyPath -Raw | ConvertFrom-Json
            $stagePath = Assert-Within -Path ([string]$ready.stage_path) -Root $destinationParent
            if ((Split-Path -Leaf $stagePath) -notlike ".omniagent-publish-*") { throw "Unexpected staging path." }
            $payloadPath = Assert-Within -Path ([string]$ready.payload_path) -Root $stagePath
            if ((Split-Path -Parent $payloadPath) -ne $stagePath -or (Split-Path -Leaf $payloadPath) -ne "dataset.jsonl") { throw "Unexpected staged payload path." }
            if (-not (Test-Path -LiteralPath $payloadPath -PathType Leaf)) { throw "Staged payload is missing." }
            Add-PeerAncestorRenameRights -Path $privateData -PeerSid $peerSid
            $ancestorRenameResultPath = Join-Path $peerOutputRoot "ancestor-rename-control.json"
            Invoke-PeerProbe -Mode "ancestor-rename" -Target $destinationParent -OutputPath $ancestorRenameResultPath -ExpectedPeerSid $peerSid
            $ancestorRenameEvidence = Get-Content -LiteralPath $ancestorRenameResultPath -Raw | ConvertFrom-Json
            if (-not $ancestorRenameEvidence.ancestor_rename_denied) { throw "Peer renamed an ancestor while publication was in progress." }
            $probeArgs = '-NoProfile -ExecutionPolicy Bypass -File "' + $PSCommandPath + '" -ProbeOnly -ProbeMode stage -RunnerTempPath "' + $runnerTemp + '" -RunRoot "' + $runRoot + '" -ControlRoot "' + $controlRoot + '" -PeerOutputRoot "' + $peerOutputRoot + '" -RunId "' + $runId + '" -ProbeTarget "' + $stagePath + '" -ProbePayloadPath "' + $payloadPath + '" -ExpectedSid "' + $peerSid + '" -ProbeEvidencePath "' + $peerEvidencePath + '"'
            $probe = Start-Process -FilePath (Join-Path $PSHOME "powershell.exe") -Credential $peerCredential -ArgumentList $probeArgs -PassThru -RedirectStandardOutput (Join-Path $runRoot "peer.stdout.txt") -RedirectStandardError (Join-Path $runRoot "peer.stderr.txt")
            if (-not $probe.WaitForExit(30000)) { & taskkill.exe /PID $probe.Id /T /F | Out-Null; throw "Peer access probe timed out." }
            $probeExitCode = $probe.ExitCode
            Set-Content -LiteralPath $releasePath -Value "peer-probe-complete" -Encoding ascii
            Remove-Item -LiteralPath $readyPath -Force
            if ($probeExitCode -ne 0) { throw "Peer token did not fail all private-stage probes." }
            $failurePhase = "publisher-wait"
        }
        Start-Sleep -Milliseconds 200
    }
    if (-not $publisherProcess.HasExited) {
        Set-Content -LiteralPath $releasePath -Value "timeout-release" -Encoding ascii
        & taskkill.exe /PID $publisherProcess.Id /T /F | Out-Null
        throw "Publisher test timed out."
    }
    $failurePhase = "result-validation"
    $publisherProcess.Refresh()
    if ($publisherProcess.ExitCode -ne 0) { throw "Publisher pytest failed." }
    $publisherEvidence = Get-Content -LiteralPath $publisherEvidencePath -Raw | ConvertFrom-Json
    $peerEvidence = Get-Content -LiteralPath $peerEvidencePath -Raw | ConvertFrom-Json
    $testResults = Get-Content -LiteralPath $resultPath -Raw | ConvertFrom-Json
    if ($publisherEvidence.user_sid -ne $publisherSid -or $peerEvidence.peer_sid -ne $peerSid) { throw "Process SID evidence did not match." }
    if (-not $peerEvidence.destination_listing_denied -or -not $peerEvidence.destination_create_denied -or
        $peerEvidence.destination_canary_was_created -or $peerEvidence.destination_canary_cleanup_error -or
        -not $peerEvidence.stage_listing_denied -or -not $peerEvidence.payload_read_denied -or -not $peerEvidence.stage_create_denied -or
        -not $peerEvidence.stage_rename_denied -or -not $peerEvidence.stage_delete_denied) { throw "Peer could access publisher-only data or mutate private staging." }
    if (-not $testResults.safe_profile -or -not $testResults.publish_success -or -not $testResults.promotion_failure) { throw "A safe-profile publisher scenario did not report success." }
    $failurePhase = "complete"
} catch {
    $failureClass = Get-ControlledErrorCategory $_.Exception
    throw ("Publisher validation failed [{0}]." -f $failureClass)
} finally {
    if ($publisherProcess -and -not $publisherProcess.HasExited) {
        Set-Content -LiteralPath $releasePath -Value "cleanup-release" -Encoding ascii -ErrorAction SilentlyContinue
        & taskkill.exe /PID $publisherProcess.Id /T /F | Out-Null
    }

    foreach ($userRecord in $usersToClean) {
        try {
            $user = Get-LocalUser -Name $userRecord.Name -ErrorAction SilentlyContinue
            if (-not $user) { continue }
            if ($user.Description -ne $userRecord.Marker -or
                ($userRecord.Sid -and $user.SID.Value -ne $userRecord.Sid)) {
                $cleanupErrors += "temporary account ownership check failed; account was left untouched"
                continue
            }
            Remove-LocalUser -Name $userRecord.Name -ErrorAction Stop
            if (Get-LocalUser -Name $userRecord.Name -ErrorAction SilentlyContinue) {
                $cleanupErrors += "temporary account remained after removal"
            }
        } catch {
            $cleanupErrors += "temporary account cleanup failed: " + $_.Exception.GetType().Name
        }
    }

    $pathAclFacts = @(
        (Get-SanitizedPathAclFact -Role "runner_temp" -Path $runnerTemp),
        (Get-SanitizedPathAclFact -Role "local_app_data" -Path $localAppData),
        (Get-SanitizedPathAclFact -Role "run_root" -Path $runRoot),
        (Get-SanitizedPathAclFact -Role "private_data" -Path $privateData),
        (Get-SanitizedPathAclFact -Role "destination_parent" -Path $destinationParent)
    )
    if ($runRoot -and (Test-Path -LiteralPath $marker)) {
        $markerMatches = (Get-Content -LiteralPath $marker -Raw) -ceq $runId
        $rootIsScoped = $runRoot.StartsWith($tempPrefix, [StringComparison]::OrdinalIgnoreCase)
        if ($markerMatches -and $rootIsScoped) {
            try { Remove-Item -LiteralPath $runRoot -Recurse -Force -ErrorAction Stop }
            catch { $cleanupErrors += "unique run directory cleanup failed: " + $_.Exception.GetType().Name }
        } else {
            $cleanupErrors += "run marker or path check failed; directory was left untouched"
        }
    } elseif ($runRoot -and (Test-Path -LiteralPath $runRoot)) {
        $cleanupErrors += "run marker missing; directory was left untouched"
    }

    $evidence = [ordered]@{
        commit = $ExpectedCommit
        tree = $tree
        runner_platform = "windows"
        publisher_peer_sid_distinct = [bool]($publisherSid -and $peerSid -and $publisherSid -ne $peerSid)
        publisher_token_validated = [bool]$publisherEvidence
        peer_token_validated = [bool]$peerEvidence
        destination_parent_acl_observed = [bool]$destinationAclEvidence
        destination_parent_inheritance_protected = if ($destinationAclEvidence) { [bool]$destinationAclEvidence.inheritance_protected } else { $null }
        destination_listing_denied = [bool]$peerEvidence.destination_listing_denied
        destination_create_denied = [bool]$peerEvidence.destination_create_denied
        destination_canary_was_created = [bool]$peerEvidence.destination_canary_was_created
        destination_canary_cleanup_failed = [bool]$peerEvidence.destination_canary_cleanup_error
        stage_listing_denied = [bool]$peerEvidence.stage_listing_denied
        payload_read_denied = [bool]$peerEvidence.payload_read_denied
        stage_create_denied = [bool]$peerEvidence.stage_create_denied
        stage_rename_denied = [bool]$peerEvidence.stage_rename_denied
        stage_delete_denied = [bool]$peerEvidence.stage_delete_denied
        canary_was_created = [bool]$peerEvidence.canary_was_created
        canary_cleanup_failed = [bool]$peerEvidence.canary_cleanup_error
        publish_success = [bool]$testResults.publish_success
        promotion_failure = [bool]$testResults.promotion_failure
        unsafe_delete_child_negative_control = (Test-Path -LiteralPath $unsafeDeleteChildResultPath -PathType Leaf)
        unsafe_write_dac_negative_control = (Test-Path -LiteralPath $unsafeWriteDacResultPath -PathType Leaf)
        peer_probe_exit_code = $probeExitCode
        failure_class = $failureClass
        failure_phase = $failurePhase
        identity_subphase = $identitySubphase
        failure_status = if ($failureClass) { "failed" } else { "passed" }
        path_acl_facts = $pathAclFacts
        cleanup_failed = ($cleanupErrors.Count -gt 0)
    }
    $evidenceBytes = [Text.UTF8Encoding]::new($false).GetBytes((ConvertTo-Json -InputObject $evidence -Depth 8))
    $evidenceStream.Write($evidenceBytes, 0, $evidenceBytes.Length)
    $evidenceStream.Flush()
    $evidenceStream.Dispose()

    if ($cleanupErrors.Count -gt 0) { Write-Error ($cleanupErrors -join "; ") }
}
