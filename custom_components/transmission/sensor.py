"""Support for monitoring the Transmission BitTorrent client API."""
from datetime import timedelta
import logging

from homeassistant.const import STATE_IDLE
from homeassistant.core import callback
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity import Entity

from . import DATA_TRANSMISSION, DATA_UPDATED, SENSOR_TYPES

_LOGGER = logging.getLogger(__name__)

DEFAULT_NAME = 'Transmission'

SCAN_INTERVAL = timedelta(seconds=120)


async def async_setup_platform(
        hass, config, async_add_entities, discovery_info=None):
    """Set up the Transmission sensors."""
    if discovery_info is None:
        return

    transmission_api = hass.data[DATA_TRANSMISSION]
    monitored_variables = discovery_info['sensors']
    name = discovery_info['client_name']
    traffic_unit = discovery_info['traffic_unit'] or None

    dev = []
    for sensor_type in monitored_variables:
        dev.append(TransmissionSensor(sensor_type, transmission_api, name, SENSOR_TYPES[sensor_type], traffic_unit))

    async_add_entities(dev, True)


class TransmissionSensor(Entity):
    """Representation of a Transmission sensor."""

    def __init__(
            self, sensor_type, transmission_api, client_name, sensor_name, unit_of_measurement):
        """Initialize the sensor."""
        self._name = sensor_name
        self._state = None
        self._transmission_api = transmission_api
        self._unit_of_measurement = unit_of_measurement
        self._data = None
        self.client_name = client_name
        self.type = sensor_type

    @property
    def name(self):
        """Return the name of the sensor."""
        return '{} {}'.format(self.client_name, self._name)

    @property
    def state(self):
        """Return the state of the sensor."""
        return self._state

    @property
    def should_poll(self):
        """Return the polling requirement for this sensor."""
        return False

    @property
    def unit_of_measurement(self):
        """Return the unit of measurement of this entity, if any."""
        if self.type in ['download_speed', 'upload_speed']:
            return self._unit_of_measurement
        else:
            return None

    @property
    def available(self):
        """Could the device be accessed during the last update call."""
        return self._transmission_api.available

    async def async_added_to_hass(self):
        """Handle entity which will be added."""
        async_dispatcher_connect(
            self.hass, DATA_UPDATED, self._schedule_immediate_update)

    @callback
    def _schedule_immediate_update(self):
        self.async_schedule_update_ha_state(True)

    def update(self):
        """Get the latest data from Transmission and updates the state."""
        self._data = self._transmission_api.data

        if self.type == 'completed_torrents':
            self._state = self._transmission_api.get_completed_torrent_count()
        elif self.type == 'started_torrents':
            self._state = self._transmission_api.get_started_torrent_count()

        if self.type == 'current_status':
            if self._data:
                upload = self._data.uploadSpeed
                download = self._data.downloadSpeed
                if upload > 0 and download > 0:
                    self._state = 'Up/Down'
                elif upload > 0 and download == 0:
                    self._state = 'Seeding'
                elif upload == 0 and download > 0:
                    self._state = 'Downloading'
                else:
                    self._state = STATE_IDLE
            else:
                self._state = None

        if self._data:
            if self.type == 'download_speed':
                self._state = self._convert_bytes_to_requested_unit(self._data.downloadSpeed)
            elif self.type == 'upload_speed':
                self._state = self._convert_bytes_to_requested_unit(self._data.uploadSpeed)
            elif self.type == 'active_torrents':
                self._state = self._data.activeTorrentCount
            elif self.type == 'paused_torrents':
                self._state = self._data.pausedTorrentCount
            elif self.type == 'total_torrents':
                self._state = self._data.torrentCount

    def _convert_bytes_to_requested_unit(self, bytes_count):
        converted = float(bytes_count)
        # Check if bits or bytes (bits if 'b' in first two letters of traffic unit)
        if 'b' in self._unit_of_measurement[:2]:
            converted = converted * 8

        # Handle Kilo and Mega
        if self._unit_of_measurement[:1].upper() == 'K':
            converted = round(converted / 1000, 1)
        elif self._unit_of_measurement[:1].upper() == 'M':
            converted = round(converted / 1000000, 2)

        return converted
