<#
.SYNOPSIS
    Launches the ReverseAPK MCP server over stdio from the repository checkout.

.DESCRIPTION
    Sets REVERSEAPK_HOME and PYTHONPATH, then runs the reverseapk_mcp package with the
    selected Python interpreter. If -Python is not given, the project virtual
    environment mcp-server\.venv\Scripts\python.exe is preferred, because the global
    Python usually does not have the mcp package installed.

.PARAMETER RepoRoot
    Repository root. Defaults to the parent directory of this script.

.PARAMETER Python
    Python interpreter to use. Defaults to the project virtual environment.

.PARAMETER Check
    Only verify the interpreter and the mcp package, then exit.

.EXAMPLE
    powershell -ExecutionPolicy Bypass -File scripts/run-mcp.ps1

.EXAMPLE
    powershell -ExecutionPolicy Bypass -File scripts/run-mcp.ps1 -Check
#>
[CmdletBinding()]
param(
    [string]$RepoRoot = '',
    [string]$Python = '',
    [switch]$Check
)

$ErrorActionPreference = 'Stop'

if ([string]::IsNullOrWhiteSpace($RepoRoot)) {
    $scriptDirectory = Split-Path -Parent $MyInvocation.MyCommand.Path
    $RepoRoot = Split-Path -Parent $scriptDirectory
}
$RepoRoot = (Resolve-Path -LiteralPath $RepoRoot).Path

$serverDir = Join-Path $RepoRoot 'mcp-server'
if (-not (Test-Path -LiteralPath $serverDir)) {
    throw "Direktori mcp-server tidak ditemukan di $serverDir"
}

if ([string]::IsNullOrWhiteSpace($Python)) {
    $venvPython = Join-Path $serverDir '.venv\Scripts\python.exe'
    if (Test-Path -LiteralPath $venvPython) {
        $Python = $venvPython
    }
    else {
        $Python = 'python'
    }
}

$env:REVERSEAPK_HOME = $RepoRoot
$env:PYTHONPATH = (Join-Path $serverDir 'src')
$env:PYTHONUTF8 = '1'

if ($Check) {
    Write-Host "RepoRoot : $RepoRoot"
    Write-Host "Python   : $Python"
    & $Python -c "import sys, mcp; from reverseapk_mcp.server import build_server; print('mcp ok:', sys.executable); print('server:', type(build_server()).__name__)"
    exit $LASTEXITCODE
}

Push-Location -LiteralPath $serverDir
try {
    & $Python -m reverseapk_mcp @args
    exit $LASTEXITCODE
}
finally {
    Pop-Location
}
