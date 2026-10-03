"""Shared offline behavior for every HTD entity platform.

Availability, assumed state, restore plumbing and the offline-command guard are identical
across media_player, number and switch, so they live here rather than three times over.
The entity ID scheme is shared the same way.
"""
import re

from homeassistant.exceptions import HomeAssistantError
from htd_client.exceptions import HtdConnectionError

from .const import CONF_RESTORE_LAST_STATE


def make_alphanumeric(input_string):
    temp = re.sub(r'[^a-zA-Z0-9]', '_', input_string)
    return re.sub(r'_+', '_', temp).strip('_')


def get_zone_entity_id(domain, device_name, zone, zone_count, suffix=None):
    """The entity ID to request for a zone's entity, e.g. number.htd_lync_12_zone_01_bass.

    Built only from the device name and the zone number, never the zone's display name, so
    every entity of a zone shares one prefix and renaming a zone cannot leak into an ID.

    Home Assistant only honours this the first time an entity is registered. Once a registry
    entry exists for the entity's unique_id, the registry's stored entity_id wins and this
    value is ignored — renaming the device or a zone never moves an existing entity.
    """
    zone_fmt = "02" if zone_count > 10 else "01"
    object_id = f"{make_alphanumeric(device_name)}_zone_{zone:{zone_fmt}}"
    if suffix:
        object_id = f"{object_id}_{suffix}"
    return f"{domain}.{object_id}".lower()


class HtdEntity:
    """Mixin. Inherit it FIRST so its properties win over the Home Assistant base class."""

    client = None
    zone: int = None
    config_entry = None

    def _live_zone(self):
        """The controller's current data for this zone, or None if there is none to trust.

        Platforms that keep their own cached copy override this; see HtdDevice.
        """
        if not self.client.ready or not self.client.has_zone_data(self.zone):
            return None

        return self.client.get_zone(self.zone)

    @property
    def _restore_enabled(self) -> bool:
        if self.config_entry is None:
            return False

        return bool(self.config_entry.data.get(CONF_RESTORE_LAST_STATE, False))

    @property
    def available(self) -> bool:
        zone_info = self._live_zone()

        if zone_info is not None:
            # the controller told us this zone has no keypad wired to it; do not present it
            # as a working speaker. only consulted when there is live data to consult.
            return bool(zone_info.enabled)

        return self._restore_enabled

    @property
    def assumed_state(self) -> bool:
        """True exactly when what is displayed is restored rather than live."""
        return self._live_zone() is None

    async def _async_command(self, factory, description: str) -> None:
        """Run a client command, failing visibly rather than silently while offline.

        There is deliberately no replay queue: a queued "turn on the kitchen" firing hours
        later, when the amplifier happens to be powered for something else, is a worse
        outcome than an error the user can see.
        """
        if not self.client.connected:
            raise HomeAssistantError(
                f"HTD device is offline; cannot {description} for zone {self.zone}"
            )

        try:
            await factory()
        except HtdConnectionError as e:
            # the connection dropped between the check above and the write
            raise HomeAssistantError(
                f"HTD device is offline; cannot {description} for zone {self.zone}"
            ) from e
