[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)]
    [ValidateSet("Create", "Cleanup")]
    [string]$Action,
    [ValidateSet("OMNIAGENT_PRIVATE_TEST_ROOT", "OMNIAGENT_PUBLISHER_STAGING_ROOT")]
    [string]$OutputVariable = "OMNIAGENT_PRIVATE_TEST_ROOT"
)
$ErrorActionPreference = "Stop"
$phase = "preflight"

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

        $phase = "root-policy-check"
        $probe = "import os; from securefs import SecureRoot; root = SecureRoot(os.environ['$OutputVariable'], writable=True, _allow_safe_inherited_ancestors=True); ok = root.supports_private_staging(); root.close(); raise SystemExit(0 if ok else 1)"
        python -c $probe *> $null
        if ($LASTEXITCODE -ne 0) { throw "Private staging root failed SecureRoot ancestry validation." }
        if (-not $env:GITHUB_ENV) { throw "Workflow environment file is unavailable." }
        [IO.File]::AppendAllText($env:GITHUB_ENV, ($OutputVariable + "=" + $root + "`n"), [Text.UTF8Encoding]::new($false))
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
