from __future__ import annotations

import logging
from pathlib import Path

import requests

log = logging.getLogger(__name__)

MAX_LEN = 1900

def post_long_message(*, webhook_url: str, content: str, file_path: Path | None = None) -> None:
    if len(content) <= MAX_LEN:
        post_message(webhook_url=webhook_url, content=content, file_path=file_path)
        return

    # First message: header + attach file
    head = content[:MAX_LEN]
    post_message(webhook_url=webhook_url, content=head, file_path=file_path)

    # Remaining chunks, no attachment
    rest = content[MAX_LEN:]
    while rest:
        chunk = rest[:MAX_LEN]
        rest = rest[MAX_LEN:]
        post_message(webhook_url=webhook_url, content=chunk, file_path=None)


def post_message(*, webhook_url: str, content: str, file_path: Path | None = None, timeout: int = 30) -> None:
    """Post a Discord message via webhook. If file_path is provided, attaches it."""
    if not webhook_url:
        raise RuntimeError("DISCORD_WEBHOOK_URL is not set")

    if file_path and file_path.exists():
        with file_path.open("rb") as f:
            files = {"file": (file_path.name, f, "text/markdown")}
            data = {"content": content}
            r = requests.post(webhook_url, data=data, files=files, timeout=timeout)
    else:
        r = requests.post(webhook_url, json={"content": content}, timeout=timeout)

    if r.status_code >= 300:
        log.error("Discord webhook failed: %s %s", r.status_code, r.text)
        r.raise_for_status()
