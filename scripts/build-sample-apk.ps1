<#
.SYNOPSIS
    Builds a small signed sample APK for testing the ReverseAPK pipeline.

.DESCRIPTION
    Creates a minimal Java Android app, compiles it with aapt2, javac, and d8,
    then aligns and signs the result. The output APK is intended only for local
    testing of decode, index, rebuild, and fidelity tools.

    Catatan teknis:
    - Memakai javac, jar, dan keytool asli dari JDK, bukan shim javapath, karena
      shim dapat merusak argumen path pada sebagian instalasi Windows.
    - Semua file sumber ditulis UTF-8 tanpa BOM agar diterima javac dan aapt2.

.PARAMETER RepoRoot
    Repository root. Defaults to the parent directory of this script.

.PARAMETER Package
    Package name for the sample app.

.PARAMETER OutputApk
    Output path relative to the repository root.

.PARAMETER MinSdk
    Minimum SDK for the sample app.

.PARAMETER TargetSdk
    Target and compile SDK for the sample app.

.PARAMETER KeepWork
    Keep the intermediate build directory.

.EXAMPLE
    powershell -ExecutionPolicy Bypass -File scripts/build-sample-apk.ps1
#>
[CmdletBinding()]
param(
    [string]$RepoRoot = '',
    [string]$Package = 'com.example.demo',
    [string]$OutputApk = 'samples/demo.apk',
    [int]$MinSdk = 24,
    [int]$TargetSdk = 35,
    [switch]$KeepWork
)

$ErrorActionPreference = 'Stop'

if ([string]::IsNullOrWhiteSpace($RepoRoot)) {
    $scriptDirectory = Split-Path -Parent $MyInvocation.MyCommand.Path
    $RepoRoot = Split-Path -Parent $scriptDirectory
}
$RepoRoot = (Resolve-Path -LiteralPath $RepoRoot).Path

function Require-File {
    param([string]$Path, [string]$Hint)
    if (-not (Test-Path -LiteralPath $Path)) {
        throw "File tidak ditemukan: $Path. $Hint"
    }
    return $Path
}

function Write-Utf8NoBom {
    param([string]$Path, [string]$Content)
    $encoding = New-Object System.Text.UTF8Encoding($false)
    [System.IO.File]::WriteAllText($Path, $Content, $encoding)
}

function Resolve-JdkHome {
    $candidates = @()
    if (-not [string]::IsNullOrWhiteSpace($env:JAVA_HOME)) {
        $candidates += $env:JAVA_HOME
    }

    try {
        $line = (& java -XshowSettings:properties -version 2>&1 | Select-String 'java.home' | Select-Object -First 1)
        if ($null -ne $line) {
            $value = ($line.ToString() -split '=', 2)[1].Trim()
            if (-not [string]::IsNullOrWhiteSpace($value)) {
                $candidates += $value
            }
        }
    }
    catch {
        # abaikan, akan gagal di pemeriksaan di bawah
    }

    foreach ($candidate in $candidates) {
        if (Test-Path -LiteralPath (Join-Path $candidate 'bin/javac.exe')) {
            return (Resolve-Path -LiteralPath $candidate).Path
        }
    }

    throw 'JDK tidak ditemukan. Set JAVA_HOME ke instalasi JDK 17 atau lebih baru.'
}

$jdkHome = Resolve-JdkHome
$javac = Require-File (Join-Path $jdkHome 'bin/javac.exe') 'Instal JDK 17 atau lebih baru.'
$jarTool = Require-File (Join-Path $jdkHome 'bin/jar.exe') 'Instal JDK 17 atau lebih baru.'
$keytool = Require-File (Join-Path $jdkHome 'bin/keytool.exe') 'Instal JDK 17 atau lebih baru.'

$androidRoot = Join-Path $RepoRoot 'tools/android'
$buildTools = Join-Path $androidRoot 'build-tools/35.0.0'
$aapt2 = Require-File (Join-Path $buildTools 'aapt2.exe') 'Jalankan scripts/setup-android-tools.ps1.'
$zipalign = Require-File (Join-Path $buildTools 'zipalign.exe') 'Jalankan scripts/setup-android-tools.ps1.'
$apksigner = Require-File (Join-Path $buildTools 'apksigner.bat') 'Jalankan scripts/setup-android-tools.ps1.'
$d8 = Require-File (Join-Path $buildTools 'd8.bat') 'Jalankan scripts/setup-android-tools.ps1.'
$platformJar = Require-File (Join-Path $androidRoot 'platforms/android-35/android.jar') 'Ekstrak platform-35 ke tools/android/platforms/android-35.'

$work = Join-Path $RepoRoot 'build/sample-apk'
if (Test-Path -LiteralPath $work) {
    Remove-Item -LiteralPath $work -Recurse -Force
}

$sourceDir = Join-Path $work 'src'
$javaDir = Join-Path $sourceDir ($Package -replace '\.', '/')
$resDir = Join-Path $work 'res/values'
$classDir = Join-Path $work 'classes'
$dexDir = Join-Path $work 'dex'
foreach ($directory in @($javaDir, $resDir, $classDir, $dexDir)) {
    New-Item -ItemType Directory -Path $directory -Force | Out-Null
}

$javaSource = @"
package $Package;

import android.app.Activity;
import android.os.Bundle;
import android.util.Log;
import android.widget.TextView;

public class MainActivity extends Activity {
    private static final String TAG = "DemoApp";
    private static final String ENDPOINT = "https://api.example.com/v1/login";

    @Override
    protected void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);
        TextView view = new TextView(this);
        view.setText("Demo sample for ReverseAPK");
        setContentView(view);
        Log.i(TAG, "MainActivity started, endpoint=" + ENDPOINT);
    }
}
"@
Write-Utf8NoBom -Path (Join-Path $javaDir 'MainActivity.java') -Content $javaSource

$stringsXml = @'
<?xml version="1.0" encoding="utf-8"?>
<resources>
    <string name="app_name">ReverseAPK Demo</string>
</resources>
'@
Write-Utf8NoBom -Path (Join-Path $resDir 'strings.xml') -Content $stringsXml

$manifestXml = @"
<?xml version="1.0" encoding="utf-8"?>
<manifest xmlns:android="http://schemas.android.com/apk/res/android"
    package="$Package"
    android:versionCode="1"
    android:versionName="1.0">

    <uses-sdk android:minSdkVersion="$MinSdk" android:targetSdkVersion="$TargetSdk" />
    <uses-permission android:name="android.permission.INTERNET" />

    <application
        android:label="@string/app_name"
        android:allowBackup="false"
        android:debuggable="false"
        android:theme="@android:style/Theme.Material.Light.NoActionBar">

        <activity android:name=".MainActivity" android:exported="true">
            <intent-filter>
                <action android:name="android.intent.action.MAIN" />
                <category android:name="android.intent.category.LAUNCHER" />
            </intent-filter>
        </activity>
    </application>
</manifest>
"@
Write-Utf8NoBom -Path (Join-Path $work 'AndroidManifest.xml') -Content $manifestXml

Write-Host '== Kompilasi Java ==' -ForegroundColor Cyan
$javaFiles = Get-ChildItem -Path $sourceDir -Recurse -Filter '*.java' | Select-Object -ExpandProperty FullName
$javacArgs = @('-source', '17', '-target', '17', '-classpath', $platformJar, '-d', $classDir) + $javaFiles
& $javac @javacArgs
if ($LASTEXITCODE -ne 0) { throw "javac gagal dengan kode $LASTEXITCODE" }

Write-Host '== Membuat classes.jar ==' -ForegroundColor Cyan
$classesJar = Join-Path $work 'classes.jar'
& $jarTool --create --file $classesJar -C $classDir .
if ($LASTEXITCODE -ne 0) { throw "jar gagal dengan kode $LASTEXITCODE" }

Write-Host '== D8 ke dex ==' -ForegroundColor Cyan
& $d8 --release --lib $platformJar --min-api $MinSdk --output $dexDir $classesJar
if ($LASTEXITCODE -ne 0) { throw "d8 gagal dengan kode $LASTEXITCODE" }
$dexFile = Require-File (Join-Path $dexDir 'classes.dex') 'd8 tidak menghasilkan classes.dex.'

Write-Host '== aapt2 compile dan link ==' -ForegroundColor Cyan
$compiled = Join-Path $work 'compiled.zip'
& $aapt2 compile --dir (Join-Path $work 'res') -o $compiled
if ($LASTEXITCODE -ne 0) { throw "aapt2 compile gagal dengan kode $LASTEXITCODE" }

$unsigned = Join-Path $work 'unsigned.apk'
& $aapt2 link -o $unsigned -I $platformJar --manifest (Join-Path $work 'AndroidManifest.xml') --min-sdk-version $MinSdk --target-sdk-version $TargetSdk $compiled
if ($LASTEXITCODE -ne 0) { throw "aapt2 link gagal dengan kode $LASTEXITCODE" }

Write-Host '== Menambahkan classes.dex ==' -ForegroundColor Cyan
Add-Type -AssemblyName System.IO.Compression.FileSystem
$zip = [System.IO.Compression.ZipFile]::Open($unsigned, 'Update')
try {
    [System.IO.Compression.ZipFileExtensions]::CreateEntryFromFile($zip, $dexFile, 'classes.dex') | Out-Null
}
finally {
    $zip.Dispose()
}

Write-Host '== zipalign ==' -ForegroundColor Cyan
$aligned = Join-Path $work 'aligned.apk'
& $zipalign -f -p 4 $unsigned $aligned
if ($LASTEXITCODE -ne 0) { throw "zipalign gagal dengan kode $LASTEXITCODE" }

Write-Host '== Menyiapkan keystore ==' -ForegroundColor Cyan
$keystore = Join-Path $RepoRoot 'tools/keystore/reverseapk-debug.keystore'
if (-not (Test-Path -LiteralPath $keystore)) {
    New-Item -ItemType Directory -Path (Split-Path -Parent $keystore) -Force | Out-Null
    $keytoolArgs = @(
        '-genkeypair', '-v',
        '-keystore', $keystore,
        '-storepass', 'android',
        '-keypass', 'android',
        '-alias', 'androiddebugkey',
        '-keyalg', 'RSA',
        '-keysize', '2048',
        '-validity', '10000',
        '-dname', 'CN=Android Debug,O=Android,C=US'
    )
    & $keytool @keytoolArgs
    if ($LASTEXITCODE -ne 0) { throw "keytool gagal dengan kode $LASTEXITCODE" }
}

$outputPath = Join-Path $RepoRoot $OutputApk
New-Item -ItemType Directory -Path (Split-Path -Parent $outputPath) -Force | Out-Null

Write-Host '== Signing ==' -ForegroundColor Cyan
& $apksigner sign --ks $keystore --ks-key-alias androiddebugkey --ks-pass pass:android --key-pass pass:android --out $outputPath $aligned
if ($LASTEXITCODE -ne 0) { throw "apksigner gagal dengan kode $LASTEXITCODE" }

& $apksigner verify --verbose $outputPath
if ($LASTEXITCODE -ne 0) { throw "Verifikasi APK gagal dengan kode $LASTEXITCODE" }

if (-not $KeepWork) {
    Remove-Item -LiteralPath $work -Recurse -Force
}

$size = (Get-Item -LiteralPath $outputPath).Length
Write-Host ''
Write-Host "APK sampel siap: $outputPath ($size byte)" -ForegroundColor Green
Write-Host 'Langkah berikutnya: jalankan mcp-server\scripts\e2e_demo.py untuk menguji pipeline.' -ForegroundColor Gray
