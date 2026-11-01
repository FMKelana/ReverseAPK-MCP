# Kebijakan Keamanan

## Model Ancaman

MCP server menjalankan tool CLI terhadap file APK yang bisa saja berbahaya bagi host.
Karena proyek berjalan native di Windows tanpa container, kontrol berikut wajib dipertahankan.

## Kontrol Wajib

1. **Tanpa shell bebas.** Semua proses dijalankan dengan list argumen melalui
   `asyncio.create_subprocess_exec`, bukan `shell=True`. Tidak ada tool yang menerima string perintah mentah.
2. **Allowlist path.** Path masukan dan keluaran harus berada di `workspaces/`, `samples/`, atau `tools/`.
   Path traversal seperti `..` ditolak sebelum eksekusi.
3. **Timeout dan terminasi.** Setiap job punya timeout; saat terlampaui proses dihentikan beserta child process.
4. **Batas output.** Output besar dipotong dan disimpan ke file log; hanya ekor log yang dikembalikan ke agent.
5. **Tanpa secret di repo.** Keystore, `.env`, dan `config/toolchain.json` tidak boleh di-commit.
6. **Privilege minimal.** Jalankan MCP server dengan akun Windows non-admin.
7. **Isolasi opsional.** Untuk APK yang tidak dikenal, jalankan analisis di Windows Sandbox,
   mesin virtual terpisah, atau perangkat uji khusus.

## Penanganan APK Tidak Tepercaya

- Jangan membuka APK di luar pipeline tool.
- Nonaktifkan fitur dynamic analysis sampai perangkat uji terisolasi tersedia.
- Jalankan `frida` hanya pada emulator atau device riset, bukan perangkat harian.
- Periksa `log_tail` setiap job untuk mendeteksi perilaku aneh dari tool.

## Melaporkan Kerentanan

Laporkan temuan pada proyek ini secara privat kepada pemilik repositori, sertakan langkah reproduksi
dan dampaknya. Jangan mempublikasikan detail sebelum ada perbaikan.
