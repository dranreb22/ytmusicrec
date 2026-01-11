from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Any

import yaml

from ytmusicrec.ollama import generate_json

log = logging.getLogger(__name__)


@dataclass
class GeneratedPrompts:
    suno: list[dict[str, Any]]


def load_prompt_templates(repo_root: Path) -> dict[str, Any]:
    path = repo_root / "config" / "prompt_templates.yaml"
    return yaml.safe_load(path.read_text(encoding="utf-8"))


def build_prompt(themes: list[dict[str, Any]], templates: dict[str, Any]) -> str:
    theme_lines = []
    for t in themes[:10]:
        theme_lines.append(f"- {t['theme']} (score={t['score']})")

    rules = templates.get("suno", {}).get("instructions", "")

    return (
        rules
        + "\n\n"
        + "Themes for today (highest priority first):\n"
        + "\n".join(theme_lines)
        + "\n\n"
        + "Return ONLY JSON."
    )


def generate_prompts(*, base_url: str, model: str, repo_root: Path, themes: list[dict[str, Any]]) -> GeneratedPrompts:
    templates = load_prompt_templates(repo_root)
    prompt = build_prompt(themes, templates)

    data = generate_json(base_url=base_url, model=model, prompt=prompt, temperature=0.8)

    suno = data.get("suno_prompts") or []

    if len(suno) != 12:
        log.warning("Model returned unexpected counts: suno=%s,  len(suno)")

    # Normalize
    suno_norm = []
    for p in suno:
        if isinstance(p, str):
            suno_norm.append({"prompt": p, "tags": [], "theme": ""})
        else:
            suno_norm.append(
                {
                    "prompt": (p.get("prompt") or "").strip(),
                    "tags": p.get("tags") or [],
                    "theme": (p.get("theme") or "").strip(),
                }
            )

    return GeneratedPrompts(suno=suno_norm)


def render_markdown(run_date: date, themes: list[dict[str, Any]], gp: GeneratedPrompts) -> str:
    lines: list[str] = []
    lines.append(f"# ytmusicrec prompts — {run_date.isoformat()}")
    lines.append("")
    lines.append("## Top themes")
    for i, t in enumerate(themes[:10], start=1):
        lines.append(f"{i}. **{t['theme']}** — score: `{t['score']}`")
    lines.append("")

    lines.append("## Suno prompts (12)")
    for i, p in enumerate(gp.suno[:12], start=1):
        theme = p.get("theme") or ""
        tag_str = ", ".join(p.get("tags") or [])
        lines.append(f"{i}. {p['prompt']}" + (f"  \n   _Theme:_ {theme}" if theme else "") + (f"  \n   _Tags:_ {tag_str}" if tag_str else ""))
    lines.append("")

    # Raw JSON block for debugging
    lines.append("---")
    lines.append("### Raw JSON (debug)")
    lines.append("```json")
    raw = {"suno_prompts": gp.suno}
    lines.append(json.dumps(raw, ensure_ascii=False, indent=2))
    lines.append("```")

    return "\n".join(lines)


def output_paths(repo_root: Path, run_date: date) -> tuple[Path, Path]:
    repo_out = repo_root / "output" / f"{run_date.isoformat()}_prompts.md"
    desktop_out = Path("/host_desktop") / "ytmusicrec" / f"{run_date.isoformat()}_prompts.md"
    return repo_out, desktop_out
