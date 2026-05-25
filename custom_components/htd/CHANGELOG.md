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
