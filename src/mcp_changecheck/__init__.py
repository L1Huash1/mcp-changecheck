"""Inspect MCP tool contract changes without invoking a server or a model."""

from .core import SnapshotError, compare_snapshots, normalize_snapshot

__version__ = "0.3.0"
__all__ = ["SnapshotError", "compare_snapshots", "normalize_snapshot", "__version__"]
