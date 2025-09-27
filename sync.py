import requests
import json
import os
from datetime import datetime, timedelta
from google.oauth2 import service_account
from googleapiclient.discovery import build

# Environment variables
NOTION_TOKEN = os.getenv('NOTION_TOKEN')
NOTION_DB_ID = os.getenv('NOTION_DB_ID')
GOOGLE_CREDENTIALS_JSON = os.getenv('GOOGLE_CREDENTIALS')
CALENDAR_ID = os.getenv('CALENDAR_ID', 'primary')

def get_google_calendar_service():
    """Initialize Google Calendar API service"""
    credentials_info = json.loads(GOOGLE_CREDENTIALS_JSON)
    credentials = service_account.Credentials.from_service_account_info(
        credentials_info,
        scopes=['https://www.googleapis.com/auth/calendar']
    )
    return build('calendar', 'v3', credentials=credentials)

def get_notion_items():
    """Fetch items from Notion database"""
    headers = {
        'Authorization': f'Bearer {NOTION_TOKEN}',
        'Notion-Version': '2022-06-28',
        'Content-Type': 'application/json'
    }

    response = requests.post(
        f'https://api.notion.com/v1/databases/{NOTION_DB_ID}/query',
        headers=headers,
        json={}
    )

    if response.status_code == 200:
        return response.json().get('results', [])
    else:
        print(f"Error fetching Notion data: {response.status_code}")
        print(response.text)
        return []

def notion_to_calendar_event(notion_item):
    """Convert Notion item to Google Calendar event"""
    properties = notion_item.get('properties', {})

    # Titel
    title = "Untitled Event"
    if 'Name' in properties:
        title_prop = properties['Name']
        if title_prop['type'] == 'title' and title_prop['title']:
            title = title_prop['title'][0]['plain_text']

    # Datum/Zeiten
    start_time = None
    end_time = None
    is_all_day = False

    if 'Date' in properties:
        date_prop = properties['Date']
        if date_prop['type'] == 'date' and date_prop['date']:
            start_time = date_prop['date']['start']
            end_time = date_prop['date'].get('end')

            # Fall 1/2: Ganztags (Format = YYYY-MM-DD)
            if len(start_time) == 10:
                is_all_day = True
                if not end_time:
                    # kein Enddatum → +1 Tag
                    end_date = datetime.strptime(start_time, "%Y-%m-%d") + timedelta(days=1)
                    end_time = end_date.strftime("%Y-%m-%d")

    if not start_time:
        return None

    # Event für Google erstellen
    event = {
        'summary': title,
        'description': f"Synced from Notion: {notion_item['url']}",
    }

    if is_all_day:
        event['start'] = {'date': start_time}
        event['end'] = {'date': end_time}
    else:
        # Fall 3: Nur Startzeit → Default Endzeit = +1h
        if not end_time:
            try:
                dt_start = datetime.fromisoformat(start_time.replace("Z", "+00:00"))
                dt_end = dt_start + timedelta(hours=1)
                end_time = dt_end.isoformat()
            except:
                end_time = start_time

        event['start'] = {'dateTime': start_time}
        event['end'] = {'dateTime': end_time}

    return event

def sync_notion_to_calendar():
    """Main sync function"""
    print("🔄 Starting Notion → Google Calendar sync...")

    notion_items = get_notion_items()
    print(f"📋 Found {len(notion_items)} Notion items")

    if not notion_items:
        print("✅ No items to sync")
        return

    try:
        service = get_google_calendar_service()
        print("🔗 Connected to Google Calendar")
    except Exception as e:
        print(f"❌ Failed to connect to Google Calendar: {e}")
        return

    synced_count = 0
    for item in notion_items:
        try:
            event = notion_to_calendar_event(item)
            if not event:
                print("⏭️  Skipping item without valid date")
                continue

            # Kein Duplicate-Check → immer ein Event erstellen
            created_event = service.events().insert(
                calendarId=CALENDAR_ID,
                body=event
            ).execute()
            print(f"✅ Created event: {event['summary']}")
            synced_count += 1

        except Exception as e:
            print(f"❌ Error syncing item: {e}")
            continue

    print(f"🎉 Sync complete! Created {synced_count} new events")

if __name__ == "__main__":
    sync_notion_to_calendar()