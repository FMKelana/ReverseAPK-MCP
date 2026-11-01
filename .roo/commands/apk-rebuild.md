# Rebuild dan Verifikasi APK

Gunakan perintah ini setelah sesi dan decode sudah siap.

1. Pastikan `session_id` tersedia.
2. Terapkan perubahan pada folder `apktool/` milik sesi, misalnya string, resource, atau smali.
3. `apktool_build` dengan `use_aapt2: true`.
4. `rebuild_and_sign` untuk build, zipalign, dan signing sekaligus.
5. `apk_signature_info` dengan path APK hasil signing untuk memastikan sertifikat benar.
6. `fidelity_check` untuk membandingkan manifest dengan APK asli.
7. `smoke_test` pada emulator atau device.
8. Bila `smoke_test` menemukan crash, baca `log_tail`, perbaiki, lalu ulangi dari langkah 3.

Laporkan:
- Path APK final.
- Hasil fidelity_check beserta checks yang gagal.
- Ringkasan logcat dan status crash.
- Perubahan yang dilakukan dan alasan teknisnya.
