import requests
import json
import os
from datetime import datetime, timezone
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

    # Query for items modified in last 24 hours
    filter_data = {
        "filter": {
            "timestamp": "last_edited_time",
            "last_edited_time": {
                "past_week": {}
            }
        }
    }

    response = requests.post(
        f'https://api.notion.com/v1/databases/{NOTION_DB_ID}/query',
        headers=headers,
        json=filter_data
    )

    if response.status_code == 200:
        return response.json().get('results', [])
    else:
        print(f"Error fetching Notion data: {response.status_code}")
        print(response.text)
        return []

def notion_to_calendar_event(notion_item):
    """Convert Notion database item to Google Calendar event"""
    properties = notion_item.get('properties', {})

    # Extract title (adjust property name as needed)
    title = "Untitled Event"
    if 'Name' in properties or 'Title' in properties:
        title_prop = properties.get('Name') or properties.get('Title')
        if title_prop['type'] == 'title' and title_prop['title']:
            title = title_prop['title'][0]['plain_text']

    # Extract date (adjust property name as needed)
    start_time = None
    end_time = None

    if 'Date' in properties:
        date_prop = properties['Date']
        if date_prop['type'] == 'date' and date_prop['date']:
            start_time = date_prop['date']['start']
            end_time = date_prop['date'].get('end', start_time)

    # Create calendar event
    event = {
        'summary': title,
        'description': f"Synced from Notion: {notion_item['url']}",
        'start': {
            'dateTime': start_time,
            'timeZone': 'UTC',
        },
        'end': {
            'dateTime': end_time,
            'timeZone': 'UTC',
        },
        'source': {
            'title': 'Notion',
            'url': notion_item['url']
        }
    }

    return event

def sync_notion_to_calendar():
    """Main sync function"""
    print("🔄 Starting Notion → Google Calendar sync...")

    # Get Notion items
    notion_items = get_notion_items()
    print(f"📋 Found {len(notion_items)} Notion items")

    if not notion_items:
        print("✅ No items to sync")
        return

    # Initialize Google Calendar service
    try:
        service = get_google_calendar_service()
        print("🔗 Connected to Google Calendar")
    except Exception as e:
        print(f"❌ Failed to connect to Google Calendar: {e}")
        return

    # Sync each item
    synced_count = 0
    for item in notion_items:
        try:
            # Convert to calendar event
            event = notion_to_calendar_event(item)

            if not event['start'].get('dateTime'):
                print(f"⏭️  Skipping item without date: {event['summary']}")
                continue

            # Check if event already exists (basic duplicate prevention)
            existing_events = service.events().list(
                calendarId=CALENDAR_ID,
                q=event['summary'],
                timeMin=event['start']['dateTime'],
                timeMax=event['end']['dateTime']
            ).execute()

            if existing_events.get('items'):
                print(f"⏭️  Event already exists: {event['summary']}")
                continue

            # Create the event
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