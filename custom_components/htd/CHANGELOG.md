## [0.0.33] - 2026-07-05
### Added
- Serial connection support in the config flow: a new connection-type step lets you choose Network or Serial when adding the integration, with a dedicated serial path step for USB/RS-232 devices (issue #19)
- Serial-configured devices now go through the same config-entry setup as network devices, gaining the options flow and zone/source naming/filtering that were previously network-only

## [0.0.32] - 2026-07-05
### Fixed
- YAML/serial-configured devices (`htd:` config block) crashed on startup with "It's not possible to configure htd number/switch by adding platform: htd" — `number.py` and `switch.py` were missing the legacy `async_setup_platform` hook that `media_player.py` already had (issue #17)

## [0.0.31] - 2026-07-04
### Changed
- Switched the `htd-client` dependency from a git-pinned fork to the `htd-client-ha` PyPI package — no more git dependency in `manifest.json`
- Updated `htd-client-ha` to 0.1.3, pulling in a model-probe retry and serial settle-delay fix for crashes on serial by-id paths (issue #6)

## [0.0.30] - 2026-06-03
### Added
- Zone Filter config flow step (between Zone Names and Source Names) letting users check/uncheck which zones get HA entities, in both initial setup and reconfigure flows
- Unchecked zones are disabled in the entity registry rather than deleted — they can be manually re-enabled at any time; checking all zones disables filtering entirely (closes #4)

### Changed
- Zone and source name customization is now always available — removed the "customize names" checkbox from the device step
- Removed stale HACS install instructions from README

## [0.0.29] - 2026-06-02
### Added
- Bass and Treble sliders (NumberEntity) per zone, enabled by default (issue #1)
- Balance slider per zone, disabled by default — enable via Settings → Devices & Services → entity list
- DND (Do Not Disturb) switch per zone, Lync-only — prevents a zone from being affected by party mode / all-zones-on commands (issue #2)

## [0.0.28] - 2026-05-25
### Added
- Per-zone source filtering: whitelist which sources appear in each zone's dropdown (issue #5)
- Source filter toggle in both initial setup and reconfigure flows
- Per-zone source checkboxes using resolved zone/source names

### Fixed
- `async_select_source` now maps by controller index instead of list position — was broken when source filtering is active

## [0.0.27] - 2026-05-24
### Added
- Zone custom naming: set per-zone display names from the HA config/options UI (closes #3)
- Source custom naming: override source display names from the HA config/options UI (closes #8)
- Zone names are now queried from the controller at startup (Lync systems only) and used as defaults
- Options flow expanded to 3 steps: Connection → Zone Names → Source Names
- Initial setup now offers optional naming step (skippable via checkbox)
- Requires python-htd v0.1.2

### Changed
- Zone entity names no longer include the device name suffix (e.g. "Zone 1" instead of "Zone 1 (My HTD)") when a controller or custom name is available

## [0.0.26] - 2026-05-24
### Added
- Source names now read from controller automatically (Lync: zone-configured names; MCA: where supported)
- Device rename option in the integration's settings (no longer need to delete and re-add)

### Changed
- Updated python-htd library to v0.1.0 (full Lync feature support, EQ command fixes)

### Fixed
- Removed deprecated `hass.loop` argument (fixes deprecation warning in HA 2024+)
- Cleaned up stale translation keys and populated empty strings.json

## Pre-fork history (hikirsch/htd_mc-home-assistant)
### 2.0.0 - TBD
- New HTD domain, support ConfigFlow, support AutoDiscovery

### 1.2.0 - July 11, 2024
- Upgrading to HASS 2024.6.4
- New client. Better support for volume changes and bass, treble and balance. ([#5](https://github.com/hikirsch/htd_mc-home-assistant/issues/5))

### 1.1.0 - March 31, 2024
- Upgrading to support HASS 2024.1.0 ([#7](https://github.com/hikirsch/htd_mc-home-assistant/issues/7))
- Adding support for HACS

### 1.0.0 - Previous log
- July 18, 2021 - Add version in manifest.json to support 2021.6+
- April 7, 2020 - Changed Icon and added unique_id (allows editing name and entity ID in Home Assistant UI)
- April 8, 2020 - Support multiple MCAs
- April 6, 2020 - Initial release
