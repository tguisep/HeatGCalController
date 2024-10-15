import json
import logging
import os

from .py_agua_iot import agua_iot
from typing import List


class StoveProvider(object):
    API_URL = "https://nobis.agua-iot.com"
    CUSTOMER_CODE = "700700"
    # 1 for NOBIS
    BRAND_ID = "1"

    def __init__(self, credentials_file_path, email=None, password=None, uuid=None):
        self.logger = logging.getLogger(__name__)
        self.connection = None
        self.devices = {}

        if os.path.exists(credentials_file_path):
            self.logger.debug(f'Getting credentials from {credentials_file_path}')
            with open(credentials_file_path) as json_file:
                data = json.load(json_file)
                self.email = data['email']
                self.password = data['password']
                self.uuid = data['uuid']
        else:
            self.logger.debug(f'Getting credentials from environment variables')
            self.email = email
            self.password = password
            self.uuid = uuid

    def connect(self):
        """Establish connection to the stove."""
        self.logger.info("Connecting to Stove pellet stove...")
        self.connection = agua_iot(self.API_URL, self.CUSTOMER_CODE, self.email, self.password, self.uuid,
                                   brand_id=self.BRAND_ID)

        for idx, device in enumerate(self.connection.devices):
            self.logger.info(f"Connected to {device.name} device with device_id ({idx})")

    def get_device_id_by_name(self, name: str) -> int:
        for idx, device in enumerate(self.connection.devices):
            if device.name.startswith(name):
                return idx

    def get_device_status(self, device_id: int) -> str:
        device = self.connection.devices[device_id]
        return device.status_translated

    def get_device_names(self) -> List[str]:
        """Get the names of all connected devices."""
        return [device.name for device in self.connection.devices]

    def get_air_temperature(self) -> List[str]:
        """Get the current air temperature for each device."""
        temperatures = []
        for device in self.connection.devices:
            temp_info = f"{device.name}: {device.air_temperature}°C"
            temperatures.append(temp_info)
            self.logger.info(temp_info)
        return temperatures

    def turn_on(self, device_id: int):
        """Turn on the stove."""
        self.logger.info(f"Turning on device with ID {device_id}...")
        self.connection.devices[device_id].turn_on()
        self.logger.info("Device turned on.")

    def turn_off(self, device_id: int):
        """Turn off the stove."""
        self.logger.info(f"Turning off device with ID {device_id}...")
        self.connection.devices[device_id].turn_off()
        self.logger.info("Device turned off.")

    def set_temperature(self, device_id: int, temperature: int):
        """Set the desired temperature for the stove."""
        self.logger.info(f"Setting temperature for device ID {device_id} to {temperature}°C...")
        self.connection.devices[device_id].set_temperature(temperature)
        self.logger.info(f"Temperature set to {temperature}")

    def disconnect(self):
        """Disconnect from the stove."""
        self.logger.info("Disconnecting from Stove pellet stove...")
        self.connection = None
        self.devices = {}
        self.logger.info("Disconnected.")
