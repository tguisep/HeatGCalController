import os

from libs.provider_heatzy import HeatzyProvider
from libs.provider_heatzy import HeaterBinaryModes
from libs.provider_edf_tempo import EDFTempoAPI
from collections import defaultdict
import time
import logging
from typing import Dict

class HeatzyDryRun(Exception):
    pass


class HeatzyCredentialsSourceFailure(Exception):
    pass


class HeatzyManager:
    DEFAULT_TIMEZONE = "Europe/Paris"

    def __init__(self, config: dict, max_delay_reapplied: int, logger:logging.Logger, use_tempo: bool = False):
        self.config = config
        self.max_delay_reapplied = max_delay_reapplied
        self.use_tempo = use_tempo

        # Initialize the logger
        self.logger = logger

        # Initialize the Heatzy provider
        self.hz = self._init_heatzy()

        # Run in dry run, do not apply changes
        self.dry_run = False

    def _init_heatzy(self) -> HeatzyProvider:
        """Initialize and return the Heatzy API connection."""
        credentials_source = self.config['set_heaters']["providers"]["heatzy"]["credentials"]
        self.logger.debug(f"Using Heatzy credentials from {credentials_source}")
        if credentials_source.startswith("file://"):
            credentials_file_path = credentials_source.split("file://")[1]
        elif credentials_source.startswith("env://"):
            env_var = os.getenv(credentials_source.split("env://")[1])
            credentials_file_path = "heatzy_credentials.json"
            with open(credentials_file_path, "w") as credentials_file:
                credentials_file.write(env_var)
        else:
            self.logger.error(f"Cannot get credentials from {credentials_source}")
            raise HeatzyCredentialsSourceFailure(
                f"Invalid credentials source {credentials_source}, `file://` or `env://` not found."
            )

        hz = HeatzyProvider(credentials_file_path)
        hz.login()
        return hz

    def set_mode_hz(self, device_id: str, mode: str) -> bool:
        """Set the mode of a Heatzy device."""
        try:
            mode_value = getattr(HeaterBinaryModes, mode)
            if self.dry_run:
                raise HeatzyDryRun(f"Dry run activated, function `hz.set_device_mode` "
                             f"with {(device_id, mode_value)} not applied")
            result = self.hz.set_device_mode(device_id, mode_value)
            if result:
                raise RuntimeError(f"Unable to set mode {mode} for device {device_id}: {result}")
            return True
        except AttributeError:
            self.logger.error(f"Mode {mode} does not exist in Heatzy modes.")
            return False
        except HeatzyDryRun as err:
            self.logger.warning(err)
            return True

    def apply_hz_schedule(self, devices_status: dict, mode_to_apply: dict, last_status: dict) -> dict:
        """Apply the schedule to the devices based on their status and modes."""
        status_devices = defaultdict(str)
        red_time = self._is_tempo_red_time()

        for device, device_params in mode_to_apply['devices'].items():
            self.logger.info(f"Applying heat schedule on {device}")

            if device_params['type'] != "heatzy":
                self.logger.debug(f"Device {device} is not a heatzy device")
                continue

            if device not in devices_status:
                self.logger.warning(f"Device {device} not found")
                status_devices[device] = 'not_found'
                continue

            if not devices_status[device]["device"]['is_online']:
                self.logger.warning(f"Device {device} is offline")
                status_devices[device] = 'OFFLINE'
                continue

            current_mode = self._get_device_current_mode(devices_status[device])

            if current_mode == device_params['mode']:
                self.logger.debug(f"Device {device} already in mode {device_params['mode']}")
                status_devices[device] = device_params['mode']
                continue

            if self._should_skip_due_to_status_change(device, current_mode, last_status):
                status_devices[device] = last_status.get(device)
                continue

            if self.use_tempo and red_time:
                device_params['mode'] = "HGEL"
                self.logger.info(f"EDF Tempo Red Time detected, setting {device} status to {device_params['mode']}")

            device_id = self.hz.alias_to_device_id(device)
            self.logger.info(f"Setting {device} to {device_params['mode']}")
            result = self.set_mode_hz(device_id, device_params['mode'])
            if result:
                status_devices[device] = device_params['mode']

        return status_devices

    def _get_device_current_mode(self, device_status: dict) -> str:
        """Get the current mode of the device if available."""
        if "attr" in device_status["devdata"]:
            current_mode = self.hz.convert_mode(device_status["devdata"]["attr"]["mode"])
            self.logger.info(f"Device detected with mode {current_mode}")
            return current_mode
        else:
            self.logger.warning(f"Cannot retrieve attribute data for device")

    def _should_skip_due_to_status_change(self, device: str, current_mode: str, last_status: dict) -> bool:
        """Check if device status has changed and if we should skip applying the mode."""
        current_time = int(time.time())
        if device in last_status and last_status.get(device) != current_mode:
            if last_status.get(device).startswith('changed_'):
                changed_time = int(last_status.get(device).split('_')[1])
                if current_time - changed_time < int(self.max_delay_reapplied):
                    self.logger.info(f"Device {device} max time between external changes not reached")
                    return True
            else:
                self.logger.warning(f"Device {device} has changed since last run from {last_status.get(device)} to {current_mode}")
                last_status[device] = f'changed_{current_time}'
                return True
        return False

    def _is_tempo_red_time(self) -> bool:
        """Check if EDF Tempo Red Time is active."""
        edf_tempo_api = EDFTempoAPI(
            tz=self.DEFAULT_TIMEZONE,
            tempo_config=self.config['set_heaters']["providers"]["edf_tempo"]
        )
        return edf_tempo_api.red_time().is_red

    def run_hz_devices(self, merged_schedule: dict, last_status: dict) -> Dict[str, str]:
        """Run Heatzy devices with the merged schedule and return the status."""
        self.logger.debug(f"Fetching all Heatzy devices status")
        devices_status = self.hz.get_all_devices_status()

        self.logger.debug(f"Applying schedule {merged_schedule}")
        status_devices = self.apply_hz_schedule(
            devices_status, merged_schedule['to_set'], last_status
        )
        return status_devices
