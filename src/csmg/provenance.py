"""Provenance resolution for memory chunks (SPEC §4, AC3).

Extracts origin labels from engine-provided metadata. When the engine does
not provide a principal label the sensor MUST NOT invent one (Constitution
§4): it degrades to provenance_mode="poor" and signals that depend on
attribution declare themselves inapplicable.
"""

from __future__ import annotations

from dataclasses import dataclass

from csmg.types import ChunkRead


@dataclass(frozen=True)
class Provenance:
    principal_id: str | None
    session_id: str | None
    author: str | None
    ts: str | None
    scope: str | None
    mode: str  # "full" | "poor"

    @property
    def attributable(self) -> bool:
        """True only when we have a real principal label (never invented)."""
        return self.mode == "full" and self.principal_id is not None


def resolve(chunk: ChunkRead) -> Provenance:
    """Extract provenance from a chunk's metadata.

    metadata keys read: principal_id, session_id, author, ts, scope. Any
    missing key stays None. mode="full" only when principal_id is present;
    otherwise "poor" (declared, never guessed).
    """
    md = chunk.metadata or {}
    principal = md.get("principal_id")
    mode = "full" if principal else "poor"
    return Provenance(
        principal_id=principal,
        session_id=md.get("session_id"),
        author=md.get("author"),
        ts=md.get("ts"),
        scope=md.get("scope"),
        mode=mode,
    )