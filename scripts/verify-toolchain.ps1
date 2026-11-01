<#
.SYNOPSIS
    Verifies that every CLI tool required by the ReverseAPK MCP server is reachable.

.DESCRIPTION
    Reads config/toolchain.json (machine specific paths) and falls back to PATH lookup.
    Prints a table with tool name, resolved path, version output and status.
    Exits with code 1 when a required tool is missing.

.PARAMETER RepoRoot
    Repository root. Defaults to the parent directory of this script.

.PARAMETER Json
    Emit machine readable JSON instead of a table.

.EXAMPLE
    powershell -ExecutionPolicy Bypass -File scripts/verify-toolchain.ps1

.EXAMPLE
    powershell -ExecutionPolicy Bypass -File scripts/verify-toolchain.ps1 -Json
#>
[CmdletBinding()]
param(
    [string]$RepoRoot = '',
    [switch]$Json
)

$ErrorActionPreference = 'Stop'

if ([string]::IsNullOrWhiteSpace($RepoRoot)) {
    $scriptDirectory = Split-Path -Parent $MyInvocation.MyCommand.Path
    $RepoRoot = Split-Path -Parent $scriptDirectory
}
$RepoRoot = (Resolve-Path -LiteralPath $RepoRoot).Path

$toolSpec = @(
    @{ Name = 'python';          Required = $true;  Probe = @('--version'); Aliases = @('python', 'python3', 'py') },
    @{ Name = 'java';            Required = $true;  Probe = @('-version');  Aliases = @('java') },
    @{ Name = 'apktool';         Required = $true;  Probe = @('--version'); Aliases = @('apktool') },
    @{ Name = 'jadx';            Required = $true;  Probe = @('--version'); Aliases = @('jadx') },
    @{ Name = 'aapt2';           Required = $true;  Probe = @('version');   Aliases = @('aapt2') },
    @{ Name = 'apksigner';       Required = $true;  Probe = @('--version'); Aliases = @('apksigner') },
    @{ Name = 'zipalign';        Required = $true;  Probe = @('-h');        Aliases = @('zipalign') },
    @{ Name = 'dexdump';         Required = $false; Probe = @();            Aliases = @('dexdump') },
    @{ Name = 'keytool';         Required = $false; Probe = @('-help');     Aliases = @('keytool') },
    @{ Name = 'adb';             Required = $false; Probe = @('version');   Aliases = @('adb') },
    @{ Name = 'gradle';          Required = $false; Probe = @('--version'); Aliases = @('gradle') },
    @{ Name = 'frida';           Required = $false; Probe = @('--version'); Aliases = @('frida') },
    @{ Name = 'ghidra_headless'; Required = $false; Probe = @();            Aliases = @('analyzeHeadless') }
)

$configPath = Join-Path $RepoRoot 'config/toolchain.json'
$configObject = $null
if (Test-Path -LiteralPath $configPath) {
    $configObject = Get-Content -Raw -LiteralPath $configPath | ConvertFrom-Json
}

function Resolve-JdkHome {
    if (-not [string]::IsNullOrWhiteSpace($env:JAVA_HOME)) {
        if (Test-Path -LiteralPath (Join-Path $env:JAVA_HOME 'bin/javac.exe')) {
            return $env:JAVA_HOME
        }
    }

    try {
        $line = (& java -XshowSettings:properties -version 2>&1 | Select-String 'java.home' | Select-Object -First 1)
        if ($null -ne $line) {
            $value = ($line.ToString() -split '=', 2)[1].Trim()
            if (-not [string]::IsNullOrWhiteSpace($value)) {
                return $value
            }
        }
    }
    catch {
        return $null
    }

    return $null
}

$jdkHome = Resolve-JdkHome

function Get-ConfiguredPath {
    param([string]$Name)

    if ($null -eq $configObject) { return $null }
    $property = $configObject.PSObject.Properties[$Name]
    if ($null -eq $property) { return $null }
    $value = [string]$property.Value
    if ([string]::IsNullOrWhiteSpace($value)) { return $null }
    return $value
}

function Resolve-ToolPath {
    param(
        [string]$Name,
        [string[]]$Aliases
    )

    $configured = Get-ConfiguredPath -Name $Name
    if ($configured) {
        $expanded = [Environment]::ExpandEnvironmentVariables($configured)
        if (Test-Path -LiteralPath $expanded) {
            return (Resolve-Path -LiteralPath $expanded).Path
        }
        return $expanded
    }

    foreach ($candidate in ($Aliases + $Name)) {
        $command = Get-Command -Name $candidate -ErrorAction SilentlyContinue | Select-Object -First 1
        if ($null -ne $command) {
            $sourceProperty = $command.PSObject.Properties['Source']
            if ($null -ne $sourceProperty -and -not [string]::IsNullOrWhiteSpace([string]$sourceProperty.Value)) {
                return [string]$sourceProperty.Value
            }
            return [string]$command.Name
        }
    }

    return $null
}

function Invoke-Probe {
    param(
        [string]$Executable,
        [string[]]$ProbeArgs
    )

    if ($null -eq $ProbeArgs -or $ProbeArgs.Count -eq 0) {
        return ''
    }

    try {
        $output = & $Executable @ProbeArgs 2>&1 | Out-String
        return $output.Trim()
    }
    catch {
        return $_.Exception.Message
    }
}

$results = @()
foreach ($tool in $toolSpec) {
    $path = Resolve-ToolPath -Name $tool.Name -Aliases $tool.Aliases

    if (-not $path -and $jdkHome) {
        $jdkTool = Join-Path $jdkHome ('bin/' + $tool.Name + '.exe')
        if (Test-Path -LiteralPath $jdkTool) {
            $path = $jdkTool
        }
    }

    $exists = $false
    if ($path) {
        $exists = Test-Path -LiteralPath $path
        if (-not $exists) {
            $exists = $null -ne (Get-Command -Name $path -ErrorAction SilentlyContinue)
        }
    }

    $versionLine = ''
    if ($exists) {
        $raw = Invoke-Probe -Executable $path -ProbeArgs $tool.Probe
        if (-not [string]::IsNullOrWhiteSpace($raw)) {
            $versionLine = ($raw -split "`r?`n" | Where-Object { -not [string]::IsNullOrWhiteSpace($_) } | Select-Object -First 1).Trim()
        }
    }

    $results += [pscustomobject]@{
        Tool     = $tool.Name
        Required = [bool]$tool.Required
        Status   = if ($exists) { 'OK' } elseif ($tool.Required) { 'MISSING' } else { 'OPTIONAL-MISSING' }
        Path     = if ($path) { $path } else { '' }
        Version  = $versionLine
    }
}

if ($Json) {
    $results | ConvertTo-Json -Depth 4
}
else {
    Write-Host ''
    Write-Host 'ReverseAPK toolchain verification' -ForegroundColor Cyan
    Write-Host "Repository : $RepoRoot"
    Write-Host "Reported   : $(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')"
    Write-Host ''
    $results |
        Format-Table -AutoSize -Property Tool, Required, Status, Version, Path |
        Out-String -Width 220 |
        Write-Host

    $missing = $results | Where-Object { $_.Status -eq 'MISSING' }
    if ($missing.Count -gt 0) {
        Write-Host 'Missing required tools:' -ForegroundColor Red
        foreach ($item in $missing) {
            Write-Host ("  - {0}" -f $item.Tool) -ForegroundColor Red
        }
        Write-Host ''
        Write-Host 'Run scripts/setup-toolchain.ps1 to download the portable tools and follow the printed Android SDK steps.' -ForegroundColor Yellow
    }
    else {
        Write-Host 'All required tools are available.' -ForegroundColor Green
    }
}

$missingRequired = $results | Where-Object { $_.Status -eq 'MISSING' }
if ($missingRequired.Count -gt 0) {
    exit 1
}
exit 0
