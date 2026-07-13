## [0.0.36] - 2026-07-12
### Fixed
- Home Assistant startup failed permanently (requiring a manual reload once the device came
  back) if the HTD amp/controller was off or unreachable at boot — a common setup for anyone who
  doesn't leave the amp powered on 24/7 (issue #23, reported by @steve28). `htd-client-ha` 0.1.6:
  the connection/model-probe failure now raises a distinct `HtdConnectionError` instead of a bare
  `ValueError`/`OSError`. The integration catches it and raises Home Assistant's
  `ConfigEntryNotReady`, which schedules an automatic retry with exponential backoff (5s up to a
  10-minute cap) instead of marking setup as failed — once the device powers on, the next retry
  succeeds with no user action needed.

## [0.0.35] - 2026-07-10
### Fixed
- Zone control (volume/source/power changes) triggered a slew of "Bad sync buffer", "Bad checksum", and "Invalid command value" errors after a successful setup (issue #19, reported by @steve28). `htd-client-ha` 0.1.5: the response parser trusted the declared length of a frame that had already failed checksum validation, so a single dropped or corrupted byte from the serial adapter — which is expected occasionally on cheap USB-serial hardware — desynced the parser permanently instead of recovering on the next valid frame. It now resyncs by discarding only the malformed frame's header, the same recovery already used for unrecognized commands.

## [0.0.34] - 2026-07-10
### Fixed
- Serial setup on cheap/slow USB-serial adapters was extremely unreliable — "Could not connect" / "unknown_model" during the config flow and "Failed to setup" after it, requiring many retries, again on every Home Assistant restart (issue #19, reported by @steve28). Three root causes fixed:
  - `htd-client-ha` 0.1.4: the model probe read the serial reply with a single `read()` call, so a reply split across USB packets was misread as a failure; it now accumulates data until the reply matches, the line goes quiet, or a deadline expires (and no longer hangs forever when the device doesn't answer)
  - `htd-client-ha` 0.1.4: probe retries re-opened the serial port each attempt — and every port open can DTR-reset the gateway, so retries kept resetting the device they were probing; retries now reuse a single open connection, and the persistent connection waits out the same settle delay before its first refresh command
  - The device-naming step of the config flow probed the device a second time right after the connection-validation probe succeeded, and aborted the whole flow with "unknown_model" if that redundant probe lost the race against a resetting gateway; it now reuses the model info from the validation step

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
