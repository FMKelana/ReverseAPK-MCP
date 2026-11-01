"""Adapter aapt2 dan aapt untuk membaca metadata APK."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from .base import AdapterError, BaseAdapter, ToolNotFoundError

_QUOTED = re.compile(r"'([^']*)'")


def _first_quoted(line: str) -> str | None:
    match = _QUOTED.search(line)
    return match.group(1) if match else None


def _attr(line: str, key: str) -> str | None:
    match = re.search(rf"\b{re.escape(key)}='([^']*)'", line)
    return match.group(1) if match else None


def _to_int(value: str | None) -> int | None:
    if value is None:
        return None
    try:
        return int(value)
    except ValueError:
        return None


def parse_badging(text: str) -> dict[str, Any]:
    """Ubah keluaran ``aapt2 dump badging`` menjadi dictionary."""

    result: dict[str, Any] = {
        "package": None,
        "version_code": None,
        "version_name": None,
        "min_sdk": None,
        "target_sdk": None,
        "label": None,
        "launchable_activity": None,
        "debuggable": False,
        "permissions": [],
        "features": [],
        "native_code": [],
        "densities": [],
    }

    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line:
            continue

        if line.startswith("package:"):
            result["package"] = _attr(line, "name")
            result["version_code"] = _to_int(_attr(line, "versionCode"))
            result["version_name"] = _attr(line, "versionName")

        elif line.startswith("sdkVersion:"):
            result["min_sdk"] = _to_int(_first_quoted(line))

        elif line.startswith("targetSdkVersion:"):
            result["target_sdk"] = _to_int(_first_quoted(line))

        elif line.startswith("uses-permission:"):
            name = _attr(line, "name")
            if name and name not in result["permissions"]:
                result["permissions"].append(name)

        elif line.startswith("uses-permission-sdk-23:"):
            name = _attr(line, "name")
            if name and name not in result["permissions"]:
                result["permissions"].append(name)

        elif line.startswith("uses-feature:"):
            name = _attr(line, "name") or _first_quoted(line)
            if name:
                result["features"].append(
                    {"name": name, "required": "required='false'" not in line}
                )

        elif line.startswith("application-label:"):
            if result["label"] is None:
                result["label"] = _first_quoted(line)

        elif line.startswith("launchable-activity:"):
            result["launchable_activity"] = _attr(line, "name")

        elif line.startswith("native-code:"):
            result["native_code"] = _QUOTED.findall(line)

        elif line.startswith("densities:"):
            value = line.split(":", 1)[1].strip().strip("'")
            result["densities"] = [item for item in value.split("' '") if item]

        elif line.startswith("application-debuggable"):
            result["debuggable"] = True

    return result


class _BadgingAdapter(BaseAdapter):
    """Mixin adapter yang mendukung ``dump badging``."""

    async def dump_badging(self, apk_path: str | Path, timeout: float | None = None) -> dict[str, Any]:
        try:
            result = await self.run(["dump", "badging", str(apk_path)], timeout=timeout)
        except ToolNotFoundError:
            raise
        except OSError as exc:
            raise AdapterError(f"Gagal menjalankan {self.name}: {exc}") from exc

        if not result.ok:
            raise AdapterError(
                f"{self.name} dump badging gagal dengan kode {result.exit_code}: {result.tail(1500)}"
            )

        return parse_badging(result.stdout)


class Aapt2Adapter(_BadgingAdapter):
    name = "aapt2"
    aliases = ("aapt2",)
    version_args = ("version",)


class AaptAdapter(_BadgingAdapter):
    name = "aapt"
    aliases = ("aapt",)
    version_args = ("version",)
