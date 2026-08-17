"""CSMG-012: kill switch (kill.py). AC5 semantics."""

import pytest

from csmg.kill import is_disabled


@pytest.mark.parametrize("value", ["1", "true", "yes", "on", "TRUE", "On", " 1 "])
def test_disabled_truthy_values(monkeypatch, value):
    monkeypatch.setenv("CSMG_DISABLED", value)
    assert is_disabled() is True


@pytest.mark.parametrize("value", ["", "0", "false", "no", "off", "disabled", "2"])
def test_disabled_falsy_values(monkeypatch, value):
    monkeypatch.setenv("CSMG_DISABLED", value)
    assert is_disabled() is False


def test_disabled_absent_env(monkeypatch):
    monkeypatch.delenv("CSMG_DISABLED", raising=False)
    assert is_disabled() is False