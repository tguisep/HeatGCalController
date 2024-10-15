import logging
import os
import json
import datetime
from google.oauth2 import service_account
from googleapiclient.discovery import build


class GoogleCalendarAPI:
    def __init__(self, credentials_file_path: str, timezone:str):
        self.logger = logging.getLogger(__name__)
        self.credentials_file_path = credentials_file_path
        self.credentials = self._get_credentials()
        self.calendar_api = self._build_calendar_api()
        self.timezone = timezone

    def _get_credentials(self):
        self.logger.debug(f'Getting credentials from {self.credentials_file_path}')
        return service_account.Credentials.from_service_account_file(
            self.credentials_file_path, scopes=['https://www.googleapis.com/auth/calendar.readonly']
        )

    def _build_calendar_api(self):
        self.logger.debug(f'Building calendar api')
        return build('calendar', 'v3', credentials=self.credentials)

    def get_meetings(self, calendar_id:str='primary', max_results:int=50):
        self.logger.debug(f'Getting meetings from {calendar_id}')

        now = datetime.datetime.utcnow()
        now_iso = now.isoformat() + 'Z'
        self.logger.debug(f'Getting meetings from {now_iso}')

        events_result = self.calendar_api.events().list(
            calendarId=calendar_id,
            timeMin=now_iso,
            maxResults=max_results,
            singleEvents=True,
            orderBy='startTime',
            timeZone=self.timezone
        ).execute()
        self.logger.debug(f'Got {len(events_result.get("items", []))} meetings')

        return events_result.get('items', [])

    @staticmethod
    def save_to_json(meetings: list, output_file: str) -> None:

        if output_file is None:
            output_file = 'outputs/heatzy_meetings.json'

        # get path only from output_file
        path = os.path.dirname(output_file)

        if not os.path.exists(path):
            os.makedirs(path)

        meetings_info = []
        for meeting in meetings:
            meetings_info.append({
                'start_time': meeting['start']['dateTime'] if 'dateTime' in meeting['start'] else meeting['start']['date'],
                'end_time': meeting['end']['dateTime'] if 'dateTime' in meeting['end'] else meeting['end']['date'],
                'title': meeting['summary']
            })

        json_content = json.dumps(meetings_info, indent=2)
        with open(output_file, 'w') as file:
            file.write(json_content)


