"""CLI: csmg audit / csmg report (SPEC §3.6, CSMG-040/041).

Exit codes: 0 = success, 2 = usage/backend error.
"""

from __future__ import annotations

import json
from pathlib import Path

import typer

from csmg.adapters import AdapterError, get_adapter
from csmg.events import JsonlEventSink
from csmg.scan import DEFAULT_SIM_THRESHOLD, run_audit

app = typer.Typer(no_args_is_help=True)


@app.callback()
def main() -> None:
    """CrossSessionMemoryGuard — read-only cross-principal memory exfiltration sensor.

    Observes, compares and alerts. Never blocks or modifies memory.
    """


@app.command()
def audit(
    store: str = typer.Option(..., "--store", help="adapter name (engram, jsonl, sqlite)"),
    principal: str = typer.Option(..., "--principal", help="principal/tenant to audit"),
    path: str = typer.Option(None, "--path", help="data source path (adapter-specific)"),
    table: str = typer.Option("mem", "--table", help="sqlite table name (sqlite adapter)"),
    shared_scopes: str = typer.Option(
        "", "--shared-scopes", help="comma-separated authorized scopes"
    ),
    out: str = typer.Option("csmg-events", "--out", help="events output directory"),
    similarity_threshold: float = typer.Option(
        DEFAULT_SIM_THRESHOLD, "--similarity-threshold", help="signal (b) threshold"
    ),
) -> None:
    cfg: dict = {}
    if path:
        cfg["db_path" if store == "engram" else "path"] = path
    if store == "sqlite":
        cfg["table"] = table
    try:
        adapter = get_adapter(store, **cfg)
    except (AdapterError, TypeError) as e:
        typer.echo(f"error: {e}", err=True)
        raise typer.Exit(2) from e
    scopes = {s.strip() for s in shared_scopes.split(",") if s.strip()}
    sink = JsonlEventSink(directory=out)
    res = run_audit(
        adapter, principal, shared_scopes=scopes, sink=sink, sim_threshold=similarity_threshold
    )
    typer.echo(
        f"audited principal={res.principal} scanned={res.scanned} "
        f"emitted={res.emitted} degraded={res.degraded} by_signal={res.by_signal}"
    )
    typer.echo(f"events -> {sink.path}")
    raise typer.Exit(0)


@app.command()
def report(
    events_dir: str = typer.Option(
        "csmg-events", "--events-dir", help="directory with events.jsonl"
    ),
    json_out: bool = typer.Option(False, "--json", help="emit JSON summary"),
) -> None:
    path = Path(events_dir) / "events.jsonl"
    if not path.exists():
        typer.echo(f"error: no events file at {path}", err=True)
        raise typer.Exit(2)
    total = 0
    by_signal: dict = {}
    by_severity: dict = {}
    try:
        with path.open(encoding="utf-8") as fh:
            for line in fh:
                if not line.strip():
                    continue
                ev = json.loads(line)
                total += 1
                by_severity[ev["severity"]] = by_severity.get(ev["severity"], 0) + 1
                for s in ev["signals"]:
                    by_signal[s["signal"]] = by_signal.get(s["signal"], 0) + 1
    except (OSError, json.JSONDecodeError) as e:
        typer.echo(f"error: corrupt events file: {e}", err=True)
        raise typer.Exit(2) from e
    summary = {"total_events": total, "by_severity": by_severity, "by_signal": by_signal}
    if json_out:
        typer.echo(json.dumps(summary, ensure_ascii=False))
    else:
        typer.echo(f"events={total} severity={by_severity} by_signal={by_signal}")
    raise typer.Exit(0)


if __name__ == "__main__":
    app()