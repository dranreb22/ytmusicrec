from __future__ import annotations

import json
import math
from collections import defaultdict
from datetime import datetime, timezone, timedelta
from typing import Any


def compute_video_score(row: dict[str, Any]) -> float:
    """Compute a lightweight trend score.

    Formula (heuristic):
    - views_per_hour since publish (log-scaled)
    - + small weights for engagement ratios
    """
    views = (row.get("view_count") or 0) or 0
    likes = (row.get("like_count") or 0) or 0
    comments = (row.get("comment_count") or 0) or 0

    published_at: datetime | None = row.get("published_at")
    fetched_at: datetime | None = row.get("fetched_at")
    if not published_at or not fetched_at:
        return float(views)

    if published_at.tzinfo is None:
        published_at = published_at.replace(tzinfo=timezone.utc)
    if fetched_at.tzinfo is None:
        fetched_at = fetched_at.replace(tzinfo=timezone.utc)

    age_hours = max((fetched_at - published_at).total_seconds() / 3600.0, 1.0)
    vph = views / age_hours

    like_ratio = likes / max(views, 1)
    comment_ratio = comments / max(views, 1)

    # log scale helps avoid a single huge video dominating.
    base = math.log10(vph + 1.0)
    boost = 1.0 + 2.0 * like_ratio + 3.0 * comment_ratio
    return base * boost


def score_themes_by_query(videos: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Group videos by query name and score each theme bucket."""
    buckets: dict[str, list[tuple[dict[str, Any], float]]] = defaultdict(list)

    for v in videos:
        theme = v.get("query") or "(unknown)"
        score = compute_video_score(v)
        buckets[theme].append((v, score))

    themes: list[dict[str, Any]] = []
    for theme, items in buckets.items():
        items_sorted = sorted(items, key=lambda x: x[1], reverse=True)
        total = float(sum(s for _, s in items_sorted))
        examples = [
            {"title": (it[0].get("title") or ""), "score": round(it[1], 4)}
            for it in items_sorted[:5]
        ]
        themes.append(
            {
                "theme": theme,
                "score": round(total, 6),
                "examples_json": json.dumps(examples, ensure_ascii=False),
            }
        )

    themes.sort(key=lambda x: x["score"], reverse=True)
    return themes

from datetime import date, timedelta
from typing import Any

def compute_theme_trends(*, run_date: date, today_themes: list[dict[str, Any]], history_rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """
    history_rows: rows of {run_date, theme, score} for the last ~7 days including yesterday.
    """
    # index history: theme -> date -> score
    by_theme: dict[str, dict[date, float]] = {}
    for r in history_rows:
        d = r["run_date"]
        if isinstance(d, str):
            d = date.fromisoformat(d)
        by_theme.setdefault(r["theme"], {})[d] = float(r["score"])

    yesterday = run_date - timedelta(days=1)
    start_7d = run_date - timedelta(days=7)

    trends: list[dict[str, Any]] = []
    for t in today_themes:
        theme = t["theme"]
        score = float(t["score"])

        hist = by_theme.get(theme, {})
        prev = hist.get(yesterday)

        # average across last 7 days prior to today
        vals = [v for d, v in hist.items() if start_7d <= d < run_date]
        avg_7d = (sum(vals) / len(vals)) if vals else None

        delta_1d = (score - prev) if prev is not None else None
        momentum = (score - avg_7d) if avg_7d is not None else None

        trends.append(
            {
                "theme": theme,
                "score": score,
                "prev_score": prev,
                "delta_1d": delta_1d,
                "avg_7d": avg_7d,
                "momentum": momentum,
            }
        )

    return trends
