<#
.SYNOPSIS
    Installs portable Android build-tools and platform-tools without Android Studio.

.DESCRIPTION
    Downloads the official Google packages:

    - build-tools (aapt2, aapt, apksigner, zipalign, d8)
    - platform-tools (adb)

    Both are extracted under tools/android and the paths are written into
    config/toolchain.json so the MCP server can find them immediately.

.PARAMETER RepoRoot
    Repository root. Defaults to the parent directory of this script.

.PARAMETER BuildToolsVersion
    Build tools folder name to create, for example 35.0.0.
    The downloaded package major version is taken from this value.

.PARAMETER SkipPlatformTools
    Only install build-tools.

.EXAMPLE
    powershell -ExecutionPolicy Bypass -File scripts/setup-android-tools.ps1

.EXAMPLE
    powershell -ExecutionPolicy Bypass -File scripts/setup-android-tools.ps1 -BuildToolsVersion 35.0.0
#>
[CmdletBinding()]
param(
    [string]$RepoRoot = '',
    [string]$BuildToolsVersion = '35.0.0',
    [switch]$SkipPlatformTools,
    [switch]$SkipPlatform
)

$ErrorActionPreference = 'Stop'

if ([string]::IsNullOrWhiteSpace($RepoRoot)) {
    $scriptDirectory = Split-Path -Parent $MyInvocation.MyCommand.Path
    $RepoRoot = Split-Path -Parent $scriptDirectory
}
$RepoRoot = (Resolve-Path -LiteralPath $RepoRoot).Path

function Write-Section {
    param([string]$Text)
    Write-Host ''
    Write-Host "== $Text ==" -ForegroundColor Cyan
}

function Invoke-Download {
    param(
        [string]$Url,
        [string]$Destination
    )

    $partial = "$Destination.part"
    $curl = Get-Command -Name 'curl.exe' -ErrorAction SilentlyContinue

    if ($null -eq $curl) {
        Invoke-WebRequest -Uri $Url -OutFile $Destination -UseBasicParsing
        return
    }

    for ($attempt = 1; $attempt -le 4; $attempt++) {
        & $curl.Source -sS -L --fail --retry 3 --retry-delay 2 -C - --max-time 900 -o $partial $Url
        $code = $LASTEXITCODE
        if ($code -eq 0) { break }
        if ($code -eq 22 -or $code -eq 33) {
            throw "curl gagal mengunduh $Url dengan kode $code"
        }
        Write-Host ("  unduhan terputus, melanjutkan percobaan ke-{0}..." -f ($attempt + 1)) -ForegroundColor Yellow
    }

    if ($LASTEXITCODE -ne 0 -or -not (Test-Path -LiteralPath $partial)) {
        throw "Gagal mengunduh $Url setelah beberapa percobaan"
    }

    Move-Item -LiteralPath $partial -Destination $Destination -Force
}

function Test-ZipUsable {
    param(
        [string]$ZipPath,
        [int]$MinimumEntries = 20
    )

    if (-not (Test-Path -LiteralPath $ZipPath)) { return $false }

    try {
        Add-Type -AssemblyName System.IO.Compression.FileSystem -ErrorAction SilentlyContinue
        $archive = [System.IO.Compression.ZipFile]::OpenRead($ZipPath)
        try {
            $count = $archive.Entries.Count
        }
        finally {
            $archive.Dispose()
        }
        return ($count -ge $MinimumEntries)
    }
    catch {
        return $false
    }
}

function Expand-ArchiveFast {
    param(
        [string]$ZipPath,
        [string]$Destination
    )

    New-Item -ItemType Directory -Path $Destination -Force | Out-Null
    $tar = Get-Command -Name 'tar.exe' -ErrorAction SilentlyContinue

    if ($null -ne $tar) {
        & $tar.Source -xf $ZipPath -C $Destination
        if ($LASTEXITCODE -ne 0) {
            throw "tar gagal mengekstrak $ZipPath"
        }
        return
    }

    Expand-Archive -LiteralPath $ZipPath -DestinationPath $Destination -Force
}

function Ensure-Package {
    param(
        [string]$Url,
        [string]$ZipPath,
        [string]$Label,
        [int]$MinimumEntries = 20
    )

    if (Test-ZipUsable -ZipPath $ZipPath $MinimumEntries) {
        Write-Host "Arsip $Label sudah ada: $ZipPath"
        return
    }

    if (Test-Path -LiteralPath $ZipPath) {
        Write-Host "Arsip $Label tidak valid, mengunduh ulang..." -ForegroundColor Yellow
        Remove-Item -LiteralPath $ZipPath -Force
    }

    Write-Host "Mengunduh $Label dari $Url"
    Invoke-Download -Url $Url -Destination $ZipPath

    if (-not (Test-ZipUsable -ZipPath $ZipPath $MinimumEntries)) {
        Remove-Item -LiteralPath $ZipPath -Force -ErrorAction SilentlyContinue
        throw "Arsip $Label tidak lolos verifikasi setelah diunduh."
    }
}

function Update-ToolchainConfig {
    param(
        [string]$RepoRoot,
        [hashtable]$Entries
    )

    $configPath = Join-Path $RepoRoot 'config/toolchain.json'
    $examplePath = Join-Path $RepoRoot 'config/toolchain.example.json'

    if (-not (Test-Path -LiteralPath $configPath)) {
        if (-not (Test-Path -LiteralPath $examplePath)) {
            throw "config/toolchain.example.json tidak ditemukan."
        }
        Copy-Item -LiteralPath $examplePath -Destination $configPath
    }

    $config = Get-Content -Raw -LiteralPath $configPath | ConvertFrom-Json

    foreach ($key in $Entries.Keys) {
        $value = [string]$Entries[$key]
        if ([string]::IsNullOrWhiteSpace($value)) { continue }
        if (-not (Test-Path -LiteralPath $value)) { continue }

        $normalized = $value.Replace('\', '/')
        $property = $config.PSObject.Properties[$key]
        if ($null -eq $property) {
            $config | Add-Member -NotePropertyName $key -NotePropertyValue $normalized
        }
        else {
            $property.Value = $normalized
        }
    }

    $json = $config | ConvertTo-Json -Depth 4
    $utf8NoBom = New-Object System.Text.UTF8Encoding($false)
    [System.IO.File]::WriteAllText($configPath, $json, $utf8NoBom)
    Write-Host "Konfigurasi diperbarui: $configPath"
}

$androidRoot = Join-Path $RepoRoot 'tools/android'
New-Item -ItemType Directory -Path $androidRoot -Force | Out-Null

$majorVersion = ($BuildToolsVersion -split '\.')[0]
$buildToolsZip = Join-Path $androidRoot ("build-tools_r{0}_windows.zip" -f $majorVersion)
$buildToolsUrl = "https://dl.google.com/android/repository/build-tools_r$majorVersion`_windows.zip"
$buildToolsDir = Join-Path $androidRoot "build-tools/$BuildToolsVersion"

Write-Section "Android build-tools $BuildToolsVersion"
Ensure-Package -Url $buildToolsUrl -ZipPath $buildToolsZip -Label 'build-tools' -MinimumEntries 100

if (-not (Test-Path -LiteralPath (Join-Path $buildToolsDir 'aapt2.exe'))) {
    Write-Host 'Mengekstrak build-tools...'
    $extractRoot = Join-Path $androidRoot '_build_tools_extract'
    if (Test-Path -LiteralPath $extractRoot) {
        Remove-Item -LiteralPath $extractRoot -Recurse -Force
    }
    Expand-ArchiveFast -ZipPath $buildToolsZip -Destination $extractRoot

    $packageDir = Get-ChildItem -Path $extractRoot -Directory | Select-Object -First 1
    if ($null -eq $packageDir) {
        throw 'Struktur arsip build-tools tidak dikenali.'
    }

    if (Test-Path -LiteralPath $buildToolsDir) {
        Remove-Item -LiteralPath $buildToolsDir -Recurse -Force
    }
    New-Item -ItemType Directory -Path (Split-Path -Parent $buildToolsDir) -Force | Out-Null
    Move-Item -LiteralPath $packageDir.FullName -Destination $buildToolsDir
    Remove-Item -LiteralPath $extractRoot -Recurse -Force
}

if (-not (Test-Path -LiteralPath (Join-Path $buildToolsDir 'aapt2.exe'))) {
    throw "aapt2.exe tidak ditemukan di $buildToolsDir setelah ekstraksi."
}
Write-Host "build-tools siap: $buildToolsDir" -ForegroundColor Green

$platformToolsDir = Join-Path $androidRoot 'platform-tools'

if (-not $SkipPlatformTools) {
    Write-Section 'Android platform-tools'
    $platformZip = Join-Path $androidRoot 'platform-tools-latest-windows.zip'
    $platformUrl = 'https://dl.google.com/android/repository/platform-tools-latest-windows.zip'
    Ensure-Package -Url $platformUrl -ZipPath $platformZip -Label 'platform-tools' -MinimumEntries 5

    if (-not (Test-Path -LiteralPath (Join-Path $platformToolsDir 'adb.exe'))) {
        if (Test-Path -LiteralPath $platformToolsDir) {
            Remove-Item -LiteralPath $platformToolsDir -Recurse -Force
        }
        Write-Host 'Mengekstrak platform-tools...'
        Expand-ArchiveFast -ZipPath $platformZip -Destination $androidRoot
    }

    if (-not (Test-Path -LiteralPath (Join-Path $platformToolsDir 'adb.exe'))) {
        throw "adb.exe tidak ditemukan di $platformToolsDir setelah ekstraksi."
    }
    Write-Host "platform-tools siap: $platformToolsDir" -ForegroundColor Green
}

if (-not $SkipPlatform) {
    Write-Section 'Android platform android-35'
    $platformZip = Join-Path $androidRoot 'platform-35_r02.zip'
    $platformUrl = 'https://dl.google.com/android/repository/platform-35_r02.zip'
    $platformDir = Join-Path $androidRoot 'platforms/android-35'

    Ensure-Package -Url $platformUrl -ZipPath $platformZip -Label 'platform-35' -MinimumEntries 50

    if (-not (Test-Path -LiteralPath (Join-Path $platformDir 'android.jar'))) {
        $extractRoot = Join-Path $androidRoot '_platform_extract'
        if (Test-Path -LiteralPath $extractRoot) {
            Remove-Item -LiteralPath $extractRoot -Recurse -Force
        }
        Expand-ArchiveFast -ZipPath $platformZip -Destination $extractRoot

        $packageDir = Get-ChildItem -Path $extractRoot -Directory | Select-Object -First 1
        if ($null -eq $packageDir) {
            throw 'Struktur arsip platform android tidak dikenali.'
        }

        New-Item -ItemType Directory -Path (Split-Path -Parent $platformDir) -Force | Out-Null
        if (Test-Path -LiteralPath $platformDir) {
            Remove-Item -LiteralPath $platformDir -Recurse -Force
        }
        Move-Item -LiteralPath $packageDir.FullName -Destination $platformDir
        Remove-Item -LiteralPath $extractRoot -Recurse -Force
    }

    if (-not (Test-Path -LiteralPath (Join-Path $platformDir 'android.jar'))) {
        throw "android.jar tidak ditemukan di $platformDir setelah ekstraksi."
    }
    Write-Host "platform android-35 siap: $platformDir" -ForegroundColor Green
}

Write-Section 'Memperbarui config/toolchain.json'
$entries = @{
    aapt2 = (Join-Path $buildToolsDir 'aapt2.exe')
    aapt = (Join-Path $buildToolsDir 'aapt.exe')
    apksigner = (Join-Path $buildToolsDir 'apksigner.bat')
    zipalign = (Join-Path $buildToolsDir 'zipalign.exe')
    dexdump = (Join-Path $buildToolsDir 'dexdump.exe')
}
if (-not $SkipPlatformTools) {
    $entries['adb'] = (Join-Path $platformToolsDir 'adb.exe')
}
Update-ToolchainConfig -RepoRoot $RepoRoot -Entries $entries

Write-Section 'Verifikasi cepat'
& (Join-Path $buildToolsDir 'aapt2.exe') version
& (Join-Path $buildToolsDir 'apksigner.bat') --version
if (-not $SkipPlatformTools) {
    & (Join-Path $platformToolsDir 'adb.exe') version
}

Write-Host ''
Write-Host 'Selesai. Jalankan scripts/verify-toolchain.ps1 untuk pemeriksaan penuh.' -ForegroundColor Green
