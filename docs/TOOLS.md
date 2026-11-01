# Referensi Tool MCP ReverseAPK

Semua tool mengembalikan JSON dengan struktur standar:

```json
{
  "status": "ok | partial | error",
  "summary": "ringkasan untuk agent",
  "artifacts": [{"path": "...", "kind": "apk|json|log|directory", "bytes": 1234}],
  "stats": {},
  "next_steps": ["..."],
  "log_tail": "opsional",
  "data": {"opsional": true},
  "error": "opsional"
}
```

Status `partial` berarti sebagian langkah berhasil dan ada bagian yang perlu ditindaklanjuti.

---

## 1. Lingkungan dan sesi

| Tool | Parameter | Fungsi |
|---|---|---|
| `env_check` | `include_versions: bool = true` | Cek tool wajib dan opsional beserta path dan versi |
| `session_create` | `apk_path`, `session_id`, `copy_apk` | Buat workspace sesi dan manifest |
| `session_list` | `limit: int = 50` | Daftar sesi terbaru |
| `session_info` | `session_id` | Tampilkan manifest lengkap |
| `apk_hash` | `session_id` | Hitung ulang hash dan deteksi perubahan file |
| `apk_info` | `session_id` | Badging, permission, komponen, framework, dex, native lib |
| `apk_signature_info` | `session_id`, `apk_path` | Sertifikat dan skema signing |

## 2. Decode statis

| Tool | Parameter | Fungsi |
|---|---|---|
| `apktool_decode` | `session_id`, `force`, `no_src` | Decode resource dan smali ke `apktool/` |
| `jadx_decompile` | `session_id`, `export_gradle`, `no_resources`, `threads` | Decompile Java ke `jadx/` |
| `decode_pipeline` | `session_id`, `skip_apktool`, `skip_jadx` | Jalankan decode plus manifest sekaligus |
| `manifest_decode` | `session_id` | Parse manifest ke `manifest-decoded.json` |
| `smali_list` | `session_id`, `query`, `limit`, `offset` | Daftar file smali dengan filter |
| `smali_read` | `session_id`, `path`, `start_line`, `end_line` | Baca potongan file, maksimal 400 baris |

Catatan: metadata versi dan SDK diambil dari `apktool.yml` bila apktool memindahkannya dari manifest.

## 3. Index dan pencarian

| Tool | Parameter | Fungsi |
|---|---|---|
| `index_build` | `session_id`, `include_java`, `include_smali`, `include_resources`, `max_files` | Bangun index SQLite FTS5 |
| `code_search` | `session_id`, `query`, `kind`, `limit`, `offset` | Cari class, method, field, string, resource |
| `code_read` | `session_id`, `path`, `start_line`, `end_line` | Baca potongan file hasil decode |
| `callgraph` | `session_id`, `symbol`, `limit` | Cari referensi simbol di seluruh index |

## 4. Build, signing, dan pengujian

| Tool | Parameter | Fungsi |
|---|---|---|
| `apktool_build` | `session_id`, `use_aapt2`, `output_name` | Build ulang project apktool |
| `zipalign_apk` | `session_id`, `apk_path`, `output_name` | Alignment APK |
| `apksign_apk` | `session_id`, `apk_path`, `keystore`, `alias`, `storepass`, `keypass`, `output_name` | Signing dan verifikasi |
| `rebuild_and_sign` | `session_id`, `use_aapt2` | Build, zipalign, signing berurutan |
| `gradle_build` | `session_id`, `project_dir`, `task` | Build project gradle hasil jadx atau scaffold |
| `apk_install` | `session_id`, `apk_path`, `device` | Instal ke emulator atau device |
| `smoke_test` | `session_id`, `apk_path`, `activity`, `device`, `wait_seconds` | Instal, buka aplikasi, ambil logcat |

Catatan: sebelum build, tool memulihkan elemen `uses-sdk` dari `apktool.yml` agar `minSdkVersion` tidak hilang.

## 5. Analisis lanjutan

| Tool | Parameter | Fungsi |
|---|---|---|
| `framework_detect` | `session_id` | Deteksi native, Flutter, React Native, Unity, Xamarin, Cordova |
| `native_lib_list` | `session_id`, `extract` | Daftar dan ekstrak `.so` per ABI |
| `strings_scan` | `session_id`, `target`, `query`, `min_length`, `limit`, `path` | Pindai string pada APK, native lib, atau file |
| `dexdump_summary` | `session_id`, `dex_name`, `disassemble` | Header DEX dan disassembly opsional |
| `ghidra_headless` | `session_id`, `binary_path`, `script_path`, `timeout_seconds` | Analisis native dengan Ghidra, opsional |
| `frida_enumerate` | `device` | Daftar proses via frida-ps, opsional |
| `frida_run_script` | `session_id`, `package`, `script_path`, `seconds`, `device` | Jalankan script hook, eksperimental |

## 6. Rekonstruksi

| Tool | Parameter | Fungsi |
|---|---|---|
| `jadx_export_gradle` | `session_id`, `threads` | Export project Gradle ke `build/jadx-gradle` |
| `kotlin_scaffold` | `session_id`, `package_name`, `app_name`, `min_sdk`, `target_sdk` | Skeleton project Kotlin untuk reimplementasi |
| `fidelity_check` | `session_id`, `rebuilt_apk`, `deep` | Bandingkan manifest APK hasil rebuild dengan asli |
| `reconstruction_plan` | `session_id`, `top_files` | Rencana rekonstruksi markdown |

## 7. Resource MCP

| URI | Isi |
|---|---|
| `workspace://sessions` | Daftar sesi dalam JSON |
| `workspace://{session_id}/manifest` | Manifest sesi |
| `workspace://{session_id}/tree` | Pohon file sesi, dibatasi 500 entri |

## 8. Batas Keamanan Tool

- Semua path file divalidasi berada di dalam workspace sesi.
- Tidak ada tool yang menerima string shell mentah.
- Timeout dan batas output diterapkan pada setiap eksekusi.
- Password keystore tidak pernah ditulis ke manifest atau log.
