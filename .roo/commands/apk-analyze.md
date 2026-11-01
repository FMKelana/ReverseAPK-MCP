# Analisis APK End-to-End

Jalankan alur berikut secara berurutan dan laporkan hasil tiap langkah secara ringkas.

1. `env_check`
2. `session_create` dengan path APK yang diberikan pengguna, aktifkan `copy_apk`.
3. `apk_info`
4. `framework_detect`
5. `apk_signature_info`
6. `decode_pipeline`
7. `manifest_decode`
8. `index_build`
9. `code_search` untuk kata kunci utama yang relevan dengan tujuan analisis
10. `callgraph` untuk method yang paling sering muncul
11. `strings_scan` untuk endpoint dan kredensial yang terlihat
12. `reconstruction_plan`

Output akhir yang diminta:
- Ringkasan package, versi, framework, dan permission penting.
- Daftar 10 komponen utama beserta perannya.
- Peta alur utama berdasarkan hasil callgraph.
- Kandidat file terpenting untuk dibaca lebih detail.
- Rencana rekonstruksi atau modifikasi beserta risikonya.

Jika ada langkah yang gagal, jelaskan penyebabnya dan tool alternatif yang dipakai.
