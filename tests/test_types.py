"""CSMG-010: canonical contracts (types.py) schema tests."""

import pytest

from csmg.types import SENSOR_VERSION, ChunkRead, FlowEvent, SignalVerdict


def _event() -> FlowEvent:
    return FlowEvent(
        ts="2026-08-17T21:00:00+00:00",
        sensor_version=SENSOR_VERSION,
        signals=[SignalVerdict(signal="mismatch", fired=True, confidence=1.0)],
        severity="warn",
        chunk_id="c1",
        origin={"principal_id": "A", "session_id": "sA"},
        requester="B",
        confidence=1.0,
        provenance_mode="full",
        evidence={"hash": "abc123", "span": "..."},
    )


def test_chunkread_default_metadata_empty():
    c = ChunkRead(chunk_id="c1", content="hola")
    assert c.metadata == {}
    assert c.chunk_id == "c1"
    assert c.content == "hola"


def test_signalverdict_fields():
    s = SignalVerdict(signal="mismatch", fired=True, confidence=1.0)
    assert s.signal == "mismatch"
    assert s.fired is True
    assert s.confidence == 1.0
    assert s.detail == {}


def test_flowevent_to_dict_contract():
    d = _event().to_dict()
    assert d["chunk_id"] == "c1"
    assert d["requester"] == "B"
    assert d["provenance_mode"] == "full"
    assert d["signals"] == [{"signal": "mismatch", "fired": True,
                             "confidence": 1.0, "detail": {}}]


def test_flowevent_never_contains_full_content_key():
    d = _event().to_dict()
    assert "content" not in d  # AC6


def test_event_evidence_only_hash_span_keys():
    d = _event().to_dict()
    assert set(d["evidence"]) <= {"hash", "span"}


def test_flowevent_frozen_immutable():
    import dataclasses

    ev = _event()
    with pytest.raises(dataclasses.FrozenInstanceError):
        ev.chunk_id = "hacked"