"""Resource MCP untuk mengakses workspace sesi."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .config import get_settings
from .tools.session import load_manifest

MAX_TREE_ENTRIES = 500


def _render_tree(root: Path, max_entries: int = MAX_TREE_ENTRIES) -> str:
    if not root.is_dir():
        return "(sesi belum memiliki file)"

    lines: list[str] = []
    count = 0

    for path in sorted(root.rglob("*")):
        try:
            relative = path.relative_to(root).as_posix()
        except ValueError:
            continue

        if path.is_dir():
            lines.append(f"{relative}/")
        else:
            try:
                size = path.stat().st_size
            except OSError:
                size = -1
            lines.append(f"{relative} ({size} byte)")

        count += 1
        if count >= max_entries:
            lines.append(f"...[dipotong setelah {max_entries} entri]")
            break

    return "\n".join(lines) if lines else "(kosong)"


def register(mcp: Any) -> None:
    @mcp.resource("workspace://sessions", mime_type="application/json")
    def list_sessions_resource() -> str:
        """Daftar sesi yang tersedia di workspace."""

        settings = get_settings()
        rows: list[dict[str, Any]] = []

        for manifest_file in sorted(settings.workspace_root.glob("*/manifest.json")):
            try:
                data = json.loads(manifest_file.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError):
                continue
            apk = data.get("apk", {})
            rows.append(
                {
                    "session_id": data.get("session_id", manifest_file.parent.name),
                    "package": apk.get("package"),
                    "version_name": apk.get("version_name"),
                    "framework": apk.get("framework"),
                    "updated_at": data.get("updated_at"),
                }
            )

        return json.dumps({"sessions": rows}, indent=2, ensure_ascii=False)

    @mcp.resource("workspace://{session_id}/manifest", mime_type="application/json")
    def session_manifest_resource(session_id: str) -> str:
        """Manifest lengkap satu sesi."""

        settings = get_settings()
        try:
            manifest = load_manifest(settings, session_id)
        except (FileNotFoundError, ValueError) as exc:
            return json.dumps({"error": str(exc)})

        return json.dumps(manifest, indent=2, ensure_ascii=False)

    @mcp.resource("workspace://{session_id}/tree", mime_type="text/plain")
    def session_tree_resource(session_id: str) -> str:
        """Daftar file pada workspace sesi, dibatasi agar tetap ringkas."""

        settings = get_settings()
        try:
            session_root = settings.session_dir(session_id)
        except ValueError as exc:
            return f"error: {exc}"

        return _render_tree(session_root)
