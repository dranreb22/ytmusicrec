from __future__ import annotations

import requests

from ytmusicrec.logging_setup import configure_logging
from ytmusicrec.settings import load_settings


def main() -> None:
    configure_logging()
    s = load_settings()
    url = s.ollama_base_url.rstrip('/') + '/api/generate'
    payload = {"model": s.ollama_model, "prompt": "Respond with the single word OK.", "stream": False}
    r = requests.post(url, json=payload, timeout=60)
    r.raise_for_status()
    data = r.json()
    print("✅ Ollama smoke test OK. Response:", (data.get("response") or "").strip())


if __name__ == "__main__":
    main()
