"""Audit scan: run the three signals over an adapter's chunks (SPEC §3).

`run_audit` scans the chunks an engine exposes for a principal, resolves
provenance, evaluates mismatch/similarity/flowgraph and emits FlowEvents
through the provided sink. Fail-open: adapter errors degrade the scan
(AdapterError -> safe_call -> None), never crash it (Constitution §2.1).
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from datetime import UTC
from typing import Any

from csmg.adapters import ReadPort, safe_call
from csmg.events import EventSink, JsonlEventSink
from csmg.provenance import resolve
from csmg.signals.flowgraph import FlowGraph
from csmg.signals.mismatch import evaluate as evaluate_mismatch
from csmg.signals.similarity import evaluate as evaluate_similarity
from csmg.types import SENSOR_VERSION, FlowEvent, SignalVerdict

_SPAN_LIMIT = 120  # evidence span marker; below MAX_SPAN_LEN (AC6)
DEFAULT_SIM_THRESHOLD = 0.75


@dataclass
class AuditResult:
    principal: str
    scanned: int = 0
    emitted: int = 0
    degraded: int = 0
    by_signal: dict = field(default_factory=dict)

    def as_dict(self) -> dict:
        return {
            "principal": self.principal,
            "scanned": self.scanned,
            "emitted": self.emitted,
            "degraded": self.degraded,
            "by_signal": dict(self.by_signal),
        }


def _hash_of(content: str) -> str:
    return hashlib.sha256(content.encode("utf-8")).hexdigest()


def _span_of(content: str) -> str:
    return content[:_SPAN_LIMIT]


def _principals_of(adapter: ReadPort) -> list[str]:
    fn = getattr(adapter, "list_principals", None)
    if fn is None:
        return []
    try:
        return fn()
    except Exception:  # noqa: BLE001 - enumeration is best-effort
        return []


def run_audit(
    adapter: ReadPort,
    principal: str,
    shared_scopes: set | None = None,
    sink: EventSink | None = None,
    sim_threshold: float = DEFAULT_SIM_THRESHOLD,
) -> AuditResult:
    shared = shared_scopes or set()
    sink = sink or JsonlEventSink()
    result = AuditResult(principal=principal)

    # KI-8 route 1: prime the write side from engine metadata. Unattributed
    # chunks are skipped by FlowGraph.rehydrate itself (KI-8 hardening).
    graph = FlowGraph()
    principals = _principals_of(adapter)
    writes: list[tuple[str, str]] = []
    for p in principals or [principal]:
        ids = safe_call(f"list_chunks[{p}]", adapter.list_chunks, p) or []
        writes.extend((cid, p) for cid in ids)
    graph.rehydrate(writes)

    # reference content of OTHER attributed principals (similarity baseline)
    references: dict[str, str] = {}
    for p in principals:
        if p == principal:
            continue
        for cid in safe_call(f"list_chunks[{p}]", adapter.list_chunks, p) or []:
            chunk = safe_call(f"get_chunk[{p}]", adapter.get_chunk, cid)
            if chunk is not None:
                references[cid] = chunk.content

    for cid in safe_call(f"list_chunks[{principal}]", adapter.list_chunks, principal) or []:
        chunk = safe_call(f"get_chunk[{principal}]", adapter.get_chunk, cid)
        if chunk is None:
            result.degraded += 1
            continue
        result.scanned += 1

        prov = resolve(chunk)
        verdicts: list[SignalVerdict] = []

        v_mismatch = evaluate_mismatch(prov, principal, shared)
        verdicts.append(v_mismatch)

        v_flow = graph.record_read(
            cid, reader=principal, authorized=(prov.scope in shared)
        )
        verdicts.append(v_flow)

        best_sim = 0.0
        for ref in references.values():
            sim = evaluate_similarity(chunk.content, ref, sim_threshold).confidence
            best_sim = max(best_sim, sim)
        verdicts.append(
            SignalVerdict(
                signal="similarity",
                fired=best_sim >= sim_threshold,
                confidence=best_sim,
                detail={"similarity": best_sim, "threshold": sim_threshold},
            )
        )

        fired = [v for v in verdicts if v.fired]
        for v in fired:  # by_signal only counts signals that FIRED (>=1)
            prev = result.by_signal.get(v.signal, 0)
            result.by_signal[v.signal] = prev + 1
        if not fired:
            continue

        event = FlowEvent(
            ts=_now_iso(),
            sensor_version=SENSOR_VERSION,
            signals=fired,
            severity="alert" if len(fired) > 1 else "warn",
            chunk_id=cid,
            origin=_origin_of(prov),
            requester=principal,
            confidence=max(v.confidence for v in fired),
            provenance_mode=prov.mode,
            evidence={"hash": _hash_of(chunk.content), "span": _span_of(chunk.content)},
        )
        sink.emit(event)
        result.emitted += 1

    return result


def _origin_of(prov) -> dict:
    d: dict[str, Any] = {}
    if prov.principal_id:
        d["principal_id"] = prov.principal_id
    if prov.session_id:
        d["session_id"] = prov.session_id
    if prov.scope:
        d["scope"] = prov.scope
    return d


def _now_iso() -> str:
    from datetime import datetime

    return datetime.now(UTC).isoformat()