"""Signal (c): who-wrote -> who-read flow graph (SPEC §3, heuristic).

In-memory indexes of writes and reads. A read of a chunk whose writer
differs from the reader and is not authorized is a cross-boundary flow.
Unknown chunks and authorized reads do not fire. No network, no deps.
"""

from __future__ import annotations

from collections.abc import Iterable

from csmg.types import SignalVerdict


class FlowGraph:
    def __init__(self) -> None:
        self._writes: dict[str, str] = {}  # chunk_id -> writing principal
        self._reads: dict[str, int] = {}  # chunk_id -> read count

    def rehydrate(self, write_records: Iterable[tuple[str, str]]) -> int:
        """Prime the write side from ENGINE metadata (KI-8 decision, route 1).

        write_records: (chunk_id, writer_principal) pairs. Detection does
        NOT depend on sensor-side history: the engine's own write metadata
        (e.g. Engram observations.project/created_at) is the source of
        truth, so a fresh process still sees who wrote each chunk.
        Returns the number of write entries loaded.
        """
        n = 0
        for chunk_id, writer in write_records:
            self._writes[chunk_id] = writer
            n += 1
        return n

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