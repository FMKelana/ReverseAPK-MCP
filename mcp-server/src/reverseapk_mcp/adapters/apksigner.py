"""Adapter apksigner untuk signing dan verifikasi APK."""

from __future__ import annotations

from pathlib import Path

from ..jobs import CommandResult
from .base import AdapterError, BaseAdapter


class ApksignerAdapter(BaseAdapter):
    name = "apksigner"
    aliases = ("apksigner",)
    version_args = ("--version",)

    async def sign(
        self,
        apk_path: Path,
        output_apk: Path,
        *,
        keystore: Path,
        alias: str,
        storepass: str,
        keypass: str | None = None,
        timeout: float | None = None,
    ) -> CommandResult:
        """Sign APK dengan keystore lokal.

        Password hanya diteruskan sebagai argumen proses dan tidak ditulis ke log
        manifest maupun response tool.
        """

        if not apk_path.is_file():
            raise AdapterError(f"APK tidak ditemukan: {apk_path}")
        if not keystore.is_file():
            raise AdapterError(f"Keystore tidak ditemukan: {keystore}")

        output_apk.parent.mkdir(parents=True, exist_ok=True)
        arguments = [
            "sign",
            "--ks",
            str(keystore),
            "--ks-key-alias",
            alias,
            "--ks-pass",
            f"pass:{storepass}",
            "--out",
            str(output_apk),
        ]
        if keypass:
            arguments += ["--key-pass", f"pass:{keypass}"]
        arguments.append(str(apk_path))

        result = await self.run(arguments, cwd=output_apk.parent, timeout=timeout)
        if not result.ok:
            raise AdapterError(
                f"apksigner gagal dengan kode {result.exit_code}: {result.tail(2000)}"
            )
        if not output_apk.is_file():
            raise AdapterError("apksigner selesai tanpa menghasilkan APK bertanda tangan")
        return result

    async def verify(self, apk_path: Path, *, timeout: float | None = None) -> CommandResult:
        """Verifikasi tanda tangan APK."""

        result = await self.run(["verify", "--verbose", str(apk_path)], timeout=timeout)
        if not result.ok:
            raise AdapterError(
                f"Verifikasi tanda tangan gagal dengan kode {result.exit_code}: {result.tail(1500)}"
            )
        return result

    async def print_certs(self, apk_path: Path, *, timeout: float | None = 120) -> CommandResult:
        """Tampilkan sertifikat penandatangan APK."""

        result = await self.run(
            ["verify", "--print-certs", "--verbose", str(apk_path)], timeout=timeout
        )
        if not result.ok:
            raise AdapterError(
                f"Sertifikat gagal dibaca dengan kode {result.exit_code}: {result.tail(1500)}"
            )
        return result
