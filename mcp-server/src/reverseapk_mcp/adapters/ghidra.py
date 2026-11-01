"""Adapter Ghidra headless untuk analisis native library. Opsional."""

from __future__ import annotations

from pathlib import Path
from typing import Sequence

from ..jobs import CommandResult
from .base import AdapterError, BaseAdapter


class GhidraAdapter(BaseAdapter):
    name = "ghidra_headless"
    aliases = ("analyzeHeadless", "analyzeHeadless.bat")
    version_args = ()

    async def analyze(
        self,
        project_dir: Path,
        binary_path: Path,
        *,
        project_name: str = "ReverseAPK",
        script_path: Path | None = None,
        extra_args: Sequence[str] = (),
        timeout: float | None = 1800,
    ) -> CommandResult:
        """Import dan analisis satu binary di project Ghidra sementara."""

        if not binary_path.is_file():
            raise AdapterError(f"Binary tidak ditemukan: {binary_path}")

        project_dir.mkdir(parents=True, exist_ok=True)
        arguments = [str(project_dir), project_name, "-import", str(binary_path), "-deleteProject"]

        if script_path is not None:
            if not script_path.is_file():
                raise AdapterError(f"Script Ghidra tidak ditemukan: {script_path}")
            arguments += [
                "-scriptPath",
                str(script_path.parent),
                "-postScript",
                script_path.name,
            ]

        arguments += list(extra_args)

        result = await self.run(arguments, cwd=project_dir.parent, timeout=timeout)
        if not result.ok:
            raise AdapterError(
                f"Ghidra headless gagal dengan kode {result.exit_code}: {result.tail(2000)}"
            )
        return result
