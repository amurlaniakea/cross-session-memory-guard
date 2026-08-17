"""Event emitters: JSONL append-only sink + pluggable hook.

Fail-open by design (Constitution §2.1): a sink error is logged and swallowed,
never propagated to the agent. Events never contain full chunk content (AC6).
"""

from __future__ import annotations

import json
import logging
import threading
from pathlib import Path
from typing import Protocol

from csmg.types import FlowEvent

logger = logging.getLogger("csmg.events")


class EventSink(Protocol):
    def emit(self, event: FlowEvent) -> None: ...


class JsonlEventSink:
    """Append-only JSONL sink (one FlowEvent per line)."""

    def __init__(self, directory: str = "csmg-events") -> None:
        self._path = Path(directory) / "events.jsonl"
        self._lock = threading.Lock()

    @property
    def path(self) -> Path:
        return self._path

    @staticmethod
    def _guard_never_content(payload: dict) -> dict:
        """AC6 hard refusal: full chunk content must never be serialized."""
        if "content" in payload:
            raise ValueError("FlowEvent must never carry full content")
        return payload

    def _write(self, payload: dict) -> None:
        with self._lock:
            self._path.parent.mkdir(parents=True, exist_ok=True)
            with self._path.open("a", encoding="utf-8") as fh:
                fh.write(json.dumps(payload, ensure_ascii=False) + "\n")

    def emit(self, event: FlowEvent) -> None:
        payload = self._guard_never_content(event.to_dict())
        try:
            self._write(payload)
        except Exception:
            logger.exception("JsonlEventSink.emit failed (fail-open)")


class NullSink:
    """No-op sink (tests / disabled mode)."""

    def emit(self, event: FlowEvent) -> None:
        pass