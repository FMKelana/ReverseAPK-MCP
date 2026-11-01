"""Skema response standar untuk seluruh tool MCP ReverseAPK."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any, Literal

Status = Literal["ok", "error", "partial"]


@dataclass(slots=True)
class Artifact:
    """Satu file atau direktori hasil tool."""

    path: str
    kind: str = "file"
    bytes: int | None = None

    def to_dict(self) -> dict[str, Any]:
        payload: dict[str, Any] = {"path": self.path, "kind": self.kind}
        if self.bytes is not None:
            payload["bytes"] = self.bytes
        return payload


@dataclass(slots=True)
class ToolResult:
    """Response standar yang dikembalikan setiap tool MCP.

    Agent menerima ringkasan dan daftar artifact, bukan seluruh isi file.
    """

    status: Status
    summary: str
    artifacts: list[Artifact] = field(default_factory=list)
    stats: dict[str, Any] = field(default_factory=dict)
    next_steps: list[str] = field(default_factory=list)
    log_tail: str | None = None
    data: dict[str, Any] | None = None
    error: str | None = None

    def to_dict(self) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "status": self.status,
            "summary": self.summary,
            "artifacts": [artifact.to_dict() for artifact in self.artifacts],
            "stats": self.stats,
            "next_steps": self.next_steps,
        }
        if self.log_tail:
            payload["log_tail"] = self.log_tail
        if self.data is not None:
            payload["data"] = self.data
        if self.error:
            payload["error"] = self.error
        return payload

    def to_json(self, indent: int = 2) -> str:
        return json.dumps(self.to_dict(), indent=indent, ensure_ascii=False, default=str)


def success(summary: str, **kwargs: Any) -> ToolResult:
    return ToolResult(status="ok", summary=summary, **kwargs)


def partial(summary: str, **kwargs: Any) -> ToolResult:
    return ToolResult(status="partial", summary=summary, **kwargs)


def failure(summary: str, error: str, **kwargs: Any) -> ToolResult:
    return ToolResult(status="error", summary=summary, error=error, **kwargs)
