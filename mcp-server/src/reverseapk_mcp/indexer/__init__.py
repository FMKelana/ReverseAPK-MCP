"""Indexer kode untuk pencarian cepat dan hemat token."""

from __future__ import annotations

from .db import build_index, index_stats, read_slice, references, search

__all__ = ["build_index", "index_stats", "read_slice", "references", "search"]
