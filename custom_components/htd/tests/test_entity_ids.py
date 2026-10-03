"""Entity IDs and unique IDs across media_player, number and switch (issue #28).

Two separate guarantees are pinned here:

- Entity IDs for newly created entities derive only from the device name and the zone
  number, so every entity of a zone shares one prefix and a zone rename cannot leak into an
  ID. Before this, number/switch IDs were slugified from the zone's mutable display name.
- Unique IDs are byte-for-byte what they were before. The unique ID is the key Home Assistant
  uses to find an entity's existing registry entry, and that entry is what keeps an existing
  install's entity IDs (and every automation referencing them) intact. Changing a unique ID
  would orphan the old entity and create a new one.
"""
import asyncio
from unittest.mock import MagicMock

from homeassistant.const import CONF_UNIQUE_ID

from custom_components.htd import media_player, number, switch
from custom_components.htd.const import CONF_ZONE_NAMES, DOMAIN
from custom_components.htd.entity import get_zone_entity_id


def _client(zones=12, kind="lync", zone_name="Kitchen"):
    client = MagicMock()
    client.model = {"zones": zones, "kind": MagicMock(value=kind)}
    client.get_zone_count = MagicMock(return_value=zones)
    client.get_source_count = MagicMock(return_value=3)
    client.get_zone_name = MagicMock(return_value=zone_name)
    return client


def _entry(title="HTD Lync 12", zone_names=None):
    entry = MagicMock()
    entry.title = title
    entry.data = {CONF_UNIQUE_ID: "uid", CONF_ZONE_NAMES: zone_names or {}}
    return entry


def _setup(module, client, entry):
    """Run a platform's async_setup_entry and return the entities it added."""
    entry.runtime_data = client
    added = []
    asyncio.run(module.async_setup_entry(MagicMock(), entry, added.extend))
    return added


def _zone_1(entities):
    return [e for e in entities if e.zone == 1]


# --- shared helper ---

def test_helper_matches_the_existing_media_player_format_for_a_12_zone_device():
    # media_player IDs already shipped in this format; it must not drift
    assert get_zone_entity_id("media_player", "HTD Lync 12", 1, 12) == "media_player.htd_lync_12_zone_01"


def test_helper_uses_single_digit_zones_on_devices_with_ten_or_fewer_zones():
    assert get_zone_entity_id("media_player", "MCA-66", 3, 6) == "media_player.mca_66_zone_3"


def test_helper_appends_the_suffix_after_the_zone():
    assert get_zone_entity_id("number", "HTD Lync 12", 1, 12, "bass") == "number.htd_lync_12_zone_01_bass"


# --- every platform, end to end through async_setup_entry ---

def test_all_platforms_share_one_per_zone_prefix_on_lync_12():
    client, entry = _client(), _entry()
    ids = sorted(
        e.entity_id
        for module in (media_player, number, switch)
        for e in _zone_1(_setup(module, client, entry))
    )
    assert ids == [
        "media_player.htd_lync_12_zone_01",
        "number.htd_lync_12_zone_01_balance",
        "number.htd_lync_12_zone_01_bass",
        "number.htd_lync_12_zone_01_treble",
        "switch.htd_lync_12_zone_01_dnd",
    ]


def test_mca_entities_use_the_same_scheme():
    # MCA has no DND switch; switch.async_setup_entry adds nothing for it
    client, entry = _client(zones=6, kind="mca"), _entry(title="MCA-66")
    ids = sorted(
        e.entity_id
        for module in (media_player, number, switch)
        for e in _setup(module, client, entry)
        if e.zone == 3
    )
    assert ids == [
        "media_player.mca_66_zone_3",
        "number.mca_66_zone_3_balance",
        "number.mca_66_zone_3_bass",
        "number.mca_66_zone_3_treble",
    ]


def test_zone_display_name_does_not_affect_entity_ids():
    """The whole point of #28: a zone named "Kitchen" (by the controller or by an override)
    must not end up as number.kitchen_bass, because zone names change and entity IDs don't."""
    client = _client(zone_name="Kitchen")
    entry = _entry(zone_names={"1": "Great Room"})
    for module in (media_player, number, switch):
        for e in _zone_1(_setup(module, client, entry)):
            assert "kitchen" not in e.entity_id
            assert "great_room" not in e.entity_id
            assert e.entity_id.split(".", 1)[1].startswith("htd_lync_12_zone_01")


def test_yaml_setup_uses_the_configured_device_name():
    client = _client()
    hass = MagicMock()
    hass.data = {DOMAIN: [{CONF_UNIQUE_ID: "uid", "device_name": "HTD Lync 12", "client": client}]}
    added = []
    asyncio.run(number.async_setup_platform(hass, None, added.extend))
    asyncio.run(switch.async_setup_platform(hass, None, added.extend))
    assert sorted(e.entity_id for e in _zone_1(added)) == [
        "number.htd_lync_12_zone_01_balance",
        "number.htd_lync_12_zone_01_bass",
        "number.htd_lync_12_zone_01_treble",
        "switch.htd_lync_12_zone_01_dnd",
    ]


# --- unique IDs are frozen ---

def test_unique_ids_are_unchanged_from_before_issue_28():
    """Literal values copied from the pre-#28 code. If this fails, existing installs would
    lose every customised entity ID, name and automation reference on upgrade."""
    client, entry = _client(), _entry()
    uids = sorted(
        e.unique_id if module is media_player else e._attr_unique_id
        for module in (media_player, number, switch)
        for e in _zone_1(_setup(module, client, entry))
    )
    assert uids == [
        "uid_01",
        "uid_zone_1_balance",
        "uid_zone_1_bass",
        "uid_zone_1_dnd",
        "uid_zone_1_treble",
    ]
