import requests
import json
import os
import sys
from datetime import datetime, timedelta
from google.oauth2 import service_account
from googleapiclient.discovery import build

# Environment variables (from GitHub Secrets)
NOTION_TOKEN = os.getenv('NOTION_TOKEN')
NOTION_DB_ID = os.getenv('NOTION_DB_ID')
GOOGLE_CREDENTIALS_JSON = os.getenv('GOOGLE_CREDENTIALS')
CALENDAR_ID = os.getenv('CALENDAR_ID', 'primary')
# Configurable property names (optional, defaults to 'Name' and 'Date' for backward compatibility)
NOTION_TITLE_PROPERTY = os.getenv('NOTION_TITLE_PROPERTY', 'Name')
NOTION_DATE_PROPERTY = os.getenv('NOTION_DATE_PROPERTY', 'Date')


def validate_env():
    """Validate required environment variables are present and non-empty."""
    missing = []
    if not NOTION_TOKEN:
        missing.append('NOTION_TOKEN')
    if not NOTION_DB_ID:
        missing.append('NOTION_DB_ID')
    if not GOOGLE_CREDENTIALS_JSON:
        missing.append('GOOGLE_CREDENTIALS')
    if not CALENDAR_ID:
        missing.append('CALENDAR_ID')

    if missing:
        print(f"❌ Missing required environment variables: {', '.join(missing)}")
        print("Ensure GitHub Secrets are configured for these names.")
        sys.exit(1)


def get_google_calendar_service():
    """Initialize the Google Calendar API service"""
    try:
        credentials_info = json.loads(GOOGLE_CREDENTIALS_JSON)
    except Exception as e:
        raise RuntimeError(f"Failed to parse GOOGLE_CREDENTIALS JSON: {e}")

    try:
        credentials = service_account.Credentials.from_service_account_info(
            credentials_info,
            scopes=['https://www.googleapis.com/auth/calendar']
        )
        return build('calendar', 'v3', credentials=credentials)
    except Exception as e:
        raise RuntimeError(f"Failed to initialize Google Calendar client: {e}")


def get_notion_items():
    """Fetch all items from the Notion database (handles pagination)"""
    headers = {
        'Authorization': f'Bearer {NOTION_TOKEN}',
        'Notion-Version': '2022-06-28',
        'Content-Type': 'application/json'
    }

    all_items = []
    next_cursor = None
    page_count = 0

    while True:
        page_count += 1
        # Build request body with pagination cursor if available
        request_body = {}
        if next_cursor:
            request_body['start_cursor'] = next_cursor

        response = requests.post(
            f'https://api.notion.com/v1/databases/{NOTION_DB_ID}/query',
            headers=headers,
            json=request_body
        )

        if response.status_code != 200:
            print(f"❌ Error fetching Notion data: {response.status_code}")
            print(response.text)
            # Return what we have so far, or empty list if first page failed
            if page_count == 1:
                return []
            break

        data = response.json()
        page_items = data.get('results', [])
        all_items.extend(page_items)

        # Check if there are more pages
        has_more = data.get('has_more', False)
        next_cursor = data.get('next_cursor')

        if not has_more or not next_cursor:
            break

        print(f"📄 Fetched page {page_count} ({len(page_items)} items)...")

    if page_count > 1:
        print(f"📚 Pagination complete: fetched {page_count} pages, {len(all_items)} total items")
    
    return all_items


def update_notion_page(page_id, title, start_date, end_date=None):
    """Update a Notion page with new title and date"""
    headers = {
        'Authorization': f'Bearer {NOTION_TOKEN}',
        'Notion-Version': '2022-06-28',
        'Content-Type': 'application/json'
    }

    # Build the date property
    date_property = {'start': start_date}
    if end_date and end_date != start_date:
        date_property['end'] = end_date

    data = {
        'properties': {
            NOTION_TITLE_PROPERTY: {
                'title': [{'text': {'content': title}}]
            },
            NOTION_DATE_PROPERTY: {
                'date': date_property
            }
        }
    }

    response = requests.patch(
        f'https://api.notion.com/v1/pages/{page_id}',
        headers=headers,
        json=data
    )
    return response.status_code == 200


def create_notion_page(title, start_date, end_date=None, gcal_event_id=None):
    """Create a new Notion page"""
    headers = {
        'Authorization': f'Bearer {NOTION_TOKEN}',
        'Notion-Version': '2022-06-28',
        'Content-Type': 'application/json'
    }

    # Build the date property
    date_property = {'start': start_date}
    if end_date and end_date != start_date:
        date_property['end'] = end_date

    data = {
        'parent': {'database_id': NOTION_DB_ID},
        'properties': {
            NOTION_TITLE_PROPERTY: {
                'title': [{'text': {'content': title}}]
            },
            NOTION_DATE_PROPERTY: {
                'date': date_property
            }
        }
    }

    response = requests.post(
        'https://api.notion.com/v1/pages',
        headers=headers,
        json=data
    )

    if response.status_code == 200:
        return response.json()['id']
    return None


def delete_notion_page(page_id):
    """Delete (archive) a Notion page"""
    headers = {
        'Authorization': f'Bearer {NOTION_TOKEN}',
        'Notion-Version': '2022-06-28',
        'Content-Type': 'application/json'
    }

    data = {'archived': True}
    response = requests.patch(
        f'https://api.notion.com/v1/pages/{page_id}',
        headers=headers,
        json=data
    )
    return response.status_code == 200


def gcal_event_to_notion_date(gcal_event):
    """Convert Google Calendar event to Notion date format"""
    start = gcal_event.get('start', {})
    end = gcal_event.get('end', {})

    # All-day event
    if 'date' in start:
        start_date = start['date']
        end_date = end.get('date')
        # Google Calendar end dates are exclusive, so subtract 1 day
        if end_date:
            end_dt = datetime.strptime(end_date, "%Y-%m-%d") - timedelta(days=1)
            end_date = end_dt.strftime("%Y-%m-%d")
            if end_date == start_date:
                end_date = None
        return start_date, end_date

    # Timed event
    elif 'dateTime' in start:
        start_datetime = start['dateTime']
        end_datetime = end.get('dateTime')
        return start_datetime, end_datetime

    return None, None


def notion_item_to_date(notion_item):
    """Extract date values from a Notion item"""
    properties = notion_item.get('properties', {})
    
    if NOTION_DATE_PROPERTY in properties:
        date_prop = properties[NOTION_DATE_PROPERTY]
        if date_prop['type'] == 'date' and date_prop['date']:
            start_date = date_prop['date']['start']
            end_date = date_prop['date'].get('end')
            return start_date, end_date
    
    return None, None


def notion_to_calendar_event(notion_item):
    """Convert a Notion item to a Google Calendar event"""
    properties = notion_item.get('properties', {})

    # Extract title
    title = "Untitled Event"
    if NOTION_TITLE_PROPERTY in properties:
        title_prop = properties[NOTION_TITLE_PROPERTY]
        if title_prop['type'] == 'title' and title_prop['title']:
            title = title_prop['title'][0]['plain_text']

    # Extract date(s)
    start_time = None
    end_time = None
    is_all_day = False

    if NOTION_DATE_PROPERTY in properties:
        date_prop = properties[NOTION_DATE_PROPERTY]
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
            # If only a start time exists, set end = start (0-duration event)
            # This preserves the "start time only" behavior from Notion
            end_time = start_time

        event['start'] = {'dateTime': start_time}
        event['end'] = {'dateTime': end_time}

    return event


def sync_notion_to_calendar(service, notion_items, notion_ids):
    """Sync Notion → Google Calendar"""
    print("🔄 Syncing Notion → Google Calendar...")

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
                print(f"🔄 Updated calendar event: {event['summary']}")
                updated_count += 1
            else:
                # Create
                service.events().insert(
                    calendarId=CALENDAR_ID,
                    body=event
                ).execute()
                print(f"✅ Created calendar event: {event['summary']}")
                created_count += 1

        except Exception as e:
            print(f"❌ Error syncing item to calendar: {e}")
            continue

    # --- DELETE EVENTS NO LONGER IN NOTION ---
    try:
        print("🔍 Checking for calendar events to delete...")

        # Get all events from the calendar (we'll filter manually)
        gcal_events = service.events().list(
            calendarId=CALENDAR_ID,
            maxResults=2500
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
                print(f"🗑️ Deleted calendar event: {g_event.get('summary', 'Untitled')}")
                deleted_count += 1

    except Exception as e:
        print(f"❌ Error during calendar deletion sync: {e}")

    return created_count, updated_count, skipped_count, deleted_count


def sync_calendar_to_notion(service, notion_items):
    """Sync Google Calendar → Notion"""
    print("🔄 Syncing Google Calendar → Notion...")

    created_count = 0
    updated_count = 0
    deleted_count = 0

    # Build a map of notion_id → notion_item for quick lookup
    notion_map = {item['id']: item for item in notion_items}

    try:
        # Get all calendar events
        gcal_events = service.events().list(
            calendarId=CALENDAR_ID,
            maxResults=2500
        ).execute().get('items', [])

        # Process events that were synced from Notion (have notion_id)
        for gcal_event in gcal_events:
            extended_props = gcal_event.get('extendedProperties', {}).get('private', {})
            notion_id = extended_props.get('notion_id')

            if not notion_id:
                # This is a new event created directly in Google Calendar
                # Create a new Notion page for it
                title = gcal_event.get('summary', 'Untitled Event')
                start_date, end_date = gcal_event_to_notion_date(gcal_event)

                if start_date:
                    new_notion_id = create_notion_page(title, start_date, end_date)
                    if new_notion_id:
                        # Update the calendar event to include the notion_id
                        gcal_event['extendedProperties'] = {
                            'private': {'notion_id': new_notion_id}
                        }
                        service.events().update(
                            calendarId=CALENDAR_ID,
                            eventId=gcal_event['id'],
                            body=gcal_event
                        ).execute()
                        print(f"✅ Created Notion page from calendar event: {title}")
                        created_count += 1
                continue

            # Check if the corresponding Notion page still exists
            if notion_id not in notion_map:
                # Notion page was deleted, but calendar event still exists
                # Delete the calendar event
                service.events().delete(
                    calendarId=CALENDAR_ID,
                    eventId=gcal_event['id']
                ).execute()
                print(f"🗑️ Deleted calendar event (Notion page gone): {gcal_event.get('summary')}")
                continue

            # Compare calendar event with Notion page and update if needed
            notion_item = notion_map[notion_id]

            # Get current values from Notion
            notion_title = "Untitled Event"
            if NOTION_TITLE_PROPERTY in notion_item['properties']:
                title_prop = notion_item['properties'][NOTION_TITLE_PROPERTY]
                if title_prop['type'] == 'title' and title_prop['title']:
                    notion_title = title_prop['title'][0]['plain_text']

            notion_start, notion_end = notion_item_to_date(notion_item)

            # Get calendar event values
            gcal_title = gcal_event.get('summary', 'Untitled Event')
            gcal_start, gcal_end = gcal_event_to_notion_date(gcal_event)

            # Check if we need to update Notion (compare both title and dates)
            needs_update = False
            changes = []

            # Compare title
            if gcal_title != notion_title:
                needs_update = True
                changes.append(f"title: '{notion_title}' → '{gcal_title}'")

            # Compare start date - normalize None to empty string for comparison
            notion_start_normalized = notion_start or ""
            gcal_start_normalized = gcal_start or ""
            if gcal_start_normalized != notion_start_normalized:
                needs_update = True
                changes.append(f"start date: '{notion_start or '(none)'}' → '{gcal_start or '(none)'}'")

            # Compare end date - normalize None to empty string for comparison
            notion_end_normalized = notion_end or ""
            gcal_end_normalized = gcal_end or ""
            if gcal_end_normalized != notion_end_normalized:
                needs_update = True
                changes.append(f"end date: '{notion_end or '(none)'}' → '{gcal_end or '(none)'}'")

            if needs_update and gcal_start:
                change_desc = ", ".join(changes)
                print(f"📝 Changes detected: {change_desc}")
                if update_notion_page(notion_id, gcal_title, gcal_start, gcal_end):
                    print(f"🔄 Updated Notion page: {gcal_title}")
                    updated_count += 1

    except Exception as e:
        print(f"❌ Error during calendar to Notion sync: {e}")

    return created_count, updated_count, deleted_count


def main():
    """Main sync function - handles both directions"""
    print("🔄 Starting 2-Way Notion ↔ Google Calendar sync...")
    print(f"📝 Using property names: Title='{NOTION_TITLE_PROPERTY}', Date='{NOTION_DATE_PROPERTY}'")

    # Validate configuration early to fail fast with clear error
    validate_env()

    notion_items = get_notion_items()
    print(f"📋 Found {len(notion_items)} Notion items")

    notion_ids = set(item['id'] for item in notion_items)

    try:
        service = get_google_calendar_service()
        print("🔗 Connected to Google Calendar")
    except Exception as e:
        print(f"❌ Failed to connect to Google Calendar: {e}")
        return

    # Sync Notion → Google Calendar
    n2c_created, n2c_updated, n2c_skipped, n2c_deleted = sync_notion_to_calendar(
        service, notion_items, notion_ids
    )

    # Sync Google Calendar → Notion
    c2n_created, c2n_updated, c2n_deleted = sync_calendar_to_notion(
        service, notion_items
    )

    print(f"""
🎉 2-Way Sync Complete!

Notion → Calendar:
  Created: {n2c_created}
  Updated: {n2c_updated}
  Skipped: {n2c_skipped}
  Deleted: {n2c_deleted}

Calendar → Notion:
  Created: {c2n_created}
  Updated: {c2n_updated}
  Deleted: {c2n_deleted}
""")


if __name__ == "__main__":
    main()