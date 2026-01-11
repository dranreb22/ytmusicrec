from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime, date
from pathlib import Path
from typing import Iterable, Any

import json
import pyodbc

from ytmusicrec.settings import Settings

log = logging.getLogger(__name__)


def _conn_str(s: Settings) -> str:
    # ODBC Driver 18 enforces encryption by default; we mirror your SSMS settings.
    driver = "ODBC Driver 18 for SQL Server"
    server = f"{s.mssql_host},{s.mssql_port}"
    return (
        f"DRIVER={{{driver}}};"
        f"SERVER={server};"
        f"DATABASE={s.mssql_db};"
        f"UID={s.mssql_user};"
        f"PWD={s.mssql_password};"
        f"Encrypt={s.mssql_encrypt};"
        f"TrustServerCertificate={s.mssql_trust_server_cert};"
        "Connection Timeout=30;"
    )


def connect(s: Settings) -> pyodbc.Connection:
    return pyodbc.connect(_conn_str(s), autocommit=False)


def ensure_schema(conn: pyodbc.Connection) -> None:
    """Create required tables if they do not exist (idempotent)."""
    sql = Path(__file__).resolve().parents[1] / "db" / "schema.sql"
    if not sql.exists():
        # fallback: schema file lives at repo_root/db/schema.sql
        sql = Path("/opt/ytmusicrec/db/schema.sql")
    ddl = sql.read_text(encoding="utf-8")
    cur = conn.cursor()
    cur.execute(ddl)
    conn.commit()


@dataclass
class RunInfo:
    run_id: int
    run_date: date
    region_code: str


def update_run_video_count(conn: pyodbc.Connection, run_id: int, video_count: int) -> None:
    cur = conn.cursor()
    cur.execute("UPDATE dbo.Runs SET video_count=? WHERE run_id=?", video_count, run_id)
    conn.commit()


def upsert_videos(conn: pyodbc.Connection, rows: Iterable[dict[str, Any]]) -> int:
    """Upsert video rows into dbo.Videos. Returns number of processed rows."""
    rows_list = list(rows)
    if not rows_list:
        return 0

    cur = conn.cursor()

    # Use a temp table + MERGE for performance and idempotency.
    cur.execute(
        """
        IF OBJECT_ID('tempdb..#VideosStage') IS NOT NULL DROP TABLE #VideosStage;
        CREATE TABLE #VideosStage (
            video_id NVARCHAR(32) NOT NULL,
            query NVARCHAR(200) NULL,
            title NVARCHAR(400) NULL,
            description NVARCHAR(MAX) NULL,
            channel_title NVARCHAR(200) NULL,
            published_at DATETIME2 NULL,
            view_count BIGINT NULL,
            like_count BIGINT NULL,
            comment_count BIGINT NULL,
            fetched_at DATETIME2 NOT NULL
        );
        """
    )

    insert_sql = (
        "INSERT INTO #VideosStage (video_id, query, title, description, channel_title, published_at, view_count, like_count, comment_count, fetched_at) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)"
    )

    for r in rows_list:
        cur.execute(
            insert_sql,
            r["video_id"],
            r.get("query"),
            r.get("title"),
            r.get("description"),
            r.get("channel_title"),
            r.get("published_at"),
            r.get("view_count"),
            r.get("like_count"),
            r.get("comment_count"),
            r.get("fetched_at"),
        )

    cur.execute(
        """
        MERGE dbo.Videos AS tgt
        USING #VideosStage AS src
            ON tgt.video_id = src.video_id
        WHEN MATCHED THEN
            UPDATE SET
                tgt.query = src.query,
                tgt.title = src.title,
                tgt.description = src.description,
                tgt.channel_title = src.channel_title,
                tgt.published_at = src.published_at,
                tgt.view_count = src.view_count,
                tgt.like_count = src.like_count,
                tgt.comment_count = src.comment_count,
                tgt.fetched_at = src.fetched_at
        WHEN NOT MATCHED THEN
            INSERT (video_id, query, title, description, channel_title, published_at, view_count, like_count, comment_count, fetched_at)
            VALUES (src.video_id, src.query, src.title, src.description, src.channel_title, src.published_at, src.view_count, src.like_count, src.comment_count, src.fetched_at);
        """
    )

    conn.commit()
    return len(rows_list)


def write_daily_themes(conn: pyodbc.Connection, run_date_: date, themes: list[dict[str, Any]]) -> None:
    cur = conn.cursor()

    cur.execute(
        """
        IF OBJECT_ID('tempdb..#ThemesStage') IS NOT NULL DROP TABLE #ThemesStage;
        CREATE TABLE #ThemesStage (
            run_date DATE NOT NULL,
            theme NVARCHAR(200) NOT NULL,
            score FLOAT NOT NULL,
            examples_json NVARCHAR(MAX) NULL
        );
        """
    )

    ins = "INSERT INTO #ThemesStage (run_date, theme, score, examples_json) VALUES (?, ?, ?, ?)"
    for t in themes:
        cur.execute(ins, run_date_, t["theme"], float(t["score"]), t.get("examples_json"))

    cur.execute(
        """
        MERGE dbo.DailyThemes AS tgt
        USING #ThemesStage AS src
          ON tgt.run_date = src.run_date AND tgt.theme = src.theme
        WHEN MATCHED THEN
          UPDATE SET tgt.score = src.score, tgt.examples_json = src.examples_json
        WHEN NOT MATCHED THEN
          INSERT (run_date, theme, score, examples_json)
          VALUES (src.run_date, src.theme, src.score, src.examples_json);
        """
    )

    conn.commit()


def fetch_videos_for_date(conn: pyodbc.Connection, run_date_: date) -> list[dict[str, Any]]:
    cur = conn.cursor()
    cur.execute(
        """
        SELECT video_id, query, title, description, channel_title, published_at, view_count, like_count, comment_count, fetched_at
        FROM dbo.Videos
        WHERE CAST(fetched_at AS date) = ?
        """,
        run_date_,
    )

    cols = [c[0] for c in cur.description]
    out: list[dict[str, Any]] = []
    for row in cur.fetchall():
        out.append({cols[i]: row[i] for i in range(len(cols))})
    return out

def create_run(conn: pyodbc.Connection, run_date_: date, region_code: str, query_count: int) -> RunInfo:
    """
    Idempotent: returns existing run for (run_date, region_code) if it exists,
    otherwise creates one.
    """
    cur = conn.cursor()
    cur.execute(
        """
        SELECT TOP 1 run_id
        FROM dbo.Runs
        WHERE run_date = ? AND region_code = ?
        ORDER BY created_at DESC;
        """,
        run_date_,
        region_code,
    )
    row = cur.fetchone()
    if row:
        run_id = int(row[0])
        # Keep metadata fresh
        cur.execute(
            "UPDATE dbo.Runs SET query_count = ? WHERE run_id = ?",
            query_count,
            run_id,
        )
        conn.commit()
        return RunInfo(run_id=run_id, run_date=run_date_, region_code=region_code)

    cur.execute(
        """
        INSERT INTO dbo.Runs (run_date, region_code, query_count, video_count)
        OUTPUT INSERTED.run_id
        VALUES (?, ?, ?, 0);
        """,
        run_date_,
        region_code,
        query_count,
    )
    run_id = int(cur.fetchone()[0])
    conn.commit()
    return RunInfo(run_id=run_id, run_date=run_date_, region_code=region_code)

def write_daily_prompts(conn: pyodbc.Connection, run_date_: date, prompts: list[dict[str, Any]]) -> None:
    cur = conn.cursor()

    # idempotent: remove prior run_date prompts then re-insert
    cur.execute("DELETE FROM dbo.DailyPrompts WHERE run_date = ?", run_date_)

    # de-dupe within this run to avoid violating UX_DailyPrompts_Unique
    seen: set[tuple[str, str]] = set()
    deduped: list[dict[str, Any]] = []
    for p in prompts:
        tool = (p.get("tool") or "").strip()
        prompt = (p.get("prompt") or "").strip()
        k = (tool, prompt)
        if not tool or not prompt:
            continue
        if k in seen:
            continue
        seen.add(k)
        p["tool"] = tool
        p["prompt"] = prompt
        deduped.append(p)

    prompts = deduped


    ins = "INSERT INTO dbo.DailyPrompts (run_date, tool, prompt, theme_tags) VALUES (?, ?, ?, ?)"
    for p in prompts:
        cur.execute(ins, run_date_, p["tool"], p["prompt"], p.get("theme_tags"))
    conn.commit()


def get_cached_video_ids(conn: pyodbc.Connection, run_date_: date, region_code: str, query_name: str) -> list[str] | None:
    cur = conn.cursor()
    cur.execute(
        """
        SELECT video_ids_json
        FROM dbo.QueryCache
        WHERE run_date = ? AND region_code = ? AND query_name = ?
        """,
        run_date_, region_code, query_name
    )
    row = cur.fetchone()
    if not row:
        return None
    return json.loads(row[0])

def set_cached_video_ids(conn: pyodbc.Connection, run_date_: date, region_code: str, query_name: str, q: str, ids: list[str], fetched_at: datetime) -> None:
    cur = conn.cursor()
    cur.execute(
        """
        MERGE dbo.QueryCache AS tgt
        USING (SELECT ? AS run_date, ? AS region_code, ? AS query_name) AS src
          ON tgt.run_date = src.run_date AND tgt.region_code = src.region_code AND tgt.query_name = src.query_name
        WHEN MATCHED THEN UPDATE SET
          tgt.q = ?, tgt.video_ids_json = ?, tgt.fetched_at = ?
        WHEN NOT MATCHED THEN INSERT (run_date, region_code, query_name, q, video_ids_json, fetched_at)
          VALUES (?, ?, ?, ?, ?, ?);
        """,
        run_date_, region_code, query_name,
        q, json.dumps(ids), fetched_at,
        run_date_, region_code, query_name, q, json.dumps(ids), fetched_at,
    )
    conn.commit()
