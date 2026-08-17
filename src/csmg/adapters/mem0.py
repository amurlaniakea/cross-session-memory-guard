"""mem0 adapter — thin read-only (API verified in B0 spike, mem0ai 2.0.18).

Read path: Memory.search / get_all with `filters` (user_id/agent_id is the
tenant boundary) and Memory.get(memory_id). The adapter NEVER instantiates
the write path (add/update) and never creates the LLM/embedder beyond what
the operator's own Memory instance already holds. Result SHAPE was not
exercised end-to-end in the spike (no operator config), so field extraction
is defensive: unexpected shapes raise AdapterError instead of guessing.
"""

from __future__ import annotations

from csmg.adapters import AdapterError, register
from csmg.types import ChunkRead


class Mem0Adapter:
    def __init__(self, memory) -> None:
        self._memory = memory

    def _filter(self, principal: str | None) -> dict | None:
        return {"user_id": principal} if principal else None

    def list_chunks(self, principal: str | None = None) -> list[str]:
        try:
            result = self._memory.get_all(filters=self._filter(principal), top_k=1000)
        except Exception as e:  # noqa: BLE001 - SDK errors surface as AdapterError
            raise AdapterError(f"mem0 get_all failed: {e}") from e
        entries = result if isinstance(result, list) else result.get("results", [])
        ids = []
        for e in entries:
            eid = e.get("id") if isinstance(e, dict) else getattr(e, "id", None)
            if eid is None:
                raise AdapterError("mem0 result entry missing id (unexpected shape)")
            ids.append(str(eid))
        return ids

    def get_chunk(self, chunk_id: str) -> ChunkRead:
        try:
            entry = self._memory.get(chunk_id)
        except Exception as e:  # noqa: BLE001
            raise AdapterError(f"mem0 get failed: {e}") from e
        if entry is None:
            raise AdapterError(f"mem0 chunk not found: {chunk_id}")
        d = entry if isinstance(entry, dict) else getattr(entry, "dict", lambda: {})()
        content = d.get("text") or d.get("content")
        if content is None:
            raise AdapterError("mem0 entry missing text/content (unexpected shape)")
        return ChunkRead(
            chunk_id=str(d.get("id", chunk_id)),
            content=content,
            metadata={"principal_id": (d.get("user_id") or None)},
        )


register("mem0", Mem0Adapter)