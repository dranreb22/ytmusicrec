# ytmusicrec architecture

## What it does
A daily Airflow DAG that:
1. Pulls recent YouTube videos for configurable search queries (YouTube Data API v3).
2. Scores "themes" (one theme per query bucket) using a trend heuristic.
3. Calls Ollama (llama3.1:8b) to generate **12 Suno prompts**.
4. Persists everything to host SQL Server Express (SQL Auth) and publishes to:
   - Discord webhook (message + attached markdown)
   - Local markdown file in repo (`output/`)
   - Local markdown file on Windows Desktop via a mounted volume
   - Google Sheets (Daily + History tabs)

## Containers
Airflow runs in Linux containers (Docker Desktop) with:
- `postgres` for Airflow metadata
- `redis` for Celery broker
- `airflow-apiserver`, `airflow-scheduler`, `airflow-worker`, `airflow-dag-processor`, `airflow-triggerer`

SQL Server is **not** containerized—Airflow connects to your **host** instance via:
- `host.docker.internal:${MSSQL_PORT}`
- ODBC Driver 18 (installed into the custom Airflow image)

## Data model (MSSQL)
- `dbo.Videos` — latest fetched stats per YouTube video id
- `dbo.Runs` — one row per pipeline run
- `dbo.DailyThemes` — top themes + scores per date
- `dbo.DailyPrompts` — prompts generated per date (tool = suno)

The schema is created automatically if missing (see `db/schema.sql`).
