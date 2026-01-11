from __future__ import annotations

import logging
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Any

import yaml

from ytmusicrec.logging_setup import configure_logging
from ytmusicrec.settings import load_settings
from ytmusicrec.youtube import QueryConfig, search_videos, fetch_video_details, parse_video_row
from ytmusicrec.mssql import connect, ensure_schema, create_run, update_run_video_count, upsert_videos, fetch_videos_for_date, write_daily_themes, write_daily_prompts,fetch_daily_themes_range, write_daily_theme_trends, write_daily_query_stats, fetch_top_queries, fetch_recent_prompt_hashes, write_prompt_history
from ytmusicrec.scoring import score_themes_by_query, compute_theme_trends
from ytmusicrec.prompts import generate_prompts, render_markdown
from ytmusicrec.io_utils import write_text
from ytmusicrec.discord_webhook import post_long_message
from ytmusicrec.sheets import write_daily as sheets_write_daily
from airflow.sdk import get_current_context


log = logging.getLogger(__name__)

def load_query_config(repo_root: Path) -> dict[str, Any]:
    path = repo_root / "config" / "queries.yaml"
    return yaml.safe_load(path.read_text(encoding="utf-8"))


def task_collect_youtube_to_mssql(run_date: str | None = None) -> dict[str, Any]:
    """Airflow task: collect YouTube video data into MSSQL.

    Returns a dict used for XCom.
    """
    configure_logging()
    s = load_settings()
    ctx = get_current_context()
    ti = ctx["ti"]
    total_views = 0
    total_likes = 0
    total_comments = 0
    video_count = 0

    if not run_date:
        

        # Airflow 3 task runtime context can vary (manual runs may not have data_interval_start).
        dt = (
            ctx.get("data_interval_start")
            or ctx.get("logical_date")
            or ctx.get("execution_date")
            or (ctx.get("dag_run").logical_date if ctx.get("dag_run") else None)
        )
        if dt is None:
            run_date = date.today().isoformat()
        else:
            run_date = dt.date().isoformat()

    

    run_dt = date.fromisoformat(run_date)
    repo_root = s.repo_root

    cfg = load_query_config(repo_root)
    region = cfg.get("region_code", s.region_code)
    rel_lang = cfg.get("relevance_language", "en")
    days_back = int(cfg.get("days_back", 7))
    max_results = int(cfg.get("max_results_per_query", 25))

    fetched_at = datetime.now(timezone.utc)
    published_after = fetched_at - timedelta(days=days_back)

    conn = connect(s)
    try:
        ensure_schema(conn)
        feedback = cfg.get("feedback_loop", {}) or {}
        fb_enabled = bool(feedback.get("enabled", False))
        lookback_days = int(feedback.get("lookback_days", 7))
        max_queries_final = int(feedback.get("max_queries", len(cfg.get("queries", [])) or 5))
        theme_query_prefix = str(feedback.get("theme_query_prefix", "music"))
        theme_query_count = int(feedback.get("theme_query_count", 2))
        queries_cfg = [QueryConfig(name=q["name"], q=q["q"]) for q in cfg.get("queries", [])]
        log.info("Collecting YouTube data: date=%s region=%s queries=%s", run_dt, region, len(queries_cfg))

        # Start from seed queries.yaml
        seed_queries = [QueryConfig(name=q["name"], q=q["q"]) for q in cfg.get("queries", [])]

        if fb_enabled:
            since = run_dt - timedelta(days=lookback_days)

            # 1) historically best raw query strings
            top_qs = fetch_top_queries(conn, region_code=region, since_date=since, limit=max_queries_final)

            # 2) pull recent themes and create theme-based queries (light expansion)
            hist_rows = fetch_daily_themes_range(conn, since, run_dt - timedelta(days=1))
            # get most frequent/high scoring themes recently
            theme_scores: dict[str, float] = {}
            for r in hist_rows:
                theme_scores[r["theme"]] = max(theme_scores.get(r["theme"], 0.0), float(r["score"]))

            top_themes_recent = sorted(theme_scores.items(), key=lambda x: x[1], reverse=True)[:theme_query_count]
            theme_queries = [f"{theme_query_prefix} {t[0]}" for t in top_themes_recent]

            # Merge into final query strings (dedupe)
            merged_q = []
            for q in [*top_qs, *theme_queries, *(sq.q for sq in seed_queries)]:
                q = (q or "").strip()
                if q and q not in merged_q:
                    merged_q.append(q)

            merged_q = merged_q[:max_queries_final]

            # Build QueryConfig with stable names
            queries_cfg = [QueryConfig(name=f"auto_{i+1}", q=q) for i, q in enumerate(merged_q)]
        else:
            queries_cfg = seed_queries

        run = create_run(conn, run_dt, region, query_count=len(queries_cfg))

        all_rows: list[dict[str, Any]] = []
        seen: set[str] = set()
        query_stats: list[dict[str, Any]] = []

        for q in queries_cfg:
            ids = search_videos(
                api_key=s.youtube_api_key,
                query=q,
                region_code=region,
                relevance_language=rel_lang,
                max_results=max_results,
                published_after=published_after,
            )
            ids = [i for i in ids if i not in seen]
            seen.update(ids)
            


            details = fetch_video_details(api_key=s.youtube_api_key, video_ids=ids)
            for item in details:
                row = parse_video_row(video_item=item, query_name=q.name, fetched_at=fetched_at)
                if row.get("video_id"):
                    all_rows.append(row)
                    video_count += 1
                    total_views += int(row.get("view_count") or 0)
                    total_likes += int(row.get("like_count") or 0)
                    total_comments += int(row.get("comment_count") or 0)
            query_stats.append(
            {
                "query_name": q.name,
                "q": q.q,
                "video_count": video_count,
                "total_views": total_views,
                "total_likes": total_likes,
                "total_comments": total_comments,
            }
        )

        processed = upsert_videos(conn, all_rows)
        update_run_video_count(conn, run.run_id, processed)

        write_daily_query_stats(conn, run_dt, region, query_stats)


        result = {"run_date": run_dt.isoformat(), "region_code": region, "video_count": processed}

        # IMPORTANT: push individual keys so XComArg(task)["run_date"] works
        ti.xcom_push(key="run_date", value=result["run_date"])
        ti.xcom_push(key="region_code", value=result["region_code"])
        ti.xcom_push(key="video_count", value=result["video_count"])


        log.info("Collected %s videos", processed)
        return result
    finally:
        conn.close()


def task_score_themes_to_mssql_and_csv(run_date: str) -> dict[str, Any]:
    configure_logging()
    s = load_settings()
    repo_root = s.repo_root

    d = date.fromisoformat(run_date)
    conn = connect(s)
    try:
        ensure_schema(conn)
        videos = fetch_videos_for_date(conn, d)
        themes = score_themes_by_query(videos)

        write_daily_themes(conn, d, themes)

        history = fetch_daily_themes_range(conn, d - timedelta(days=7), d - timedelta(days=1))
        trends = compute_theme_trends(run_date=d, today_themes=themes[:25], history_rows=history)
        write_daily_theme_trends(conn, d, trends)

        # also write a CSV snapshot
        out_csv = repo_root / "output" / "themes_latest.csv"
        out_csv.parent.mkdir(parents=True, exist_ok=True)
        lines = ["theme,score"]
        for t in themes[:25]:
            theme = (t["theme"] or "").replace('"', '""')
            lines.append(f'"{theme}",{t["score"]}')
        desktop_csv = Path(s.host_desktop_mount) / "ytmusicrec" / "themes_latest.csv"
        out_csv_text = "\n".join(lines)
        out_csv.write_text(out_csv_text, encoding="utf-8")
        write_text(desktop_csv, out_csv_text)
        ctx = get_current_context()
        ti = ctx["ti"]
        ti.xcom_push(key="run_date", value=run_date)
        ti.xcom_push(key="top_themes", value=themes[:10])

        return {"run_date": run_date, "top_themes": themes[:10]}
    finally:
        conn.close()


def task_generate_prompts_to_mssql_and_md(run_date: str, top_themes: list[dict[str, Any]]) -> dict[str, Any]:
    configure_logging()
    s = load_settings()
    repo_root = s.repo_root

    d = date.fromisoformat(run_date)
    gp = generate_prompts(
        base_url=s.ollama_base_url,
        model=s.ollama_model,
        repo_root=repo_root,
        themes=top_themes,
    )

    md = render_markdown(d, top_themes, gp)

    repo_md = repo_root / "output" / f"{d.isoformat()}_prompts.md"
    desktop_md = Path(s.host_desktop_mount) / "ytmusicrec" / f"{d.isoformat()}_prompts.md"

    write_text(repo_md, md)
    write_text(desktop_md, md)

    prompts_for_db: list[dict[str, Any]] = []
    for p in gp.suno[:12]:
        prompts_for_db.append({"tool": "suno", "prompt": p.get("prompt"), "theme_tags": ",".join(p.get("tags") or [])})

    conn = connect(s)
    try:
        ensure_schema(conn)
        write_daily_prompts(conn, d, prompts_for_db)
        write_prompt_history(conn, d, "suno", prompts_for_db)
    finally:
        conn.close()

    ctx = get_current_context()
    ti = ctx["ti"]
    ti.xcom_push(key="run_date", value=run_date)
    ti.xcom_push(key="repo_md_path", value=str(repo_md))
    ti.xcom_push(key="desktop_md_path", value=str(desktop_md))
    ti.xcom_push(key="suno", value=gp.suno[:12])

    return {"run_date": run_date, "repo_md_path": str(repo_md), "desktop_md_path": str(desktop_md), "suno": gp.suno[:12]}


def task_publish_outputs(run_date: str, top_themes: list[dict[str, Any]], suno: list[dict[str, Any]], repo_md_path: str) -> None:
    configure_logging()
    s = load_settings()
    d = date.fromisoformat(run_date)

    repo_md = Path(repo_md_path)

    # Discord
    if s.discord_webhook_url:
        lines = []
        lines.append(f"✅ ytmusicrec — {d.isoformat()}")
        lines.append("")
        lines.append("**Top Themes**")
        for t in top_themes[:10]:
            lines.append(f"• {t['theme']} (score {t['score']})")
        lines.append("")
        lines.append("**Suno (top 3)**")
        for p in suno[:3]:
            lines.append(f"• {p.get('prompt')}")
        lines.append("")

        if s.google_sheets_spreadsheet_id:
            lines.append("")
            lines.append("Google Sheet: https://docs.google.com/spreadsheets/d/%s" % s.google_sheets_spreadsheet_id)

        content = "\n".join(lines)

        if not s.dry_run:
            post_long_message(webhook_url=s.discord_webhook_url, content=content, file_path=repo_md)
        else:
            log.info("DRY_RUN: would post Discord message")

    # Google Sheets
    if s.google_sheets_spreadsheet_id:
        if not s.dry_run:
            sheets_write_daily(
                spreadsheet_id=s.google_sheets_spreadsheet_id,
                token_json_path=s.google_oauth_token_json,
                run_date=d,
                themes=top_themes,
                suno=suno,
            )
        else:
            log.info("DRY_RUN: would write Google Sheet")
