# Notion ↔ Google Calendar Sync

Automated sync from a Notion database into Google Calendar using **Python + GitHub Actions**.  
Works with all types of Notion date properties:
- All-day events (single day)
- All-day events (multi-day)
- Events with a start time only (creates 0-duration events in Google Calendar)
- Events with start and end times

---

## Features
- Runs automatically every 6 hours via **GitHub Actions**
- Secure credentials using **GitHub Secrets**
- Works for any **google calendar** 
- Designed for **free hosting**, nothing else required
- Has **duplicate check** (prevent duplicate events when workflow reruns)
- **Bi-directional sync** (Google Calendar ↔ Notion)
  - Syncs title and date changes in both directions
  - Automatically detects and syncs changes from either source
- **Configurable property names** - Use any property names in your Notion database
- **Pagination support** - Handles databases with hundreds or thousands of items

---

## Architecture Overview

```
┌────────────┐         ┌──────────────┐         ┌────────────────┐
│  Notion DB │ <-----> │ GitHub Action│ <-----> │ Google Calendar│
└────────────┘         │  (sync.py)   │         └────────────────┘
                       └──────────────┘

```

- **Notion DB** → Source of tasks/events
- **GitHub Actions** → Runs `sync.py` every 6 hours
- **Google Calendar** → Receives automatically created events
- **Secrets** → Secure credentials (`NOTION_TOKEN`, `NOTION_DB_ID`, `GOOGLE_CREDENTIALS`, `CALENDAR_ID`, plus optional property name overrides)

---

## 🛠Setup Instructions

### 1. Fork and Clone this repository
1. Click the **Fork** button at the top-right of this repository
2. Clone your forked repository:
```bash
git clone https://github.com/<your-username>/notion-googlecalender-sync.git
cd notion-googlecalender-sync
```

> 💡 You need your own fork because GitHub Secrets are stored per-repository.

### 2. Notion Setup

#### Get your Integration Token (`NOTION_TOKEN`)
1. Go to [Notion Integrations](https://www.notion.so/my-integrations)
2. Click **+ New integration**
3. Give it a name (e.g., `CalendarSync`)
4. Select the workspace where your database lives
5. Click **Submit**
6. Copy the **Internal Integration Secret** (starts with `secret_...`) — this is your `NOTION_TOKEN`

#### Get your Database ID (`NOTION_DB_ID`)
1. Open your Notion database in the browser
2. Look at the URL: `https://www.notion.so/[DATABASE_ID]?v=...`
3. Copy the **32-character string** before `?v=` — this is your `NOTION_DB_ID`

#### Connect the Integration to your Database
1. Open your Notion database
2. Click **⋯** (three dots) in the top-right corner
3. Go to **Connections** → **Connect to** → Select your integration (`CalendarSync`)

#### Required Database Properties

Your Notion database **must** have these two properties:

| Property | Type   | Description                          |
|----------|--------|--------------------------------------|
| Title property | Title  | The event title (syncs to calendar)  |
| Date property | Date   | The event date/time                  |

> 💡 **Property names are configurable!** By default, the sync looks for properties named `Name` and `Date`. If your database uses different property names, you can configure them using GitHub Secrets (see step 4 below).

### 3. Google Calendar Setup

#### Create a Google Cloud Project
1. Go to [Google Cloud Console](https://console.cloud.google.com/)
2. Click the project dropdown (top-left) → **New Project**
3. Name it (e.g., `notion-calendar-sync`) → **Create**
4. Make sure your new project is selected

#### Enable the Google Calendar API
1. Go to **APIs & Services** → **Library**
2. Search for **Google Calendar API**
3. Click on it → **Enable**

#### Create Service Account Credentials (`GOOGLE_CREDENTIALS`)
1. Go to **APIs & Services** → **Credentials**
2. Click **+ Create Credentials** → **Service Account**
3. Give it a name (e.g., `calendar-sync`) → **Create and Continue**
4. Skip the optional steps → **Done**
5. Click on your newly created service account
6. Go to the **Keys** tab → **Add Key** → **Create new key**
7. Select **JSON** → **Create**
8. A JSON file will download — **the entire content of this file** is your `GOOGLE_CREDENTIALS`

> 💡 The JSON file also contains a `client_email` field — you'll need this email in the next step.

#### Get your Calendar ID (`CALENDAR_ID`)
1. Go to [Google Calendar](https://calendar.google.com/)
2. Hover over the calendar you want to sync → Click **⋮** → **Settings and sharing**
3. Scroll down to **Integrate calendar**
4. Copy the **Calendar ID** — this is your `CALENDAR_ID`
   - For your primary calendar, you can use `primary`
   - For other calendars, it looks like: `abc123xyz@group.calendar.google.com`

#### Share Calendar with Service Account
1. In the same **Settings and sharing** page, scroll to **Share with specific people or groups**
2. Click **+ Add people and groups**
3. Paste your **Service Account email** (the `client_email` from the JSON file)
4. Set permission to **Make changes to events**
5. Click **Send**

### 4. GitHub Secrets

Add the following secrets in your repo: **Settings** → **Secrets and variables** → **Actions** → **New repository secret**

#### Required Secrets

| Name                 | Value                                                    |
|----------------------|----------------------------------------------------------|
| `NOTION_TOKEN`       | Your Notion integration token (starts with `secret_...`) |
| `NOTION_DB_ID`       | Your Notion database ID (32-character string)            |
| `GOOGLE_CREDENTIALS` | The **entire JSON content** of the service account file  |
| `CALENDAR_ID`        | `primary` or your full calendar ID                       |

#### Optional Secrets (Property Names)

If your Notion database uses different property names than `Name` and `Date`, you can configure them:

| Name                    | Value                                    | Default |
|-------------------------|------------------------------------------|---------|
| `NOTION_TITLE_PROPERTY` | The name of your title property          | `Name`  |
| `NOTION_DATE_PROPERTY`  | The name of your date property           | `Date`  |

> 💡 **Example:** If your database uses `Event Name` and `Event Date` instead, set:
> - `NOTION_TITLE_PROPERTY` = `Event Name`
> - `NOTION_DATE_PROPERTY` = `Event Date`

---

## Logs and Debugging
To see workflow output:
1. Go to your GitHub repo → **Actions**
2. Click the recent run → expand the **Run sync** step
3. You’ll see logs like:
   ```
   🔄 Starting 2-Way Notion ↔ Google Calendar sync...
   📝 Using property names: Title='Name', Date='Date'
   📄 Fetched page 1 (100 items)...
   📄 Fetched page 2 (50 items)...
   📚 Pagination complete: fetched 2 pages, 150 total items
   📋 Found 150 Notion items
   🔄 Syncing Notion → Google Calendar...
   ✅ Created calendar event: Meeting with Client
   ⏭️ Skipping item without valid date
   🔄 Syncing Google Calendar → Notion...
   📝 Changes detected: start date: '2024-01-15' → '2024-01-20', end date: '2024-01-15' → '2024-01-20'
   🔄 Updated Notion page: Team Meeting
   🎉 2-Way Sync Complete!
   ```

---

## Future Roadmap

- Automatic updates when Notion entries change
- Richer logs (e.g. [All-day Event] vs [Timed Event])

---
