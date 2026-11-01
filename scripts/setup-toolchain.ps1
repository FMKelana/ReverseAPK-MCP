<#
.SYNOPSIS
    Bootstraps the portable ReverseAPK toolchain on Windows without Docker.

.DESCRIPTION
    - Optionally installs Python 3.12 and JDK 17 through winget when -InstallPrereqs is used.
    - Downloads apktool and jadx into tools/ with resume support and integrity checks.
    - Supports a download mirror prefix for slow GitHub connections.
    - Writes an apktool.bat wrapper next to the jar.
    - Prints the Android SDK components that must be installed manually through sdkmanager.

.PARAMETER RepoRoot
    Repository root. Defaults to the parent directory of this script.

.PARAMETER ApktoolVersion
    apktool release tag to download.

.PARAMETER JadxVersion
    jadx release tag to download.

.PARAMETER MirrorPrefix
    Optional prefix for GitHub URLs, for example https://ghproxy.net/
    Use when direct downloads from GitHub are very slow or unstable.

.PARAMETER InstallPrereqs
    Use winget to install Python and JDK 17 when they are missing.

.PARAMETER SkipDownload
    Only prepare folders and print instructions.

.EXAMPLE
    powershell -ExecutionPolicy Bypass -File scripts/setup-toolchain.ps1 -InstallPrereqs

.EXAMPLE
    powershell -ExecutionPolicy Bypass -File scripts/setup-toolchain.ps1 -MirrorPrefix "https://ghproxy.net/"
#>
[CmdletBinding()]
param(
    [string]$RepoRoot = '',
    [string]$ApktoolVersion = '2.11.1',
    [string]$JadxVersion = '1.5.1',
    [string]$MirrorPrefix = '',
    [switch]$InstallPrereqs,
    [switch]$SkipDownload
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

function Test-CommandExists {
    param([string]$Name)
    return $null -ne (Get-Command -Name $Name -ErrorAction SilentlyContinue)
}

function Install-WithWinget {
    param(
        [string]$PackageId,
        [string]$FriendlyName
    )

    if (-not (Test-CommandExists -Name 'winget')) {
        Write-Host "winget tidak tersedia, lewati instalasi $FriendlyName." -ForegroundColor Yellow
        return
    }

    Write-Host "Menginstal $FriendlyName melalui winget..." -ForegroundColor Yellow
    & winget install --id $PackageId --exact --accept-package-agreements --accept-source-agreements --silent
    if ($LASTEXITCODE -ne 0) {
        Write-Host "winget gagal untuk $PackageId dengan kode $LASTEXITCODE. Instal manual bila perlu." -ForegroundColor Yellow
    }
}

function Resolve-DownloadUrl {
    param([string]$Url)

    if ([string]::IsNullOrWhiteSpace($MirrorPrefix)) {
        return $Url
    }

    $prefix = $MirrorPrefix
    if (-not $prefix.EndsWith('/')) {
        $prefix = "$prefix/"
    }
    return "$prefix$Url"
}

function Invoke-Download {
    <#
    Unduh berkas dengan curl dan resume otomatis. Unduhan ditulis ke .part lalu
    dipindahkan setelah selesai sehingga file terpotong tidak pernah dipakai.
    #>
    param(
        [string]$Url,
        [string]$Destination
    )

    $partial = "$Destination.part"
    $curl = Get-Command -Name 'curl.exe' -ErrorAction SilentlyContinue

    if ($null -ne $curl) {
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
        return
    }

    Invoke-WebRequest -Uri $Url -OutFile $Destination -UseBasicParsing
}

function Test-JarUsable {
    param([string]$JarPath)

    if (-not (Test-Path -LiteralPath $JarPath)) { return $false }
    if (-not (Test-CommandExists -Name 'java')) { return $true }

    try {
        $null = & java -jar $JarPath --version 2>&1
        return ($LASTEXITCODE -eq 0)
    }
    catch {
        return $false
    }
}

function Test-ZipUsable {
    param(
        [string]$ZipPath,
        [int]$MinimumEntries = 50
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

$toolsRoot = Join-Path $RepoRoot 'tools'
foreach ($relative in @('apktool', 'jadx')) {
    $target = Join-Path $toolsRoot $relative
    if (-not (Test-Path -LiteralPath $target)) {
        New-Item -ItemType Directory -Path $target -Force | Out-Null
    }
}

Write-Section 'Pemeriksaan prasyarat'
$pythonOk = Test-CommandExists -Name 'python'
$javaOk = Test-CommandExists -Name 'java'
Write-Host ("Python : {0}" -f $(if ($pythonOk) { 'tersedia' } else { 'belum ada' }))
Write-Host ("Java   : {0}" -f $(if ($javaOk) { 'tersedia' } else { 'belum ada' }))

if ($InstallPrereqs) {
    if (-not $pythonOk) {
        Install-WithWinget -PackageId 'Python.Python.3.12' -FriendlyName 'Python 3.12'
    }
    if (-not $javaOk) {
        Install-WithWinget -PackageId 'EclipseAdoptium.Temurin.17.JDK' -FriendlyName 'JDK 17 Temurin'
    }
    Write-Host 'Setelah instalasi selesai, buka terminal baru agar PATH diperbarui.' -ForegroundColor Yellow
}

if (-not $SkipDownload) {
    Write-Section "Menyiapkan apktool $ApktoolVersion"
    $apktoolJar = Join-Path $toolsRoot ("apktool/apktool_{0}.jar" -f $ApktoolVersion)

    if (Test-JarUsable -JarPath $apktoolJar) {
        Write-Host "Sudah ada dan valid: $apktoolJar"
    }
    else {
        if (Test-Path -LiteralPath $apktoolJar) {
            Write-Host "File apktool tidak valid atau terpotong, mengunduh ulang..." -ForegroundColor Yellow
            Remove-Item -LiteralPath $apktoolJar -Force
        }

        $apktoolUrl = Resolve-DownloadUrl "https://github.com/iBotPeaches/Apktool/releases/download/v$ApktoolVersion/apktool_$ApktoolVersion.jar"
        Write-Host "URL: $apktoolUrl"
        try {
            Invoke-Download -Url $apktoolUrl -Destination $apktoolJar
        }
        catch {
            Write-Host "Gagal mengunduh apktool: $($_.Exception.Message)" -ForegroundColor Red
            Write-Host "Coba lagi dengan mirror, contoh: -MirrorPrefix `"https://ghproxy.net/`"" -ForegroundColor Yellow
            Write-Host "Atau unduh manual dari https://github.com/iBotPeaches/Apktool/releases dan simpan sebagai $apktoolJar." -ForegroundColor Yellow
            exit 1
        }

        if (-not (Test-JarUsable -JarPath $apktoolJar)) {
            Remove-Item -LiteralPath $apktoolJar -Force -ErrorAction SilentlyContinue
            Write-Host 'File apktool hasil unduhan tidak bisa dijalankan. Periksa koneksi lalu ulangi.' -ForegroundColor Red
            exit 1
        }
        Write-Host 'apktool terunduh dan lolos verifikasi versi.' -ForegroundColor Green
    }

    $wrapperPath = Join-Path $toolsRoot 'apktool/apktool.bat'
    $wrapperContent = @'
@echo off
setlocal
set "APKTOOL_DIR=%~dp0"
if exist "%APKTOOL_DIR%apktool.jar" (
    java -jar "%APKTOOL_DIR%apktool.jar" %*
) else (
    for %%f in ("%APKTOOL_DIR%apktool_*.jar") do java -jar "%%~ff" %*
)
'@
    Set-Content -LiteralPath $wrapperPath -Value $wrapperContent -Encoding ASCII
    Write-Host "Wrapper dibuat: $wrapperPath"

    Write-Section "Menyiapkan jadx $JadxVersion"
    $jadxZip = Join-Path $toolsRoot ("jadx-{0}.zip" -f $JadxVersion)
    $jadxDir = Join-Path $toolsRoot 'jadx'
    $jadxBat = Join-Path $jadxDir 'bin/jadx.bat'

    if (Test-Path -LiteralPath $jadxBat) {
        Write-Host "Sudah ada: $jadxBat"
    }
    else {
        if (-not (Test-ZipUsable -ZipPath $jadxZip)) {
            if (Test-Path -LiteralPath $jadxZip) {
                Write-Host 'Arsip jadx tidak valid atau terpotong, mengunduh ulang...' -ForegroundColor Yellow
                Remove-Item -LiteralPath $jadxZip -Force
            }

            $jadxUrl = Resolve-DownloadUrl "https://github.com/skylot/jadx/releases/download/v$JadxVersion/jadx-$JadxVersion.zip"
            Write-Host "URL: $jadxUrl"
            try {
                Invoke-Download -Url $jadxUrl -Destination $jadxZip
            }
            catch {
                Write-Host "Gagal mengunduh jadx: $($_.Exception.Message)" -ForegroundColor Red
                Write-Host "Coba lagi dengan mirror, contoh: -MirrorPrefix `"https://ghproxy.net/`"" -ForegroundColor Yellow
                Write-Host "Atau unduh manual dari https://github.com/skylot/jadx/releases dan simpan sebagai $jadxZip." -ForegroundColor Yellow
                exit 1
            }

            if (-not (Test-ZipUsable -ZipPath $jadxZip)) {
                Remove-Item -LiteralPath $jadxZip -Force -ErrorAction SilentlyContinue
                Write-Host 'Arsip jadx tidak lolos verifikasi. Periksa koneksi lalu ulangi.' -ForegroundColor Red
                exit 1
            }
        }

        Write-Host 'Mengekstrak jadx...'
        New-Item -ItemType Directory -Path $jadxDir -Force | Out-Null
        Expand-Archive -LiteralPath $jadxZip -DestinationPath $jadxDir -Force

        if (-not (Test-Path -LiteralPath $jadxBat)) {
            Write-Host "Ekstraksi selesai tetapi $jadxBat tidak ditemukan. Periksa isi $jadxZip." -ForegroundColor Red
            exit 1
        }
        Write-Host 'jadx siap digunakan.' -ForegroundColor Green
    }
}

Write-Section 'Android SDK yang perlu dipasang manual'
Write-Host @'
1) Instal Android Studio atau command line tools, lalu buka terminal baru.
2) Jalankan perintah berikut dengan sdkmanager:

   sdkmanager "platform-tools" "build-tools;35.0.0" "platforms;android-35"

3) Salin config/toolchain.example.json menjadi config/toolchain.json
   lalu isi path aapt2, apksigner, zipalign, dan adb sesuai lokasi SDK Anda.

4) Verifikasi dengan:

   powershell -ExecutionPolicy Bypass -File scripts/verify-toolchain.ps1
'@ -ForegroundColor Gray

Write-Host ''
Write-Host 'Selesai. Langkah berikutnya: verifikasi toolchain lalu registrasikan MCP server ke Roo Code.' -ForegroundColor Green
