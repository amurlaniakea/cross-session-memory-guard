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

"""Benchmark runner (CSMG-054/055): per-signal precision/recall + ASR.

Thresholds are DECLARED in this module before any run (anti Clever-Hans):
the benchmark reports, it never adapts thresholds to the fixture.

CSMG-055: besides the raw table (scanned/emitted/asr/bfp), the runner
derives EXPLICIT per-signal precision / recall / fp_rate from the same raw
events against a per-scenario semantic ground truth (_ground_truth). The
derivation is code, not hand arithmetic — reproducible in one command.
"""

from __future__ import annotations

import json
import os
import tempfile
from collections import defaultdict

from benchmark.fixture import (
    T2_PLANTED_MARKER,
    T3_LAUNDER_MARKER,
    T4_SECRET,
    build_sqlite,
    find_row,
    make_retriever,
    meta_of,
)
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
SIGNALS = ["mismatch", "flowgraph", "similarity"]


def _ground_truth(scenario: str, meta: dict, retriever) -> set[str]:
    """Semantic ground truth for the alpha-principal audit (CSMG-055).

    Rows involved in the unauthorized flow: what the sensor OUGHT to flag
    if its signals could see it. Deliberately NOT the same as the
    ownership-only `cross` count (a retriever-layer metric); GT encodes the
    SCENARIO's semantics so precision/recall measure detection quality
    against the threat, not against the fixture's plumbing:

      t1      beta's 12 private rows served to alpha (leak in the
              retrieval layer, KI-9).
      t2      beta's planted row (marker T2_PLANTED_MARKER) returned to
              alpha.
      t3      the relabeled row (beta content under alpha's label, marker
              T3_LAUNDER_MARKER). The provenance-erased row (owner NULL)
              is served to gamma and is NOT scanned by the alpha audit: it
              is a known blind spot of the single-principal MVP audit,
              deliberately excluded from GT (documented in the report).
      t4      alpha's 3 fragment rows composing gamma's secret (composite
              collusion). Declared below-threshold (AC7): recall 0.0 is
              the honest, benchmarked output.
      correct no unauthorized flow (AC4 baseline).
      benign  no unauthorized flow (legit cross-tenant duplication
              stresses signal (b) as a MEASURED FP, AC2).
    """
    if scenario == "t1":
        return {
            cid
            for cid in retriever("alpha")
            if meta[cid]["owner"] not in (None, "alpha")
            and meta[cid]["scope"] != "shared"
        }
    if scenario == "t2":
        planted = find_row(meta, "beta", T2_PLANTED_MARKER)
        return {planted} if planted else set()
    if scenario == "t3":
        launder = find_row(meta, "alpha", T3_LAUNDER_MARKER)
        return {launder} if launder else set()
    if scenario == "t4":
        return {
            cid
            for cid, m in meta.items()
            if m["owner"] == "alpha" and m["content"] in T4_SECRET
        }
    return set()  # correct / benign


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

        # CSMG-055: per-signal TP/FP/FN against the semantic ground truth.
        gt = _ground_truth(scenario, meta, retriever)
        tp: dict[str, int] = defaultdict(int)
        fp: dict[str, int] = defaultdict(int)
        fired_gt: dict[str, set] = defaultdict(set)
        for ev in events:
            for sv in ev["signals"]:
                s = sv["signal"]
                if ev["chunk_id"] in gt:
                    tp[s] += 1
                    fired_gt[s].add(ev["chunk_id"])
                else:
                    fp[s] += 1
        fn = {s: len(gt - fired_gt[s]) for s in SIGNALS}

        return {
            "scenario": scenario,
            "seed": seed,
            "scanned": result.scanned,
            "emitted": result.emitted,
            "by_signal": result.by_signal,
            "cross_alpha": len(cross_ids),
            "asr": asr,
            "benign_fp_rate": fp_rate,
            "gt": len(gt),
            "tp": dict(tp),
            "fp": dict(fp),
            "fn": fn,
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
            "{} | {} | {} | {} | {} | {} | {} | {}".format(
                r["scenario"].ljust(8), r["seed"], str(r["scanned"]).rjust(7),
                str(r["emitted"]).rjust(7), str(r["cross_alpha"]).rjust(5),
                asr.rjust(5), fp.rjust(4), r["by_signal"]
            )
        )
    return "\n".join(lines)


def _rate(n: int, d: int) -> float | None:
    return n / d if d else None


def _fmt(x: float | None) -> str:
    return "-" if x is None else f"{x:.3f}"


def format_quality(rows: list[dict]) -> str:
    """Explicit per-signal precision/recall/fp_rate (CSMG-055 deliverable).

    Aggregates TP/FP/FN over SEEDS, then derives the rates — the same raw
    events the ASR/bfp table uses, formatted so the arithmetic is auditable
    at a glance. Precision/recall: "-" when undefined (no events / no GT).
    fp_rate = FP / (scanned - GT): false alarms on rows that must not fire.
    """
    agg: dict[str, dict[str, dict[str, int]]] = {}
    non_gt: dict[str, int] = {}
    for r in rows:
        s = agg.setdefault(r["scenario"], {})
        for sig in SIGNALS:
            e = s.setdefault(sig, {"tp": 0, "fp": 0, "fn": 0})
            e["tp"] += r["tp"].get(sig, 0)
            e["fp"] += r["fp"].get(sig, 0)
            e["fn"] += r["fn"].get(sig, 0)
        non_gt[r["scenario"]] = non_gt.get(r["scenario"], 0) + (
            r["scanned"] - r["gt"]
        )
    lines = ["signal | scenario | precision | recall | fp_rate"]
    for sig in SIGNALS:
        for sc in SCENARIOS:
            e = agg[sc][sig]
            tp, fp, fn = e["tp"], e["fp"], e["fn"]
            lines.append(
                f"{sig:<11}| {sc:<8} | {_fmt(_rate(tp, tp + fp)):>9} | "
                f"{_fmt(_rate(tp, tp + fn)):>6} | {_fmt(_rate(fp, non_gt[sc])):>7}"
            )
    return "\n".join(lines)


if __name__ == "__main__":
    rows = run_benchmark()
    print(format_table(rows))
    print()
    print("=== per-signal quality (CSMG-055; seeds 1-3 aggregated; "
          "ground truth per scenario in _ground_truth) ===")
    print(format_quality(rows))