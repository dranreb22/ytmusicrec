from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any

import requests

log = logging.getLogger(__name__)


@dataclass(frozen=True)
class QueryConfig:
    name: str
    q: str


def _iso(dt: datetime) -> str:
    return dt.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def search_videos(
    *,
    api_key: str,
    query: QueryConfig,
    region_code: str,
    relevance_language: str,
    max_results: int,
    published_after: datetime,
) -> list[str]:
    """Return a list of video ids for a given query."""
    url = "https://www.googleapis.com/youtube/v3/search"
    params = {
        "key": api_key,
        "part": "snippet",
        "type": "video",
        "q": query.q,
        "maxResults": max_results,
        "regionCode": region_code,
        "relevanceLanguage": relevance_language,
        "publishedAfter": _iso(published_after),
        # "order": "viewCount",  # keep deterministic for recent trends
        "order": "date",
    }

    r = requests.get(url, params=params, timeout=30)
    r.raise_for_status()
    data = r.json()

    ids: list[str] = []
    for item in data.get("items", []):
        vid = (item.get("id") or {}).get("videoId")
        if vid:
            ids.append(vid)

    return ids


def fetch_video_details(*, api_key: str, video_ids: list[str]) -> list[dict[str, Any]]:
    if not video_ids:
        return []

    url = "https://www.googleapis.com/youtube/v3/videos"
    out: list[dict[str, Any]] = []

    # Videos API supports up to 50 ids per request.
    for i in range(0, len(video_ids), 50):
        chunk = video_ids[i : i + 50]
        params = {
            "key": api_key,
            "part": "snippet,statistics,contentDetails",
            "id": ",".join(chunk),
            "maxResults": len(chunk),
        }
        r = requests.get(url, params=params, timeout=30)
        r.raise_for_status()
        data = r.json()
        out.extend(data.get("items", []))

    return out


def parse_video_row(*, video_item: dict[str, Any], query_name: str, fetched_at: datetime) -> dict[str, Any]:
    snippet = video_item.get("snippet", {}) or {}
    stats = video_item.get("statistics", {}) or {}

    published_at_raw = snippet.get("publishedAt")
    published_at: datetime | None = None
    if published_at_raw:
        try:
            published_at = datetime.fromisoformat(published_at_raw.replace("Z", "+00:00")).astimezone(timezone.utc)
        except Exception:  # noqa: BLE001
            published_at = None

    def to_int(x: Any) -> int | None:
        if x is None:
            return None
        try:
            return int(x)
        except Exception:  # noqa: BLE001
            return None

    return {
        "video_id": video_item.get("id"),
        "query": query_name,
        "title": snippet.get("title"),
        "description": snippet.get("description"),
        "channel_title": snippet.get("channelTitle"),
        "published_at": published_at,
        "view_count": to_int(stats.get("viewCount")),
        "like_count": to_int(stats.get("likeCount")),
        "comment_count": to_int(stats.get("commentCount")),
        "fetched_at": fetched_at,
    }
