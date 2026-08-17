"""Canonical data contracts — SINGLE SOURCE OF TRUTH (anti-duplication rule).

Every module imports its dataclasses from here:
    from csmg.types import ChunkRead, SignalVerdict, FlowEvent
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

SENSOR_VERSION = "0.1.0"


@dataclass(frozen=True)
class ChunkRead:
    """A memory chunk as observed by the guard (read-only view).

    metadata: engine-provided provenance (principal_id, session_id, author,
    ts, scope). Keys may be absent -> provenance_mode="poor" (the sensor
    never invents labels, Constitution §4 / SPEC AC3).
    """

    chunk_id: str
    content: str
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class SignalVerdict:
    """Verdict of one detection signal."""

    signal: str  # "mismatch" | "similarity" | "flowgraph"
    fired: bool
    confidence: float  # 1.0 deterministic; heuristic for (b)/(c)
    detail: dict[str, Any] = field(default_factory=dict)  # evidence, never full content


@dataclass(frozen=True)
class FlowEvent:
    """Structured alert event.

    NEVER carries the full sensitive chunk content (AC6 / Constitution §2.3):
    evidence only holds a hash + minimal span.
    """

    ts: str
    sensor_version: str
    signals: list[SignalVerdict]
    severity: str  # "info" | "warn" | "alert"
    chunk_id: str
    origin: dict[str, Any]  # write-side principal/session attribution
    requester: str  # principal that requested the read
    confidence: float
    provenance_mode: str  # "full" | "poor"
    evidence: dict[str, Any]  # {"hash": sha256, "span": ...}

    def to_dict(self) -> dict[str, Any]:
        return {
            "ts": self.ts,
            "sensor_version": self.sensor_version,
            "signals": [vars(s) for s in self.signals],
            "severity": self.severity,
            "chunk_id": self.chunk_id,
            "origin": self.origin,
            "requester": self.requester,
            "confidence": self.confidence,
            "provenance_mode": self.provenance_mode,
            "evidence": self.evidence,
        }