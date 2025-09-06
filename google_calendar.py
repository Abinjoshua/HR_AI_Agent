import datetime
import pickle
import os.path
import logging
from google.auth.transport.requests import Request
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

# Updated scope for managing calendar events
SCOPES = ['https://www.googleapis.com/auth/calendar.events']

logging.basicConfig(level=logging.INFO)

def get_calendar_service():
    creds = None
    try:
        if os.path.exists('token.pickle'):
            with open('token.pickle', 'rb') as token:
                creds = pickle.load(token)
        if not creds or not creds.valid:
            if creds and creds.expired and creds.refresh_token:
                creds.refresh(Request())
            else:
                # Update this filename if your OAuth file is named differently
                flow = InstalledAppFlow.from_client_secrets_file('client_secrets.json', SCOPES)
                creds = flow.run_local_server(port=0)
            with open('token.pickle', 'wb') as token:
                pickle.dump(creds, token)
        service = build('calendar', 'v3', credentials=creds)
        return service
    except Exception as e:
        logging.error(f"Failed to get calendar service: {e}")
        return None

def schedule_interview(service, candidate_email, candidate_name, start_datetime, end_datetime):
    if not service:
        logging.error("No calendar service available to schedule the interview")
        return None

    event = {
        'summary': f'Interview with {candidate_name}',
        'start': {
            'dateTime': start_datetime.isoformat(),
            'timeZone': 'Asia/Kolkata',
        },
        'end': {
            'dateTime': end_datetime.isoformat(),
            'timeZone': 'Asia/Kolkata',
        },
        'attendees': [
            {'email': candidate_email},
        ],
        'reminders': {
            'useDefault': True,
        },
    }

    try:
        created_event = service.events().insert(calendarId='primary', body=event, sendUpdates='all').execute()
        logging.info(f"Scheduled interview for {candidate_name} ({candidate_email}) at {start_datetime}")
        return created_event.get('htmlLink')
    except HttpError as error:
        logging.error(f"An error occurred scheduling interview: {error}")
        return None

# Example usage:
if __name__ == "__main__":
    service = get_calendar_service()
    if service:
        # Example candidate and interview time
        candidate_email = "candidate@example.com"
        candidate_name = "John Doe"
        start_time = datetime.datetime.now() + datetime.timedelta(days=1)
        end_time = start_time + datetime.timedelta(hours=1)
        link = schedule_interview(service, candidate_email, candidate_name, start_time, end_time)
        if link:
            print(f"Interview scheduled: {link}")
        else:
            print("Failed to schedule interview.")
    else:
        print("Failed to authenticate Google Calendar service.")
