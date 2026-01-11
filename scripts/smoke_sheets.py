from __future__ import annotations

from datetime import datetime

from googleapiclient.discovery import build

from ytmusicrec.logging_setup import configure_logging
from ytmusicrec.settings import load_settings
from ytmusicrec.sheets import load_creds


def main() -> None:
    configure_logging()
    s = load_settings()
    if not s.google_sheets_spreadsheet_id:
        raise RuntimeError("GOOGLE_SHEETS_SPREADSHEET_ID not set")

    creds = load_creds(s.google_oauth_token_json)
    service = build("sheets", "v4", credentials=creds, cache_discovery=False)

    # Ensure History sheet exists
    meta = service.spreadsheets().get(spreadsheetId=s.google_sheets_spreadsheet_id).execute()
    existing = {sh["properties"]["title"] for sh in meta.get("sheets", [])}
    if "History" not in existing:
        service.spreadsheets().batchUpdate(
            spreadsheetId=s.google_sheets_spreadsheet_id,
            body={"requests": [{"addSheet": {"properties": {"title": "History"}}}]},
        ).execute()

    now = datetime.utcnow().isoformat() + "Z"
    service.spreadsheets().values().append(
        spreadsheetId=s.google_sheets_spreadsheet_id,
        range="History!A1",
        valueInputOption="RAW",
        insertDataOption="INSERT_ROWS",
        body={"values": [["smoke", now, "ok", "ytmusicrec", "sheets write ok"]]},
    ).execute()

    print("✅ Google Sheets smoke test OK (appended one row to History)")


if __name__ == "__main__":
    main()
