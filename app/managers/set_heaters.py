import argparse
import datetime
import json
import logging
import os
import traceback
from collections import defaultdict
from datetime import datetime
import pytz

from libs.common import read_yaml_config, get_logger
from controllers.heatzy import HeatzyManager
from controllers.stove import StoveManager

class HeaterManager:
    def __init__(self, config_heater_file_path: str):
        """Initialize HeaterManager with configuration files"""
        self.config_heater_file_path = config_heater_file_path

        # Read the configuration files
        self.configs = self._load_configs()

        # Initialize the logger
        self.logger = logging.getLogger(__name__)
        self._set_logging()

        # Load mode configurations
        self.modes = self._load_modes()

        # Run in dry run, do not apply changes
        self.dry_run = False

    def _load_configs(self) -> dict:
        """Load configurations from YAML files."""
        configs_heater = read_yaml_config(self.config_heater_file_path)
        return configs_heater

    def _set_logging(self):
        """Set up logging based on the configuration."""
        log_file_path = f'{self.configs["logs"]["directory"]}/set_heaters.log'
        log_level = self.configs["logs"]["level"].upper()

        return get_logger(self.logger, log_file_path=log_file_path, level=log_level)

    def _load_modes(self) -> dict:
        """Load heating modes from the configuration."""
        self.logger.debug("Reading modes configuration")
        set_heaters_configs = self.configs['set_heaters']
        modes_file_path = set_heaters_configs["inputs"]["modes"]
        return read_yaml_config(modes_file_path)

    def _get_schedules(self) -> dict:
        """Get schedules from the configuration file."""
        set_heaters_configs = self.configs['set_heaters']
        schedule_file_path = set_heaters_configs["inputs"]["schedules"]

        if os.path.exists(schedule_file_path):
            self.logger.debug(f"Reading schedule file from {schedule_file_path}")
            return read_yaml_config(schedule_file_path)
        else:
            self.logger.error(f"Schedule file {schedule_file_path} not found. Run get_schedules.py first.")
            exit(1)

    def _get_last_status(self) -> dict:
        """Get last status from file, or return an empty dictionary if not found."""
        set_heaters_configs = self.configs['set_heaters']
        last_status_file_path = set_heaters_configs["inputs"]["status"]

        if os.path.exists(last_status_file_path):
            self.logger.debug(f"Reading last status from {last_status_file_path}")
            return read_yaml_config(last_status_file_path)
        else:
            self.logger.info(f"Last status file {last_status_file_path} not found, initializing empty status.")
            return {}

    def _merge_schedules(self, schedules: list) -> dict:
        """Merge applicable schedules by priority."""
        self.logger.debug("Merging schedules based on priority")
        return merge_definitions(schedules)

    def run(self):
        """Run the heater manager process to set modes."""
        set_heaters_configs = self.configs['set_heaters']
        max_delay_reapplied = set_heaters_configs['max_delay_reapplied']
        self.logger.info(f"Max delay reapplied: {max_delay_reapplied}")

        timezone = self.configs['timezone']
        self.logger.info(f"Timezone: {timezone}")

        # Get the default mode and applicable schedules
        default_mode = self.modes['default']
        schedules = self._get_schedules()
        applicable_schedules = [self.modes[schedule['title']] for schedule in schedules if is_current_time_between(schedule, timezone)]
        applicable_schedules.append(default_mode)

        # Merge schedules based on priority
        merged_schedule = self._merge_schedules(applicable_schedules)

        # Get last device statuses
        last_status = self._get_last_status()

        # Apply settings for Heatzy devices
        status_devices_heatzy = {}
        if "heatzy" in set_heaters_configs["providers"]:
            hz_manager = HeatzyManager(self.configs, max_delay_reapplied, logger=self.logger)
            hz_manager.dry_run = self.dry_run
            if "edf_tempo" in set_heaters_configs["providers"]:
                if set_heaters_configs["providers"]["edf_tempo"]['enabled']:
                    self.logger.info("EDF tempo activated, applying for Heatzy Devices...")
                    hz_manager.use_tempo = True

            status_devices_heatzy = hz_manager.run_hz_devices(
                merged_schedule, last_status
            )

        # Apply settings for Stove devices
        status_devices_stove = {}
        if "stove" in set_heaters_configs["providers"]:
            try:
                stove_manager = StoveManager(
                    self.configs['set_heaters']["providers"]["stove"],
                    max_delay_reapplied, logger=self.logger
                )
                stove_manager.dry_run = self.dry_run
                status_devices_stove = stove_manager.run_stove_devices(
                    merged_schedule, last_status
                )
            except Exception as err:
                self.logger.error(f"Could not start NOBIS services: {err}")
                self.logger.error(f"Make sure than your device is connected properly.")
                self.logger.error(traceback.format_exc())

        # Save last status
        last_status_file_path = set_heaters_configs["inputs"]["status"]
        self.logger.debug(f"Write {last_status_file_path} status")
        data = {**status_devices_heatzy, **status_devices_stove}
        if not self.dry_run:
            json_content = json.dumps(data, indent=2)
            with open(last_status_file_path, 'w') as file:
                file.write(json_content)
        else:
            self.logger.info("Dry run activated, status file not updated")
        self.logger.debug(json.dumps(data))


def merge_definitions(definitions: list) -> dict:
    """Merge device definitions by priority."""
    result = {"to_set": {"devices": defaultdict(dict)}}
    definitions.sort(key=lambda x: x['priority'], reverse=True)

    for definition in definitions:
        for device, device_params in definition['devices'].items():
            result['to_set']['devices'][device]["mode"] = device_params["mode"]
            result['to_set']['devices'][device]["type"] = device_params["type"]
            result['to_set']['devices'][device]["sequences"] = device_params["sequences"]
    return result


def is_current_time_between(schedule: dict, timezone: str) -> bool:
    """Check if the current time falls between the start and end times of a schedule."""
    start_time = schedule['start_time']
    end_time = schedule['end_time']

    start_datetime = datetime.fromisoformat(start_time)
    end_datetime = datetime.fromisoformat(end_time)

    if start_datetime.tzinfo is None:
        start_datetime = pytz.timezone(timezone).localize(start_datetime)
    if end_datetime.tzinfo is None:
        end_datetime = pytz.timezone(timezone).localize(end_datetime)

    current_time = datetime.now(pytz.timezone(timezone))
    return start_datetime <= current_time <= end_datetime


def main(config_heater_file_path: str, dry_run:bool = False):
    """Entry point for HeaterManager"""
    heater_manager = HeaterManager(config_heater_file_path)
    heater_manager.dry_run = dry_run
    heater_manager.run()


if __name__ == '__main__':
    parser = argparse.ArgumentParser(prog='Set heaters mode')
    parser.add_argument("--configs", required=False, default="configs/main.yaml", help="Set heaters config file")
    parser.add_argument("--dry-run", default=False, action='store_true', help="Run as dry run")
    args = parser.parse_args()

    main(args.configs, dry_run=args.dry_run)
