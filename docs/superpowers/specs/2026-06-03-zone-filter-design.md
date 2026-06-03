# Zone Filter Design — htd-home-assistant v0.0.30

**Date:** 2026-06-03
**Feature:** Allow users to hide/filter unused zones from the HA UI (Issue #4)
**Version:** 0.0.30

---

## Goal

Users with a Lync 12 (12 zones) often only use a subset of zones. This feature lets them hide unused zones by disabling all HA entities for those zones, reducing clutter in the UI. Configuration happens through the existing config/options flow.

---

## Section 1 — Config Flow

### Unified step order

Both the initial setup flow (`HtdConfigFlow`) and the reconfigure flow (`HtdOptionsFlowHandler`) follow the same step order from Zone Names onward:

**Initial setup:**
Connection → Device Setup → Zone Names → **Zone Filter** → Source Names → Source Filter Toggle → (Source Filter per zone, if enabled)

**Reconfigure:**
Configure Device → Zone Names → **Zone Filter** → Source Names → Source Filter Toggle → (Source Filter per zone, if enabled)

The only structural difference between the two flows is that initial setup has a separate Connection step to validate host/port before presenting Device Setup. In reconfigure, connection settings and device name are combined on the Configure Device page (`async_step_init`).

### Removal of CONF_CUSTOMIZE_NAMES

The "Customize zone and source names now" checkbox is removed from the Device Setup step in `HtdConfigFlow`. Zone Names and Source Names now always appear in both flows. Users who don't want custom names leave the fields blank and continue.

- `CONF_CUSTOMIZE_NAMES` is removed from `const.py`
- The conditional routing in `async_step_device` is removed; it always routes to `async_step_zone_names`
- No config entry migration is needed — the key was only read during initial setup, never persisted in a way that affects runtime

### New Zone Filter step

A new `async_step_zone_filter` is added to both `HtdConfigFlow` and `HtdOptionsFlowHandler`. It appears between Zone Names and Source Names in both flows.

The step shows one boolean field per zone (`zone_{i}_enabled`, default `True`). Zone labels show the custom name from the preceding Zone Names step when available, falling back to the controller's zone name.

The step description explains: all zones are checked by default; unchecking a zone disables all of its HA entities; entities remain in the registry and can be manually re-enabled.

---

## Section 2 — Data Model

### New constants

```python
# const.py
CONF_ZONE_FILTER_ENABLED = "zone_filter_enabled"  # bool
CONF_ENABLED_ZONES       = "enabled_zones"         # list[int]
```

### Storage format

Stored in `config_entry.data` alongside existing keys.

**Filtering off (all zones checked — default):**
```python
"zone_filter_enabled": False,
"enabled_zones": [],
```

**Filtering on (some zones unchecked):**
```python
"zone_filter_enabled": True,
"enabled_zones": [1, 2, 5],  # only these zones create active entities
```

### Submission logic

```python
enabled = [i for i in range(1, zone_count + 1) if user_input.get(f"zone_{i}_enabled", True)]
if len(enabled) == zone_count:
    # All on — store as disabled to avoid false-positive filtering
    self._zone_filter_enabled = False
    self._enabled_zones = []
else:
    self._zone_filter_enabled = True
    self._enabled_zones = enabled
```

The flag pattern is consistent with `CONF_SOURCE_FILTER_ENABLED`, which is already used the same way. Platforms can skip list inspection entirely when the flag is `False`.

---

## Section 3 — Entity Disabling

### Scope

All entity types for a filtered zone are disabled: `media_player`, `number` (bass, treble, balance), and `switch` (DND). Each platform applies the filter independently in its own `async_setup_entry`.

### Two-mechanism approach

**Mechanism 1 — First setup (new entity registration):**

Each entity class adds an `entity_registry_enabled_default` property:

```python
@property
def entity_registry_enabled_default(self) -> bool:
    if self.config_entry is None:
        return True
    if not self.config_entry.data.get(CONF_ZONE_FILTER_ENABLED, False):
        return True
    return self.zone in self.config_entry.data.get(CONF_ENABLED_ZONES, [])
```

This controls whether the entity is enabled when first added to the entity registry. Has no effect on entities already registered.

**Mechanism 2 — Reconfigure (existing entity registry entries):**

Before `async_add_entities`, each platform's `async_setup_entry` walks the entity registry and updates `disabled_by` to match the current config:

```python
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.entity_registry import RegistryEntryDisabler

registry = er.async_get(hass)
zone_filter_enabled = config_entry.data.get(CONF_ZONE_FILTER_ENABLED, False)
enabled_zones = set(config_entry.data.get(CONF_ENABLED_ZONES, []))

for zone in range(1, zone_count + 1):
    should_enable = not zone_filter_enabled or zone in enabled_zones
    for platform_domain, uid_suffix in platform_unique_ids(zone):
        entity_id = registry.async_get_entity_id(platform_domain, DOMAIN, uid_suffix)
        if entity_id:
            entry = registry.async_get(entity_id)
            if entry:
                if should_enable and entry.disabled_by == RegistryEntryDisabler.INTEGRATION:
                    registry.async_update_entity(entity_id, disabled_by=None)
                elif not should_enable and entry.disabled_by is None:
                    registry.async_update_entity(entity_id, disabled_by=RegistryEntryDisabler.INTEGRATION)
```

All zone entities are still passed to `async_add_entities` regardless of filter state. The registry controls visibility.

### Unique ID patterns per platform

| Platform | Unique ID suffix |
|---|---|
| `media_player` | `{unique_id}_{zone:02}` |
| `number` (bass) | `{unique_id}_{zone:02}_bass` |
| `number` (treble) | `{unique_id}_{zone:02}_treble` |
| `number` (balance) | `{unique_id}_{zone:02}_balance` |
| `switch` (DND) | `{unique_id}_{zone:02}_dnd` |

### User escape hatch

Entities disabled by the integration (`disabled_by = RegistryEntryDisabler.INTEGRATION`) can be manually re-enabled by the user through HA's entity registry UI. Re-checking the zone in the config flow and saving re-enables them automatically on reload.

---

## Section 4 — UI Strings

### New zone_filter step (both config and options flows)

```json
"zone_filter": {
  "title": "Zone Filter",
  "description": "Choose which zones to create Home Assistant entities for. Unchecked zones will be disabled — they still exist in the entity registry and can be manually re-enabled at any time.\n\nIf all zones are checked, no filtering is applied.",
  "data": {
    "zone_1_enabled": "Zone 1",
    ...
    "zone_12_enabled": "Zone 12"
  }
}
```

Zone labels use `data_description` placeholders for the zone name (custom override or controller name), consistent with how the zone_source_filter step labels sources.

### Updated step numbering

Step count strings in all step descriptions are updated to reflect the new total. The `en.json` "Step X of Y" strings in zone_names, source_names, and source_filter_toggle update accordingly. `strings.json` mirrors `en.json` exactly.

### Removed

The `customize_names` key is removed from the `device` step in both `en.json` and `strings.json`.

---

## Section 5 — Other Changes

### Version bump

`manifest.json`: `"version": "0.0.30"`

### README — remove HACS install instructions

The "Install via HACS" section is removed from `README.md`. The integration is not currently listed in HACS. Manual installation instructions remain.

---

## Files Changed

| File | Change |
|---|---|
| `custom_components/htd/const.py` | Add `CONF_ZONE_FILTER_ENABLED`, `CONF_ENABLED_ZONES`; remove `CONF_CUSTOMIZE_NAMES` |
| `custom_components/htd/config_flow.py` | Remove customize_names logic; add `async_step_zone_filter` to both flow classes; update routing and entry creation |
| `custom_components/htd/media_player.py` | Add `entity_registry_enabled_default`; add pre-setup registry update in `async_setup_entry` |
| `custom_components/htd/number.py` | Same zone filter logic as media_player |
| `custom_components/htd/switch.py` | Same zone filter logic as media_player |
| `custom_components/htd/translations/en.json` | Add `zone_filter` step; update step numbering; remove `customize_names` |
| `custom_components/htd/strings.json` | Mirror `en.json` |
| `custom_components/htd/manifest.json` | Bump version to `0.0.30` |
| `README.md` | Remove HACS installation section |

---

## Testing

- Unit tests for `async_step_zone_filter` submission logic (all checked → filter disabled; some unchecked → correct enabled_zones list)
- Unit tests for `entity_registry_enabled_default` on each entity class
- Unit tests for the pre-setup registry update logic (enable → disable, disable → enable, no-op cases)
- Existing 18 tests must continue to pass
