from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class Settings:
    # YouTube
    youtube_api_key: str
    region_code: str = "US"

    # Ollama
    ollama_base_url: str = "http://host.docker.internal:11434"
    ollama_model: str = "llama3.1:8b"

    # MSSQL
    mssql_host: str = "host.docker.internal"
    mssql_port: int = 14330
    mssql_db: str = "ytmusicrec"
    mssql_user: str = "ytmusicrec_app"
    mssql_password: str = ""
    mssql_encrypt: str = "yes"
    mssql_trust_server_cert: str = "yes"

    # Outputs
    discord_webhook_url: str | None = None
    google_sheets_spreadsheet_id: str | None = None

    # In-container paths
    google_oauth_client_json: str = "/run/secrets/google_oauth_client.json"
    google_oauth_token_json: str = "/run/secrets/google_token.json"
    host_desktop_mount: str = "/host_desktop"

    # Repo root inside container
    repo_root: Path = Path("/opt/ytmusicrec")

    dry_run: bool = False


def _env(name: str, default: str | None = None) -> str | None:
    v = os.getenv(name)
    if v is None or v == "":
        return default
    return v


def load_settings() -> Settings:
    youtube_api_key = _env("YOUTUBE_API_KEY")
    if not youtube_api_key or youtube_api_key == "placeholder":
        # allow local smoke tests to fail fast with clear message
        raise RuntimeError(
            "YOUTUBE_API_KEY is not set. Add it to airflow/.env (or your environment) before running."
        )

    return Settings(
        youtube_api_key=youtube_api_key,
        region_code=_env("REGION_CODE", "US") or "US",
        ollama_base_url=_env("OLLAMA_BASE_URL", "http://host.docker.internal:11434") or "http://host.docker.internal:11434",
        ollama_model=_env("OLLAMA_MODEL", "llama3.1:8b") or "llama3.1:8b",
        mssql_host=_env("MSSQL_HOST", "host.docker.internal") or "host.docker.internal",
        mssql_port=int(_env("MSSQL_PORT", "14330") or "14330"),
        mssql_db=_env("MSSQL_DB", "ytmusicrec") or "ytmusicrec",
        mssql_user=_env("MSSQL_USER", "ytmusicrec_app") or "ytmusicrec_app",
        mssql_password=_env("MSSQL_PASSWORD", "") or "",
        mssql_encrypt=_env("MSSQL_ENCRYPT", "yes") or "yes",
        mssql_trust_server_cert=_env("MSSQL_TRUST_SERVER_CERT", "yes") or "yes",
        discord_webhook_url=_env("DISCORD_WEBHOOK_URL"),
        google_sheets_spreadsheet_id=_env("GOOGLE_SHEETS_SPREADSHEET_ID"),
        google_oauth_client_json=_env("GOOGLE_OAUTH_CLIENT_JSON", "/run/secrets/google_oauth_client.json")
        or "/run/secrets/google_oauth_client.json",
        google_oauth_token_json=_env("GOOGLE_OAUTH_TOKEN_JSON", "/run/secrets/google_token.json")
        or "/run/secrets/google_token.json",
        host_desktop_mount=_env("HOST_DESKTOP_MOUNT", "/host_desktop") or "/host_desktop",
        repo_root=Path(_env("YTMUSICREC_REPO_ROOT", "/opt/ytmusicrec") or "/opt/ytmusicrec"),
        dry_run=(_env("YTMUSICREC_DRY_RUN", "false") or "false").lower() in {"1", "true", "yes"},
    )
