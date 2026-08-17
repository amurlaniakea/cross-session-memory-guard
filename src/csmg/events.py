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

MAX_SPAN_LEN = 200  # max length of ANY string value in a serialized event


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

    @staticmethod
    def _guard_evidence_shape(payload: dict) -> dict:
        """ALLOWLIST for evidence (auditor finding, B2 hardening).

        Only {"hash", "span"} may appear; span is length-capped. This makes
        the AC6 rule structural instead of a convention each signal must
        remember: content smuggled under any other key (e.g. "snippet",
        "matched_text") is rejected at the sink.
        """
        evidence = payload.get("evidence", {})
        if not isinstance(evidence, dict):
            raise ValueError("evidence must be a dict")
        extra = set(evidence) - {"hash", "span"}
        if extra:
            raise ValueError(
                f"evidence keys must be exactly hash/span, got: {sorted(extra)}"
            )
        if "hash" in evidence and (
            not isinstance(evidence["hash"], str) or not evidence["hash"]
        ):
            raise ValueError("evidence.hash must be a non-empty string")
        if "span" in evidence:
            span = evidence["span"]
            if not isinstance(span, str):
                raise ValueError("evidence.span must be a string")
            if len(span) > MAX_SPAN_LEN:
                raise ValueError(f"evidence.span exceeds MAX_SPAN_LEN={MAX_SPAN_LEN}")
        return payload

    @staticmethod
    def _guard_no_long_strings(payload: dict, max_len: int = MAX_SPAN_LEN) -> dict:
        """Structural net: no string value anywhere in the event may exceed
        max_len. Labels/snippets are short; real chunk content is not. This
        catches content smuggled into signals[].detail or origin under any
        key name, even when the key itself is innocent."""
        def walk(node: object) -> None:
            if isinstance(node, dict):
                for v in node.values():
                    walk(v)
            elif isinstance(node, list):
                for v in node:
                    walk(v)
            elif isinstance(node, str) and len(node) > max_len:
                raise ValueError(f"string value exceeds MAX_SPAN_LEN={max_len}")

        walk(payload)
        return payload

    def _write(self, payload: dict) -> None:
        with self._lock:
            self._path.parent.mkdir(parents=True, exist_ok=True)
            with self._path.open("a", encoding="utf-8") as fh:
                fh.write(json.dumps(payload, ensure_ascii=False) + "\n")

    def emit(self, event: FlowEvent) -> None:
        # Contract violations are LOUD (raised outside try): a buggy signal
        # must be noticed. I/O failures stay fail-open (Constitution §2.1).
        payload = self._guard_never_content(event.to_dict())
        payload = self._guard_evidence_shape(payload)
        payload = self._guard_no_long_strings(payload)
        try:
            self._write(payload)
        except Exception:
            logger.exception("JsonlEventSink.emit failed (fail-open)")


class NullSink:
    """No-op sink (tests / disabled mode)."""

    def emit(self, event: FlowEvent) -> None:
        pass