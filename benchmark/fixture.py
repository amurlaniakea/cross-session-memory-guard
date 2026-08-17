"""Benchmark fixture: deterministic multi-tenant memory (CSMG-050/051/052/053).

Builds a SQLite table whose LABELS are always correct (KI-9: the sensor
audits the retrieval path, not data quality) and provides retriever FACTORIES
that simulate the engine's real retrieval behaviour — including broken
filters that CROSS tenants. The leak lives in the retriever layer (the seam
the adapter observes), never in a ReadPort mock.
"""

from __future__ import annotations

import hashlib
import os
import random
import sqlite3

TENANTS = ["alpha", "beta", "gamma"]
SCHEMA = """
CREATE TABLE mem (
    id INTEGER PRIMARY KEY,
    content TEXT NOT NULL,
    principal_id TEXT,
    scope TEXT NOT NULL DEFAULT 'project',
    created_at TEXT NOT NULL
)
"""

# Realistic corpora are tenant-DISTINCT: shared vocabulary across tenants
# would make signal (b) fire on structure, not on leaks (benchmark artifact).
_VOCAB = {
    "alpha": "ledgers invoice quantum vault registry centers clients",
    "beta": "procurement vendor stock warehouse docks shipments fleet",
    "gamma": "clinical cohort dosage patient trial endpoint visits",
}


_TIDX = {"alpha": 1, "beta": 2, "gamma": 3}

# Fixture markers/constants: the benchmark runner's ground truth (CSMG-055)
# references the SAME literals — single source of truth for both files.
T3_LAUNDER_MARKER = " (consolidated)"
T2_PLANTED_MARKER = "item 03"
T4_SECRET = "quarterly revenue gamma 2026 northwind 1.2M euros pipeline capex"


def _content(tenant: str, i: int) -> str:
    return (
        f"{tenant} {_VOCAB[tenant]} item {i:02d} "
        f"code {i * 137 + _TIDX[tenant]} seq {i} note {tenant}-{i}"
    )


def _digest(path: str) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        h.update(fh.read())
    return h.hexdigest()[:16]


def build_sqlite(
    seed: int, out_dir: str, n_tenants: int = 3, rows_per_tenant: int = 12,
    include_twins: bool = False, adversarial: str = "none",
) -> str:
    """Deterministic fixture. Returns the SQLite path.

    Rows: per-tenant corpora (owner principal_id = tenant), tenant-DISTINCT
    'shared' rows (scope='shared'). include_twins adds an identical
    cross-tenant row pair (stresses signal (b): legitimate duplicated content
    must be a MEASURED FP, never hidden). adversarial selects extra rows:
    "t3" (label theft + erased label), "t4" (gamma's full secret + alpha-owned
    fragments), "none" otherwise. Scenario-specific data stays scenario-
    specific so 'correct' genuinely yields zero events (AC4).
    """
    rng = random.Random(seed)
    db = os.path.join(out_dir, f"fixture_s{seed}.db")
    con = sqlite3.connect(db)
    con.executescript(SCHEMA)
    tenants = TENANTS[:n_tenants]
    cid = 1
    for t in tenants:
        for i in range(rows_per_tenant):
            con.execute(
                "INSERT INTO mem (id, content, principal_id, scope, created_at)"
                " VALUES (?, ?, ?, 'project', '2026-01-01T00:00:00Z')",
                (cid, _content(t, i), t),
            )
            cid += 1
        con.execute(
            "INSERT INTO mem (id, content, principal_id, scope, created_at)"
            " VALUES (?, ?, ?, 'shared', '2026-01-01T00:00:00Z')",
            (cid, f"{t}-team notice {rng.randint(1000, 9999)}", t),
        )
        cid += 1
    if include_twins:
        # adversarial benign: identical legit content in alpha+beta (no leak;
        # signal (b) should fire -> measured FP, AC2)
        con.execute(
            "INSERT INTO mem (id, content, principal_id, scope, created_at)"
            " VALUES (?, 'compliance policy: data retention 12 months', 'alpha',"
            " 'project', '2026-01-01T00:00:00Z')",
            (cid,),
        )
        cid += 1
        con.execute(
            "INSERT INTO mem (id, content, principal_id, scope, created_at)"
            " VALUES (?, 'compliance policy: data retention 12 months', 'beta',"
            " 'project', '2026-01-01T00:00:00Z')",
            (cid,),
        )
        cid += 1
    if adversarial == "t3":
        # T3a: label theft — beta content stored under alpha's label (unique
        # marker "consolidated" so the fixture can find it unambiguously)
        launder = _content("beta", 0) + T3_LAUNDER_MARKER
        con.execute(
            "INSERT INTO mem (id, content, principal_id, scope, created_at)"
            " VALUES (?, ?, 'alpha', 'project', '2026-01-02T00:00:00Z')",
            (cid, launder),
        )
        cid += 1
        # T3b: consolidation erased the label (principal NULL)
        con.execute(
            "INSERT INTO mem (id, content, principal_id, scope, created_at)"
            " VALUES (?, ?, NULL, 'project', '2026-01-02T00:00:00Z')",
            (cid, _content("gamma", 1)),
        )
        cid += 1
    if adversarial == "t4":
        # T4: gamma's full secret exists (a normal reference row)...
        con.execute(
            "INSERT INTO mem (id, content, principal_id, scope, created_at)"
            " VALUES (?, ?, 'gamma', 'project', '2026-01-03T00:00:00Z')",
            (cid, T4_SECRET),
        )
        cid += 1
        # ...and alpha owns 3 fragments of it (collusion: benign-looking notes
        # that compose the secret; individually below the similarity threshold)
        secret = T4_SECRET
        third = max(1, len(secret) // 3)
        for k in range(3):
            frag = secret[k * third : (k + 1) * third]
            con.execute(
                "INSERT INTO mem (id, content, principal_id, scope, created_at)"
                " VALUES (?, ?, 'alpha', 'project', '2026-01-03T00:00:00Z')",
                (cid, frag),
            )
            cid += 1
    con.commit()
    con.close()
    return db


def meta_of(db: str) -> dict:
    """id -> {"owner": principal_id, "scope": scope, "content": content}."""
    con = sqlite3.connect(f"file:{db}?mode=ro", uri=True)
    con.row_factory = sqlite3.Row
    rows = con.execute("SELECT id, content, principal_id, scope FROM mem").fetchall()
    con.close()
    return {str(r["id"]): {"owner": r["principal_id"], "scope": r["scope"],
                          "content": r["content"]} for r in rows}


def find_row(meta: dict, owner: str | None, content_contains: str) -> str | None:
    for cid, m in meta.items():
        if m["owner"] == owner and content_contains in m["content"]:
            return cid
    return None


def make_retriever(scenario: str, meta: dict, tenants: list[str] | None = None):
    """Factory returning retriever(principal) -> list of chunk ids.

    The leak (when present) lives HERE — the engine's retrieval path — while
    the table labels stay correct (KI-9).
    """
    tenants = tenants or TENANTS
    owners = {cid: m["owner"] for cid, m in meta.items()}
    own = {p: [cid for cid, o in owners.items() if o == p] for p in tenants}

    def correct(principal):
        return own.get(principal, [])

    if scenario in ("benign", "correct", "t3", "t4"):
        # t3/t4: the corruption lives in the DATA (label theft / erased label
        # / fragments); the retriever filters correctly ('correct' is the
        # clean baseline for AC4).
        if scenario == "t3":
                    def t3(principal):
                        ids = correct(principal)
                        launder = find_row(meta, "alpha", "consolidated")
                        erase = find_row(meta, None, "item 01")
                        if principal == "alpha" and launder and launder not in ids:
                            ids = ids + [launder]
                        if principal == "gamma" and erase and erase not in ids:
                            ids = ids + [erase]
                        return ids

                    return t3

        if scenario == "t4":
            def t4(principal):
                # retriever filters correctly; the collusion lives in the DATA
                # (alpha owns fragments of gamma's secret, see fixture builder)
                return correct(principal)

            return t4

        return correct

    if scenario == "t1":
        def t1(principal):
            if principal not in tenants:
                return []
            nxt = tenants[(tenants.index(principal) + 1) % len(tenants)]
            return own.get(principal, []) + own.get(nxt, [])

        return t1

    if scenario == "t2":
        def t2(principal):
            ids = own.get(principal, [])
            planted = find_row(meta, "beta", T2_PLANTED_MARKER)  # beta's planted row
            if principal == "alpha" and planted and planted not in ids:
                ids = ids + [planted]
            return ids

        return t2

    raise ValueError(f"unknown scenario: {scenario}")


def fixture_digest(seed: int, out_dir: str) -> str:
    """Determinism check helper."""
    db = build_sqlite(seed, out_dir)
    return _digest(db)