"""Offline behavior across all three platforms (issue #30).

Entities must exist and be legible while the amplifier is off, must be honest that what they
are showing is assumed, and must fail loudly rather than silently when commanded.
"""
import asyncio
from unittest.mock import MagicMock

import pytest
from homeassistant.const import CONF_UNIQUE_ID
from homeassistant.exceptions import HomeAssistantError

from custom_components.htd.const import CONF_RESTORE_LAST_STATE
from custom_components.htd.entity import HtdEntity


class _Entity(HtdEntity):
    """Minimal concrete consumer — the mixin's contract is what is under test here."""

    def __init__(self, client, config_entry, zone=1):
        self.client = client
        self.config_entry = config_entry
        self.zone = zone


def _entry(restore: bool):
    entry = MagicMock()
    entry.data = {CONF_UNIQUE_ID: "uid", CONF_RESTORE_LAST_STATE: restore}
    return entry


def _client(*, ready=True, has_data=True, connected=True, enabled=True):
    client = MagicMock()
    client.ready = ready
    client.connected = connected
    client.has_zone_data = MagicMock(return_value=has_data)
    client.get_zone = MagicMock(return_value=MagicMock(enabled=enabled))
    return client


# --- availability matrix ---

def test_live_data_is_available_regardless_of_the_restore_setting():
    """Restoration must not change anything while the device is reachable — the option is
    about outages only."""
    for restore in (True, False):
        entity = _Entity(_client(), _entry(restore))
        assert entity.available is True
        assert entity.assumed_state is False


def test_offline_with_restore_off_is_unavailable():
    """With the option off, behavior is exactly what it is today, except that the entity now
    exists during an outage instead of being missing from the state machine entirely."""
    entity = _Entity(_client(ready=False, has_data=False, connected=False), _entry(False))
    assert entity.available is False


def test_offline_with_restore_on_is_available_and_assumed():
    """The requested behavior: the dashboard reads "off" rather than Unavailable, and Home
    Assistant renders explicit on/off buttons instead of a toggle, because the value may be
    stale."""
    entity = _Entity(_client(ready=False, has_data=False, connected=False), _entry(True))
    assert entity.available is True
    assert entity.assumed_state is True


def test_connected_but_no_zone_data_yet_follows_the_same_rule():
    """The window between connecting and the first zone frame is an outage as far as the card
    is concerned, and must not flicker to a third presentation."""
    entity = _Entity(_client(ready=False, has_data=False, connected=True), _entry(True))
    assert entity.available is True
    assert entity.assumed_state is True


def test_no_config_entry_means_no_restoration():
    """The YAML setup path passes no config entry, so there is nowhere for the option to
    live. It must default to today's behavior rather than crashing on a None lookup."""
    entity = _Entity(_client(ready=False, has_data=False, connected=False), None)
    assert entity.available is False


# --- the protocol's own zone-enabled flag ---

def test_a_zone_the_controller_reports_as_disabled_is_unavailable():
    """This is what the removed Entity.enabled override actually meant: a zone with no keypad
    wired to it should not present as a working speaker."""
    entity = _Entity(_client(enabled=False), _entry(False))
    assert entity.available is False


def test_the_disabled_flag_is_not_inferred_from_missing_data():
    """Absence of data is not the controller saying "disabled". Conflating the two is what
    made every entity vanish during an outage in the first place."""
    entity = _Entity(
        _client(ready=False, has_data=False, connected=False, enabled=False),
        _entry(True),
    )
    assert entity.available is True


# --- commands while offline ---

def test_a_command_issued_while_offline_raises_a_visible_error():
    """A silently dropped command produces an automation trace that claims success and a card
    that snaps back a second later. An error is the only honest outcome, and it is why there
    is deliberately no replay queue."""
    client = _client(connected=False)
    entity = _Entity(client, _entry(True))

    async def _run():
        await entity._async_command(lambda: client.async_power_on(1), "turn on")

    with pytest.raises(HomeAssistantError):
        asyncio.run(_run())


def test_a_connection_dropping_mid_command_also_raises_a_visible_error():
    """The connection check and the write are not atomic. The library's own exception is the
    backstop for the race, and it must reach the user as the same error."""
    from htd_client.exceptions import HtdConnectionError

    client = _client(connected=True)

    async def _boom():
        raise HtdConnectionError("not connected")

    entity = _Entity(client, _entry(True))

    async def _run():
        await entity._async_command(_boom, "turn on")

    with pytest.raises(HomeAssistantError):
        asyncio.run(_run())


def test_a_command_that_succeeds_raises_nothing():
    """Guards the guard: the wrapper must not turn a working command into an error."""
    client = _client(connected=True)
    calls = []

    async def _ok():
        calls.append("sent")

    entity = _Entity(client, _entry(False))

    asyncio.run(entity._async_command(_ok, "turn on"))
    assert calls == ["sent"]
