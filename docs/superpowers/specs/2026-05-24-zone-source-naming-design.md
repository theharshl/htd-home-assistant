# Zone & Source Custom Naming — Design Spec

**Date:** 2026-05-24
**Branch:** `feat/zone-source-naming`
**Closes:** Issues #3 (zone naming), #8 (source naming)
**Status:** Approved, ready for planning

---

## Overview

Allow admins to assign custom display names to zones and sources from the HA config/options UI. Names pulled from the HTD controller are the default; HA stores only user overrides. No names are written back to the controller hardware.

---

## Goals

- Zone entities show a user-defined name instead of the hardcoded `"Zone N (device_name)"`.
- Source names in the media player `source_list` and `source` properties reflect user overrides.
- Controller-provided names serve as defaults; clearing an override reverts to the controller value.
- Naming is available during initial setup (skippable) and always available via the options flow.

---

## Non-Goals

- Writing names back to the HTD controller (`async_set_zone_name` / `async_set_source_name` not called).
- Zone filtering or hiding unused zones (tracked separately as deferred work).
- Changing entity IDs — only the friendly name changes.

---

## Architecture

### Name Resolution Priority

For every zone and source name, resolution follows this chain:

```
HA override dict → controller cached value → numeric fallback ("Zone N" / "Source N")
```

### Data Storage

Names stored in `config_entry.data` as sparse dicts — only entries the user has explicitly set are stored. Missing key means "no override, use controller value." Keys are strings (JSON constraint).

```json
{
  "host": "192.168.1.100",
  "port": 10006,
  "unique_id": "...",
  "device_name": "My HTD",
  "zone_names": {"2": "Master Suite"},
  "source_names": {"1": "Spotify", "5": "TV"}
}
```

Empty string submitted by user = treated as cleared override, excluded from the dict.

---

## Changes by Component

### 1. python-htd Library (new v0.1.2)

**Problem:** `get_source_name(source)` exists backed by `_source_names` cache. No equivalent for zone names.

**Changes to `base_client.py`:**
- Add `self._zone_names: dict = {}` in `__init__` alongside `_source_names`.
- Add `get_zone_name(zone: int) -> str | None` getter reading from `_zone_names`.
- Wire zone name responses from `async_query_zone_name()` into `_zone_names[zone]` in `_handle_message` — same parsing logic as source names.

No changes to the abstract interface (`async_query_zone_name` is already declared abstract on `BaseClient` and implemented on both `LyncClient` and `McaClient`).

**Release:** tag `v0.1.2`, update `manifest.json` to pin to it.

### 2. `const.py`

Three new constants:

```python
CONF_ZONE_NAMES = "zone_names"
CONF_SOURCE_NAMES = "source_names"
CONF_CUSTOMIZE_NAMES = "customize_names"
```

### 3. `__init__.py`

Add zone name querying at startup, immediately after the existing source name query block:

```python
for zone in range(1, zone_count + 1):
    await client.async_query_zone_name(zone)
```

Zone names are then cached in the client via `_zone_names` and readable via `client.get_zone_name(zone)`.

### 4. `config_flow.py` — Initial Setup

**`async_step_custom_connection`** (modified):
After successful `async_get_model_info`, create a temporary full client to query all zone and source names. Store results on the flow instance, then close the temporary client.

```python
temp_client = await async_get_client(network_address=network_address)
zone_count = temp_client.get_zone_count()
source_count = temp_client.get_source_count()
for z in range(1, zone_count + 1):
    await temp_client.async_query_zone_name(z)
for s in range(1, source_count + 1):
    await temp_client.async_query_source_name(s)
self._controller_zone_names = {
    z: temp_client.get_zone_name(z) for z in range(1, zone_count + 1)
}
self._controller_source_names = {
    s: temp_client.get_source_name(s) for s in range(1, source_count + 1)
}
self._zone_count = zone_count
self._source_count = source_count
await temp_client.close()  # verify exact disconnect method name against library API
return await self.async_step_device()
```

If name querying fails (timeout, controller busy): log a warning, set `_controller_zone_names` and `_controller_source_names` to empty dicts. Setup continues — naming steps show fields without controller hint text.

**New `async_step_device`** (replaces current `async_step_options`):
- Fields: `CONF_DEVICE_NAME`, `CONF_CUSTOMIZE_NAMES` (boolean, default `False`)
- `customize_names=True` → `async_step_zone_names`
- `customize_names=False` → `async_create_entry` with `zone_names: {}`, `source_names: {}`

**New `async_step_zone_names`**:
- Schema built dynamically at runtime using `self._zone_count` — only includes `zone_1_name` through `zone_N_name` for the actual zone count of the connected model (6 for MCA/Lync 6, 12 for Lync 12). All fields `vol.Optional`, blank by default.
- `description_placeholders` populated from `self._controller_zone_names` (e.g. `{"zone_1_controller": "Living Room", ...}`). If controller name is `None`, placeholder shows `"(not available)"`.
- Translation file includes keys for all 12 zone slots; HA only looks up keys present in the schema, so unused keys for smaller models are harmless.
- On submit: build sparse dict — skip entries where value is blank or `None`.
- Store result on `self._zone_name_overrides`, advance to `async_step_source_names`.

**New `async_step_source_names`**:
- Same pattern as zone names, using `self._controller_source_names` and `self._source_count`. Translation file includes all 19 source slots; schema includes only the model's actual count.
- On submit: call `async_create_entry` with full data dict including both sparse override dicts.

### 5. `config_flow.py` — Options Flow (`HtdOptionsFlowHandler`)

**`async_step_init`** (modified): Keep existing host, port, `device_name` fields. On submit, instead of calling `async_create_entry`, chain to `async_step_zone_names`.

**New `async_step_zone_names`**:
- Schema built dynamically using zone count from live client (`self.config_entry.runtime_data.get_zone_count()`).
- Controller names read from **live running client** (`self.config_entry.runtime_data`) — no temporary client needed.
- Existing overrides from `config_entry.data.get(CONF_ZONE_NAMES, {})` pre-fill their corresponding fields.
- `description_placeholders` built from `client.get_zone_name(zone)` for each zone.
- If client reports `not ready`: description hints show `"(controller unavailable)"`, existing overrides still pre-fill.
- On submit: build sparse dict, advance to `async_step_source_names`.

**New `async_step_source_names`**:
- Same pattern. On submit, calls `async_create_entry` → triggers integration reload.

No skip checkbox in the options flow — user explicitly opened Configure, so all three steps always shown.

**DHCP discovery path**: `async_step_dhcp` routes through `async_step_custom_connection`, which now continues to `async_step_device`. DHCP-discovered devices therefore also go through the naming steps — correct and desirable behavior.

### 6. `media_player.py`

**`HtdDevice.__init__`**: add `config_entry` parameter. Store as `self.config_entry`.

**`name` property** (currently returns `f"Zone {self.zone} ({self.device_name})"`):

```python
@property
def name(self) -> str:
    overrides = self.config_entry.data.get(CONF_ZONE_NAMES, {})
    return (
        overrides.get(str(self.zone))
        or self.client.get_zone_name(self.zone)
        or f"Zone {self.zone}"
    )
```

**New `_resolve_source_name` helper**:

```python
def _resolve_source_name(self, source: int) -> str:
    overrides = self.config_entry.data.get(CONF_SOURCE_NAMES, {})
    return (
        overrides.get(str(source))
        or self.client.get_source_name(source)
        or f"Source {source}"
    )
```

`source` and `source_list` properties both call `_resolve_source_name` instead of `client.get_source_name()` directly.

**`entity_id`** generation remains based on `device_name` — existing entity IDs are stable across naming changes.

### 7. `strings.json` / `translations/en.json`

New steps added (both files kept identical per HA convention):

```json
"device": {
  "title": "Device Setup",
  "data": {
    "device_name": "Device name",
    "customize_names": "Customize zone and source names now"
  },
  "data_description": {
    "customize_names": "You can update names later at any time via Configure."
  }
},
"zone_names": {
  "title": "Zone Names",
  "description": "Leave a field blank to use the controller's name for that zone.",
  "data": {
    "zone_1_name": "Zone 1",
    "zone_2_name": "Zone 2",
    "zone_3_name": "Zone 3",
    "zone_4_name": "Zone 4",
    "zone_5_name": "Zone 5",
    "zone_6_name": "Zone 6",
    "zone_7_name": "Zone 7",
    "zone_8_name": "Zone 8",
    "zone_9_name": "Zone 9",
    "zone_10_name": "Zone 10",
    "zone_11_name": "Zone 11",
    "zone_12_name": "Zone 12"
  },
  "data_description": {
    "zone_1_name": "Controller: {zone_1_controller}",
    "zone_2_name": "Controller: {zone_2_controller}",
    "zone_3_name": "Controller: {zone_3_controller}",
    "zone_4_name": "Controller: {zone_4_controller}",
    "zone_5_name": "Controller: {zone_5_controller}",
    "zone_6_name": "Controller: {zone_6_controller}",
    "zone_7_name": "Controller: {zone_7_controller}",
    "zone_8_name": "Controller: {zone_8_controller}",
    "zone_9_name": "Controller: {zone_9_controller}",
    "zone_10_name": "Controller: {zone_10_controller}",
    "zone_11_name": "Controller: {zone_11_controller}",
    "zone_12_name": "Controller: {zone_12_controller}"
  }
},
"source_names": {
  "title": "Source Names",
  "description": "Leave a field blank to use the controller's name for that source.",
  "data": {
    "source_1_name": "Source 1",
    ...
    "source_19_name": "Source 19"
  },
  "data_description": {
    "source_1_name": "Controller: {source_1_controller}",
    ...
    "source_19_name": "Controller: {source_19_controller}"
  }
}
```

Translation keys for the options flow steps use the same step IDs (`zone_names`, `source_names`) under the `"options"` key.

---

## Error Handling

| Scenario | Behavior |
|---|---|
| Temporary client fails to query names during initial setup | Log warning; proceed with empty hint dicts; naming fields show no "Controller:" text |
| `get_zone_name()` returns `None` at runtime | Fall back to `"Zone N"` |
| `get_source_name()` returns `None` at runtime | Fall back to `"Source N"` |
| User submits empty string for a name | Excluded from sparse dict; treated as cleared override |
| Options flow opened while client not connected | Description hints show `"(controller unavailable)"`; existing overrides still pre-fill |

---

## Testing

- **Name resolution logic**: unit test the three-tier fallback (override → controller → numeric) in isolation for both zones and sources.
- **Config flow — initial setup**: mock `async_get_client` returning known zone/source names; assert `description_placeholders` populated correctly; assert sparse dict built correctly (empty fields excluded); assert skip path produces empty dicts.
- **Config flow — options flow**: mock live client with known cached names; assert existing overrides pre-fill fields; assert save produces correct sparse dict in `config_entry.data`.
- **Media player regression**: assert `entity_id` unchanged after naming update; assert `name` and `source_list` reflect correct resolution order.
- **Library (python-htd)**: assert `get_zone_name()` returns cached value after `async_query_zone_name()` response processed; returns `None` if not yet queried.

---

## Affected Files Summary

| File | Change |
|---|---|
| `python-htd/htd_client/base_client.py` | Add `_zone_names` dict, `get_zone_name()`, wire `_handle_message` |
| `manifest.json` | Pin library to `v0.1.2` |
| `custom_components/htd/const.py` | Add 3 new constants |
| `custom_components/htd/__init__.py` | Add zone name queries at startup |
| `custom_components/htd/config_flow.py` | New steps: `device`, `zone_names`, `source_names` (both flows) |
| `custom_components/htd/media_player.py` | Update `name`, `source`, `source_list`; add `config_entry` param |
| `custom_components/htd/strings.json` | Add new step translations |
| `custom_components/htd/translations/en.json` | Mirror strings.json |
