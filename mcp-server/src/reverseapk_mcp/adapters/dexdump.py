"""Adapter dexdump dari Android build-tools."""

from __future__ import annotations

import os
from pathlib import Path

from ..jobs import CommandResult
from .base import AdapterError, BaseAdapter


class DexdumpAdapter(BaseAdapter):
    name = "dexdump"
    aliases = ("dexdump",)
    version_args = ("-h",)

    @property
    def executable(self) -> str | None:
        resolved = super().executable
        if resolved:
            return resolved

        aapt2 = self.settings.toolchain.resolve("aapt2", ("aapt2",))
        if aapt2:
            suffix = ".exe" if os.name == "nt" else ""
            candidate = Path(aapt2).parent / f"dexdump{suffix}"
            if candidate.is_file():
                return str(candidate)
        return None

    async def header(self, dex_path: Path, *, timeout: float | None = 180) -> CommandResult:
        """Ambil header dan ringkasan DEX tanpa disassembly penuh."""

        if not dex_path.is_file():
            raise AdapterError(f"File DEX tidak ditemukan: {dex_path}")

        result = await self.run(["-f", str(dex_path)], timeout=timeout)
        if not result.ok:
            raise AdapterError(
                f"dexdump gagal dengan kode {result.exit_code}: {result.tail(1500)}"
            )
        return result

    async def disassemble(
        self,
        dex_path: Path,
        *,
        timeout: float | None = 300,
    ) -> CommandResult:
        """Disassembly penuh satu DEX. Output bisa sangat besar."""

        result = await self.run(["-d", str(dex_path)], timeout=timeout)
        if not result.ok:
            raise AdapterError(
                f"dexdump -d gagal dengan kode {result.exit_code}: {result.tail(1500)}"
            )
        return result
