# Zone & Source Custom Naming Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Allow admins to assign custom display names to zones and sources from the HA config/options UI, with controller-provided names as defaults and HA storing only sparse overrides.

**Architecture:** Library gains `get_zone_name()` backed by a `_zone_names` cache populated from `ZONE_NAME_RECEIVE_COMMAND` responses. HA stores only user-set overrides as string-keyed dicts in `config_entry.data`. Media player resolves names as: HA override → controller cached value → numeric fallback. Initial setup offers naming with blank optional fields (no controller hints — responses are async and the client isn't running yet); the options flow reads from the live client and shows "Controller: X" hints via `description_placeholders`.

**Tech Stack:** Python, Home Assistant config flow (`voluptuous`/`cv`), `htd_client` library, `pytest`, `pytest-asyncio`

---

## File Map

| File | Change |
|---|---|
| `python-htd/htd_client/base_client.py` | Add `_zone_names = {}` in `async_connect`, update `ZONE_NAME_RECEIVE_COMMAND` handler, add `get_zone_name()` getter |
| `python-htd/tests/test_zone_name_cache.py` | New: unit tests for `get_zone_name()` |
| `custom_components/htd/const.py` | Add `CONF_ZONE_NAMES`, `CONF_SOURCE_NAMES`, `CONF_CUSTOMIZE_NAMES` |
| `custom_components/htd/__init__.py` | Add zone name queries at startup (Lync only) |
| `custom_components/htd/media_player.py` | Add `config_entry` param to `HtdDevice`, update `name` property, add `_resolve_source_name`, update `source`/`source_list` |
| `custom_components/htd/config_flow.py` | Rename `async_step_options` → `async_step_device`; add `async_step_zone_names`, `async_step_source_names` to both initial setup and options flows |
| `custom_components/htd/strings.json` | Add `device`, `zone_names`, `source_names` steps under `config` and `options` |
| `custom_components/htd/translations/en.json` | Mirror `strings.json` exactly |
| `custom_components/htd/manifest.json` | Pin library to `v0.1.2` |
| `custom_components/htd/CHANGELOG.md` | Add `0.0.27` entry |

---

## Task 1: Add `get_zone_name()` to python-htd library

**Files:**
- Modify: `python-htd/htd_client/base_client.py`
- Create: `python-htd/tests/test_zone_name_cache.py`

- [ ] **Step 1.1: Write the failing test**

Create `python-htd/tests/test_zone_name_cache.py`:

```python
import asyncio
import pytest
from unittest.mock import MagicMock
from htd_client.lync_client import HtdLyncClient
from htd_client.constants import HtdDeviceKind, HtdCommonCommands
from htd_client.models import ZoneDetail


@pytest.fixture
def lync_client():
    loop = MagicMock()
    model_info = {
        "zones": 6, "sources": 12, "friendly_name": "Lync6",
        "name": "Lync6", "kind": HtdDeviceKind.lync, "identifier": b'Wangine_Lync6'
    }
    client = HtdLyncClient(loop, model_info)
    client._connection = MagicMock()
    client._socket_lock = asyncio.Lock()
    client._zone_names = {}
    client._zone_data = {}
    client._source_names = {}
    return client


def test_get_zone_name_returns_none_before_query(lync_client):
    assert lync_client.get_zone_name(1) is None


def test_get_zone_name_returns_none_for_unknown_zone(lync_client):
    lync_client._zone_names[1] = "Living Room"
    assert lync_client.get_zone_name(99) is None


def test_get_zone_name_returns_cached_name(lync_client):
    lync_client._zone_names[1] = "Living Room"
    assert lync_client.get_zone_name(1) == "Living Room"


def test_zone_name_cached_independently_of_zone_data(lync_client):
    # Zone data does NOT exist for zone 2 yet
    # Simulate _handle_message processing a ZONE_NAME_RECEIVE_COMMAND for zone 2
    lync_client._zone_names[2] = "office"
    # zone_data should NOT be required for get_zone_name to work
    assert 2 not in lync_client._zone_data
    assert lync_client.get_zone_name(2) == "office"


def test_zone_name_also_updates_zone_data_when_present(lync_client):
    # When zone_data already exists, _zone_data[zone].name should also be updated
    lync_client._zone_data[1] = ZoneDetail(1)
    lync_client._zone_names[1] = "living room"
    lync_client._zone_data[1].name = "living room"
    assert lync_client._zone_data[1].name == "living room"
    assert lync_client.get_zone_name(1) == "living room"
```

- [ ] **Step 1.2: Run tests to verify they fail**

```bash
cd /Users/lharsh/projects/htd-home-assistant/python-htd
uv run pytest tests/test_zone_name_cache.py -v
```

Expected: FAIL — `HtdLyncClient` has no `get_zone_name` method; `_zone_names` not initialized.

- [ ] **Step 1.3: Add `_zone_names` to `async_connect` in `base_client.py`**

In `base_client.py`, locate `async_connect`. Find the line `self._source_names = {}` and add `_zone_names` immediately after it:

```python
self._source_names = {}
self._zone_names = {}
```

- [ ] **Step 1.4: Update `ZONE_NAME_RECEIVE_COMMAND` handler in `_handle_message`**

In `base_client.py`, find this block:

```python
elif cmd == HtdCommonCommands.ZONE_NAME_RECEIVE_COMMAND:
    name = str(data[0:11].decode(errors="ignore").rstrip('\0')).lower()
    if self.has_zone_data(zone):
        self._zone_data[zone].name = name
```

Replace it with:

```python
elif cmd == HtdCommonCommands.ZONE_NAME_RECEIVE_COMMAND:
    name = str(data[0:11].decode(errors="ignore").rstrip('\0')).lower()
    self._zone_names[zone] = name
    if self.has_zone_data(zone):
        self._zone_data[zone].name = name
```

- [ ] **Step 1.5: Add `get_zone_name()` getter to `base_client.py`**

Locate the existing `get_source_name` method:

```python
def get_source_name(self, source: int) -> str:
    return self._source_names.get(source, f"Source {source}")
```

Add `get_zone_name` immediately after it:

```python
def get_zone_name(self, zone: int) -> str | None:
    return self._zone_names.get(zone)
```

- [ ] **Step 1.6: Run tests to verify they pass**

```bash
cd /Users/lharsh/projects/htd-home-assistant/python-htd
uv run pytest tests/test_zone_name_cache.py -v
```

Expected: all 5 tests PASS.

- [ ] **Step 1.7: Run full test suite to confirm no regressions**

```bash
cd /Users/lharsh/projects/htd-home-assistant/python-htd
uv run pytest --tb=short -q
```

Expected: 157 passed (152 original + 5 new), 0 failures.

- [ ] **Step 1.8: Tag library as v0.1.2 and push**

```bash
cd /Users/lharsh/projects/htd-home-assistant/python-htd
git add htd_client/base_client.py tests/test_zone_name_cache.py
git commit -m "feat: add get_zone_name() getter with independent _zone_names cache"
git tag v0.1.2
git push && git push --tags
```

---

## Task 2: Add new constants

**Files:**
- Modify: `custom_components/htd/const.py`

- [ ] **Step 2.1: Add constants**

Open `custom_components/htd/const.py` and add after the existing constants:

```python
CONF_ZONE_NAMES = "zone_names"
CONF_SOURCE_NAMES = "source_names"
CONF_CUSTOMIZE_NAMES = "customize_names"
```

- [ ] **Step 2.2: Commit**

```bash
cd /Users/lharsh/projects/htd-home-assistant/htd-home-assistant
git add custom_components/htd/const.py
git commit -m "feat: add CONF_ZONE_NAMES, CONF_SOURCE_NAMES, CONF_CUSTOMIZE_NAMES constants"
```

---

## Task 3: Add zone name queries at startup

**Files:**
- Modify: `custom_components/htd/__init__.py`

- [ ] **Step 3.1: Update `async_setup_entry` to query zone names**

Open `custom_components/htd/__init__.py`. Add `HtdDeviceKind` to the import from `htd_client`:

```python
from htd_client import async_get_client
from htd_client.constants import HtdDeviceKind
```

Then locate this existing block in `async_setup_entry`:

```python
source_count = client.get_source_count()
await asyncio.gather(*[
    client.async_query_source_name(i)
    for i in range(1, source_count + 1)
])
```

Add zone name queries immediately after it:

```python
source_count = client.get_source_count()
await asyncio.gather(*[
    client.async_query_source_name(i)
    for i in range(1, source_count + 1)
])

if client.model.get("kind") == HtdDeviceKind.lync:
    zone_count = client.get_zone_count()
    try:
        await asyncio.gather(*[
            client.async_query_zone_name(z)
            for z in range(1, zone_count + 1)
        ])
    except NotImplementedError:
        _LOGGER.warning("Zone name queries not supported on this model")
```

- [ ] **Step 3.2: Commit**

```bash
git add custom_components/htd/__init__.py
git commit -m "feat: query zone names from controller at startup (Lync only)"
```

---

## Task 4: Update `media_player.py` for name resolution

**Files:**
- Modify: `custom_components/htd/media_player.py`

- [ ] **Step 4.1: Write failing tests for name resolution logic**

Create `custom_components/htd/tests/__init__.py` (empty) and `custom_components/htd/tests/test_name_resolution.py`:

```python
from unittest.mock import MagicMock


def _make_device(zone_names_override=None, source_names_override=None,
                  controller_zone_name=None, controller_source_name=None):
    """Build a minimal HtdDevice-like object to test name resolution."""
    config_entry = MagicMock()
    config_entry.data = {
        "zone_names": zone_names_override or {},
        "source_names": source_names_override or {},
    }
    client = MagicMock()
    client.get_zone_name.return_value = controller_zone_name
    client.get_source_name.return_value = controller_source_name or f"Source 1"
    return config_entry, client


def resolve_zone_name(zone, config_entry, client):
    overrides = config_entry.data.get("zone_names", {})
    return overrides.get(str(zone)) or client.get_zone_name(zone) or f"Zone {zone}"


def resolve_source_name(source, config_entry, client):
    overrides = config_entry.data.get("source_names", {})
    return overrides.get(str(source)) or client.get_source_name(source) or f"Source {source}"


def test_zone_name_uses_ha_override_first():
    config_entry, client = _make_device(
        zone_names_override={"1": "Living Room"},
        controller_zone_name="lounge"
    )
    assert resolve_zone_name(1, config_entry, client) == "Living Room"


def test_zone_name_falls_back_to_controller():
    config_entry, client = _make_device(controller_zone_name="office")
    assert resolve_zone_name(1, config_entry, client) == "office"


def test_zone_name_falls_back_to_numeric():
    config_entry, client = _make_device(controller_zone_name=None)
    client.get_zone_name.return_value = None
    assert resolve_zone_name(3, config_entry, client) == "Zone 3"


def test_source_name_uses_ha_override_first():
    config_entry, client = _make_device(
        source_names_override={"1": "Spotify"},
        controller_source_name="source 1"
    )
    assert resolve_source_name(1, config_entry, client) == "Spotify"


def test_source_name_falls_back_to_controller():
    config_entry, client = _make_device(controller_source_name="Apple TV")
    assert resolve_source_name(2, config_entry, client) == "Apple TV"


def test_source_name_falls_back_to_numeric():
    config_entry, client = _make_device()
    client.get_source_name.return_value = None
    assert resolve_source_name(5, config_entry, client) == "Source 5"


def test_empty_string_override_treated_as_no_override():
    config_entry, client = _make_device(
        zone_names_override={"1": ""},
        controller_zone_name="den"
    )
    assert resolve_zone_name(1, config_entry, client) == "den"
```

- [ ] **Step 4.2: Run tests to confirm they pass (pure logic, no HA needed)**

```bash
cd /Users/lharsh/projects/htd-home-assistant/htd-home-assistant
python -m pytest custom_components/htd/tests/test_name_resolution.py -v
```

Expected: 7 tests PASS. (If pytest not installed locally, run `pip install pytest` first.)

- [ ] **Step 4.3: Update `media_player.py` imports**

Open `custom_components/htd/media_player.py`. Update the import from `.const`:

```python
from .const import DOMAIN, CONF_DEVICE_NAME, CONF_ZONE_NAMES, CONF_SOURCE_NAMES
```

- [ ] **Step 4.4: Add `config_entry` parameter to `HtdDevice.__init__`**

Find the `HtdDevice.__init__` signature:

```python
def __init__(
    self,
    unique_id,
    device_name,
    zone,
    sources,
    client
):
    self.unique_id = f"{unique_id}_{zone:02}"
    self.device_name = device_name
    self.zone = zone
    self.client = client
    self.sources = sources
    zone_fmt = f"02" if self.client.model["zones"] > 10 else "01"
    self.entity_id = get_media_player_entity_id(device_name, zone, zone_fmt)
```

Replace with:

```python
def __init__(
    self,
    unique_id,
    device_name,
    zone,
    sources,
    client,
    config_entry=None
):
    self.unique_id = f"{unique_id}_{zone:02}"
    self.device_name = device_name
    self.zone = zone
    self.client = client
    self.sources = sources
    self.config_entry = config_entry
    zone_fmt = f"02" if self.client.model["zones"] > 10 else "01"
    self.entity_id = get_media_player_entity_id(device_name, zone, zone_fmt)
```

- [ ] **Step 4.5: Update the `name` property**

Find:

```python
@property
def name(self):
    return f"Zone {self.zone} ({self.device_name})"
```

Replace with:

```python
@property
def name(self) -> str:
    if self.config_entry is None:
        return f"Zone {self.zone} ({self.device_name})"
    overrides = self.config_entry.data.get(CONF_ZONE_NAMES, {})
    return (
        overrides.get(str(self.zone))
        or self.client.get_zone_name(self.zone)
        or f"Zone {self.zone}"
    )
```

- [ ] **Step 4.6: Add `_resolve_source_name` helper and update `source` / `source_list`**

Find:

```python
@property
def source(self) -> str:
    return self.client.get_source_name(self.zone_info.source)

@property
def source_list(self):
    return [self.client.get_source_name(i) for i in range(1, len(self.sources) + 1)]
```

Replace with:

```python
def _resolve_source_name(self, source: int) -> str:
    if self.config_entry is None:
        return self.client.get_source_name(source) or f"Source {source}"
    overrides = self.config_entry.data.get(CONF_SOURCE_NAMES, {})
    return (
        overrides.get(str(source))
        or self.client.get_source_name(source)
        or f"Source {source}"
    )

@property
def source(self) -> str:
    return self._resolve_source_name(self.zone_info.source)

@property
def source_list(self):
    return [self._resolve_source_name(i) for i in range(1, len(self.sources) + 1)]
```

- [ ] **Step 4.7: Pass `config_entry` when creating entities in `async_setup_entry`**

Find in `async_setup_entry`:

```python
for zone in range(1, zone_count + 1):
    entity = HtdDevice(
        unique_id,
        device_name,
        zone,
        sources,
        client
    )
```

Replace with:

```python
for zone in range(1, zone_count + 1):
    entity = HtdDevice(
        unique_id,
        device_name,
        zone,
        sources,
        client,
        config_entry
    )
```

- [ ] **Step 4.8: Commit**

```bash
git add custom_components/htd/media_player.py custom_components/htd/tests/
git commit -m "feat: resolve zone/source names from HA overrides with controller fallback"
```

---

## Task 5: Config flow — rename `async_step_options` → `async_step_device`, add customize checkbox

**Files:**
- Modify: `custom_components/htd/config_flow.py`

- [ ] **Step 5.1: Add new imports to `config_flow.py`**

Open `custom_components/htd/config_flow.py`. Update the import from `.const`:

```python
from .const import CONF_DEVICE_NAME, CONF_ZONE_NAMES, CONF_SOURCE_NAMES, CONF_CUSTOMIZE_NAMES, DOMAIN
```

The library import line already has `async_get_model_info` — no change needed there.

- [ ] **Step 5.2: Rename `async_step_options` to `async_step_device` and add checkbox**

Find the entire `async_step_options` method:

```python
async def async_step_options(self, user_input=None):
    if user_input is not None:
        config_entry = {
            CONF_HOST: self.host,
            CONF_PORT: self.port,
            CONF_UNIQUE_ID: self.unique_id,
        }

        return self.async_create_entry(
            title=user_input[CONF_DEVICE_NAME],
            data=config_entry,
            options={}
        )

    network_address = (self.host, self.port)
    model_info = await async_get_model_info(network_address=network_address)

    return self.async_show_form(
        step_id='options',
        data_schema=get_options_schema(
            model_info["friendly_name"],
        )
    )
```

Replace it entirely with:

```python
async def async_step_device(self, user_input=None):
    if user_input is not None:
        self._device_name = user_input.get(CONF_DEVICE_NAME, "")
        if user_input.get(CONF_CUSTOMIZE_NAMES, False):
            return await self.async_step_zone_names()
        return self.async_create_entry(
            title=self._device_name,
            data={
                CONF_HOST: self.host,
                CONF_PORT: self.port,
                CONF_UNIQUE_ID: self.unique_id,
                CONF_DEVICE_NAME: self._device_name,
                CONF_ZONE_NAMES: {},
                CONF_SOURCE_NAMES: {},
            },
            options={}
        )

    network_address = (self.host, self.port)
    model_info = await async_get_model_info(network_address=network_address)
    self._model_info = model_info

    return self.async_show_form(
        step_id='device',
        data_schema=vol.Schema({
            vol.Optional(
                CONF_DEVICE_NAME, default=model_info["friendly_name"]
            ): cv.string,
            vol.Optional(CONF_CUSTOMIZE_NAMES, default=False): cv.boolean,
        })
    )
```

- [ ] **Step 5.3: Update `async_step_custom_connection` to call `async_step_device`**

Find:

```python
return await self.async_step_options()
```

Replace with:

```python
return await self.async_step_device()
```

- [ ] **Step 5.4: Add `_device_name`, `_model_info`, `_zone_name_overrides` instance variables**

Add these to the `HtdConfigFlow` class body (alongside existing `host`, `port`, `unique_id`):

```python
host: str = None
port: int = HtdConstants.DEFAULT_PORT
unique_id: str = None
_device_name: str = None
_model_info: dict = None
_zone_name_overrides: dict = None
```

- [ ] **Step 5.5: Remove the now-orphaned `get_options_schema` function**

`get_options_schema` was only called from `async_step_options` which we just replaced. Find and delete the entire function:

```python
def get_options_schema(friendly_name: str):
    return vol.Schema(
        {
            vol.Required(
                CONF_DEVICE_NAME, default=friendly_name
            ): cv.string,
        }
    )
```

- [ ] **Step 5.6: Commit**

```bash
git add custom_components/htd/config_flow.py
git commit -m "feat: rename async_step_options to async_step_device, add customize names checkbox"
```

---

## Task 6: Config flow — add `async_step_zone_names` to initial setup

**Files:**
- Modify: `custom_components/htd/config_flow.py`

- [ ] **Step 6.1: Add `async_step_zone_names` to `HtdConfigFlow`**

Add the following method to the `HtdConfigFlow` class, after `async_step_device`:

```python
async def async_step_zone_names(self, user_input=None):
    zone_count = self._model_info["zones"]

    if user_input is not None:
        self._zone_name_overrides = {
            str(i): name
            for i in range(1, zone_count + 1)
            if (name := (user_input.get(f"zone_{i}_name") or "").strip())
        }
        return await self.async_step_source_names()

    return self.async_show_form(
        step_id='zone_names',
        data_schema=vol.Schema({
            vol.Optional(f"zone_{i}_name", default=""): cv.string
            for i in range(1, zone_count + 1)
        })
    )
```

- [ ] **Step 6.2: Commit**

```bash
git add custom_components/htd/config_flow.py
git commit -m "feat: add zone name customization step to initial config flow"
```

---

## Task 7: Config flow — add `async_step_source_names` to initial setup

**Files:**
- Modify: `custom_components/htd/config_flow.py`

- [ ] **Step 7.1: Add `async_step_source_names` to `HtdConfigFlow`**

Add the following method to the `HtdConfigFlow` class, after `async_step_zone_names`:

```python
async def async_step_source_names(self, user_input=None):
    source_count = self._model_info["sources"]

    if user_input is not None:
        source_name_overrides = {
            str(i): name
            for i in range(1, source_count + 1)
            if (name := (user_input.get(f"source_{i}_name") or "").strip())
        }
        return self.async_create_entry(
            title=self._device_name,
            data={
                CONF_HOST: self.host,
                CONF_PORT: self.port,
                CONF_UNIQUE_ID: self.unique_id,
                CONF_DEVICE_NAME: self._device_name,
                CONF_ZONE_NAMES: self._zone_name_overrides or {},
                CONF_SOURCE_NAMES: source_name_overrides,
            },
            options={}
        )

    return self.async_show_form(
        step_id='source_names',
        data_schema=vol.Schema({
            vol.Optional(f"source_{i}_name", default=""): cv.string
            for i in range(1, source_count + 1)
        })
    )
```

- [ ] **Step 7.2: Commit**

```bash
git add custom_components/htd/config_flow.py
git commit -m "feat: add source name customization step to initial config flow"
```

---

## Task 8: Config flow — convert options flow to multi-step with controller hints

**Files:**
- Modify: `custom_components/htd/config_flow.py`

- [ ] **Step 8.1: Rewrite `HtdOptionsFlowHandler.async_step_init`**

Find the entire `HtdOptionsFlowHandler` class and replace `async_step_init`:

```python
class HtdOptionsFlowHandler(OptionsFlowWithConfigEntry):
    _new_title: str = None
    _connection_data: dict = None
    _zone_name_overrides: dict = None

    async def async_step_init(self, user_input: dict[str, Any] | None = None):
        if user_input is not None:
            self._new_title = user_input.get(CONF_DEVICE_NAME, self.config_entry.title)
            self._connection_data = user_input
            return await self.async_step_zone_names()

        return self.async_show_form(
            step_id='init',
            data_schema=get_connection_settings_schema(self.config_entry)
        )
```

- [ ] **Step 8.2: Add `async_step_zone_names` to `HtdOptionsFlowHandler`**

Add the following method to `HtdOptionsFlowHandler`:

```python
    async def async_step_zone_names(self, user_input: dict[str, Any] | None = None):
        client = self.config_entry.runtime_data
        zone_count = client.get_zone_count()

        if user_input is not None:
            self._zone_name_overrides = {
                str(i): name
                for i in range(1, zone_count + 1)
                if (name := (user_input.get(f"zone_{i}_name") or "").strip())
            }
            return await self.async_step_source_names()

        existing_zone_overrides = self.config_entry.data.get(CONF_ZONE_NAMES, {})
        placeholders = {
            f"zone_{i}_controller": client.get_zone_name(i) or f"Zone {i}"
            for i in range(1, zone_count + 1)
        }

        return self.async_show_form(
            step_id='zone_names',
            data_schema=vol.Schema({
                vol.Optional(
                    f"zone_{i}_name",
                    default=existing_zone_overrides.get(str(i), "")
                ): cv.string
                for i in range(1, zone_count + 1)
            }),
            description_placeholders=placeholders
        )
```

- [ ] **Step 8.3: Add `async_step_source_names` to `HtdOptionsFlowHandler`**

Add the following method to `HtdOptionsFlowHandler`:

```python
    async def async_step_source_names(self, user_input: dict[str, Any] | None = None):
        client = self.config_entry.runtime_data
        source_count = client.get_source_count()

        if user_input is not None:
            source_name_overrides = {
                str(i): name
                for i in range(1, source_count + 1)
                if (name := (user_input.get(f"source_{i}_name") or "").strip())
            }
            data = {
                **self.config_entry.data,
                **self._connection_data,
                CONF_ZONE_NAMES: self._zone_name_overrides or {},
                CONF_SOURCE_NAMES: source_name_overrides,
            }
            self.hass.config_entries.async_update_entry(
                self.config_entry,
                data=data,
                title=self._new_title,
            )
            return self.async_create_entry(title=self._new_title, data={})

        existing_source_overrides = self.config_entry.data.get(CONF_SOURCE_NAMES, {})
        placeholders = {
            f"source_{i}_controller": client.get_source_name(i) or f"Source {i}"
            for i in range(1, source_count + 1)
        }

        return self.async_show_form(
            step_id='source_names',
            data_schema=vol.Schema({
                vol.Optional(
                    f"source_{i}_name",
                    default=existing_source_overrides.get(str(i), "")
                ): cv.string
                for i in range(1, source_count + 1)
            }),
            description_placeholders=placeholders
        )
```

- [ ] **Step 8.4: Commit**

```bash
git add custom_components/htd/config_flow.py
git commit -m "feat: add multi-step zone/source naming to options flow with controller hints"
```

---

## Task 9: Update translations

**Files:**
- Modify: `custom_components/htd/strings.json`
- Modify: `custom_components/htd/translations/en.json`

- [ ] **Step 9.1: Update `strings.json`**

Replace the entire content of `custom_components/htd/strings.json` with:

```json
{
  "config": {
    "step": {
      "user": {
        "title": "Home Theater Direct",
        "description": "Enter your HTD gateway connection details.",
        "data": {
          "host": "Host name or IP Address",
          "port": "Port"
        }
      },
      "device": {
        "title": "Device Setup",
        "data": {
          "device_name": "Device name",
          "customize_names": "Customize zone and source names now"
        },
        "data_description": {
          "customize_names": "You can update names at any time via Configure."
        }
      },
      "zone_names": {
        "title": "Zone Names",
        "description": "Leave a field blank to use the controller's default name for that zone.",
        "data": {
          "zone_1_name": "Zone 1", "zone_2_name": "Zone 2", "zone_3_name": "Zone 3",
          "zone_4_name": "Zone 4", "zone_5_name": "Zone 5", "zone_6_name": "Zone 6",
          "zone_7_name": "Zone 7", "zone_8_name": "Zone 8", "zone_9_name": "Zone 9",
          "zone_10_name": "Zone 10", "zone_11_name": "Zone 11", "zone_12_name": "Zone 12"
        }
      },
      "source_names": {
        "title": "Source Names",
        "description": "Leave a field blank to use the controller's default name for that source.",
        "data": {
          "source_1_name": "Source 1", "source_2_name": "Source 2", "source_3_name": "Source 3",
          "source_4_name": "Source 4", "source_5_name": "Source 5", "source_6_name": "Source 6",
          "source_7_name": "Source 7", "source_8_name": "Source 8", "source_9_name": "Source 9",
          "source_10_name": "Source 10", "source_11_name": "Source 11", "source_12_name": "Source 12",
          "source_13_name": "Source 13", "source_14_name": "Source 14", "source_15_name": "Source 15",
          "source_16_name": "Source 16", "source_17_name": "Source 17", "source_18_name": "Source 18",
          "source_19_name": "Source 19"
        }
      }
    },
    "error": {
      "no_connection": "Could not connect to the HTD gateway",
      "missing_input": "Please fill in all required fields"
    }
  },
  "options": {
    "step": {
      "init": {
        "title": "Configure Device",
        "data": {
          "host": "Host name or IP Address",
          "port": "Port",
          "device_name": "Device name"
        }
      },
      "zone_names": {
        "title": "Zone Names",
        "description": "Leave a field blank to use the controller's name. Clear an override to revert.",
        "data": {
          "zone_1_name": "Zone 1", "zone_2_name": "Zone 2", "zone_3_name": "Zone 3",
          "zone_4_name": "Zone 4", "zone_5_name": "Zone 5", "zone_6_name": "Zone 6",
          "zone_7_name": "Zone 7", "zone_8_name": "Zone 8", "zone_9_name": "Zone 9",
          "zone_10_name": "Zone 10", "zone_11_name": "Zone 11", "zone_12_name": "Zone 12"
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
        "description": "Leave a field blank to use the controller's name. Clear an override to revert.",
        "data": {
          "source_1_name": "Source 1", "source_2_name": "Source 2", "source_3_name": "Source 3",
          "source_4_name": "Source 4", "source_5_name": "Source 5", "source_6_name": "Source 6",
          "source_7_name": "Source 7", "source_8_name": "Source 8", "source_9_name": "Source 9",
          "source_10_name": "Source 10", "source_11_name": "Source 11", "source_12_name": "Source 12",
          "source_13_name": "Source 13", "source_14_name": "Source 14", "source_15_name": "Source 15",
          "source_16_name": "Source 16", "source_17_name": "Source 17", "source_18_name": "Source 18",
          "source_19_name": "Source 19"
        },
        "data_description": {
          "source_1_name": "Controller: {source_1_controller}",
          "source_2_name": "Controller: {source_2_controller}",
          "source_3_name": "Controller: {source_3_controller}",
          "source_4_name": "Controller: {source_4_controller}",
          "source_5_name": "Controller: {source_5_controller}",
          "source_6_name": "Controller: {source_6_controller}",
          "source_7_name": "Controller: {source_7_controller}",
          "source_8_name": "Controller: {source_8_controller}",
          "source_9_name": "Controller: {source_9_controller}",
          "source_10_name": "Controller: {source_10_controller}",
          "source_11_name": "Controller: {source_11_controller}",
          "source_12_name": "Controller: {source_12_controller}",
          "source_13_name": "Controller: {source_13_controller}",
          "source_14_name": "Controller: {source_14_controller}",
          "source_15_name": "Controller: {source_15_controller}",
          "source_16_name": "Controller: {source_16_controller}",
          "source_17_name": "Controller: {source_17_controller}",
          "source_18_name": "Controller: {source_18_controller}",
          "source_19_name": "Controller: {source_19_controller}"
        }
      }
    }
  }
}
```

- [ ] **Step 9.2: Mirror `strings.json` to `translations/en.json`**

Copy the exact content of `strings.json` to `translations/en.json` (both files must be identical).

- [ ] **Step 9.3: Commit**

```bash
git add custom_components/htd/strings.json custom_components/htd/translations/en.json
git commit -m "feat: add zone_names, source_names, device step translations"
```

---

## Task 10: Pin library, version bump, changelog

**Files:**
- Modify: `custom_components/htd/manifest.json`
- Modify: `custom_components/htd/CHANGELOG.md`

- [ ] **Step 10.1: Update `manifest.json` to pin `v0.1.2`**

Open `manifest.json`. Find the `requirements` entry referencing `python-htd`. Update the tag from `v0.1.1` to `v0.1.2`:

```json
"requirements": ["htd-client @ git+https://github.com/theharshl/python-htd.git@v0.1.2"]
```

- [ ] **Step 10.2: Bump integration version to `0.0.27`**

In `manifest.json`, update:

```json
"version": "0.0.27"
```

- [ ] **Step 10.3: Add changelog entry**

Open `CHANGELOG.md`. Add this entry at the top (above the `2.0.0` placeholder):

```markdown
## 0.0.27

### Added
- Zone custom naming: set per-zone display names from the HA config/options UI (closes #3)
- Source custom naming: override source display names from the HA config/options UI (closes #8)
- Zone names are now queried from the controller at startup (Lync systems only) and used as defaults
- Options flow expanded to 3 steps: Connection → Zone Names → Source Names
- Initial setup now offers optional naming step (skippable via checkbox)
- Requires python-htd v0.1.2

### Changed
- Zone entity names no longer include the device name suffix (e.g. "Zone 1" instead of "Zone 1 (My HTD)") when a controller or custom name is available
```

- [ ] **Step 10.4: Commit and push integration**

```bash
git add custom_components/htd/manifest.json custom_components/htd/CHANGELOG.md
git commit -m "chore: bump to v0.0.27, pin python-htd v0.1.2"
git push -u origin feat/zone-source-naming
```

---

## Manual Verification Checklist

After deploying to your Lync 12 test system:

- [ ] **Fresh install**: Add integration → connection screen → submit → device screen appears with checkbox → check box → zone name screen shows 12 blank fields → source name screen shows 19 blank fields → submit both → integration loads → zone entities appear
- [ ] **Zone names from controller**: Open Configure → Zone Names step → verify "Controller: X" hints show your controller's zone names below each field
- [ ] **Override a zone name**: Enter "Living Room" for Zone 1 → save → verify entity friendly name updates to "Living Room"
- [ ] **Revert an override**: Return to Configure → clear "Living Room" → save → verify entity reverts to controller's zone name
- [ ] **Source names override**: Set "Spotify" for Source 1 → save → verify source_list in HA shows "Spotify"
- [ ] **Skip naming at setup**: Add integration → device step → leave checkbox unchecked → verify integration loads with controller defaults immediately
- [ ] **MCA safety**: Confirm no errors on MCA systems — zone name queries are guarded behind `HtdDeviceKind.lync` check

---

## Implementation Note: Initial Setup Controller Hints

The initial setup zone/source name steps show blank optional fields only — no "Controller: X" hints. This is intentional: zone/source name responses from the controller arrive asynchronously (the library uses an asyncio push model), and a temp connection during the config flow cannot reliably deliver names before the form renders. The "Controller: X" hints appear fully in the **options flow** once the integration is running. Users can always skip naming at setup and return to Configure once the integration is live.
