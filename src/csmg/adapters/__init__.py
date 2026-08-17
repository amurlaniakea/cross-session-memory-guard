"""ReadPort protocol + adapter registry (SPEC §4, Constitution §4).

Every adapter is READ-ONLY: it must never expose write methods. The
registry resolves adapters by name; the monitor/CLI import all adapters
via import_all(). Adapters signal failures with AdapterError, and
safe_call() is the fail-open wrapper (Constitution §2.1, AC5): an adapter
failure degrades the sensor, never the agent.
"""

from __future__ import annotations

import importlib
import logging
from collections.abc import Callable
from typing import Protocol, TypeVar

from csmg.types import ChunkRead

logger = logging.getLogger("csmg.adapters")

T = TypeVar("T")


class AdapterError(RuntimeError):
    """Adapter-level failure (broken store, missing data, missing config...)."""


class ReadPort(Protocol):
    """Minimal read-only contract every memory backend must satisfy.

    list_chunks(principal=None): ids of chunks visible to the principal; if
    principal is None, unattributed/provenance-poor chunks (adapter-defined
    semantics, never invented labels).
    get_chunk(chunk_id): ChunkRead with engine-provided metadata.
    """

    def list_chunks(self, principal: str | None = None) -> list[str]: ...

    def get_chunk(self, chunk_id: str) -> ChunkRead: ...


_REGISTRY: dict[str, type] = {}


def register(name: str, cls: type) -> None:
    """Register an adapter class under a canonical name."""
    _REGISTRY[name] = cls


def available() -> list[str]:
    import_all()
    return sorted(_REGISTRY)


def get_adapter(name: str, **cfg) -> ReadPort:
    import_all()
    cls = _REGISTRY.get(name)
    if cls is None:
        raise AdapterError(
            f"unknown adapter {name!r}; available: {sorted(_REGISTRY)}"
        )
    return cls(**cfg)


def import_all() -> None:
    """Import every adapter module so registry is complete. A module that
    fails to import (missing optional extra) is logged, not fatal."""
    for mod in (
        "csmg.adapters.engram",
        "csmg.adapters.jsonl_sqlite",
        "csmg.adapters.mem0",
        "csmg.adapters.langmem",
        "csmg.adapters.zep",
        "csmg.adapters.letta",
    ):
        try:
            importlib.import_module(mod)
        except Exception as e:  # noqa: BLE001 - optional extras must not kill the registry
            logger.debug("adapter module %s not importable: %s", mod, e)


def safe_call(label: str, fn: Callable[..., T], *args) -> T | None:
    """Fail-open wrapper for adapter reads (Constitution §2.1, AC5).

    On AdapterError or any unexpected exception, logs and returns None —
    the agent's flow is never altered. The monitor (B5) turns None into a
    'degraded' event.
    """
    try:
        return fn(*args)
    except AdapterError as e:
        logger.warning("adapter %s degraded: %s", label, e)
        return None
    except Exception as e:  # noqa: BLE001
        logger.exception("adapter %s internal error (degraded): %s", label, e)
        return None