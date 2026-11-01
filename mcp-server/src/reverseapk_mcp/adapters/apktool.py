"""Adapter apktool untuk decode dan build APK."""

from __future__ import annotations

from pathlib import Path

from ..jobs import CommandResult
from .base import AdapterError, BaseAdapter


class ApktoolAdapter(BaseAdapter):
    name = "apktool"
    aliases = ("apktool",)
    version_args = ("--version",)

    async def decode(
        self,
        apk_path: Path,
        output_dir: Path,
        *,
        force: bool = True,
        no_src: bool = False,
        no_res: bool = False,
        timeout: float | None = None,
    ) -> CommandResult:
        """Decode APK menjadi smali dan resource."""

        arguments = ["decode"]
        if force:
            arguments.append("--force")
        if no_src:
            arguments.append("--no-src")
        if no_res:
            arguments.append("--no-res")
        arguments += ["--output", str(output_dir), str(apk_path)]

        result = await self.run(arguments, cwd=output_dir.parent, timeout=timeout)
        if not result.ok:
            raise AdapterError(
                f"apktool decode gagal dengan kode {result.exit_code}: {result.tail(2000)}"
            )
        return result

    async def build(
        self,
        project_dir: Path,
        output_apk: Path,
        *,
        use_aapt2: bool = True,
        timeout: float | None = None,
    ) -> CommandResult:
        """Build ulang project hasil decode menjadi APK."""

        if not project_dir.is_dir():
            raise AdapterError(f"Direktori project tidak ditemukan: {project_dir}")

        arguments = ["build", "--force-all"]
        if use_aapt2:
            arguments.append("--use-aapt2")
        arguments += ["--output", str(output_apk), str(project_dir)]

        output_apk.parent.mkdir(parents=True, exist_ok=True)
        result = await self.run(arguments, cwd=project_dir.parent, timeout=timeout)
        if not result.ok:
            raise AdapterError(
                f"apktool build gagal dengan kode {result.exit_code}: {result.tail(2000)}"
            )
        if not output_apk.is_file():
            raise AdapterError(f"apktool build selesai tanpa menghasilkan {output_apk.name}")
        return result
