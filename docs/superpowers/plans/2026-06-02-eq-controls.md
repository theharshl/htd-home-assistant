# EQ Controls Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Expose bass, treble, and balance as `NumberEntity` sliders in HA — three per zone, created automatically on restart, balance hidden by default.

**Architecture:** New `custom_components/htd/number.py` registers `HtdEqNumber` entities via `async_setup_entry`. Ranges are looked up by device kind string (`"lync"` / `"mca"`). Three pure helper functions (`_eq_range`, `_eq_enabled_default`, `_apply_eq`) contain all the testable logic. `HtdEqNumber` subscribes to the existing push model exactly like `HtdDevice`.

**Tech Stack:** Python 3.12+, Home Assistant `NumberEntity`, `htd_client.BaseClient`, `uvx pytest` for tests.

---

> **Spec deviations (intentional):**
> - `_RANGES` uses string keys `"lync"`/`"mca"` (matching `HtdDeviceKind.value`) rather than `HtdDeviceKind` enum keys — the enum is mocked in tests, making it unusable as a dict key in a testable way.
> - `async_added_to_hass` does NOT call `client.refresh()` — the zone's `HtdDevice` already calls it; calling it 3× per zone (once per EQ entity) is wasteful.
> - `device_info` is not implemented — `HtdDevice` also lacks it, and HA groups all entities from a config entry under one device automatically.

---

## File Map

| Action | File | Purpose |
|--------|------|---------|
| Create | `custom_components/htd/number.py` | `HtdEqNumber` entity + helpers |
| Modify | `conftest.py` | Add `homeassistant.components.number` stub |
| Modify | `custom_components/htd/tests/conftest.py` | Same stub (inner conftest mirrors root) |
| Create | `custom_components/htd/tests/test_eq_controls.py` | 9 tests for range, defaults, dispatch |
| Modify | `custom_components/htd/__init__.py` | Add `Platform.NUMBER` to `PLATFORMS` |
| Modify | `README.md` | Document EQ entities + balance visibility |
| Modify | `custom_components/htd/manifest.json` | Version `0.0.28` → `0.0.29` |
| Modify | `custom_components/htd/CHANGELOG.md` | Add `0.0.29` entry |

---

### Task 1: Update conftest files + write failing tests

**Files:**
- Modify: `conftest.py`
- Modify: `custom_components/htd/tests/conftest.py`
- Create: `custom_components/htd/tests/test_eq_controls.py`

- [ ] **Step 1: Add `homeassistant.components.number` stub to root `conftest.py`**

The existing mock loop makes `NumberEntity` a `MagicMock` attribute, which Python rejects as a base class. Replace the plain module entry with a proper stub class. Add these lines at the end of `conftest.py`, after the `for` loop:

```python
# homeassistant.components.number needs a real class for HtdEqNumber to inherit from
import types as _types
from unittest.mock import MagicMock as _MagicMock

_number_mod = _MagicMock()

class _NumberEntityStub:
    """Stub base — lets HtdEqNumber be defined and instantiated in tests."""
    should_poll = False
    def async_write_ha_state(self): pass

_number_mod.NumberEntity = _NumberEntityStub
sys.modules["homeassistant.components.number"] = _number_mod
```

- [ ] **Step 2: Apply the same addition to the inner conftest**

`custom_components/htd/tests/conftest.py` is an identical copy of the root conftest. Add the same block at the end of that file too.

- [ ] **Step 3: Write `test_eq_controls.py`**

Create `custom_components/htd/tests/test_eq_controls.py`:

```python
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
```

- [ ] **Step 4: Run the new tests — confirm they fail**

```bash
uvx pytest custom_components/htd/tests/test_eq_controls.py -v
```

Expected: `ImportError: cannot import name '_eq_range' from 'custom_components.htd.number'` (module doesn't exist yet). If you see a different error, investigate before proceeding.

---

### Task 2: Create `number.py` and make tests pass

**Files:**
- Create: `custom_components/htd/number.py`

- [ ] **Step 1: Create `custom_components/htd/number.py`**

```python
"""EQ controls (bass, treble, balance) as NumberEntity sliders for HTD zones."""
import logging

from homeassistant.components.number import NumberEntity, NumberMode
from homeassistant.const import CONF_UNIQUE_ID

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

# Ranges as (min, max, step). String keys match HtdDeviceKind.value ("lync"/"mca").
_RANGES: dict[str, dict[str, tuple[float, float, float]]] = {
    "lync": {
        "bass":    (-10.0, 10.0, 1.0),
        "treble":  (-10.0, 10.0, 1.0),
        "balance": (-18.0, 18.0, 1.0),
    },
    "mca": {
        "bass":    (-12.0, 12.0, 4.0),
        "treble":  (-12.0, 12.0, 4.0),
        "balance": (-12.0, 12.0, 6.0),
    },
}


def _eq_range(kind_value: str, control: str) -> tuple[float, float, float]:
    """Return (min, max, step) for the given device kind value and control name."""
    return _RANGES[kind_value][control]


def _eq_enabled_default(control: str) -> bool:
    """Balance is hidden by default; bass and treble are shown."""
    return control != "balance"


async def async_setup_entry(_, config_entry, async_add_entities):
    client = config_entry.runtime_data
    unique_id = config_entry.data.get(CONF_UNIQUE_ID)
    entities = [
        HtdEqNumber(client, unique_id, zone, control)
        for zone in range(1, client.get_zone_count() + 1)
        for control in ("bass", "treble", "balance")
    ]
    async_add_entities(entities)


class HtdEqNumber(NumberEntity):
    _attr_mode = NumberMode.SLIDER
    _attr_has_entity_name = True
    should_poll = False

    def __init__(self, client, unique_id: str, zone: int, control: str):
        self.client = client
        self.zone = zone
        self.control = control
        kind_value = client.model["kind"].value
        min_val, max_val, step = _eq_range(kind_value, control)
        self._attr_native_min_value = min_val
        self._attr_native_max_value = max_val
        self._attr_native_step = step
        self._attr_unique_id = f"{unique_id}_zone_{zone}_{control}"
        self._attr_name = control.capitalize()
        self._attr_entity_registry_enabled_default = _eq_enabled_default(control)

    @property
    def native_value(self) -> float | None:
        if not self.client.has_zone_data(self.zone):
            return None
        return getattr(self.client.get_zone(self.zone), self.control)

    async def async_set_native_value(self, value: float) -> None:
        int_val = int(value)
        if self.control == "bass":
            await self.client.async_set_bass(self.zone, int_val)
        elif self.control == "treble":
            await self.client.async_set_treble(self.zone, int_val)
        else:
            await self.client.async_set_balance(self.zone, int_val)

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

- [ ] **Step 2: Run the new tests — confirm they pass**

```bash
uvx pytest custom_components/htd/tests/test_eq_controls.py -v
```

Expected: 12 tests, all `PASSED`.

- [ ] **Step 3: Run the full test suite — confirm nothing broken**

```bash
uvx pytest custom_components/htd/tests/ -v
```

Expected: 30 tests, all `PASSED`.

- [ ] **Step 4: Commit**

```bash
git add conftest.py custom_components/htd/tests/conftest.py \
        custom_components/htd/number.py \
        custom_components/htd/tests/test_eq_controls.py
git commit -m "feat: add bass, treble, balance NumberEntity controls (issue #1)"
```

---

### Task 3: Register `Platform.NUMBER` in `__init__.py`

**Files:**
- Modify: `custom_components/htd/__init__.py` line 17

- [ ] **Step 1: Add `Platform.NUMBER` to PLATFORMS**

Change line 17 in `__init__.py` from:

```python
PLATFORMS: list[Platform] = [Platform.MEDIA_PLAYER]
```

to:

```python
PLATFORMS: list[Platform] = [Platform.MEDIA_PLAYER, Platform.NUMBER]
```

- [ ] **Step 2: Run full test suite**

```bash
uvx pytest custom_components/htd/tests/ -v
```

Expected: 30 tests, all `PASSED`.

- [ ] **Step 3: Commit**

```bash
git add custom_components/htd/__init__.py
git commit -m "feat: register number platform for EQ controls"
```

---

### Task 4: Update README

**Files:**
- Modify: `README.md`

- [ ] **Step 1: Add EQ controls to the Features section**

In `README.md`, find the Features section (starting at line 16). Add a new bullet after the source names bullet:

```markdown
- Per-zone **Bass** and **Treble** sliders (enabled by default) and a **Balance** slider (disabled by default — see below)
```

Then add a new section after "Customizing Zone and Source Names":

```markdown
## EQ Controls (Bass, Treble, Balance)

Each zone exposes three `number` entities for equalizer adjustments:

| Entity | Default | Range (Lync) | Range (MCA) |
|--------|---------|-------------|-------------|
| Bass   | Enabled | -10 to +10, step 1 | -12 to +12, step 4 |
| Treble | Enabled | -10 to +10, step 1 | -12 to +12, step 4 |
| Balance | **Hidden** | -18 to +18, step 1 | -12 to +12, step 6 |

Bass and Treble appear automatically on the device page and in dashboards after installing this version. Balance is created but hidden by default because most fixed-speaker whole-home audio setups never need it.

**To enable Balance:** Go to **Settings → Devices & Services → your HTD device** → find the Balance entity for the zone you want → click the toggle to enable it.
```

- [ ] **Step 2: Commit**

```bash
git add README.md
git commit -m "docs: document EQ controls and balance visibility in README"
```

---

### Task 5: Version bump and CHANGELOG

**Files:**
- Modify: `custom_components/htd/manifest.json`
- Modify: `custom_components/htd/CHANGELOG.md`

- [ ] **Step 1: Bump version in `manifest.json`**

Change `"version": "0.0.28"` to `"version": "0.0.29"`.

- [ ] **Step 2: Add CHANGELOG entry**

Prepend to `custom_components/htd/CHANGELOG.md`:

```markdown
## [0.0.29] - 2026-06-02
### Added
- Bass and Treble sliders (NumberEntity) per zone, enabled by default (issue #1)
- Balance slider per zone, disabled by default — enable via Settings → Devices & Services → entity list

```

- [ ] **Step 3: Run full test suite one final time**

```bash
uvx pytest custom_components/htd/tests/ -v
```

Expected: 30 tests, all `PASSED`.

- [ ] **Step 4: Commit**

```bash
git add custom_components/htd/manifest.json custom_components/htd/CHANGELOG.md
git commit -m "chore: bump version to 0.0.29"
```
