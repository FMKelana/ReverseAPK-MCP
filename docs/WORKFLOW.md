# Alur Kerja Reverse Engineering APK

Dokumen ini menjelaskan urutan kerja yang dipakai mode `apk-reverse`.

---

## Fase 0 — Persiapan

```powershell
powershell -ExecutionPolicy Bypass -File scripts/verify-toolchain.ps1
```

Jika ada tool wajib yang hilang, jalankan `scripts/setup-toolchain.ps1` dan `scripts/setup-android-tools.ps1`.

Melalui MCP: panggil `env_check`.

---

## Fase 1 — Sesi

```text
session_create(apk_path="samples/demo.apk", copy_apk=true)
→ session_id
```

Semua langkah berikutnya memakai `session_id` tersebut. Manifest sesi menyimpan hash APK, riwayat langkah, dan artifact.

---

## Fase 2 — Inventaris

```text
apk_info(session_id)
framework_detect(session_id)
apk_signature_info(session_id)
```

Keluaran penting: package, versi, SDK, permission, activity peluncur, framework, daftar dex, dan native ABI.

---

## Fase 3 — Decode

```text
decode_pipeline(session_id)
```

Setara dengan:

```text
apktool_decode(session_id)
jadx_decompile(session_id)
manifest_decode(session_id)
```

Hasil ada di `workspaces/<session_id>/apktool`, `jadx`, dan `manifest-decoded.json`.

---

## Fase 4 — Index

```text
index_build(session_id)
```

Index FTS5 memungkinkan pencarian cepat tanpa membaca seluruh file.

```text
code_search(session_id, query="login", kind="method")
callgraph(session_id, symbol="onCreate")
code_read(session_id, path="jadx/sources/.../MainActivity.java", start_line=1, end_line=120)
```

Aturan praktis: maksimal 400 baris per pembacaan dan selalu mulai dari hasil `code_search`.

---

## Fase 5 — Analisis tambahan

| Kebutuhan | Tool |
|---|---|
| Endpoint dan kunci | `strings_scan(session_id, target="apk", query="http")` |
| Logika di native library | `native_lib_list(session_id, extract=true)` lalu `strings_scan(target="native")` |
| Struktur DEX | `dexdump_summary(session_id)` |
| Framework khusus | `framework_detect(session_id)` untuk panduan pendekatan |
| Analisis dinamis | `frida_enumerate()` lalu `frida_run_script(...)` pada device riset |

---

## Fase 6 — Jalur A: patch dan rebuild

1. Edit file di `workspaces/<session_id>/apktool/` (smali, resource, atau manifest).
2. `apktool_build(session_id)`.
3. `rebuild_and_sign(session_id)` untuk build, zipalign, signing, dan verifikasi.
4. `fidelity_check(session_id)`.
5. `smoke_test(session_id)` bila device tersedia.

Contoh perubahan kecil: mengubah teks pada `res/values/strings.xml`, menambah log pada method smali, atau menonaktifkan pengecekan tertentu.

---

## Fase 7 — Jalur B: reimplementasi Kotlin

1. `jadx_export_gradle(session_id)` untuk mendapatkan basis project, atau
2. `kotlin_scaffold(session_id, package_name="com.example.reimpl")` untuk project bersih.
3. Lengkapi `build/reimplement/docs/SPEC.md` dari hasil analisis.
4. Implementasikan modul inti di `app/src/main/java/...`.
5. `gradle_build(session_id, project_dir="build/reimplement")`.
6. `fidelity_check(session_id, rebuilt_apk="build/gradle-1-app-debug.apk")`.
7. `smoke_test(session_id)`.

Jalur B dipakai ketika hasil decompile sulit dibuild ulang atau ketika ingin menambah fitur baru di codebase modern.

---

## Fase 8 — Verifikasi

```text
fidelity_check(session_id, rebuilt_apk="build/...-signed.apk")
```

Pemeriksaan yang dilakukan:

| Check | Arti |
|---|---|
| `package` | applicationId sama |
| `version_name` | versi sama |
| `min_sdk` | minimum SDK sama |
| `target_sdk` | target SDK sama |
| `permissions` | tidak ada permission hilang atau berlebih |
| `components` | activity, service, receiver, provider sama |
| `launchable_activity` | activity peluncur sama |

Skor 1.0 berarti seluruh pemeriksaan lolos.

---

## Contoh End-to-End dengan APK Sampel

```powershell
# 1. Bangun APK sampel lokal
powershell -ExecutionPolicy Bypass -File scripts/build-sample-apk.ps1

# 2. Jalankan demo pipeline lewat tool MCP
set "REVERSEAPK_HOME=g:\ReverseAPK"
mcp-server\.venv\Scripts\python.exe mcp-server\scripts\e2e_demo.py samples\demo.apk
```

Hasil yang diharapkan pada APK sampel:

- `decode_pipeline` menghasilkan 1 smali, 2 file Java, dan 1 komponen.
- `index_build` menghasilkan 22 simbol.
- `rebuild_and_sign` menghasilkan APK bertanda tangan.
- `fidelity_check` menghasilkan skor 1.0.

---

## Contoh Prompt untuk Agent

```text
Analisis APK di samples/demo.apk. Mulai dari env_check, buat sesi,
inventaris, decode, index, lalu jelaskan alur utama aplikasi berdasarkan
code_search dan callgraph. Akhiri dengan reconstruction_plan.
```

```text
Dari sesi <session_id>, ubah teks app_name menjadi "ReverseAPK Mod",
rebuild, sign, lalu jalankan fidelity_check dan laporkan hasilnya.
```

---

## Kriteria Selesai

1. `env_check` status `ok`.
2. Sesi dan manifest tercatat.
3. Decode dan index berhasil.
4. Build dan signing berhasil dengan verifikasi lolos.
5. `fidelity_check` skor mendekati atau sama dengan 1.0.
6. `smoke_test` tidak menemukan crash pada device uji.
