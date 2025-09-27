import requests
import json
import os
from datetime import datetime, timedelta
from google.oauth2 import service_account
from googleapiclient.discovery import build

# Environment variables (from GitHub Secrets)
NOTION_TOKEN = os.getenv('NOTION_TOKEN')
NOTION_DB_ID = os.getenv('NOTION_DB_ID')
GOOGLE_CREDENTIALS_JSON = os.getenv('GOOGLE_CREDENTIALS')
CALENDAR_ID = os.getenv('CALENDAR_ID', 'primary')


def get_google_calendar_service():
    """Initialize the Google Calendar API service"""
    credentials_info = json.loads(GOOGLE_CREDENTIALS_JSON)
    credentials = service_account.Credentials.from_service_account_info(
        credentials_info,
        scopes=['https://www.googleapis.com/auth/calendar']
    )
    return build('calendar', 'v3', credentials=credentials)


def get_notion_items():
    """Fetch items from the Notion database"""
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
    """Convert a Notion item to a Google Calendar event"""
    properties = notion_item.get('properties', {})

    # Extract title
    title = "Untitled Event"
    if 'Name' in properties:
        title_prop = properties['Name']
        if title_prop['type'] == 'title' and title_prop['title']:
            title = title_prop['title'][0]['plain_text']

    # Extract date(s)
    start_time = None
    end_time = None
    is_all_day = False

    if 'Date' in properties:
        date_prop = properties['Date']
        if date_prop['type'] == 'date' and date_prop['date']:
            start_time = date_prop['date']['start']
            end_time = date_prop['date'].get('end')

            # Case: all-day (format = YYYY-MM-DD)
            if len(start_time) == 10:
                is_all_day = True
                if not end_time:
                    # if no end date → set end = start + 1 day
                    end_date = datetime.strptime(start_time, "%Y-%m-%d") + timedelta(days=1)
                    end_time = end_date.strftime("%Y-%m-%d")

    if not start_time:
        return None

    # Build calendar event
    event = {
        'summary': title,
        'description': f"Synced from Notion: {notion_item['url']}",
    }

    if is_all_day:
        event['start'] = {'date': start_time}
        event['end'] = {'date': end_time}
    else:
        # Case: has time
        if not end_time:
            # If only a start time exists, set end = start + 1 hour
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
    print("🔄 Starting Notion ↔ Google Calendar sync...")

    notion_items = get_notion_items()
    print(f"📋 Found {len(notion_items)} Notion items")

    notion_ids = set(item['id'] for item in notion_items)

    if not notion_items:
        print("⚠️ No Notion items found, nothing to sync.")
        return

    try:
        service = get_google_calendar_service()
        print("🔗 Connected to Google Calendar")
    except Exception as e:
        print(f"❌ Failed to connect to Google Calendar: {e}")
        return

    created_count = 0
    updated_count = 0
    skipped_count = 0
    deleted_count = 0

    # --- CREATE or UPDATE ---
    for item in notion_items:
        try:
            event = notion_to_calendar_event(item)
            if not event:
                print("⏭️ Skipping item without valid date")
                skipped_count += 1
                continue

            notion_id = item['id']
            # Always attach the Notion ID
            event['extendedProperties'] = {'private': {'notion_id': notion_id}}

            # Look for existing event
            existing = service.events().list(
                calendarId=CALENDAR_ID,
                privateExtendedProperty=f"notion_id={notion_id}"
            ).execute().get('items', [])

            if existing:
                # Update
                existing_event_id = existing[0]['id']
                service.events().update(
                    calendarId=CALENDAR_ID,
                    eventId=existing_event_id,
                    body=event
                ).execute()
                print(f"🔄 Updated event: {event['summary']}")
                updated_count += 1
            else:
                # Create
                service.events().insert(
                    calendarId=CALENDAR_ID,
                    body=event
                ).execute()
                print(f"✅ Created event: {event['summary']}")
                created_count += 1

        except Exception as e:
            print(f"❌ Error syncing item: {e}")
            continue

    # --- DELETE EVENTS NO LONGER IN NOTION ---


try:
    print("🔍 Checking for events to delete...")

    # Get all events from the calendar (we'll filter manually)
    gcal_events = service.events().list(
        calendarId=CALENDAR_ID,
        maxResults=2500  # Adjust if you have more events
    ).execute().get('items', [])

    # Filter for events that have our notion_id extended property
    synced_events = []
    for event in gcal_events:
        extended_props = event.get('extendedProperties', {}).get('private', {})
        if 'notion_id' in extended_props:
            synced_events.append(event)

    print(f"🔍 Found {len(synced_events)} previously synced events")

    # Delete events whose notion_id is no longer in our Notion DB
    for g_event in synced_events:
        notion_id = g_event['extendedProperties']['private']['notion_id']
        if notion_id not in notion_ids:
            service.events().delete(
                calendarId=CALENDAR_ID,
                eventId=g_event['id']
            ).execute()
            print(f"🗑️ Deleted event (no longer in Notion): {g_event.get('summary', 'Untitled')}")
            deleted_count += 1

except Exception as e:
    print(f"❌ Error during deletion sync: {e}")

    print(f"""
    🎉 Sync complete!
    Created: {created_count}
    Updated: {updated_count}
    Skipped: {skipped_count}
    Deleted: {deleted_count}
    """)

if __name__ == "__main__":
    sync_notion_to_calendar()