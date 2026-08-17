"""CSMG-011: JSONL event sink (events.py). AC6 + fail-open."""

import json
import pathlib

import pytest

from csmg.events import MAX_SPAN_LEN, JsonlEventSink, NullSink
from csmg.types import SENSOR_VERSION, FlowEvent, SignalVerdict


def _event() -> FlowEvent:
    return FlowEvent(
        ts="2026-08-17T21:00:00+00:00",
        sensor_version=SENSOR_VERSION,
        signals=[SignalVerdict(signal="mismatch", fired=True, confidence=1.0)],
        severity="warn",
        chunk_id="c1",
        origin={"principal_id": "A"},
        requester="B",
        confidence=1.0,
        provenance_mode="full",
        evidence={"hash": "abc123", "span": "..."},
    )


def test_jsonl_append_two_events_valid_lines(tmp_path):
    sink = JsonlEventSink(directory=str(tmp_path))
    sink.emit(_event())
    sink.emit(_event())
    lines = (tmp_path / "events.jsonl").read_text(encoding="utf-8").splitlines()
    assert len(lines) == 2
    for line in lines:
        payload = json.loads(line)  # must be valid JSON per line
        assert payload["sensor_version"] == SENSOR_VERSION
        assert "content" not in payload  # AC6


def test_jsonl_sink_path_property(tmp_path):
    sink = JsonlEventSink(directory=str(tmp_path))
    assert sink.path.name == "events.jsonl"
    assert sink.path.parent == tmp_path


def test_jsonl_sink_guard_refuses_content_smuggle():
    # AC6 hard refusal: even if a future caller smuggles "content" into the
    # payload, the guard raises instead of serializing it.
    ev = _event()
    payload = ev.to_dict()
    payload["content"] = "secret"  # simulate contract drift
    with pytest.raises(ValueError):
        JsonlEventSink._guard_never_content(payload)


def test_evidence_allowlist_rejects_extra_key():
    # Auditor finding (B2 hardening): content smuggled under any OTHER key
    # name (snippet/matched_text/...) must be rejected structurally.
    ev = _event()
    payload = ev.to_dict()
    payload["evidence"] = {"snippet": "full span of a memory chunk"}
    with pytest.raises(ValueError):
        JsonlEventSink._guard_evidence_shape(payload)


def test_evidence_span_length_capped():
    ev = _event()
    payload = ev.to_dict()
    payload["evidence"] = {"hash": "abc", "span": "x" * (MAX_SPAN_LEN + 1)}
    with pytest.raises(ValueError):
        JsonlEventSink._guard_evidence_shape(payload)


def test_evidence_span_short_ok():
    ev = _event()
    payload = ev.to_dict()
    payload["evidence"] = {"hash": "abc", "span": "x" * MAX_SPAN_LEN}
    assert JsonlEventSink._guard_evidence_shape(payload) is payload


def test_no_long_strings_blocks_detail_smuggle():
    ev = _event()
    payload = ev.to_dict()
    payload["signals"][0]["detail"] = {"matched_text": "y" * 500}
    with pytest.raises(ValueError):
        JsonlEventSink._guard_no_long_strings(payload)


def test_no_long_strings_blocks_origin_smuggle():
    ev = _event()
    payload = ev.to_dict()
    payload["origin"] = {"note": "z" * 500}
    with pytest.raises(ValueError):
        JsonlEventSink._guard_no_long_strings(payload)


def test_jsonl_sink_write_exposes_raw_payload_for_audit(tmp_path):
    sink = JsonlEventSink(directory=str(tmp_path))
    ev = _event()
    sink._write(ev.to_dict())  # intentional: keep the write primitive testable
    lines = (tmp_path / "events.jsonl").read_text(encoding="utf-8").splitlines()
    assert len(lines) == 1
    assert json.loads(lines[0])["chunk_id"] == "c1"


def test_jsonl_sink_fail_open_on_write_error(monkeypatch):
    sink = JsonlEventSink(directory="/tmp/csmg-tests-failopen")

    def boom(self, *args, **kwargs):
        raise OSError("disk full (simulated)")

    monkeypatch.setattr(pathlib.Path, "open", boom)
    sink.emit(_event())  # must NOT raise (Constitution §2.1 / AC5)


def test_null_sink_noop():
    NullSink().emit(_event())  # must not raise