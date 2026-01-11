from __future__ import annotations

import json
import logging
from typing import Any

import requests

log = logging.getLogger(__name__)


def generate_json(*, base_url: str, model: str, prompt: str, temperature: float = 0.7) -> dict[str, Any]:
    """Call Ollama /api/generate and return parsed JSON from the model output.

    We instruct the model to output JSON. If the model returns extra text, we try to extract the first JSON object.
    """
    url = base_url.rstrip("/") + "/api/generate"
    payload = {
        "model": model,
        "prompt": prompt,
        "stream": False,
        "options": {
            "temperature": temperature,
        },
    }

    r = requests.post(url, json=payload, timeout=120)
    r.raise_for_status()
    data = r.json()
    text = (data.get("response") or "").strip()

    try:
        return json.loads(text)
    except Exception:  # noqa: BLE001
        # Try to locate JSON object boundaries.
        start = text.find("{")
        end = text.rfind("}")
        if start != -1 and end != -1 and end > start:
            return json.loads(text[start : end + 1])
        raise
