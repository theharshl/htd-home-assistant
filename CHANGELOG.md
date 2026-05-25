## [0.0.26] - 2026-05-24
### Added
- Source names now read from controller automatically (Lync: zone-configured names; MCA: where supported)
- Device rename option in the integration's settings (no longer need to delete and re-add)

### Changed
- Updated python-htd library to v0.1.0 (full Lync feature support, EQ command fixes)

### Fixed
- Removed deprecated `hass.loop` argument (fixes deprecation warning in HA 2024+)
- Cleaned up stale translation keys and populated empty strings.json

### 2.0.0 - TBD
- new HTD domain, 
- support ConfigFlow
- support AutoDiscovery

### 1.2.0 - July  11, 2024
- Upgrading to HASS 2024.6.4
- New client. Better support for volume changes and bass, treble and balance. ([#5](https://github.com/hikirsch/htd_mc-home-assistant/issues/5)).

### 1.1.0 - March 31, 2024 
- Upgrading to support HASS 2024.1.0 ([#7](https://github.com/hikirsch/htd_mc-home-assistant/issues/7)). 
- Adding support for HACS

### 1.0.0 - Previous log
- July 18, 2021 - Add version in manifest.json to support 2021.6+
- April 7, 2020 - Changed Icon and added unique_id (allows editing name and entity ID in Home Assistant UI)
- April 8, 2020 - Support multiple MCAs
- April 6, 2020 - Initial release



