# Per-Zone Source Filtering — Design Spec

**Issue:** [#5](https://github.com/theharshl/htd-home-assistant/issues/5)
**Branch:** `feat/per-zone-source-filtering` (to be created)
**Date:** 2026-05-25

---

## Overview

Allow users to define a per-zone whitelist of sources. When filtering is enabled, only whitelisted sources appear in the source dropdown for a given zone. Filtering is off by default; all sources are shown on all zones unless the user explicitly enables and configures it.

This feature also corrects a latent bug in `async_select_source` where source selection is mapped by list position rather than controller index — a bug that becomes visible once filtering is active.

---

## Data Model

Two new keys added to `config_entry.data`:

```python
CONF_SOURCE_FILTER_ENABLED = "source_filter_enabled"  # bool
CONF_ZONE_SOURCE_FILTERS   = "zone_source_filters"    # dict[str, list[int]]
```

Example stored value:

```json
{
  "source_filter_enabled": true,
  "zone_source_filters": {
    "1": [1, 3, 5],
    "2": [1, 2, 3, 4, 5, 6],
    "3": []
  }
}
```

**Rules:**
- Keys are zone numbers as strings (consistent with `CONF_ZONE_NAMES`).
- Values are 1-based controller source indices that are whitelisted for that zone.
- A zone absent from the dict, or with an empty list `[]`, is treated as **no filter** — all sources shown. This prevents accidentally blanking a zone's source list.
- When `source_filter_enabled` is `false`, `zone_source_filters` is ignored entirely and all zones show all sources.

---

## Config Flow Changes

Both `HtdConfigFlow` (initial setup) and `HtdOptionsFlowHandler` (reconfigure) receive the same two new steps.

### New Step: `source_filter_toggle`

A single boolean field. No other fields. The description text (see Localization section) explains what filtering is, that it is a whitelist, and that per-zone configuration follows if enabled.

Routing:
- Submitted as `False` → set `source_filter_enabled=False`, clear `zone_source_filters`, route to finish.
- Submitted as `True` → set `source_filter_enabled=True`, initialize `_current_filter_zone = 1`, route to `async_step_zone_source_filter`.

### New Step: `zone_source_filter`

A single step ID reused for all zones. The flow handler tracks `_current_filter_zone: int`. Each submission saves that zone's selections, increments the counter, and re-renders the same step for the next zone. When the counter exceeds zone count, routes to finish.

**Form fields:** One `vol.Optional(...): bool` field per source. Labels use resolved source names (see Name Resolution below).

**Defaults:**
- No prior config: all `True` (all checked).
- Prior config exists: `True` if source index is in the saved whitelist, `False` otherwise.

**`last_step` flag:** `True` only when rendering the final zone.

**Routing after final zone:** Both flows call their respective finish method (create entry for initial setup, update entry for options).

### Flow Sequences

**Initial config flow** (5 base steps, +N zone steps if filtering enabled):

```
user → device → zone_names → source_names → source_filter_toggle → [zone_1 … zone_N]
```

**Options flow** (4 base steps, +N zone steps if filtering enabled):

```
init → zone_names → source_names → source_filter_toggle → [zone_1 … zone_N]
```

**Step indicator strings** in `zone_names` and `source_names` steps update from their current values ("Step 3 of 4", "Step 4 of 4", "Step 1 of 3", etc.) to reflect the new base step counts ("Step 3 of 5", "Step 4 of 5", "Step 2 of 4", "Step 3 of 4", "Step 4 of 4").

---

## Name Resolution in Filter Steps

Zone and source names entered earlier in the same flow run are held in flow state and must be used to label the filter step — not `config_entry.data`, which may be stale (options flow) or nonexistent (initial setup).

Flow state variables required:
- `self._zone_name_overrides: dict` — already exists, populated in `async_step_zone_names`.
- `self._source_name_overrides: dict` — **new**, populated in `async_step_source_names` (currently this data is only passed to `config_entry.data` on submit; it needs to also be saved to flow state for use in the filter step).

**Zone name resolution in filter step title/description:**
```
self._zone_name_overrides.get(str(zone)) or client.get_zone_name(zone) or f"Zone {zone}"
```

**Source name resolution for checkbox labels:**
```
self._source_name_overrides.get(str(i)) or client.get_source_name(i) or f"Source {i}"
```

This ensures the filter step reflects the names the user just configured, not stale or generic labels.

---

## Media Player Fix

### Problem

`async_select_source` currently maps source name to controller index by list position:

```python
async def async_select_source(self, source: int):
    source_index = self.source_list.index(source)   # position in list
    await self.client.async_set_source(self.zone, source_index + 1)  # wrong when filtered
```

If `source_list` is `["Apple TV", "Spotify", "Radio"]` mapped to controller indices `[3, 7, 12]`, position 0 ("Apple TV") maps to `source_index + 1 = 1`, which is the wrong controller source.

### Fix

Introduce `_build_source_map()` returning `{display_name: controller_index}`. Both `source_list` and `async_select_source` use this map. The name-to-index mapping is always correct regardless of filtering.

```python
def _build_source_map(self) -> dict[str, int]:
    filter_enabled = (
        self.config_entry.data.get(CONF_SOURCE_FILTER_ENABLED, False)
        if self.config_entry else False
    )
    filters = (
        self.config_entry.data.get(CONF_ZONE_SOURCE_FILTERS, {})
        if self.config_entry else {}
    )
    allowed = filters.get(str(self.zone)) if filter_enabled else None

    result = {}
    for i in range(1, len(self.sources) + 1):
        # allowed=None means no filter; allowed=[] also means no filter (show all)
        if allowed is None or not allowed or i in allowed:
            result[self._resolve_source_name(i)] = i
    return result

@property
def source_list(self) -> list[str]:
    return list(self._build_source_map().keys())

async def async_select_source(self, source: str) -> None:
    controller_index = self._build_source_map().get(source)
    if controller_index is not None:
        await self.client.async_set_source(self.zone, controller_index)
```

`_build_source_map` is a pure dict comprehension with no I/O. Calling it twice per source selection is acceptable.

The type annotation on `async_select_source` is corrected from `int` to `str`.

---

## Localization

New and updated strings in `strings.json` and `translations/en.json`.

### `source_filter_toggle` step

**Title:** "Per-Zone Source Filtering"

**Description (verbatim draft):**
> Source filtering lets you control which sources appear in the source dropdown for each zone. This is a **whitelist** — only sources you check will be shown in that zone.
>
> By default, filtering is disabled and all sources are visible on every zone. If you enable filtering below, you will be taken through each zone one at a time to configure its source list.
>
> You can change this setting at any time via the integration's reconfigure option.

**Field label:** "Enable per-zone source filtering"

### `zone_source_filter` step

**Title:** "Source Filter — {zone_name} (Zone {zone_number} of {zone_count})"

**Description (verbatim draft):**
> Check each source that should be visible in **{zone_name}**. Unchecked sources will be hidden from the source dropdown for this zone.
>
> **Note:** If all sources are checked, or all are unchecked, all sources will be shown for this zone — both states produce the same result.

**Field labels:** Resolved source names (dynamic — no static strings needed for individual sources).

The `zone_source_filter` step uses "Zone X of N" progress phrasing in its title/description rather than "Step X of Y" — this keeps it visually distinct from the base setup steps and accurately reflects that the user is iterating through zones, not advancing through a linear setup sequence.

### Updated step indicators

| Step | Old | New |
|---|---|---|
| Config: zone_names description | "Step 3 of 4" | "Step 3 of 5" |
| Config: source_names description | "Step 4 of 4" | "Step 4 of 5" |
| Config: source_filter_toggle description | — | "Step 5 of 5" |
| Options: init description | "Step 1 of 3" | "Step 1 of 4" |
| Options: zone_names description | "Step 2 of 3" | "Step 2 of 4" |
| Options: source_names description | "Step 3 of 3" | "Step 3 of 4" |
| Options: source_filter_toggle description | — | "Step 4 of 4" |

---

## Files Changed

| File | Change |
|---|---|
| `custom_components/htd/const.py` | Add `CONF_SOURCE_FILTER_ENABLED`, `CONF_ZONE_SOURCE_FILTERS` |
| `custom_components/htd/config_flow.py` | Add `async_step_source_filter_toggle`, `async_step_zone_source_filter`; add `_source_name_overrides` state; update step routing; update step indicators |
| `custom_components/htd/media_player.py` | Add `_build_source_map`; replace `source_list` and `async_select_source` implementations; fix type annotation |
| `custom_components/htd/strings.json` | Add new steps; update step indicator strings |
| `custom_components/htd/translations/en.json` | Mirror `strings.json` changes |
| `custom_components/htd/CHANGELOG.md` | Add entry for v0.0.28 |
| `custom_components/htd/manifest.json` | Bump version to `0.0.28` |

---

## Out of Scope

- Filtering via the controller itself (HTD hardware has no per-zone source restriction capability).
- Zone hiding / disabling unused zones (separate issue).
- Source filtering on the legacy `async_setup_platform` (YAML config) path — that path does not use `config_entry.data` and is not modified.
