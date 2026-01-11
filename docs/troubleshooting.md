# Troubleshooting

## Airflow service names
Airflow 3 in this setup uses **airflow-apiserver** (not airflow-webserver).

Useful commands:
```bash
docker compose ps
docker compose logs -f airflow-scheduler
docker compose logs -f airflow-worker
```

## MSSQL: Error 18456 (Login failed)
Common causes:
- Mixed Mode auth not enabled
- SQL login disabled or wrong password
- You connected to the wrong instance/port

Verify from a container:
```bash
docker compose exec airflow-scheduler python /opt/ytmusicrec/scripts/smoke_mssql.py
```

## MSSQL: connection timeout from containers
- Confirm TCP/IP is enabled and a fixed port is set in SQL Server Configuration Manager.
- Confirm the port in airflow/.env matches.
- If Windows Firewall is enabled, add an inbound rule for the port.

## Ollama not reachable
- Ollama must be running on Windows and listening on port 11434.
- From a container:
```bash
docker compose exec airflow-scheduler python /opt/ytmusicrec/scripts/smoke_ollama.py
```

## Google Sheets write fails
- Ensure `secrets/google_token.json` exists and is mounted to `/run/secrets/google_token.json`.
- From a container:
```bash
docker compose exec airflow-scheduler python /opt/ytmusicrec/scripts/smoke_sheets.py
```

## Discord webhook fails
- Ensure DISCORD_WEBHOOK_URL is set in airflow/.env.
- From a container:
```bash
docker compose exec airflow-scheduler python /opt/ytmusicrec/scripts/smoke_discord.py
```
