"""Signal (c): who-wrote -> who-read flow graph (SPEC §3, heuristic).

In-memory indexes of writes and reads. A read of a chunk whose writer
differs from the reader and is not authorized is a cross-boundary flow.
Unknown chunks and authorized reads do not fire. No network, no deps.
"""

from __future__ import annotations

from csmg.types import SignalVerdict


class FlowGraph:
    def __init__(self) -> None:
        self._writes: dict[str, str] = {}  # chunk_id -> writing principal
        self._reads: dict[str, int] = {}  # chunk_id -> read count

    def record_write(self, principal: str, chunk_id: str) -> None:
        self._writes[chunk_id] = principal

    def record_read(self, chunk_id: str, reader: str, authorized: bool) -> SignalVerdict:
        self._reads[chunk_id] = self._reads.get(chunk_id, 0) + 1
        writer = self._writes.get(chunk_id)
        if writer is None:
            return SignalVerdict(
                signal="flowgraph",
                fired=False,
                confidence=0.0,
                detail={"reason": "unknown_chunk"},
            )
        if authorized or writer == reader:
            return SignalVerdict(
                signal="flowgraph",
                fired=False,
                confidence=1.0,
                detail={"reason": "authorized"},
            )
        return SignalVerdict(
            signal="flowgraph",
            fired=True,
            confidence=1.0,
            detail={
                "reason": "cross_boundary",
                "writer": writer,
                "reader": reader,
                "chunk_id": chunk_id,
            },
        )