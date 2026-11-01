"""Adapter gradle untuk build project Android."""

from __future__ import annotations

import os
from pathlib import Path

from ..config import ensure_within
from ..jobs import CommandResult, run_command
from .base import AdapterError, BaseAdapter


class GradleAdapter(BaseAdapter):
    name = "gradle"
    aliases = ("gradle",)
    version_args = ("--version",)

    async def assemble(
        self,
        project_dir: Path,
        *,
        task: str = "assembleDebug",
        timeout: float | None = None,
    ) -> CommandResult:
        workdir = ensure_within(project_dir, [self.settings.workspace_root], "project_dir")
        if not workdir.is_dir():
            raise AdapterError(f"Direktori project tidak ditemukan: {workdir}")

        timeout_value = timeout if timeout is not None else self.settings.default_timeout
        wrapper = workdir / ("gradlew.bat" if os.name == "nt" else "gradlew")

        if wrapper.is_file():
            command = [str(wrapper), task, "--no-daemon", "--stacktrace"]
        else:
            command = [self.require_executable(), task, "--no-daemon", "--stacktrace"]

        result = await run_command(
            command,
            cwd=workdir,
            timeout=timeout_value,
            max_output_bytes=self.settings.max_output_bytes,
        )
        if not result.ok:
            raise AdapterError(
                f"gradle {task} gagal dengan kode {result.exit_code}: {result.tail(2500)}"
            )
        return result

    @staticmethod
    def find_apks(project_dir: Path) -> list[Path]:
        """Cari APK hasil build, terbaru lebih dulu."""

        found = {
            path.resolve()
            for path in project_dir.glob("**/build/outputs/apk/**/*.apk")
            if path.is_file()
        }
        return sorted(found, key=lambda path: path.stat().st_mtime, reverse=True)
