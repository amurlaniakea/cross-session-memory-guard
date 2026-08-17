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

"""CSMG-040/041: CLI audit + report (Typer CliRunner; exit 0/2)."""

import json

from typer.testing import CliRunner

from csmg.cli import app

runner = CliRunner()


def _jsonl_fixture(tmp_path) -> str:
    p = tmp_path / "mem.jsonl"
    p.write_text(
        json.dumps(
            {"id": "a1", "content": "alice private note",
             "metadata": {"principal_id": "alice"}}
        )
        + "\n"
        + json.dumps(
            {"id": "b1", "content": "bob private note",
             "metadata": {"principal_id": "bob"}}
        )
        + "\n",
        encoding="utf-8",
    )
    return str(p)


def test_cli_audit_jsonl_exit0(tmp_path):
    # subcommand routing works (no "Got unexpected extra argument")
    r = runner.invoke(
        app,
        ["audit", "--store", "jsonl", "--path", _jsonl_fixture(tmp_path),
         "--principal", "alice", "--out", str(tmp_path / "ev")],
    )
    assert r.exit_code == 0, r.output
    assert "audited principal=alice scanned=1 emitted=0" in r.output


def test_cli_audit_unknown_store_exit2():
    r = runner.invoke(app, ["audit", "--store", "nope", "--principal", "x"])
    assert r.exit_code == 2
    assert "error:" in r.output


def test_cli_report_exit0_and_json(tmp_path):
    ev_dir = tmp_path / "ev"
    ev_dir.mkdir()
    (ev_dir / "events.jsonl").write_text(
        json.dumps({"severity": "warn", "signals": [{"signal": "mismatch"}], "ts": "t",
                    "sensor_version": "0.1.0", "chunk_id": "c", "origin": {},
                    "requester": "r", "confidence": 1.0, "provenance_mode": "full",
                    "evidence": {"hash": "h"}})
        + "\n",
        encoding="utf-8",
    )
    r = runner.invoke(app, ["report", "--events-dir", str(ev_dir)])
    assert r.exit_code == 0, r.output
    assert "events=1" in r.output
    rj = runner.invoke(app, ["report", "--events-dir", str(ev_dir), "--json"])
    assert rj.exit_code == 0
    payload = json.loads(rj.output)
    assert payload["total_events"] == 1
    assert payload["by_signal"] == {"mismatch": 1}


def test_cli_report_missing_dir_exit2(tmp_path):
    r = runner.invoke(app, ["report", "--events-dir", str(tmp_path / "no-such")])
    assert r.exit_code == 2
    assert "error:" in r.output