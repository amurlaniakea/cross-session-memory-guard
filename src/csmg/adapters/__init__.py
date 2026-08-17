# SPDX-FileCopyrightText: 2026 Pedro Sordo Martínez <amurlaniakea@gmail.com>
#
# SPDX-License-Identifier: AGPL-3.0-or-later
#
# Copyright (C) 2026 Pedro Sordo Martínez
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License as
# published by the Free Software Foundation, either version 3 of the
# License, or (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
# GNU Affero General Public License for more details.
#
# You should have received a copy of the GNU Affero General Public
# License along with this program. If not, see
# <https://www.gnu.org/licenses/>.

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

    list_chunks(principal=None): MUST represent "what the engine's REAL
    retrieval returns when queried as this principal" — OBSERVE the
    retrieval path, do not reconstruct your own "correct" filtered query
    (KI-9, hallazgo del auditor 2026-08-17). A schema-scoped listing that
    pre-filters by principal makes signal (a) structurally inert: the
    adapter would audit "are the labels correct?" instead of "did the real
    read path filter?" (the security question). If a backend has no
    observable retrieval path, the adapter must declare "schema-scoped
    mode" (signal (a) inapplicable, provenance_mode noted per event) —
    never pretend to observe what it does not.
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