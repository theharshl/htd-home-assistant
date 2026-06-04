# Home Theater Direct Integration for Home Assistant

![HTD](logo-htd.png)

This integration adds support for the Home Theater Direct line of Whole House Audio to Home Assistant.

## Supported Models

| Model | Zones | Sources | Kind |
|---|---|---|---|
| MC/MCA-66 | 6 | 6 | MCA |
| Lync 6 | 6 | 12 | Lync |
| Lync 12 | 12 | 19 | Lync |

Model is auto-detected at connection time. No manual configuration of device type is required.

## Features

- Auto-discovery via DHCP (MAC prefix `A44F29*` / `A64F29*`)
- Per-zone power, volume, mute, and source selection
- Zone and source names read automatically from the controller on connect
- Customize zone and source names during setup or at any time via the integration's settings
- Hide unused zones so only the zones you care about appear in Home Assistant
- Per-zone source filtering — restrict which sources are selectable per zone
- Per-zone **Bass** and **Treble** sliders (enabled by default) and a **Balance** slider (hidden by default)
- Per-zone **DND (Do Not Disturb)** switch — controls party mode / all-zones-on exclusion (Lync only)
- Device rename via the integration's settings — no need to delete and re-add
- Serial (USB) or network connection

## Customizing Zone and Source Names

Zone and source names can be customized during initial setup or at any time via the integration's settings (reconfigure).

- **Zone names** default to the names stored on your HTD controller. You can override them per-zone in the integration UI.
- **Source names** default to the names stored on your HTD controller (Lync) or generic labels (MCA). You can override them per-source in the integration UI.

Both are optional — leave fields blank to keep the controller's names.

### Home Assistant entity name overrides

If you have manually renamed an entity directly in Home Assistant (via **Settings → Devices & Services → Entities**), that name takes precedence over whatever the integration provides. The integration cannot override a name you have set manually.

To let the integration's name take effect, clear the manual override:

1. Go to **Settings → Devices & Services → Entities**
2. Find the entity and open it
3. Click the name field and delete the custom value (leave it blank / reset to default)
4. Save — the entity will now use the name from the integration

## Zone Filtering (Hide Unused Zones)

During initial setup or reconfigure, you can choose to filter zones so that only the zones you actually use appear in Home Assistant.

- Enable zone filtering with the checkbox, then select which zones are active.
- Entities for deselected zones are **disabled by the integration** — they remain in the registry and can be manually re-enabled per-entity in **Settings → Devices & Services → Entities** if needed.
- Disable zone filtering at any time via reconfigure to restore all zones.

## Source Filtering (Per-Zone Source List)

You can restrict which sources appear in the source selection dropdown for each zone.

- During setup or reconfigure, enable source filtering.
- For each zone, choose which sources should be available.
- Sources not selected are removed from that zone's source list in Home Assistant.
- Useful when only a subset of sources are wired to certain zones.

## EQ Controls (Bass, Treble, Balance)

Each zone exposes three `number` entities for equalizer adjustments:

| Entity | Default | Range (Lync) | Range (MCA) |
|--------|---------|-------------|-------------|
| Bass   | Enabled | -10 to +10, step 1 | -12 to +12, step 4 |
| Treble | Enabled | -10 to +10, step 1 | -12 to +12, step 4 |
| Balance | **Hidden** | -18 to +18, step 1 | -12 to +12, step 6 |

Bass and Treble appear automatically on the device page. Balance is created but hidden by default because most fixed-speaker whole-home audio setups never need it.

**To enable Balance:** Go to **Settings → Devices & Services → your HTD device** → find the Balance entity for the zone you want → click the toggle to enable it.

## DND (Do Not Disturb)

*Lync systems only.*

Each Lync zone has a **DND switch** entity. When DND is on for a zone:

- The zone is excluded from party mode and all-zones-on commands.
- Individual control of the zone is unaffected — you can still power it on/off and adjust volume independently.

DND state is read from and written to the controller. Toggling the switch in Home Assistant sends the command immediately.

## Installation

### Manually

Download all the files from this repo and place them in your `config/custom_components/htd/` directory.

### HACS

Search for **Home Theater Direct** in the HACS integration catalog and install from there.

### Configuration

Go to **Settings → Devices & Services → Add Integration → Home Theater Direct**.

The integration will attempt to auto-discover your device via DHCP. If it is not found automatically, enter the IP address and port (default: `10006`) manually.

#### Serial (USB) connection

If you are using a USB-to-serial adapter, configure the integration manually in `configuration.yaml`:

```yaml
htd:
  - device_name: Lync 6 over Serial
    path: /dev/ttyUSB0
```

## Code Credits
- https://github.com/dustinmcintire/htd-lync
- https://github.com/whitingj/mca66
- https://github.com/qguernsey/Lync12
- https://github.com/steve28/mca66
- http://www.brandonclaps.com/?p=173
- https://github.com/lounsbrough/htd-mca-66-api
- **[hikirsch/htd-home-assistant](https://github.com/hikirsch/htd-home-assistant)** — the upstream integration this fork is built on.
- **Special thanks to [kingfetty](https://github.com/kingfetty/python-htd)** — whose foundational work on full Lync support (zone/source naming, DND, device discovery, and all-zone queries) made this integration significantly more capable.
