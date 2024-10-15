import os

from pydantic.v1 import BaseModel

from libs.provider_stove import StoveProvider
import time
import logging
from collections import defaultdict
from typing import Dict

class StoveDryRun(Exception):
    pass

class StoveModes(BaseModel):
    comfort_plus = "COMFORT_PLUS"
    comfort = "COMFORT"
    comfort_eco = "COMFORT_ECO"
    low_mode = "LOW_MODE"
    off = "OFF"


class StoveCredentialsSourceFailure(Exception):
    pass


class StoveManager:
    def __init__(self, config: dict, max_delay_reapplied: int, logger:logging.Logger, use_tempo: bool = False):
        self.config = config
        self.max_delay_reapplied = max_delay_reapplied
        self.use_tempo = use_tempo

        # Initialize the logger
        self.logger = logger

        # Initialize the Stove provider
        self.stove = self._init_stove()

        #  Dry Run
        self.dry_run = False

    def _init_stove(self) -> StoveProvider:
        """Initialize and return the Stove API connection."""
        credentials_source = self.config["credentials"]
        self.logger.debug(f"Using Heatzy credentials from {credentials_source}")
        if credentials_source.startswith("file://"):
            credentials_file_path = credentials_source.split("file://")[1]
        elif credentials_source.startswith("env://"):
            env_var = os.getenv(credentials_source.split("env://")[1])
            credentials_file_path = "~/stove_credentials.json"
            with open(credentials_file_path, "w") as credentials_file:
                credentials_file.write(env_var)
        else:
            self.logger.error(f"Cannot get credentials from {credentials_source}")
            raise StoveCredentialsSourceFailure(
                f"Invalid credentials source {credentials_source}, `file://` or `env://` not found."
            )

        stove = StoveProvider(credentials_file_path)
        stove.connect()
        return stove

    def _get_temperature_config(self, mode) -> int:
        temperatures_config = self.config["temperatures"]
        return temperatures_config.get(mode, StoveModes.comfort)

    def set_temperature_stove(self, device_name: str, mode: str):
        try:
            if self.dry_run:
                raise StoveDryRun(
                    f"Dry run activated, function `stove.set_temperature` "
                    f"with {device_name} not applied"
                )
            self.stove.set_temperature(
                device_id=self.stove.get_device_id_by_name(device_name),
                temperature=self._get_temperature_config(mode)
            )
        except Exception as e:
            self.logger.error(f"Error setting temperature for {device_name}: {e}")


    def set_mode_stove(self, device_name: str, mode: str) -> bool:
        """Set the mode of a Stove device."""
        try:
            if mode == StoveModes.off:
                self.logger.info(f"Turn OFF {device_name}")
                if self.dry_run:
                    raise StoveDryRun(
                        f"Dry run activated, function `stove.turn_off` "
                        f"with {device_name} not applied"
                    )
                self.stove.turn_off(self.stove.get_device_id_by_name(device_name))
            elif mode.startswith(StoveModes.comfort) or mode == StoveModes.low_mode:
                self.set_temperature_stove(device_name, mode)
                self.logger.info(f"Turn ON {device_name} with mode {mode}")
                if self.dry_run:
                    raise StoveDryRun(
                        f"Dry run activated, function `stove.turn_on` "
                        f"with {device_name} not applied"
                    )
                self.stove.turn_on(self.stove.get_device_id_by_name(device_name))
            else:
                raise Exception(f"Unknown mode {mode}")
        except StoveDryRun:
            """ Pass, nothing to except """
            return True
        except Exception as e:
            self.logger.error(f"Error setting mode for {device_name}: {e}")
        else:
            return True


    def apply_stove_schedule(self, devices_status: Dict[str, str], mode_to_apply: dict, last_status: dict) -> dict:
        """Apply the schedule to Stove devices based on their status and modes."""
        status_devices = defaultdict(str)

        for device, device_params in mode_to_apply['devices'].items():
            if device_params['type'] != "stove":
                self.logger.debug(f"Device {device} is not a Stove device")
                continue

            if device not in devices_status:
                self.logger.warning(f"Device {device} not found")
                status_devices[device] = 'not_found'
                continue

            if devices_status[device] == device_params['mode']:
                self.logger.debug(f"Device {device} already in mode {device_params['mode']}")
                status_devices[device] = device_params['mode']
                continue

            if self._should_skip_due_to_status_change(device, devices_status, last_status):
                status_devices[device] = last_status.get(device)
                continue

            if self._should_skip_due_to_status_invalid(device, devices_status):
                "We accept only ON or OFF status, intermediate must be ignored"
                status_devices[device] = last_status.get(device)
                continue

            self.logger.info(f"Setting {device} to {device_params['mode']}")
            result = self.set_mode_stove(device, device_params['mode'])
            if result:
                status_devices[device] = device_params['mode']

        return status_devices

    def _should_skip_due_to_status_change(self, device: str, devices_status: dict, last_status: dict) -> bool:
        """Check if device status has changed and if we should skip applying the mode."""
        current_time = int(time.time())
        if device in last_status and last_status.get(device) != devices_status[device]:
            if last_status.get(device).startswith('changed_'):
                changed_time = int(last_status.get(device).split('_')[1])
                if current_time - changed_time < int(self.max_delay_reapplied):
                    self.logger.info(f"Device {device} max time between external changes not reached")
                    return True
            else:
                self.logger.warning(f"Device {device} has changed since last run from {last_status.get(device)} to {devices_status[device]}")
                last_status[device] = f'changed_{current_time}'
                return True
        return False

    def _should_skip_due_to_status_invalid(self, device: str, devices_status: dict) -> bool:
        if devices_status[device] in ["OFF", "ON"]:
            self.logger.info(f"Stove {device} detected with status {devices_status[device]}")
            return False
        else:
            self.logger.warning(f"Stove {device} detected with an intermediate status {devices_status[device]}")
            self.logger.warning(f"Stove {device} need to be on ON or OFF status, please try again later.")
            return True


    def run_stove_devices(self, merged_schedule: dict, last_status: dict) -> Dict[str, str]:
        """Run Stove devices with the merged schedule and return the status."""
        self.logger.debug(f"Reading Stove credentials")

        devices_status = self._get_devices_status()

        self.logger.debug(f"Applying schedule {merged_schedule}")
        status_devices = self.apply_stove_schedule(
            devices_status, merged_schedule['to_set'], last_status
        )

        self.logger.info("Disconnecting Stove")
        self.stove.disconnect()
        return status_devices

    def _get_devices_status(self) -> dict:
        """Get the current status of all Stove devices."""
        self.logger.info("Reading devices status")
        devices_status = {}
        for idx, device in enumerate(self.stove.connection.devices):
            devices_status[device.name.strip()] = self.stove.get_device_status(idx)
        return devices_status
