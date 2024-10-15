import argparse
import logging
import os

from libs.common import read_yaml_config, get_logger
from libs.google_calendar import GoogleCalendarAPI


class GoogleCredentialsSourceFailure(Exception):
    pass


class ScheduleManager:
    def __init__(self, config_schedule_file_path):
        """Initialize ScheduleManager with configuration files"""
        self.config_schedule_file_path = config_schedule_file_path

        # Read the configuration files
        self.configs = self._load_configs()

        # Initialize the logger
        self.logger = logging.getLogger(__name__)
        self._set_logging()

        # Initialize the Google Calendar API
        self.google_calendar_api = self._init_google_calendar()

    def _load_configs(self) -> dict:
        """Load configurations from YAML files."""
        #self.logger.debug(f"Reading configs from {self.config_schedule_file_path}")
        configs_heater = read_yaml_config(self.config_schedule_file_path)
        return configs_heater

    def _set_logging(self):
        """Set up logging based on the configuration."""
        log_file_path = f'{self.configs["logs"]["directory"]}/get_schedules.log'
        log_level = self.configs["logs"]["level"].upper()

        return get_logger(self.logger, log_file_path=log_file_path, level=log_level)

    def _init_google_calendar(self) -> GoogleCalendarAPI:
        """Initialize the GoogleCalendarAPI with credentials."""
        credentials_source = self.configs['get_schedules']["providers"]["google"]["credentials"]

        if credentials_source.startswith("file://"):
            credentials_file_path = credentials_source.split("file://")[1]
        elif credentials_source.startswith("env://"):
            env_var = os.getenv(credentials_source.split("env://")[1])
            credentials_file_path = "google_credentials.json"
            with open(credentials_file_path, "w") as credentials_file:
                credentials_file.write(env_var)
        else:
            self.logger.error(f"Cannot get credentials from {credentials_source}")
            raise GoogleCredentialsSourceFailure(
                f"Invalid credentials source {credentials_source}, `file://` or `env://` not found."
            )

        timezone = self.configs['timezone']
        return GoogleCalendarAPI(credentials_file_path, timezone)

    def get_and_save_meetings(self):
        """Get meetings from Google Calendar and save them to a file."""
        output_file = self.configs['get_schedules']["outputs"]["schedules"]

        # Get HeatZy meetings from Google Calendar API
        self.logger.debug("Fetching meetings from Google Calendar")
        heatzy_meetings = self.google_calendar_api.get_meetings()

        # Save meetings to JSON
        self.logger.debug(f"Saving meetings to {output_file}")
        GoogleCalendarAPI.save_to_json(heatzy_meetings, output_file)

    def run(self):
        """Run the full schedule manager process."""
        self.get_and_save_meetings()


def main(config_schedule_file_path: str):
    """Entry point for the ScheduleManager"""
    schedule_manager = ScheduleManager(config_schedule_file_path)
    schedule_manager.run()


if __name__ == '__main__':
    parser = argparse.ArgumentParser(prog='Get reservations from Google Calendar')
    parser.add_argument("--configs", required=False, default="configs/main.yaml", help="General config file")
    args = parser.parse_args()

    main(args.configs)
