# Notion ↔ Google Calendar Sync

Automated sync from a Notion database into Google Calendar using **Python + GitHub Actions**.  
Works with all types of Notion date properties:
- All-day events (single day)
- All-day events (multi-day)
- Events with a start time (end = +1h by default)
- Events with start and end times

---

## Features
- Runs automatically every 15 minutes via **GitHub Actions**
- Secure credentials using **GitHub Secrets**
- Works for any **google calendar** 
- Designed for **free hosting**,  nothing else required

---

## Architecture Overview

```
┌────────────┐        ┌──────────────┐        ┌────────────────┐
│  Notion DB │ -----> │ GitHub Action│ -----> │ Google Calendar│
└────────────┘        │  (sync.py)   │        └────────────────┘
                      └──────────────┘

```

- **Notion DB** → Source of tasks/events
- **GitHub Actions** → Runs `sync.py` every 15 minutes
- **Google Calendar** → Receives automatically created events
- **Secrets** → Secure credentials (`NOTION_TOKEN`, `NOTION_DB_ID`, `GOOGLE_CREDENTIALS`, `CALENDAR_ID`)

---

## 🛠Setup Instructions

### 1. Clone this repository
```bash
git clone https://github.com/<your-username>/notion-gcal-sync.git
cd notion-gcal-sync
```

### 2. Notion Setup
1. Go to [Notion Integrations](https://www.notion.so/my-integrations).
2. Create a new integration (name: `CalendarSync`).
3. Copy the **integration token** (starts with `secret_...`).
4. Share your Notion **database** with this integration.
5. Copy the **database ID** (from the database URL, 32-character string).

### 3. Google Calendar Setup
1. Go to [Google Cloud Console](https://console.cloud.google.com/).
2. Create a new project (`notion-calendar-sync`).
3. Enable the **Google Calendar API**.
4. Create **Service Account credentials** and download JSON.
5. In [Google Calendar](https://calendar.google.com/):
    - Open **Settings and sharing**
    - Find the **Calendar ID** under *Integrate calendar*
    - Share calendar with your **Service Account email**

### 4. GitHub Secrets
Add the following secrets in your repo settings:

| Name               | Value                                          |
|--------------------|-----------------------------------------------|
| `NOTION_TOKEN`     | Notion integration token                     |
| `NOTION_DB_ID`     | Notion database ID (32 chars)                 |
| `GOOGLE_CREDENTIALS` | JSON content of service account credentials |
| `CALENDAR_ID`      | `primary` or full calendar ID                 |

---

## Logs and Debugging
To see workflow output:
1. Go to your GitHub repo → **Actions**
2. Click the recent run → expand the **Run sync** step
3. You’ll see logs like:
   ```
   🔄 Starting Notion → Google Calendar sync...
   📋 Found 10 Notion items
   ✅ Created event: Meeting with Client
   ⏭️  Skipping item without valid date
   🎉 Sync complete! Created 5 new events
   ```

---

## Future Roadmap
- Add **duplicate check** (prevent duplicate events when workflow reruns)
- Bi-directional sync (Google Calendar → Notion)
- Automatic updates when Notion entries change
- Richer logs (e.g. [All-day Event] vs [Timed Event])

---
