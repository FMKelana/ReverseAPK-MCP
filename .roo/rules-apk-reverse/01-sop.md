# SOP Reverse Engineering APK

## Fase 1 — Persiapan
1. Panggil `env_check`. Pastikan apktool, jadx, aapt2, apksigner, dan zipalign tersedia.
2. Panggil `session_create` dengan path APK. Gunakan `copy_apk: true` agar artifact lengkap.
3. Simpan `session_id` pada catatan kerja. Semua tool berikutnya memakai id tersebut.

## Fase 2 — Inventaris
1. `apk_info` untuk package, versi, SDK, permission, activity peluncur, dan framework.
2. `framework_detect` untuk memastikan pendekatan analisis.
3. `apk_signature_info` untuk mengetahui sertifikat dan skema signing.

## Fase 3 — Decode
1. `decode_pipeline` untuk menjalankan apktool dan jadx sekaligus, atau panggil terpisah bila perlu kontrol.
2. `manifest_decode` untuk mendapatkan struktur manifest dalam JSON.
3. `index_build` untuk membangun index pencarian.

## Fase 4 — Analisis
1. Mulai dari `code_search` dengan kata kunci domain, misalnya login, api, token, database.
2. `callgraph` untuk melihat siapa yang memanggil method penting.
3. `code_read` hanya pada rentang baris yang relevan, maksimal 400 baris per panggilan.
4. `strings_scan` untuk endpoint, API key, atau pesan error.
5. `native_lib_list` dan `strings_scan` target native bila framework memakai `.so`.

## Fase 5 — Rebuild jalur A
1. Patch file smali atau resource di folder `apktool/` memakai edit file.
2. `apktool_build` untuk menghasilkan APK.
3. `zipalign_apk` lalu `apksign_apk`, atau langsung `rebuild_and_sign`.
4. `fidelity_check` untuk membandingkan hasil dengan APK asli.
5. `smoke_test` untuk memastikan aplikasi berjalan tanpa crash.

## Fase 6 — Reimplementasi jalur B
1. `jadx_export_gradle` bila ingin basis project dari jadx.
2. `kotlin_scaffold` bila ingin project Kotlin bersih.
3. Lengkapi `docs/SPEC.md` berdasarkan hasil analisis.
4. `gradle_build` dengan `project_dir` yang sesuai.
5. `fidelity_check` dengan `rebuilt_apk` hasil budi daya.
6. Tambahkan fitur baru setelah baseline setara.

## Aturan Bukti
- Setiap klaim perilaku harus merujuk ke path file dan nomor baris.
- Jika tool mengembalikan `partial`, jelaskan bagian yang belum terbukti.
- Jangan menyimpulkan perilaku hanya dari nama method.
