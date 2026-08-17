"""CSMG-050..055: benchmark fixture + metrics (fast) + seed sweep (slow)."""

import os
import tempfile

import pytest

from benchmark.fixture import build_sqlite, fixture_digest, make_retriever, meta_of
from benchmark.runner import SHARED_SCOPES, SIM_THRESHOLD, _metrics, run_benchmark
from csmg.adapters.jsonl_sqlite import SqliteGenericAdapter
from csmg.events import JsonlEventSink
from csmg.scan import run_audit


def _audit(tmp, scenario, seed=1, include_twins=False, adversarial="none"):
    db = build_sqlite(seed, tmp, include_twins=include_twins, adversarial=adversarial)
    meta = meta_of(db)
    retriever = make_retriever(scenario, meta)
    adapter = SqliteGenericAdapter(db, "mem", retriever=retriever)
    sink = JsonlEventSink(directory=os.path.join(tmp, "ev"))
    res = run_audit(adapter, "alpha", shared_scopes=SHARED_SCOPES,
                    sink=sink, sim_threshold=SIM_THRESHOLD)
    events = []
    ev_path = os.path.join(tmp, "ev", "events.jsonl")
    if os.path.exists(ev_path):
        import json
        with open(ev_path, encoding="utf-8") as fh:
            events = [json.loads(line) for line in fh if line.strip()]
    return res, meta, retriever, events


# ---- CSMG-050: determinism ----

def test_fixture_deterministic_same_seed():
    with tempfile.TemporaryDirectory() as t1, tempfile.TemporaryDirectory() as t2:
        assert fixture_digest(1, t1) == fixture_digest(1, t2)


def test_fixture_differs_between_seeds():
    with tempfile.TemporaryDirectory() as tmp:
        assert fixture_digest(1, tmp) != fixture_digest(2, tmp)


# ---- CSMG-051: AC1 (mismatch 100% on T1, leak at the DATA layer) ----

def test_ac1_t1_mismatch_recall_100pct():
    with tempfile.TemporaryDirectory() as tmp:
        res, meta, retriever, events = _audit(tmp, "t1")
        cross = [cid for cid in retriever("alpha")
                 if meta[cid]["owner"] not in (None, "alpha")
                 and meta[cid]["scope"] != "shared"]
        assert len(cross) == 12  # beta's rows leaked into alpha's view
        assert res.by_signal["mismatch"] == 12  # AC1: deterministic 100%
        assert res.emitted >= 12
        assert all("content" not in ev for ev in events)  # AC6


def test_t2_planted_chunk_detected():
    with tempfile.TemporaryDirectory() as tmp:
        res, meta, retriever, _ = _audit(tmp, "t2")
        cross = [cid for cid in retriever("alpha")
                 if meta[cid]["owner"] not in (None, "alpha")]
        assert len(cross) == 1  # beta's planted invoice 03
        assert res.by_signal["mismatch"] == 1


# ---- CSMG-052: T3 (label theft / erased label) + T4 (composite, declared) ----

def test_t3_label_theft_caught_by_similarity():
    # (a) is inert for label theft (labels are "correct"); (b) must catch
    # the stolen content against the true owner's references.
    with tempfile.TemporaryDirectory() as tmp:
        res, meta, retriever, _ = _audit(tmp, "t3", adversarial="t3")
        assert res.by_signal.get("mismatch", 0) == 0
        assert res.by_signal.get("similarity", 0) >= 1
        assert res.emitted >= 1


def test_t4_composite_collusion_undetected_declared():
    # AC7: composite detection is OUT of MVP scope; fragments are individually
    # below threshold -> the benchmark REPORTS the limitation, not a fake pass.
    with tempfile.TemporaryDirectory() as tmp:
        res, meta, retriever, events = _audit(tmp, "t4", adversarial="t4")
        assert res.emitted == 0  # declared limitation (see KNOWN_ISSUES AC7)


# ---- CSMG-053: benign (AC4 zero-events + AC2 adversarial FP) ----

def test_ac4_correct_retriever_zero_events_no_prelabels():
    # AC4 anti-circular: same table, CORRECT retriever, no twins -> 0 events.
    # The fixture never pre-labels rows as suspicious.
    with tempfile.TemporaryDirectory() as tmp:
        res, meta, retriever, events = _audit(tmp, "correct", include_twins=False)
        assert res.emitted == 0


def test_ac2_benign_adversarial_fp_measured_not_hidden():
    # Twins are legitimate duplicated content across tenants: signal (b)
    # fires on them — a MEASURED FP with a declared tolerance, never hidden.
    with tempfile.TemporaryDirectory() as tmp:
        res, meta, retriever, _ = _audit(tmp, "benign", include_twins=True)
        assert res.by_signal.get("similarity", 0) >= 1
        fp_rate = res.emitted / res.scanned if res.scanned else 0.0
        assert fp_rate <= 0.30  # declared tolerance (AC2), never 0 absolute


# ---- CSMG-054/055: runner metrics + raw table (watch-item) ----

def test_runner_metrics_t1_asr_zero_and_benign_declared():
    m = _metrics("t1", 1)
    assert m["asr"] == 0.0
    assert m["cross_alpha"] == 12
    b = _metrics("benign", 1)
    assert b["asr"] is None
    assert b["benign_fp_rate"] > 0.0  # measured FP, declared
    c = _metrics("correct", 1)
    assert c["emitted"] == 0


@pytest.mark.slow
def test_seed_sweep_consistency():
    # single-seed fragility rule: AC1 must hold across >=3 seeds
    rows = run_benchmark(seeds=[1, 2, 3], scenarios=["t1", "correct", "benign"])
    for r in rows:
        if r["scenario"] == "t1":
            assert r["asr"] == 0.0, r
        if r["scenario"] == "correct":
            assert r["emitted"] == 0, r
        if r["scenario"] == "benign":
            assert r["benign_fp_rate"] <= 0.30, r