from __future__ import annotations

import logging
from datetime import date, datetime
from typing import Any

from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request
from googleapiclient.discovery import build

log = logging.getLogger(__name__)

SCOPES = ["https://www.googleapis.com/auth/spreadsheets"]


def load_creds(token_json_path: str) -> Credentials:
    creds = Credentials.from_authorized_user_file(token_json_path, SCOPES)
    if creds.expired and creds.refresh_token:
        creds.refresh(Request())
    return creds


def _ensure_sheets(service, spreadsheet_id: str, names: list[str]) -> None:
    meta = service.spreadsheets().get(spreadsheetId=spreadsheet_id).execute()
    existing = {s["properties"]["title"] for s in meta.get("sheets", [])}
    requests_: list[dict[str, Any]] = []
    for name in names:
        if name not in existing:
            requests_.append({"addSheet": {"properties": {"title": name}}})
    if requests_:
        service.spreadsheets().batchUpdate(spreadsheetId=spreadsheet_id, body={"requests": requests_}).execute()


def write_daily(*, spreadsheet_id: str, token_json_path: str, run_date: date, themes: list[dict[str, Any]], suno: list[dict[str, Any]]) -> None:
    creds = load_creds(token_json_path)
    service = build("sheets", "v4", credentials=creds, cache_discovery=False)

    _ensure_sheets(service, spreadsheet_id, ["Daily", "History"])

    # Daily sheet layout: summary at top
    daily_values: list[list[Any]] = []
    daily_values.append(["Date", run_date.isoformat()])
    daily_values.append([])
    daily_values.append(["Top Themes", "Score"])
    for t in themes[:10]:
        daily_values.append([t["theme"], t["score"]])
    daily_values.append([])
    daily_values.append(["Suno Prompts", "Theme", "Tags"])
    for p in suno[:12]:
        daily_values.append([p.get("prompt"), p.get("theme"), ", ".join(p.get("tags") or [])])
    daily_values.append([])
    
    service.spreadsheets().values().update(
        spreadsheetId=spreadsheet_id,
        range="Daily!A1",
        valueInputOption="RAW",
        body={"values": daily_values},
    ).execute()

    # History append
    now = datetime.utcnow().isoformat() + "Z"
    hist_rows: list[list[Any]] = []
    for t in themes[:10]:
        hist_rows.append([run_date.isoformat(), now, "theme", t["theme"], t["score"]])
    for p in suno[:12]:
        hist_rows.append([run_date.isoformat(), now, "suno", p.get("theme"), p.get("prompt")])

    service.spreadsheets().values().append(
        spreadsheetId=spreadsheet_id,
        range="History!A1",
        valueInputOption="RAW",
        insertDataOption="INSERT_ROWS",
        body={"values": hist_rows},
    ).execute()
