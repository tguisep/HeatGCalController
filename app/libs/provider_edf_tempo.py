import logging

import requests
import datetime
from typing import Dict, Union

from pydantic import BaseModel
from pytz import timezone


class RedTimeResults(BaseModel):
    current_time: str
    red_time_start: str
    red_time_end: str
    is_red: bool
    margin_min: int

class TempoColorsValues(BaseModel):
    TEMPO_RED: int = 3
    TEMPO_WHITE: int = 2
    TEMPO_BLUE: int = 1
    UNKNOWN: int = 0

class EDFTempoAPI:
    """
    A class to interact with the EDF Tempo API to get the color of the current day and the next day.
    """

    BASE_URL = "https://www.api-couleur-tempo.fr/api/jourTempo"

    def __init__(self, tz, tempo_config, credentials=None):
        self.logger = logging.getLogger(__name__)
        self.timezone = tz
        self.schedules_margin: int = tempo_config["red_hour_margin"]
        self.schedules: dict = tempo_config["schedules"]
        # This API does not need cred - Not in use
        self.api_credentials: Dict = credentials

    def _build_url(self, date: datetime.date) -> str:
        """
        Build the API URL with the given date.

        Args:
            date (datetime.date): The relevant date.

        Returns:
            str: The complete URL for the API request.
        """
        return f"{self.BASE_URL}/{date}"

    def _get_api_response(self, url: str) -> Union[Dict, None]:
        """
        Send a GET request to the API and return the JSON response.

        Args:
            url (str): The URL for the API request.

        Returns:
            Union[Dict, None]: The JSON response from the API if successful, None otherwise.
        """
        try:
            response = requests.get(url)
            response.raise_for_status()
            return response.json()
        except requests.RequestException as e:
            self.logger.error(f"Error fetching data from EDF API: {e}")
            return None

    def get_tempo_colors(self) -> Dict[str, Union[str, datetime.date]]:
        """
        Get the color of the current day and the next day from the EDF Tempo API.

        Returns:
            Dict[str, Union[str, datetime.date]]: A dictionary containing the colors of the current and next day.
        """
        current_date = datetime.datetime.now().date()
        next_date = current_date + datetime.timedelta(days=1)

        current_day_url = self._build_url(current_date)
        current_day_data = self._get_api_response(current_day_url)

        next_day_url = self._build_url(next_date)
        next_day_data = self._get_api_response(next_day_url)

        if current_day_data and next_day_data:
            return {
                "current_date": current_date,
                "current_day_color": current_day_data.get("codeJour"),
                "next_date": next_date,
                "next_day_color": current_day_data.get("codeJour")
            }
        else:
            return {
                "error": "Failed to retrieve data from EDF API"
            }

    def red_time(self, margin_minutes: int = 5) -> RedTimeResults:
        """
        Check if the current time is within the "red time" range (6 AM to 11 PM) with an optional margin.

        Args:
            margin_minutes (int): The margin in minutes to extend the red time range. Default is 0.

        Returns:
            str: A JSON string with the status and parameters used.
        """
        now = datetime.datetime.now(timezone(self.timezone))

        _is_red_time = False
        start_with_margin = ...
        end_with_margin = ...

        for schedule in self.schedules:
            start_time = datetime.time(hour=schedule["red_hour_start"], minute=self.schedules_margin)
            end_time = datetime.time(hour=schedule["red_hour_stop"], minute=self.schedules_margin)

            start_with_margin = (
                    datetime.datetime.combine(now.date(), start_time) - datetime.timedelta(minutes=margin_minutes)
            ).time()

            end_with_margin = (
                    datetime.datetime.combine(now.date(), end_time) + datetime.timedelta(minutes=margin_minutes)
            ).time()

            _is_red_time = start_with_margin <= now.time() <= end_with_margin

            self.logger.info(f"Schedule: {schedule} detected as `{_is_red_time}`")
            if _is_red_time:
                break

        _is_red_day = self.get_tempo_colors()['current_day_color'] == TempoColorsValues().TEMPO_RED

        result: RedTimeResults = RedTimeResults(
            current_time=now.strftime("%Y-%m-%d %H:%M:%S"),
            red_time_start=start_with_margin.strftime("%H:%M"),
            red_time_end=end_with_margin.strftime("%H:%M"),
            is_red=True if _is_red_time and _is_red_day else False,
            margin_min=margin_minutes
        )
        return result
