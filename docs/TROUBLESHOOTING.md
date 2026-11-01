# Troubleshooting Windows

Kumpulan masalah nyata yang ditemukan saat pengembangan proyek ini beserta solusinya.

---

## Toolchain

### `apktool tidak ditemukan` atau `ToolNotFound`

- Jalankan `scripts/verify-toolchain.ps1` untuk melihat path efektif.
- Isi `config/toolchain.json` dengan path absolut bila tool tidak ada di PATH.
- Untuk `dexdump`, adapter mencari otomatis di folder yang sama dengan `aapt2.exe`.
- Untuk `keytool`, adapter mencari di `JAVA_HOME\bin` atau folder `java.exe`.

### Java versi terlalu baru atau terlalu lama

- apktool, jadx, dan Ghidra membutuhkan JDK 17 atau lebih baru.
- Ingin menurunkan versi javac:

```powershell
javac --release 17 -classpath tools\android\platforms\android-35\android.jar -d build\classes src\Main.java
```

### `javac: invalid flag: :` saat memakai PowerShell

Penyebab: shim `javac.exe` pada `C:\Program Files\Common Files\Oracle\Java\javapath` dapat merusak argumen path.

Solusi: panggil javac asli dari JDK.

```powershell
$jdk = (java -XshowSettings:properties -version 2>&1 | Select-String 'java.home') -replace '.*=\s*',''
& (Join-Path $jdk 'bin\javac.exe') -source 17 -target 17 -classpath $jar -d $out $source
```

`scripts/build-sample-apk.ps1` sudah menerapkan pola ini.

### `illegal character: '\ufeff'` saat kompilasi

Penyebab: PowerShell 5.1 menulis UTF-8 dengan BOM.

Solusi: tulis file tanpa BOM.

```powershell
$utf8 = New-Object System.Text.UTF8Encoding($false)
[System.IO.File]::WriteAllText($path, $content, $utf8)
```

### `$Home` tidak bisa diisi pada script PowerShell

`$HOME` adalah automatic variable. Gunakan nama lain, misalnya `$RepoRoot`.

### `$PSScriptRoot` kosong

Terjadi pada PowerShell 5.1 saat script dipanggil dengan `-File` dan path relatif. Gunakan:

```powershell
$scriptDirectory = Split-Path -Parent $MyInvocation.MyCommand.Path
$RepoRoot = Split-Path -Parent $scriptDirectory
```

---

## Unduhan

### Unduhan GitHub hanya sekitar 10 KB/s atau terputus

Gunakan mirror dan resume:

```powershell
powershell -ExecutionPolicy Bypass -File scripts/setup-toolchain.ps1 -MirrorPrefix "https://ghproxy.net/"
```

Script memakai `curl -C -`, menulis ke `.part`, dan memvalidasi hasil sebelum dipakai.

### `Invoke-WebRequest` menggantung tanpa progres

Gunakan `curl.exe` yang tersedia di Windows 10 1803 ke atas. Script proyek sudah memakai curl.

### Ekstraksi sangat lambat pada drive jaringan

Gunakan `tar.exe`:

```powershell
tar -xf archive.zip -C destination
```

---

## apktool dan jadx

### `minSdkVersion` hilang setelah rebuild

apktool menyimpan `sdkInfo` di `apktool.yml` dan tidak selalu menuliskannya kembali ke manifest. Tool `apktool_build` dan `rebuild_and_sign` memulihkan elemen `uses-sdk` secara otomatis sebelum build.

### `aapt2 dump badging` tidak menampilkan `sdkVersion`

Beberapa APK hasil apktool tetap memiliki `uses-sdk` yang benar meskipun badging kosong. Verifikasi dengan:

```powershell
aapt2 dump xmltree --file AndroidManifest.xml app.apk
```

`fidelity_check` memakai manifest hasil decode sebagai sumber utama, bukan badging.

### jadx gagal decompile sebagian kelas

- Tambahkan `show_bad_code: true` pada `jadx_decompile`.
- Coba `apktool_decode` lalu baca smali untuk kelas tersebut.
- Gunakan `dexdump_summary` untuk memastikan kelas benar-benar ada.

---

## Build dan signing

### `apksigner` gagal karena password

- Password harus cocok dengan keystore.
- Untuk keystore debug bawaan proyek: alias `androiddebugkey`, password `android`.

### APK tidak bisa diinstal

- Pastikan sudah `zipalign` sebelum signing.
- Signing harus menjadi langkah terakhir.
- Periksa `apk_signature_info` untuk memastikan sertifikat terpasang.

### Gradle build gagal

- Pastikan `local.properties` berisi `sdk.dir` yang benar.
- Jika tidak ada `gradlew`, pasang Gradle 8.x atau salin folder wrapper.
- Jalankan `gradle_build` dengan `project_dir` yang tepat, misalnya `build/reimplement`.

---

## Device dan emulator

### `adb devices` kosong

- Jalankan emulator atau aktifkan USB debugging.
- Terima dialog otorisasi pada device.
- Jika ada beberapa device, isi parameter `device` dengan serial.

### `smoke_test` melaporkan crash

- Baca `log_tail`, cari `FATAL EXCEPTION`.
- Perbaiki penyebab, lalu ulangi `rebuild_and_sign` dan `smoke_test`.
- Pastikan permission yang dibutuhkan tersedia.

---

## MCP dan Roo Code

### Tool tidak muncul di Roo

- Pastikan konfigurasi MCP memakai `command`, `args`, `cwd`, dan `env` yang benar.
- Cek `REVERSEAPK_HOME` dan `PYTHONPATH`.
- Jalankan smoke test server:

```powershell
mcp-server\.venv\Scripts\python.exe mcp-server\scripts\smoke_server.py
```

### `ModuleNotFoundError: No module named 'mcp'` saat server start

Penyebab: `command` pada konfigurasi MCP memakai `python` global, sedangkan paket `mcp` terpasang di virtual environment proyek.

Solusi: arahkan konfigurasi ke interpreter venv.

```json
{
  "mcpServers": {
    "reverseapk": {
      "command": "<REPO_ROOT>/mcp-server/.venv/Scripts/python.exe",
      "args": ["-m", "reverseapk_mcp"],
      "cwd": "<REPO_ROOT>/mcp-server",
      "env": {
        "REVERSEAPK_HOME": "<REPO_ROOT>",
        "PYTHONPATH": "<REPO_ROOT>/mcp-server/src"
      }
    }
  }
}
```

Ganti `<REPO_ROOT>` dengan path absolut checkout Anda, misalnya `D:/tools/ReverseAPK`.

Alternatif: gunakan launcher `scripts/run-mcp.ps1` yang otomatis memilih venv proyek.

```powershell
powershell -ExecutionPolicy Bypass -File scripts/run-mcp.ps1 -Check
```

### Server mati saat start

- Jalankan `powershell -ExecutionPolicy Bypass -File scripts/run-mcp.ps1 -Check` untuk memastikan interpreter dan paket benar.
- Jalankan `python -m reverseapk_mcp` di terminal untuk melihat traceback.
- Pastikan dependency terpasang dengan `pip install -e "mcp-server[dev]"`.

### Mode `apk-reverse` tidak muncul

- Pastikan file `.roomodes` ada di root repository.
- Muat ulang window Roo Code.
- Alternatif: tambahkan mode manual dengan slug `apk-reverse`.

---

## Diagnostik cepat

```powershell
powershell -ExecutionPolicy Bypass -File scripts/verify-toolchain.ps1
powershell -ExecutionPolicy Bypass -File scripts/run-mcp.ps1 -Check
mcp-server\.venv\Scripts\python.exe mcp-server\scripts\smoke_server.py
mcp-server\.venv\Scripts\python.exe -m pytest mcp-server\tests -q
```
