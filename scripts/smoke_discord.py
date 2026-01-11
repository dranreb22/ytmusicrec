from __future__ import annotations

from pathlib import Path

from ytmusicrec.logging_setup import configure_logging
from ytmusicrec.settings import load_settings
from ytmusicrec.discord_webhook import post_message


def main() -> None:
    configure_logging()
    s = load_settings()
    if not s.discord_webhook_url:
        raise RuntimeError("DISCORD_WEBHOOK_URL not set")

    tmp = Path("/tmp/ytmusicrec_discord_smoke.md")
    tmp.write_text("# ytmusicrec discord smoke\n\nok\n", encoding="utf-8")

    post_message(webhook_url=s.discord_webhook_url, content="✅ ytmusicrec Discord smoke test", file_path=tmp)
    print("✅ Discord smoke test OK")


if __name__ == "__main__":
    main()
