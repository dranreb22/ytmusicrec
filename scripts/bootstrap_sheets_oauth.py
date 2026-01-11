from __future__ import annotations

from pathlib import Path

from google_auth_oauthlib.flow import InstalledAppFlow
from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request

SCOPES = ["https://www.googleapis.com/auth/spreadsheets"]

ROOT = Path(__file__).resolve().parents[1]
SECRETS = ROOT / "secrets"
CLIENT_JSON = SECRETS / "google_oauth_client.json"
TOKEN_JSON = SECRETS / "google_token.json"


def main() -> None:
    if not CLIENT_JSON.exists():
        raise FileNotFoundError(
            f"Missing OAuth client JSON: {CLIENT_JSON}\n"
            "Download your OAuth Desktop client JSON from Google Cloud and save it to that path."
        )

    creds: Credentials | None = None

    if TOKEN_JSON.exists():
        creds = Credentials.from_authorized_user_file(str(TOKEN_JSON), SCOPES)

    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file(str(CLIENT_JSON), SCOPES)
            creds = flow.run_local_server(port=0)

        TOKEN_JSON.write_text(creds.to_json(), encoding="utf-8")

    print("✅ OAuth complete.")
    print(f"Client: {CLIENT_JSON}")
    print(f"Token saved to: {TOKEN_JSON}")


if __name__ == "__main__":
    main()
