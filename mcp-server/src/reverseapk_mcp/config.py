"""Konfigurasi runtime ReverseAPK MCP server.

Semua path divalidasi agar berada di dalam root yang diizinkan. Konfigurasi
toolchain dibaca dari ``config/toolchain.json`` dan jika entri kosong akan
jatuh ke pencarian PATH.
"""

from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path
from typing import Iterable, Sequence

PACKAGE_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = PACKAGE_DIR.parents[2]

SESSION_ID_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,79}$")

DEFAULT_TOOL_ENTRIES: dict[str, str] = {
    "java": "",
    "apktool": "",
    "jadx": "",
    "aapt2": "",
    "aapt": "",
    "apksigner": "",
    "zipalign": "",
    "adb": "",
    "gradle": "",
    "frida": "",
    "ghidra_headless": "",
}

TOOL_ALIASES: dict[str, tuple[str, ...]] = {
    "python": ("python", "python3", "py"),
    "java": ("java",),
    "apktool": ("apktool",),
    "jadx": ("jadx",),
    "aapt2": ("aapt2",),
    "aapt": ("aapt",),
    "apksigner": ("apksigner",),
    "zipalign": ("zipalign",),
    "adb": ("adb",),
    "gradle": ("gradle",),
    "frida": ("frida",),
    "ghidra_headless": ("analyzeHeadless",),
}


class ConfigError(RuntimeError):
    """Konfigurasi tidak valid atau tidak lengkap."""


class PathNotAllowedError(ConfigError, ValueError):
    """Path berada di luar root yang diizinkan.

    Mewarisi ``ValueError`` agar pemanggil bisa menangkap pelanggaran path
    bersama error validasi argumen lain.
    """


def ensure_within(path: str | Path, roots: Iterable[str | Path], label: str = "path") -> Path:
    """Pastikan ``path`` berada di dalam salah satu ``roots``.

    Mengembalikan path yang sudah di-resolve. Melempar :class:`PathNotAllowedError`
    jika path keluar dari root, misalnya karena ``..``.
    """

    candidate = Path(path).expanduser().resolve()
    for root in roots:
        root_path = Path(root).expanduser().resolve()
        try:
            candidate.relative_to(root_path)
            return candidate
        except ValueError:
            continue
    allowed = ", ".join(str(Path(root).resolve()) for root in roots)
    raise PathNotAllowedError(f"{label} di luar root yang diizinkan: {candidate} (allowed: {allowed})")


def _env_int(name: str, default: int) -> int:
    raw = os.environ.get(name)
    if not raw:
        return default
    try:
        value = int(raw)
    except ValueError as exc:
        raise ConfigError(f"{name} harus berupa angka, didapat: {raw!r}") from exc
    return value if value > 0 else default


def _env_float(name: str, default: float) -> float:
    raw = os.environ.get(name)
    if not raw:
        return default
    try:
        value = float(raw)
    except ValueError as exc:
        raise ConfigError(f"{name} harus berupa angka, didapat: {raw!r}") from exc
    return value if value > 0 else default


@lru_cache(maxsize=1)
def detect_java_home() -> str | None:
    """Deteksi direktori JDK untuk tool seperti keytool dan javac.

    Urutan: ``JAVA_HOME``, lalu properti ``java.home`` dari executable java.
    Penting karena shim ``javapath`` tidak menyediakan keytool.
    """

    env_home = os.environ.get("JAVA_HOME", "").strip()
    if env_home:
        candidate = Path(env_home)
        if (candidate / "bin" / ("javac.exe" if os.name == "nt" else "javac")).is_file():
            return str(candidate)

    java = shutil.which("java")
    if not java:
        return None

    try:
        result = subprocess.run(
            [java, "-XshowSettings:properties", "-version"],
            capture_output=True,
            text=True,
            timeout=20,
        )
    except (OSError, subprocess.SubprocessError):
        return None

    for line in (result.stderr or "").splitlines():
        if "java.home" not in line or "=" not in line:
            continue
        value = line.split("=", 1)[1].strip()
        if not value:
            continue
        home = Path(value)
        if (home / "bin" / ("javac.exe" if os.name == "nt" else "javac")).is_file():
            return str(home)

    return None


@dataclass(slots=True)
class Toolchain:
    """Pemetaan nama tool ke executable dan resolver PATH."""

    entries: dict[str, str] = field(default_factory=dict)

    def resolve(self, name: str, aliases: Sequence[str] = ()) -> str | None:
        candidates: list[str] = [name, *aliases, *TOOL_ALIASES.get(name, ())]

        for candidate in candidates:
            configured = self.entries.get(candidate)
            if not configured:
                continue
            expanded = Path(os.path.expandvars(os.path.expanduser(str(configured))))
            if expanded.is_file():
                return str(expanded)
            found = shutil.which(str(configured))
            if found:
                return found

        for candidate in candidates:
            found = shutil.which(candidate)
            if found:
                return found

        jdk_home = detect_java_home()
        if jdk_home:
            suffix = ".exe" if os.name == "nt" else ""
            jdk_tool = Path(jdk_home) / "bin" / f"{name}{suffix}"
            if jdk_tool.is_file():
                return str(jdk_tool)

        return None

    def describe(self) -> dict[str, str]:
        return {name: value for name, value in self.entries.items() if value}


@dataclass(slots=True)
class Settings:
    """Konfigurasi lengkap satu proses MCP server."""

    home: Path
    config_path: Path
    toolchain: Toolchain
    max_output_bytes: int = 64_000
    default_timeout: float = 600.0
    log_level: str = "INFO"

    @property
    def workspace_root(self) -> Path:
        return self.home / "workspaces"

    @property
    def samples_root(self) -> Path:
        return self.home / "samples"

    @property
    def tools_root(self) -> Path:
        return self.home / "tools"

    @property
    def read_roots(self) -> tuple[Path, ...]:
        return (self.workspace_root, self.samples_root)

    def ensure_directories(self) -> None:
        for directory in (self.workspace_root, self.samples_root, self.tools_root):
            directory.mkdir(parents=True, exist_ok=True)

    def session_dir(self, session_id: str) -> Path:
        if not SESSION_ID_PATTERN.match(session_id):
            raise PathNotAllowedError(
                f"session_id tidak valid: {session_id!r}. Gunakan huruf, angka, titik, garis bawah, atau strip."
            )
        return ensure_within(self.workspace_root / session_id, [self.workspace_root], "session_id")


def load_settings() -> Settings:
    env_home = os.environ.get("REVERSEAPK_HOME", "").strip()
    home = Path(env_home).expanduser() if env_home else PROJECT_ROOT
    home = home.resolve()
    if not home.exists():
        raise ConfigError(
            f"REVERSEAPK_HOME tidak ditemukan: {home}. Set variabel ini ke root repository ReverseAPK."
        )

    config_path = home / "config" / "toolchain.json"
    entries: dict[str, str] = dict(DEFAULT_TOOL_ENTRIES)

    if config_path.is_file():
        try:
            raw = json.loads(config_path.read_text(encoding="utf-8-sig"))
        except json.JSONDecodeError as exc:
            raise ConfigError(f"JSON tidak valid pada {config_path}: {exc}") from exc
        if not isinstance(raw, dict):
            raise ConfigError(f"{config_path} harus berisi objek JSON.")
        for key, value in raw.items():
            if key.startswith("$") or not isinstance(value, str):
                continue
            entries[key] = value

    return Settings(
        home=home,
        config_path=config_path,
        toolchain=Toolchain(entries=entries),
        max_output_bytes=_env_int("REVERSEAPK_MAX_OUTPUT_BYTES", 64_000),
        default_timeout=_env_float("REVERSEAPK_DEFAULT_TIMEOUT", 600.0),
        log_level=os.environ.get("REVERSEAPK_LOG_LEVEL", "INFO").upper(),
    )


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Ambil settings proses saat ini, di-cache agar tidak dibaca berulang."""

    settings = load_settings()
    settings.ensure_directories()
    return settings


def reset_settings_cache() -> None:
    """Bersihkan cache settings. Dipakai oleh unit test."""

    get_settings.cache_clear()
    detect_java_home.cache_clear()
