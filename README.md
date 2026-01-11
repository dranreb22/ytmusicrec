# ytmusicrec
Daily YouTube-driven AI music prompt recommender.

- Orchestration: **Apache Airflow 3** (Docker Compose)
- Data: **YouTube Data API v3** (no scraping)
- LLM: **Ollama** on Windows host (model: `llama3.1:8b`)
- Datastore: **Host SQL Server Express** (SQL Auth)
- Outputs: Discord webhook + local markdown (repo + Desktop) + Google Sheets
- Quickstart Once Setup: run powershell script `runytmusic.ps1` on system start.

---

## License
This project is licensed under the **GNU Affero General Public License v3.0**.

---

## How it works (high level)

Each day, the system:

1. Pulls **recent YouTube videos** for configured search queries
2. Stores videos + engagement metrics in SQL Server
3. Scores themes based on **relative popularity & velocity**
4. Uses a **local LLM (Ollama)** to generate AI music prompts
5. Publishes outputs to:
   - Markdown files
   - Discord
   - Google Sheets

Airflow orchestrates this pipeline on a **daily schedule**.

---

## How “learning” works (important)

This project does **not train a model**.

Instead, it *learns* in a **data-driven way**:

- Every day’s videos are stored in SQL (`dbo.Videos`)
- Themes are re-scored daily based on:
  - View count
  - Like count
  - Comment count
  - Freshness window (`days_back`)
- The LLM receives **today’s top themes** as structured context

This creates **emergent adaptation**:
- Trends rise/fall naturally
- Prompts change as YouTube behavior changes
- No fine-tuning required

## Day-to-day tracking (how dates work)

- Each run is tied to a **run_date** (YYYY-MM-DD)
- Stored in:
  - `dbo.Runs`
  - `dbo.DailyThemes`
  - `dbo.DailyPrompts`
- Airflow provides the date automatically
- Manual runs still resolve a correct run_date

You can re-run a day safely:
- Videos are upserted
- Themes are merged
- Prompts are deleted + regenerated for that date

Download and install: https://ollama.com
From PowerShell:
- ollama serve
- ollama pull llama3.1:8b


## Setup

### 1) Put this repo at
`C:\Users\YOURNAME\.ytmusicrec`  (or any path, but this guide assumes that)

### 2) Required files you already have
These must exist on the **host**:
- `secrets/google_oauth_client.json`
- `secrets/google_token.json`

> These are OAuth Desktop-client tokens. This project **does not** use service accounts.

### 3) Create Airflow env file
In `airflow/`:
1. Copy `airflow/.env.example` -> `airflow/.env`
2. Open `airflow/.env` and set:
   - `YOUTUBE_API_KEY`
   - `MSSQL_PORT` (your fixed TCP port)
   - `MSSQL_USER` / `MSSQL_PASSWORD` (SQL Auth)
   - `DISCORD_WEBHOOK_URL` (optional)
   - `WINDOWS_DESKTOP_PATH` e.g. `C:\Users\YOURUSER\Desktop`

### 4) Start Airflow
From **PowerShell**:
```powershell
cd C:\Users\berna\.ytmusicrec\airflow
docker compose up -d --build
if "ERROR [airflow-apiserver] exporting to image"
- docker compose down --remove-orphans
- $env:COMPOSE_BAKE="false"
- docker compose build
- docker compose up -d
- docker compose ps

if you need to delete existing image
- docker image rm -f ytmusicrec-airflow:3.1.5-msodbc18
in between remove orphans and compose bake

```

Then open Airflow UI:
- `http://localhost:8080`
- User: `airflow`
- Password: `airflow`

### 5) Unpause and run the DAG
In the Airflow UI:
1. Go to **DAGs**
2. Find **`ytmusicrec_daily`**
3. Toggle it **ON** (unpause)
4. Click the **Play ▶** button → **Trigger DAG**

Scheduled run: **daily at 9:00 AM America/New_York**.

## What you get each day
- `output/YYYY-MM-DD_prompts.md` in the repo
- `C:\Users\berna\Desktop\ytmusicrec\YYYY-MM-DD_prompts.md` on your Windows Desktop (via `/host_desktop` mount)
- One Discord webhook post (message + attached markdown)
- Google Sheet updated:
  - Tab **Daily** overwritten with latest
  - Tab **History** appended with a log

## Config
### YouTube queries
Edit `config/queries.yaml`.

- Keep `max_results_per_query` small (25–50) to stay quota-friendly.
- Each query becomes a “theme bucket” (scored by velocity + engagement).

### Prompt generation
Edit `config/prompt_templates.yaml`.

- Suno prompts are short + structured.

## Smoke tests (run inside containers)
From PowerShell:
```powershell
cd C:\Users\berna\.ytmusicrec\airflow

# MSSQL connectivity + schema
docker compose exec airflow-scheduler python /opt/ytmusicrec/scripts/smoke_mssql.py

# YouTube API key
docker compose exec airflow-scheduler python /opt/ytmusicrec/scripts/smoke_youtube.py

# Ollama connectivity
docker compose exec airflow-scheduler python /opt/ytmusicrec/scripts/smoke_ollama.py

# Google Sheets write
docker compose exec airflow-scheduler python /opt/ytmusicrec/scripts/smoke_sheets.py

# Discord webhook post
docker compose exec airflow-scheduler python /opt/ytmusicrec/scripts/smoke_discord.py
```

## Airflow CLI notes (Airflow 3)
- There is **no** `airflow-webserver` service in this compose. It’s `airflow-apiserver`.
- Some CLI flags changed vs Airflow 2. These work:

```bash
docker compose exec airflow-scheduler airflow dags list
docker compose exec airflow-scheduler airflow dags list-runs ytmusicrec_daily
```

For task logs, use the UI, or:
```bash
docker compose logs -f airflow-worker
```

## Project layout
- `airflow/` — Docker Compose + custom Airflow image
- `airflow/dags/ytmusicrec_daily.py` — DAG definition
- `ytmusicrec/` — python package used by DAG tasks
- `config/` — YouTube query config + prompt templates
- `db/schema.sql` — idempotent SQL schema
- `output/` — markdown + CSV outputs
- `scripts/` — smoke tests + OAuth helper

## Security
- Do **not** commit secrets.
- `.gitignore` excludes:
  - `secrets/`
  - `airflow/.env`
  - OAuth token files

## Troubleshooting
See `docs/troubleshooting.md`. 


