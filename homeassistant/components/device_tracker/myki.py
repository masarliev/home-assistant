"""
Support for the Myki.watch device tracker.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/device_tracker.myki/

"""
import logging
import json

import asyncio
import requests
from requests.auth import HTTPBasicAuth
import voluptuous as vol
import homeassistant.helpers.config_validation as cv
from homeassistant.core import callback
from homeassistant.components.device_tracker import PLATFORM_SCHEMA
from homeassistant.const import (
    CONF_SCAN_INTERVAL, CONF_USERNAME, CONF_PASSWORD)
_LOGGER = logging.getLogger(__name__)


PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Required(CONF_USERNAME): cv.string,
    vol.Required(CONF_PASSWORD): cv.string,
    vol.Optional(CONF_SCAN_INTERVAL,
                 default=300): cv.time_period,
})


@asyncio.coroutine
def async_setup_scanner(hass, config, async_see, discovery_info=None):
    """Set up the scanner and return the update function."""
    devices = _get_devices(config)
    interval = config.get(CONF_SCAN_INTERVAL)
    _LOGGER.debug('%d devices found.' % len(devices))

    @callback
    def see_device(device: dict):
        _LOGGER.debug('Getting information for device %s' % device.get('id'))
        try:
            response = requests.get(
                'https://my.myki.watch/api/watch/app-data',
                params={"id": device.get('id')},
                auth=HTTPBasicAuth(config.get(CONF_USERNAME),
                                   config.get(CONF_PASSWORD))
            )
        except requests.exceptions.ConnectionError:
            _LOGGER.error('Connection error.')
            return False
        if response.status_code != 200:
            _LOGGER.error("No response for %s failed=%d",
                          device.get('id'), response.status_code)
            return False
        _LOGGER.debug('Information received for %s' % device.get('id'))
        data = json.loads(response.content.decode('utf-8'))
        info = data.get('data', {}).get('current')
        if not info:
            _LOGGER.error('Missing info for device %s' % device.get('id'))
            return False

        gps_location = (info['position']['latitude'],
                        info['position']['longitude'])
        attrs = {}
        attrs['type'] = info.get('position').get('type')
        attrs['updated'] = info.get('takenat')
        attrs['speed'] = info.get('speed')
        hass.async_add_job(async_see(
            dev_id=device.get('id'), gps=gps_location,
            battery=info.get('battery'),
            gps_accuracy=info.get('position').get('accuracy')
        ))

    @asyncio.coroutine
    def update(now):
        """Update all the devices on every interval time."""
        _LOGGER.debug('Updating device states.')
        for item in devices:
            see_device(item)

    hass.helpers.event.async_track_time_interval(
        update, interval)
    return True


def _get_devices(config):
    try:
        response = requests.get(
            'https://my.myki.watch/api/watch',
            auth=HTTPBasicAuth(config.get(CONF_USERNAME),
                               config.get(CONF_PASSWORD))
        )
    except requests.exceptions.ConnectionError:
        _LOGGER.error('Connection error.')
        return
    if response.status_code != 200:
        _LOGGER.error("No response from myki failed=%d",
                      response.status_code)
        return []
    data = json.loads(response.content.decode('utf-8'))
    if not data.get('isok', False):
        _LOGGER.error(data.get('err'))
        return []
    return data.get('data', {}).get('allw', [])
