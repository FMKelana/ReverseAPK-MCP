"""Adapter frida untuk analisis dinamis. Eksperimental dan opsional."""

from __future__ import annotations

import shutil
from pathlib import Path
from typing import Any

from ..jobs import CommandResult, run_command
from .base import AdapterError, BaseAdapter, ToolNotFoundError


class FridaAdapter(BaseAdapter):
    name = "frida"
    aliases = ("frida", "frida-tools")
    version_args = ("--version",)

    def _frida_ps(self) -> str:
        executable = self.settings.toolchain.resolve("frida-ps", ("frida-ps",)) or shutil.which("frida-ps")
        if not executable:
            raise ToolNotFoundError("frida-ps tidak ditemukan. Instal dengan: python -m pip install frida-tools")
        return executable

    async def ps(self, *, device: str = "", timeout: float | None = 60) -> list[dict[str, Any]]:
        """Daftar proses pada device atau emulator."""

        executable = self._frida_ps()
        arguments = [executable, "-D", device] if device else [executable, "-U"]

        result = await run_command(
            arguments, timeout=timeout or 60, max_output_bytes=self.settings.max_output_bytes
        )
        if not result.ok:
            raise AdapterError(f"frida-ps gagal: {result.tail(1500)}")

        processes: list[dict[str, Any]] = []
        for line in result.stdout.splitlines():
            stripped = line.strip()
            if not stripped or stripped.lower().startswith("pid") or set(stripped) <= {"-", " "}:
                continue
            parts = stripped.split(None, 1)
            if len(parts) == 2 and parts[0].isdigit():
                processes.append({"pid": int(parts[0]), "name": parts[1]})
            elif len(parts) == 2:
                processes.append({"pid": None, "name": stripped})
        return processes

    async def run_script(
        self,
        package: str,
        script_path: Path,
        *,
        device: str = "",
        runtime: str = "v8",
        timeout: float | None = 30,
    ) -> CommandResult:
        """Jalankan script hook pada aplikasi target.

        Proses akan dihentikan saat timeout tercapai, sehingga script sebaiknya
        bersifat observasi singkat.
        """

        if not script_path.is_file():
            raise AdapterError(f"Script frida tidak ditemukan: {script_path}")

        arguments = [self.require_executable()]
        arguments += ["-D", device] if device else ["-U"]
        arguments += [
            "-f",
            package,
            "-l",
            str(script_path),
            "--runtime",
            runtime,
            "--exit-on-error",
        ]

        result = await self.run(arguments, timeout=timeout or 30)
        return result
