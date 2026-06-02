## [0.0.29] - 2026-06-02
### Added
- Bass and Treble sliders (NumberEntity) per zone, enabled by default (issue #1)
- Balance slider per zone, disabled by default — enable via Settings → Devices & Services → entity list

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
