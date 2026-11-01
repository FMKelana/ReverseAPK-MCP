"""Adapter zipalign untuk alignment APK sebelum signing."""

from __future__ import annotations

from pathlib import Path

from ..jobs import CommandResult
from .base import AdapterError, BaseAdapter


class ZipalignAdapter(BaseAdapter):
    name = "zipalign"
    aliases = ("zipalign",)
    version_args = ("-h",)

    async def align(
        self,
        source_apk: Path,
        target_apk: Path,
        *,
        alignment: int = 4,
        timeout: float | None = None,
    ) -> CommandResult:
        if not source_apk.is_file():
            raise AdapterError(f"APK sumber tidak ditemukan: {source_apk}")
        if alignment not in {4, 8, 16, 32, 64}:
            raise AdapterError(f"Nilai alignment tidak wajar: {alignment}")

        target_apk.parent.mkdir(parents=True, exist_ok=True)
        result = await self.run(
            ["-f", "-p", str(alignment), str(source_apk), str(target_apk)],
            timeout=timeout,
        )
        if not result.ok:
            raise AdapterError(
                f"zipalign gagal dengan kode {result.exit_code}: {result.tail(1500)}"
            )
        if not target_apk.is_file():
            raise AdapterError("zipalign selesai tanpa menghasilkan file target")
        return result

    async def check(self, apk_path: Path, *, timeout: float | None = None) -> CommandResult:
        return await self.run(["-c", "-v", "4", str(apk_path)], timeout=timeout)
