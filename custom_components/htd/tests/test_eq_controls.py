"""Tests for EQ control helpers and dispatch logic in number.py."""
import asyncio
from unittest.mock import AsyncMock, MagicMock

from custom_components.htd.number import _eq_range, _eq_enabled_default, HtdEqNumber


# --- Range lookup ---

def test_lync_bass_range():
    assert _eq_range("lync", "bass") == (-10.0, 10.0, 1.0)


def test_lync_treble_range():
    assert _eq_range("lync", "treble") == (-10.0, 10.0, 1.0)


def test_lync_balance_range():
    assert _eq_range("lync", "balance") == (-18.0, 18.0, 1.0)


def test_mca_bass_range():
    assert _eq_range("mca", "bass") == (-12.0, 12.0, 4.0)


def test_mca_treble_range():
    assert _eq_range("mca", "treble") == (-12.0, 12.0, 4.0)


def test_mca_balance_range():
    assert _eq_range("mca", "balance") == (-12.0, 12.0, 6.0)


# --- Enabled defaults ---

def test_bass_enabled_by_default():
    assert _eq_enabled_default("bass") is True


def test_treble_enabled_by_default():
    assert _eq_enabled_default("treble") is True


def test_balance_disabled_by_default():
    assert _eq_enabled_default("balance") is False


# --- Dispatch ---

def _make_client(kind_value="lync"):
    client = MagicMock()
    client.model = {"kind": MagicMock(value=kind_value)}
    client.async_set_bass = AsyncMock()
    client.async_set_treble = AsyncMock()
    client.async_set_balance = AsyncMock()
    return client


def test_bass_dispatch():
    client = _make_client("lync")
    entity = HtdEqNumber(client, "uid", zone=1, control="bass")
    asyncio.run(entity.async_set_native_value(5.0))
    client.async_set_bass.assert_called_once_with(1, 5)
    client.async_set_treble.assert_not_called()
    client.async_set_balance.assert_not_called()


def test_treble_dispatch():
    client = _make_client("lync")
    entity = HtdEqNumber(client, "uid", zone=2, control="treble")
    asyncio.run(entity.async_set_native_value(-3.0))
    client.async_set_treble.assert_called_once_with(2, -3)
    client.async_set_bass.assert_not_called()


def test_balance_dispatch():
    client = _make_client("mca")
    entity = HtdEqNumber(client, "uid", zone=3, control="balance")
    asyncio.run(entity.async_set_native_value(6.0))
    client.async_set_balance.assert_called_once_with(3, 6)
    client.async_set_bass.assert_not_called()
