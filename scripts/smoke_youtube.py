from __future__ import annotations

from datetime import datetime, timedelta, timezone

from ytmusicrec.logging_setup import configure_logging
from ytmusicrec.settings import load_settings
from ytmusicrec.youtube import QueryConfig, search_videos, fetch_video_details


def main() -> None:
    configure_logging()
    s = load_settings()
    after = datetime.now(timezone.utc) - timedelta(days=2)
    ids = search_videos(
        api_key=s.youtube_api_key,
        query=QueryConfig(name="smoke", q="lofi"),
        region_code=s.region_code,
        relevance_language="en",
        max_results=5,
        published_after=after,
    )
    print("Found ids:", ids)
    details = fetch_video_details(api_key=s.youtube_api_key, video_ids=ids)
    print("✅ YouTube smoke test OK. Returned items:", len(details))


if __name__ == "__main__":
    main()
