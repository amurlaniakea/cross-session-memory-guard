"""CSMG-030: ReadPort registry + CSMG-034: safe_call fail-open (AC5)."""

import pytest

from csmg.adapters import AdapterError, available, get_adapter, safe_call
from csmg.adapters.engram import EngramAdapter


def test_registry_available_includes_known_adapters():
    names = available()
    assert {"engram", "jsonl", "sqlite", "mem0", "langmem", "zep", "letta"} <= set(names)


def test_get_adapter_unknown_raises():
    with pytest.raises(AdapterError):
        get_adapter("no-such-backend")


def test_get_adapter_engram_constructs():
    a = get_adapter("engram")
    assert isinstance(a, EngramAdapter)


def test_safe_call_healthy_returns_result():
    assert safe_call("t", lambda x: x * 2, 21) == 42


def test_safe_call_adapter_error_returns_none():
    def boom():
        raise AdapterError("store down")

    assert safe_call("broken", boom) is None


def test_safe_call_generic_exception_returns_none():
    def boom():
        raise ValueError("unexpected")

    assert safe_call("broken", boom) is None  # fail-open, never propagates (AC5)