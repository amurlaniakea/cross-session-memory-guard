"""langmem adapter — thin read-only (API verified in B0 spike, langmem 0.0.30).

Read path: langgraph BaseStore.get/search with `namespace` tuples — the
namespace IS the tenant boundary (default ('memories', '{user_id}')). The
adapter needs an operator-provided store instance; it never writes (put/
delete are out of contract). Functional integration requires a configured
store (InMemoryStore is fine for tests) and is exercised via fake stores
here; real langgraph stores are deferred to slow tests.
"""

from __future__ import annotations

from csmg.adapters import AdapterError, register
from csmg.types import ChunkRead


class LangMemAdapter:
    def __init__(self, store, namespace_prefix: tuple[str, ...] = ("memories",)) -> None:
        self._store = store
        self._prefix = namespace_prefix

    def _ns(self, principal: str | None) -> tuple[str, ...]:
        return self._prefix + ((principal,) if principal else ())

    def list_chunks(self, principal: str | None = None) -> list[str]:
        try:
            items = self._store.search(self._ns(principal), limit=1000)
        except Exception as e:  # noqa: BLE001
            raise AdapterError(f"langmem search failed: {e}") from e
        return [getattr(it, "key", None) or it["key"] for it in items]

    def get_chunk(self, chunk_id: str) -> ChunkRead:
            # langmem keys live under per-user namespaces; the public API does
            # not expose "find key anywhere under prefix", so we list under the
            # prefix and filter by key (read-only, bounded by limit).
            try:
                items = self._store.search(self._prefix, limit=1000)
            except Exception as e:  # noqa: BLE001
                raise AdapterError(f"langmem search failed: {e}") from e
            hit = next((it for it in items if str(getattr(it, "key", "")) == chunk_id), None)
            if hit is None:
                raise AdapterError(f"langmem chunk not found: {chunk_id}")
            value = hit.value if hasattr(hit, "value") else {}
            content = value.get("content") if isinstance(value, dict) else str(value)
            if content is None:
                raise AdapterError("langmem entry missing content (unexpected shape)")
            return ChunkRead(chunk_id=chunk_id, content=content, metadata={"principal_id": None})


register("langmem", LangMemAdapter)