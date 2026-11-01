"""Adapter jadx untuk dekompilasi DEX ke Java."""

from __future__ import annotations

from pathlib import Path

from ..jobs import CommandResult
from .base import AdapterError, BaseAdapter


class JadxAdapter(BaseAdapter):
    name = "jadx"
    aliases = ("jadx",)
    version_args = ("--version",)

    async def decompile(
        self,
        apk_path: Path,
        output_dir: Path,
        *,
        export_gradle: bool = False,
        no_resources: bool = False,
        threads: int = 0,
        show_bad_code: bool = False,
        timeout: float | None = None,
    ) -> CommandResult:
        """Dekompilasi APK ke sumber Java.

        Args:
            export_gradle: simpan sebagai project Gradle dengan ``--export-gradle``.
            no_resources: lewati decode resource.
            threads: jumlah thread, 0 berarti default jadx.
        """

        output_dir.mkdir(parents=True, exist_ok=True)
        arguments = ["--output-dir", str(output_dir)]

        if export_gradle:
            arguments += ["--export-gradle", "--export-gradle-type", "auto"]
        if no_resources:
            arguments.append("--no-res")
        if show_bad_code:
            arguments.append("--show-bad-code")
        if threads > 0:
            arguments += ["--threads-count", str(threads)]

        arguments.append(str(apk_path))

        result = await self.run(arguments, cwd=output_dir.parent, timeout=timeout)
        if not result.ok:
            raise AdapterError(
                f"jadx gagal dengan kode {result.exit_code}: {result.tail(2000)}"
            )
        return result

    async def single_class(
        self,
        apk_path: Path,
        class_name: str,
        output_path: Path,
        *,
        timeout: float | None = None,
    ) -> CommandResult:
        """Dekompilasi satu kelas saja, berguna untuk hemat waktu."""

        output_path.parent.mkdir(parents=True, exist_ok=True)
        arguments = [
            "--single-class",
            class_name,
            "--single-class-output",
            str(output_path),
            str(apk_path),
        ]

        result = await self.run(arguments, cwd=output_path.parent, timeout=timeout)
        if not result.ok:
            raise AdapterError(
                f"jadx single-class gagal dengan kode {result.exit_code}: {result.tail(2000)}"
            )
        return result
