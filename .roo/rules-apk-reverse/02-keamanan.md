# Batas Keamanan


## Path dan File
- Operasi tulis hanya di dalam `workspaces/<session_id>/`.
- Jangan mengubah file di `tools/`, `config/toolchain.json`, atau `samples/` kecuali membuat file baru.
- Tolak path yang mengandung `..`, drive lain, atau UNC path.
- Maksimal 400 baris per pembacaan file; gunakan pagination.

## Eksekusi
- Jangan memanggil shell mentah dengan string gabungan.
- Tool hanya menerima argumen terstruktur.

## Rahasia
- Bila menemukan kredensial, cukup catat lokasinya dan sarankan rotasi.

## Device
- Dynamic analysis hanya pada emulator atau device riset.
- Jangan menjalankan frida pada perangkat harian.
- Lepas instalasi aplikasi uji setelah selesai bila diminta.

## Pelaporan
Selalu akhiri dengan ringkasan:
1. Apa yang berhasil dibuktikan.
2. Apa yang masih asumsi.
3. Risiko atau batasan yang tersisa.
