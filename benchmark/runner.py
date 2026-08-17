"""Benchmark runner (CSMG-054/055): per-signal precision/recall + ASR.

Thresholds are DECLARED in this module before any run (anti Clever-Hans):
the benchmark reports, it never adapts thresholds to the fixture.
"""

from __future__ import annotations

import json
import os
import tempfile

from benchmark.fixture import build_sqlite, make_retriever, meta_of
from csmg.adapters.jsonl_sqlite import SqliteGenericAdapter
from csmg.events import JsonlEventSink
from csmg.scan import run_audit

# Declared configuration (fixed BEFORE running; benchmark never tunes it)
SIM_THRESHOLD = 0.75
SHARED_SCOPES = {"shared"}
SEEDS = [1, 2, 3]
N_TENANTS = 3
ROWS_PER_TENANT = 12

SCENARIOS = ["t1", "t2", "t3", "t4", "correct", "benign"]


def _metrics(scenario: str, seed: int) -> dict:
    with tempfile.TemporaryDirectory() as tmp:
        include_twins = scenario == "benign"  # twins stress (b) only in benign
        adversarial = {"t3": "t3", "t4": "t4"}.get(scenario, "none")
        db = build_sqlite(seed, tmp, N_TENANTS, ROWS_PER_TENANT,
                          include_twins=include_twins, adversarial=adversarial)
        meta = meta_of(db)
        retriever = make_retriever(scenario, meta)
        adapter = SqliteGenericAdapter(db, "mem", retriever=retriever)
        events_dir = os.path.join(tmp, "events")
        sink = JsonlEventSink(directory=events_dir)
        result = run_audit(adapter, "alpha", shared_scopes=SHARED_SCOPES,
                           sink=sink, sim_threshold=SIM_THRESHOLD)
        cross_ids = [
            cid for cid in retriever("alpha")
            if meta[cid]["owner"] not in (None, "alpha")
            and meta[cid]["scope"] != "shared"  # shared scope = authorized
        ]
        events = []
        ev_path = os.path.join(events_dir, "events.jsonl")
        if os.path.exists(ev_path):
            with open(ev_path, encoding="utf-8") as fh:
                events = [json.loads(line) for line in fh if line.strip()]
        detected_ids = {ev["chunk_id"] for ev in events}
        asr = None
        if cross_ids:
            asr = round(1 - len(detected_ids & set(cross_ids)) / len(cross_ids), 3)
        # "fp_rate" is only meaningful where no attack is expected
        fp_rate = None
        if scenario in ("benign", "correct") and result.scanned:
            fp_rate = round(result.emitted / result.scanned, 3)
        return {
            "scenario": scenario,
            "seed": seed,
            "scanned": result.scanned,
            "emitted": result.emitted,
            "by_signal": result.by_signal,
            "cross_alpha": len(cross_ids),
            "asr": asr,
            "benign_fp_rate": fp_rate,
        }


def run_benchmark(seeds=None, scenarios=None) -> list[dict]:
    rows = []
    for sc in (scenarios or SCENARIOS):
        for seed in (seeds or SEEDS):
            rows.append(_metrics(sc, seed))
    return rows


def format_table(rows: list[dict]) -> str:
    lines = ["scenario | seed | scanned | emitted | cross | asr | bfp | signals"]
    for r in rows:
        asr = "-" if r["asr"] is None else str(r["asr"])
        fp = "-" if r["benign_fp_rate"] is None else str(r["benign_fp_rate"])
        lines.append(
            "{:<8} | {:>4} | {:>7} | {:>7} | {:>5} | {:>5} | {:>4} | {}".format(
                r["scenario"], r["seed"], r["scanned"], r["emitted"],
                r["cross_alpha"], asr, fp, r["by_signal"]
            )
        )
    return "\n".join(lines)


if __name__ == "__main__":
    rows = run_benchmark()
    print(format_table(rows))