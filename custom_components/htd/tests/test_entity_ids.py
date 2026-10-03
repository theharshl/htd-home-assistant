"""Entity id and unique_id construction across media_player, number and switch.

Entity ids are only a suggestion Home Assistant uses at first registration; unique_ids are
what tie existing registry entries (and therefore every existing entity id) to their
entities. These tests pin the first and guard the second.
"""
import asyncio
import re
from unittest.mock import MagicMock

from homeassistant.const import CONF_UNIQUE_ID

from custom_components.htd.const import CONF_DEVICE_NAME, CONF_ZONE_NAMES, DOMAIN
from custom_components.htd.entity import get_zone_entity_id
from custom_components.htd.media_player import HtdDevice
from custom_components.htd import number, switch
from custom_components.htd.number import HtdEqNumber
from custom_components.htd.switch import HtdDndSwitch


def _make_client(zones=12, kind_value="lync", zone_name=None):
    client = MagicMock()
    client.model = {"kind": MagicMock(value=kind_value), "zones": zones}
    client.get_zone_count = MagicMock(return_value=zones)
    client.get_zone_name = MagicMock(return_value=zone_name)
    return client


def _make_entry(title="HTD Lync 12", zone_names=None, client=None):
    entry = MagicMock()
    entry.title = title
    entry.data = {CONF_UNIQUE_ID: "uid", CONF_ZONE_NAMES: zone_names or {}}
    entry.runtime_data = client
    return entry


# --- the shared helper ---

def test_helper_pads_zone_on_controllers_with_more_than_ten_zones():
    assert get_zone_entity_id("media_player", "HTD Lync 12", 1, 12) == "media_player.htd_lync_12_zone_01"


def test_helper_does_not_pad_zone_on_small_controllers():
    assert get_zone_entity_id("media_player", "HTD MCA-66", 1, 6) == "media_player.htd_mca_66_zone_1"


def test_helper_appends_suffix():
    assert get_zone_entity_id("number", "HTD Lync 12", 12, 12, "bass") == "number.htd_lync_12_zone_12_bass"


def test_helper_matches_the_previous_media_player_format():
    """New media_player installs must get exactly the ids they always have."""
    def make_alphanumeric(input_string):
        temp = re.sub(r'[^a-zA-Z0-9]', '_', input_string)
        return re.sub(r'_+', '_', temp).strip('_')

    old = lambda name, zone_number, zone_fmt: f"media_player.{make_alphanumeric(name)}_zone_{zone_number:{zone_fmt}}".lower()

    for name in ("HTD Lync 12", "HTD MCA-66", "  My -- Amp!! ", "Upstairs/Downstairs"):
        for zones in (6, 12, 24):
            zone_fmt = "02" if zones > 10 else "01"
            for zone in range(1, zones + 1):
                assert get_zone_entity_id("media_player", name, zone, zones) == old(name, zone, zone_fmt)


# --- every platform follows the same scheme ---

def test_media_player_entity_id():
    device = HtdDevice("uid", "HTD Lync 12", 1, [], _make_client(), _make_entry())
    assert device.entity_id == "media_player.htd_lync_12_zone_01"


def test_number_entity_ids():
    client = _make_client()
    for control in ("bass", "treble", "balance"):
        entity = HtdEqNumber(client, "uid", 1, control, _make_entry(), "HTD Lync 12")
        assert entity.entity_id == f"number.htd_lync_12_zone_01_{control}"


def test_switch_entity_id():
    entity = HtdDndSwitch(_make_client(), "uid", 1, _make_entry(), "HTD Lync 12")
    assert entity.entity_id == "switch.htd_lync_12_zone_01_dnd"


def test_zone_display_name_does_not_affect_entity_ids():
    client = _make_client(zone_name="Kitchen")
    entry = _make_entry(zone_names={"1": "Great Room"})

    assert HtdDevice("uid", "HTD Lync 12", 1, [], client, entry).entity_id == "media_player.htd_lync_12_zone_01"
    assert HtdEqNumber(client, "uid", 1, "bass", entry, "HTD Lync 12").entity_id == "number.htd_lync_12_zone_01_bass"
    assert HtdDndSwitch(client, "uid", 1, entry, "HTD Lync 12").entity_id == "switch.htd_lync_12_zone_01_dnd"


def test_setup_entry_suggests_ids_from_the_entry_title():
    client = _make_client(zones=12)
    entry = _make_entry(title="HTD Lync 12", client=client)

    numbers, switches = [], []
    asyncio.run(number.async_setup_entry(None, entry, numbers.extend))
    asyncio.run(switch.async_setup_entry(None, entry, switches.extend))

    assert [e.entity_id for e in numbers[:3]] == [
        "number.htd_lync_12_zone_01_bass",
        "number.htd_lync_12_zone_01_treble",
        "number.htd_lync_12_zone_01_balance",
    ]
    assert switches[0].entity_id == "switch.htd_lync_12_zone_01_dnd"
    assert switches[-1].entity_id == "switch.htd_lync_12_zone_12_dnd"


def test_yaml_setup_suggests_ids_from_the_configured_device_name():
    client = _make_client(zones=12)
    hass = MagicMock()
    hass.data = {DOMAIN: [{CONF_UNIQUE_ID: "uid", CONF_DEVICE_NAME: "HTD Lync 12", "client": client}]}

    numbers, switches = [], []
    asyncio.run(number.async_setup_platform(hass, None, numbers.extend))
    asyncio.run(switch.async_setup_platform(hass, None, switches.extend))

    assert numbers[0].entity_id == "number.htd_lync_12_zone_01_bass"
    assert switches[0].entity_id == "switch.htd_lync_12_zone_01_dnd"


# --- unique_ids must never change: they are what keep existing entity ids intact ---

def test_media_player_unique_id_unchanged():
    assert HtdDevice("uid", "HTD Lync 12", 1, [], _make_client(), _make_entry()).unique_id == "uid_01"
    assert HtdDevice("uid", "HTD Lync 12", 12, [], _make_client(), _make_entry()).unique_id == "uid_12"


def test_number_unique_ids_unchanged():
    client = _make_client()
    for control in ("bass", "treble", "balance"):
        assert HtdEqNumber(client, "uid", 1, control, _make_entry(), "HTD Lync 12")._attr_unique_id == f"uid_zone_1_{control}"
        assert HtdEqNumber(client, "uid", 12, control, _make_entry(), "HTD Lync 12")._attr_unique_id == f"uid_zone_12_{control}"


def test_switch_unique_ids_unchanged():
    assert HtdDndSwitch(_make_client(), "uid", 1, _make_entry(), "HTD Lync 12")._attr_unique_id == "uid_zone_1_dnd"
    assert HtdDndSwitch(_make_client(), "uid", 12, _make_entry(), "HTD Lync 12")._attr_unique_id == "uid_zone_12_dnd"
