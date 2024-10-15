import json
import logging
import os
import time
import requests


class HeatzyException(Exception):
    pass


class HeaterBinaryModes:
    COMFORT = 0
    ECO = 1
    HGEL = 2
    OFF = 3
    LOW_1 = 4
    LOW_2 = 5


class HeatzyModes:
    cft = 'COMFORT'
    eco = 'ECO'
    off = 'OFF'
    fro = 'HGEL'
    stop = 'OFF'


class HeatzyProvider:
    GIZWIT_APP_ID = 'c70a66ff039d41b4a220e198b0fcc8b3'
    GITWIT_URL = 'https://euapi.gizwits.com/app'

    def __init__(self, credentials_file_path, username=None, password=None):
        self.logger = logging.getLogger(__name__)
        if os.path.exists(credentials_file_path):
            self.logger.debug(f'Getting credentials from {credentials_file_path}')
            with open(credentials_file_path) as json_file:
                data = json.load(json_file)
                self.username = data['username']
                self.password = data['password']
        else:
            self.logger.debug(f'Getting credentials from environment variables')
            self.username = username
            self.password = password

        self.headers = {
            'X-Gizwits-Application-Id': self.GIZWIT_APP_ID,
            'X-Gizwits-Timestamp': str(time.time()),
            'X-Gizwits-Signature': '',
            'Accept': 'application/json',
            'Content-Type': 'application/json',
        }
        self.session = requests.Session()

    def login(self):
        """Login to Heatzy."""
        self.logger.debug(f'Logging in to Heatzy')
        response = self.session.post(
            url=f'{self.GITWIT_URL}/login',
            headers=self.headers,
            json={'username': self.username, 'password': self.password}
        )
        self.headers['X-Gizwits-User-token'] = response.json()['token']
        return response.json()

    def get_devices(self):
        """Get Heatzy devices."""
        self.logger.debug(f'Getting devices')
        devices = self.session.get(
            url=f'{self.GITWIT_URL}/bindings',
            headers=self.headers
        ).json()
        return devices['devices']

    def alias_to_device_id(self, alias):
        """Get device id from alias."""
        self.logger.debug(f'Getting device id from alias {alias}')
        devices = self.get_devices()
        for device in devices:
            if device['dev_alias'] == alias:
                return device['did']

    def set_device_mode(self, device_id, mode):
        """Set device mode."""
        self.logger.debug(f'Setting device {device_id} to mode {mode}')
        return self.session.post(
            url=f'{self.GITWIT_URL}/control/{device_id}',
            headers=self.headers,
            json={'attrs': {'mode': mode}}
        ).json()

    def get_device_status_details(self, device_id):
        """Get device status."""
        self.logger.debug(f'Getting device status details for {device_id}')
        return self.session.get(
            url=f'{self.GITWIT_URL}/devdata/{device_id}/latest',
            headers=self.headers,
        ).json()

    def get_device_status(self, device_id):
        """Get device status."""
        self.logger.debug(f'Getting device status for {device_id}')
        return self.session.get(
            url=f'{self.GITWIT_URL}/devices/{device_id}',
            headers=self.headers
        ).json()

    def convert_mode(self, heatzy_mode):
        """Convert Heatzy mode to Modes."""
        self.logger.debug(f'Converting Heatzy mode {heatzy_mode} to Modes')
        converted_mode = getattr(HeatzyModes, heatzy_mode)
        self.logger.debug(f'Converted mode {heatzy_mode} to {converted_mode}')
        return converted_mode

    def get_all_devices_status(self):
        """Get device status."""
        self.logger.debug(f'Getting all devices status')
        devices = self.get_devices()
        return {
            device['dev_alias']: {
                "device": self.get_device_status(device['did']),
                "devdata": self.get_device_status_details(device['did'])
            }
            for device in devices
        }
