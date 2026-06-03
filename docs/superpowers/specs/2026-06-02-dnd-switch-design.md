# DND Switch Design — HTD Home Assistant (Issue #2)

**Date:** 2026-06-02
**Status:** Approved

## Summary

Add a `SwitchEntity` per zone for the HTD Do Not Disturb (DND) feature. DND prevents a zone from being affected by party mode and all-zones-on commands. This is a Lync-only feature; MCA devices receive no entities.

## Architecture & Files

| File | Change |
|---|---|
| `custom_components/htd/__init__.py` | Add `Platform.SWITCH` to `PLATFORMS` list |
| `custom_components/htd/switch.py` | **New** — `HtdDndSwitch(SwitchEntity)` with Lync-only guard |
| `README.md` | Add `hikirsch/htd-home-assistant` to thank-you list |

No config flow strings are needed; DND has no user-facing configuration step.

### `switch.py` Structure

Mirrors `number.py`:

- `async_setup_entry` checks `client.model["kind"]`; if not Lync, calls `async_add_entities([])` and returns immediately (no crash, no entities).
- Creates one `HtdDndSwitch` per zone (1 through `zone_count`).
- `HtdDndSwitch(SwitchEntity)` subscribes/unsubscribes in `async_added_to_hass` / `async_will_remove_from_hass`.
- `_attr_unique_id`: `"<unique_id>_zone_<N>_dnd"`.
- `_attr_entity_registry_enabled_default = True` (visible by default).

### Entity Naming

`"<zone_name> - DND"` — same zone-name resolution as EQ controls:
1. Config override from `CONF_ZONE_NAMES`
2. `client.get_zone_name(zone)`
3. Fallback: `"Zone N"`

## Data Flow

### State (read)

DND state is already parsed from zone packets by the library into `ZoneDetail.dnd` (bool). No new queries needed.

1. HTD controller pushes a zone state packet.
2. Library sets `ZoneDetail.dnd` and notifies all subscribers with the zone number (or `0` for all zones).
3. `HtdDndSwitch._do_update(zone)` filters to its own zone, calls `self.async_write_ha_state()`.

`is_on` reads `client.get_zone(zone).dnd`. Returns `None` when `has_zone_data(zone)` is `False`.

### Command (write)

1. User toggles the switch in HA.
2. `async_turn_on` calls `client.async_set_dnd(zone, True)`; `async_turn_off` calls `client.async_set_dnd(zone, False)`.
3. Lync client sends the command, validates the response, updates zone state, and notifies subscribers.
4. `_do_update` fires; HA reflects the new state.

No optimistic state, no debouncing — identical to EQ controls.

## Testing

New file: `custom_components/htd/tests/test_dnd_switch.py`

| Test | Verifies |
|---|---|
| `test_is_on_reflects_zone_dnd` | `is_on` is `True` when `ZoneDetail.dnd` is `True` |
| `test_is_on_false_when_dnd_off` | `is_on` is `False` when `ZoneDetail.dnd` is `False` |
| `test_is_on_none_when_no_zone_data` | `is_on` is `None` when `has_zone_data` returns `False` |
| `test_async_turn_on_calls_set_dnd` | `async_turn_on` calls `client.async_set_dnd(zone, True)` |
| `test_async_turn_off_calls_set_dnd` | `async_turn_off` calls `client.async_set_dnd(zone, False)` |
| `test_no_entities_for_mca` | `async_setup_entry` adds no entities when device kind is `mca` |
| `test_entity_name_uses_zone_override` | Name reads from `CONF_ZONE_NAMES` override when present |
| `test_entity_name_falls_back_to_zone_n` | Name falls back to `"Zone N - DND"` with no override |

Mocking approach: same `conftest.py` stubs as existing tests (no real network or HA runtime).
