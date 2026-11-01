# Tambah Fitur di Atas Hasil Rekonstruksi

1. Pastikan baseline sudah lolos `smoke_test` dan `fidelity_check`.
2. Tentukan target fitur baru dan batas perubahannya.
3. Bila memakai jalur A, edit smali dengan perubahan minimal dan terisolasi.
4. Bila memakai jalur B, tambahkan modul baru pada project Kotlin hasil `kotlin_scaffold`.
5. Perbarui `docs/SPEC.md` dengan kebutuhan fitur, alur, dan kriteria uji.
6. Jalankan `gradle_build` atau `rebuild_and_sign`.
7. Jalankan `smoke_test` dan verifikasi fitur baru berjalan.
8. Jalankan `fidelity_check` untuk memastikan fitur lama tidak rusak.

Aturan:
- Jangan menambah permission baru tanpa alasan yang jelas.
- Jangan menghapus pemeriksaan keamanan atau validasi input.
- Sertakan bukti path dan baris kode untuk setiap perubahan penting.
- Akhiri dengan ringkasan dampak, risiko, dan cara menguji.
