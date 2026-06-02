# EQ Controls (Bass, Treble, Balance) — Design Spec

**Issue:** [#1](https://github.com/theharshl/htd-home-assistant/issues/1)
**Branch:** `feat/eq-controls`
**Date:** 2026-06-02

---

## Overview

Expose bass, treble, and balance as `NumberEntity` sliders in Home Assistant — one set of three entities per zone. All three are created automatically on HA restart for both new and existing installs. Bass and treble are enabled by default; balance is disabled by default (users can enable it via Settings → Devices & Services → entity list). No config flow changes are needed.

---

## Entity Type

`NumberEntity` with `NumberMode.SLIDER`. This is the standard HA pattern for numeric range controls. It renders as a slider in dashboards and the Lovelace media control card area, and is usable in automations.

---

## New File: `number.py`

Single class `HtdEqNumber(NumberEntity)` handles all three controls. A `control` parameter (`"bass"`, `"treble"`, `"balance"`) determines which library method is called and which `ZoneDetail` field is read.

### Range table

Ranges and step sizes are derived from `client.model["kind"]` at setup time via a module-level lookup table. No branching logic inside the class.

```python
from htd_client.constants import HtdConstants, HtdDeviceKind

_RANGES: dict[HtdDeviceKind, dict[str, tuple[float, float, float]]] = {
    HtdDeviceKind.lync: {
        "bass":    (HtdConstants.LYNC_MIN_BASS,    HtdConstants.LYNC_MAX_BASS,    1),
        "treble":  (HtdConstants.LYNC_MIN_TREBLE,  HtdConstants.LYNC_MAX_TREBLE,  1),
        "balance": (HtdConstants.LYNC_MIN_BALANCE, HtdConstants.LYNC_MAX_BALANCE, 1),
    },
    HtdDeviceKind.mca: {
        "bass":    (HtdConstants.MCA_MIN_BASS,    HtdConstants.MCA_MAX_BASS,    HtdConstants.MCA_BASS_TREBLE_STEP),
        "treble":  (HtdConstants.MCA_MIN_TREBLE,  HtdConstants.MCA_MAX_TREBLE,  HtdConstants.MCA_BASS_TREBLE_STEP),
        "balance": (HtdConstants.MCA_MIN_BALANCE, HtdConstants.MCA_MAX_BALANCE, HtdConstants.MCA_BALANCE_STEP),
    },
}
```

Effective ranges at runtime:

| Control | Lync | MCA |
|---|---|---|
| Bass    | -10 to +10, step 1 | -12 to +12, step 4 |
| Treble  | -10 to +10, step 1 | -12 to +12, step 4 |
| Balance | -18 to +18, step 1 | -12 to +12, step 6 |

### Entity attributes

```python
_attr_mode = NumberMode.SLIDER
_attr_has_entity_name = True
```

Balance entities only:
```python
_attr_entity_registry_enabled_default = False
```

Bass and treble entities use the default (`True`).

### Unique ID

`{unique_id}_zone_{zone}_{control}`

Example: `lync12-192.168.1.10_zone_3_bass`

### Device linkage

`device_info` uses `identifiers={(DOMAIN, unique_id)}` — same identifier as the zone's `MediaPlayerEntity`. HA groups all entities (media player + bass + treble + balance) under the same device card.

### `native_value`

Reads from `client.get_zone(zone).bass`, `.treble`, or `.balance`.

### `async_set_native_value`

Dispatches to the appropriate library method:

| control   | library call |
|-----------|-------------|
| `"bass"`    | `client.async_set_bass(zone, int(value))` |
| `"treble"`  | `client.async_set_treble(zone, int(value))` |
| `"balance"` | `client.async_set_balance(zone, int(value))` |

### Push subscription

Follows the same pattern as `HtdDevice` in `media_player.py`:

- `async_added_to_hass` — subscribes via `client.async_subscribe(zone, self._do_update)`
- `async_will_remove_from_hass` — unsubscribes
- `_do_update(zone)` — calls `self.async_write_ha_state()` when the zone's data changes

### `async_setup_entry`

```python
async def async_setup_entry(_, config_entry, async_add_entities):
    client = config_entry.runtime_data
    unique_id = config_entry.data.get(CONF_UNIQUE_ID)
    entities = [
        HtdEqNumber(client, config_entry, unique_id, zone, control)
        for zone in range(1, client.get_zone_count() + 1)
        for control in ("bass", "treble", "balance")
    ]
    async_add_entities(entities)
```

---

## Changes to Existing Files

### `__init__.py`

Add `Platform.NUMBER` to the platforms list:

```python
PLATFORMS: list[Platform] = [Platform.MEDIA_PLAYER, Platform.NUMBER]
```

### `const.py`

No changes. No new `CONF_` keys are needed — ranges live in `number.py`.

### `README.md`

Add a note in the Features section:

> Each zone exposes **Bass** and **Treble** sliders (enabled by default) and a **Balance** slider (disabled by default). To enable Balance, go to Settings → Devices & Services → your HTD device → entity list and toggle it on.

---

## Upgrade Behavior

Existing installs require only a **full HA restart** after dropping updated files. HA will automatically call `async_setup_entry` for `Platform.NUMBER` on every existing config entry. Bass and Treble appear immediately; Balance is registered but hidden until the user enables it. No reconfiguration required.

---

## Testing

New file: `tests/test_eq_controls.py`

1. **Range correctness** — for Lync and MCA kinds, assert `native_min_value`, `native_max_value`, and `native_step` match the expected values for each control.
2. **Enabled default** — assert balance entities have `entity_registry_enabled_default = False`; bass and treble have `True`.
3. **Set value dispatch** — assert `async_set_native_value` calls `async_set_bass`, `async_set_treble`, or `async_set_balance` with the correct zone and integer value.

---

## Version

`manifest.json` and `CHANGELOG.md`: `0.0.28` → `0.0.29`
