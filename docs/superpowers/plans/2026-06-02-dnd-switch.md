# DND Switch Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a `SwitchEntity` per zone for HTD's Do Not Disturb feature, visible by default, Lync-only.

**Architecture:** New `switch.py` platform file mirrors the `number.py` EQ controls pattern — `async_setup_entry` guards on device kind and returns early for non-Lync, then creates one `HtdDndSwitch(SwitchEntity)` per zone. `__init__.py` gains `Platform.SWITCH` in its `PLATFORMS` list. Tests mock HA and htd_client identically to existing test files.

**Tech Stack:** Home Assistant `SwitchEntity`, `htd_client.BaseClient.async_set_dnd`, `unittest.mock`, `pytest`

---

### Task 1: Add switch stub to conftest and write failing DND tests

**Files:**
- Modify: `custom_components/htd/tests/conftest.py`
- Create: `custom_components/htd/tests/test_dnd_switch.py`

- [ ] **Step 1: Add `SwitchEntity` stub to conftest.py**

Open `custom_components/htd/tests/conftest.py`. After the `_number_mod` block at the bottom, append:

```python
# homeassistant.components.switch needs a real class for HtdDndSwitch to inherit from
_switch_mod = MagicMock()

class _SwitchEntityStub:
    """Stub base — lets HtdDndSwitch be defined and instantiated in tests."""
    should_poll = False
    def async_write_ha_state(self): pass

_switch_mod.SwitchEntity = _SwitchEntityStub
sys.modules["homeassistant.components.switch"] = _switch_mod
```

- [ ] **Step 2: Create `test_dnd_switch.py` with all 8 tests**

Create `custom_components/htd/tests/test_dnd_switch.py`:

```python
"""Tests for HtdDndSwitch in switch.py."""
import asyncio
from unittest.mock import AsyncMock, MagicMock

from custom_components.htd.switch import HtdDndSwitch, async_setup_entry


def _make_client(kind_value="lync", zone_name=None, has_zone_data=True, dnd=False):
    client = MagicMock()
    client.model = {"kind": MagicMock(value=kind_value)}
    client.async_set_dnd = AsyncMock()
    client.get_zone_name = MagicMock(return_value=zone_name)
    client.has_zone_data = MagicMock(return_value=has_zone_data)
    zone = MagicMock()
    zone.dnd = dnd
    client.get_zone = MagicMock(return_value=zone)
    return client


def _make_config_entry(zone_names=None):
    entry = MagicMock()
    entry.data = {"zone_names": zone_names or {}}
    return entry


def _make_entity(client, zone=1, zone_names=None):
    return HtdDndSwitch(client, "uid", zone=zone, config_entry=_make_config_entry(zone_names))


def test_is_on_reflects_zone_dnd():
    client = _make_client(dnd=True)
    entity = _make_entity(client)
    assert entity.is_on is True


def test_is_on_false_when_dnd_off():
    client = _make_client(dnd=False)
    entity = _make_entity(client)
    assert entity.is_on is False


def test_is_on_none_when_no_zone_data():
    client = _make_client(has_zone_data=False)
    entity = _make_entity(client)
    assert entity.is_on is None


def test_async_turn_on_calls_set_dnd():
    client = _make_client()
    entity = _make_entity(client, zone=2)
    asyncio.run(entity.async_turn_on())
    client.async_set_dnd.assert_called_once_with(2, True)


def test_async_turn_off_calls_set_dnd():
    client = _make_client()
    entity = _make_entity(client, zone=3)
    asyncio.run(entity.async_turn_off())
    client.async_set_dnd.assert_called_once_with(3, False)


def test_no_entities_for_mca():
    client = _make_client(kind_value="mca")
    config_entry = MagicMock()
    config_entry.runtime_data = client

    captured = []
    asyncio.run(async_setup_entry(None, config_entry, lambda ents: captured.extend(ents)))
    assert captured == []
    client.get_zone_count.assert_not_called()


def test_entity_name_uses_zone_override():
    client = _make_client(zone_name="Kitchen")
    entity = _make_entity(client, zone=1, zone_names={"1": "01-Family Room"})
    assert entity.name == "01-Family Room - DND"


def test_entity_name_falls_back_to_zone_n():
    client = _make_client(zone_name=None)
    entity = _make_entity(client, zone=4)
    assert entity.name == "Zone 4 - DND"
```

- [ ] **Step 3: Run tests — verify they fail with ImportError**

```bash
cd /home/harshl/projects/htd-home-assistant/htd-home-assistant && python -m pytest custom_components/htd/tests/test_dnd_switch.py -v
```

Expected: `ImportError: cannot import name 'HtdDndSwitch' from 'custom_components.htd.switch'` (file doesn't exist yet — that's correct).

- [ ] **Step 4: Commit**

```bash
git add custom_components/htd/tests/conftest.py custom_components/htd/tests/test_dnd_switch.py
git commit -m "test: add failing DND switch tests (issue #2)"
```

---

### Task 2: Implement `switch.py`

**Files:**
- Create: `custom_components/htd/switch.py`

- [ ] **Step 1: Create `switch.py`**

Create `custom_components/htd/switch.py`:

```python
"""DND (Do Not Disturb) per-zone switch entity for HTD Lync devices."""
from homeassistant.components.switch import SwitchEntity
from homeassistant.const import CONF_UNIQUE_ID

from .const import CONF_ZONE_NAMES


async def async_setup_entry(_, config_entry, async_add_entities):
    client = config_entry.runtime_data
    if client.model["kind"].value != "lync":
        return
    unique_id = config_entry.data.get(CONF_UNIQUE_ID)
    entities = [
        HtdDndSwitch(client, unique_id, zone, config_entry)
        for zone in range(1, client.get_zone_count() + 1)
    ]
    async_add_entities(entities)


class HtdDndSwitch(SwitchEntity):
    should_poll = False
    _attr_entity_registry_enabled_default = True

    def __init__(self, client, unique_id: str, zone: int, config_entry):
        self.client = client
        self.zone = zone
        self.config_entry = config_entry
        self._attr_unique_id = f"{unique_id}_zone_{zone}_dnd"

    @property
    def name(self) -> str:
        overrides = self.config_entry.data.get(CONF_ZONE_NAMES, {})
        zone_name = (
            overrides.get(str(self.zone))
            or self.client.get_zone_name(self.zone)
            or f"Zone {self.zone}"
        )
        return f"{zone_name} - DND"

    @property
    def is_on(self) -> bool | None:
        if not self.client.has_zone_data(self.zone):
            return None
        return self.client.get_zone(self.zone).dnd

    async def async_turn_on(self, **kwargs) -> None:
        await self.client.async_set_dnd(self.zone, True)

    async def async_turn_off(self, **kwargs) -> None:
        await self.client.async_set_dnd(self.zone, False)

    def _do_update(self, zone: int) -> None:
        if zone is None and not self.client.has_zone_data(self.zone):
            return
        if zone is not None and zone != 0 and zone != self.zone:
            return
        if not self.client.has_zone_data(self.zone):
            return
        self.async_write_ha_state()

    async def async_added_to_hass(self) -> None:
        await self.client.async_subscribe(self._do_update)

    async def async_will_remove_from_hass(self) -> None:
        await self.client.async_unsubscribe(self._do_update)
```

- [ ] **Step 2: Run DND tests — verify all 8 pass**

```bash
cd /home/harshl/projects/htd-home-assistant/htd-home-assistant && python -m pytest custom_components/htd/tests/test_dnd_switch.py -v
```

Expected: `8 passed`

- [ ] **Step 3: Run full test suite — verify no regressions**

```bash
cd /home/harshl/projects/htd-home-assistant/htd-home-assistant && python -m pytest custom_components/htd/tests/ -v
```

Expected: all existing tests still pass alongside the 8 new ones.

- [ ] **Step 4: Commit**

```bash
git add custom_components/htd/switch.py
git commit -m "feat: add DND switch entity per zone for Lync devices (issue #2)"
```

---

### Task 3: Register `Platform.SWITCH` in `__init__.py`

**Files:**
- Modify: `custom_components/htd/__init__.py:17`

- [ ] **Step 1: Add `Platform.SWITCH` to `PLATFORMS`**

In `custom_components/htd/__init__.py`, find line 17:

```python
PLATFORMS: list[Platform] = [Platform.MEDIA_PLAYER, Platform.NUMBER]
```

Change it to:

```python
PLATFORMS: list[Platform] = [Platform.MEDIA_PLAYER, Platform.NUMBER, Platform.SWITCH]
```

- [ ] **Step 2: Run full test suite — verify nothing broke**

```bash
cd /home/harshl/projects/htd-home-assistant/htd-home-assistant && python -m pytest custom_components/htd/tests/ -v
```

Expected: all tests still pass.

- [ ] **Step 3: Commit**

```bash
git add custom_components/htd/__init__.py
git commit -m "feat: register switch platform for DND controls"
```

---

### Task 4: Update README

**Files:**
- Modify: `README.md`

- [ ] **Step 1: Add `hikirsch/htd-home-assistant` to Code Credits**

In `README.md`, find the `## Code Credits` section. The last line currently reads:

```
- **Special thanks to [kingfetty](https://github.com/kingfetty/python-htd)** — whose foundational work on full Lync support (zone/source naming, DND, device discovery, and all-zone queries) made this integration significantly more capable.
```

Insert one line immediately above it:

```
- **[hikirsch/htd-home-assistant](https://github.com/hikirsch/htd-home-assistant)** — the upstream integration this fork is built on.
```

So the section ends with:

```
- **[hikirsch/htd-home-assistant](https://github.com/hikirsch/htd-home-assistant)** — the upstream integration this fork is built on.
- **Special thanks to [kingfetty](https://github.com/kingfetty/python-htd)** — whose foundational work on full Lync support (zone/source naming, DND, device discovery, and all-zone queries) made this integration significantly more capable.
```

- [ ] **Step 2: Commit**

```bash
git add README.md
git commit -m "docs: add hikirsch/htd-home-assistant to code credits"
```
