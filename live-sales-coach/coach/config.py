"""Load config.yaml, .env, and the three prompt documents."""
from __future__ import annotations

import os
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

APP_DIR = Path(__file__).resolve().parent.parent
PROMPTS_DIR = APP_DIR / "prompts"
WEB_DIR = APP_DIR / "web"

PROMPT_FILES = {
    "instructions": "coach-instructions.md",
    "playbook": "playbook-hormozi-miner-voss.md",
    "offer": "offer-reference.md",
}


def load_env() -> None:
    """Load .env next to main.py if python-dotenv is installed. Never prints values."""
    try:
        from dotenv import load_dotenv
    except ImportError:
        return
    load_dotenv(APP_DIR / ".env", override=False)


def load_config(path: str | os.PathLike | None = None) -> dict[str, Any]:
    cfg_path = Path(path) if path else APP_DIR / "config.yaml"
    with open(cfg_path, "r", encoding="utf-8") as f:
        cfg = yaml.safe_load(f) or {}
    return cfg


def get(cfg: dict, dotted: str, default: Any = None) -> Any:
    node: Any = cfg
    for part in dotted.split("."):
        if not isinstance(node, dict) or part not in node:
            return default
        node = node[part]
    return default if node is None else node


@dataclass
class Prompts:
    instructions: str
    playbook: str
    offer: str


class MissingPrompts(Exception):
    pass


def _instructions_body(text: str) -> str:
    """coach-instructions.md says 'paste everything below the line'. Honor that."""
    lines = text.splitlines()
    for i, line in enumerate(lines):
        if line.strip() and set(line.strip()) == {"-"} and len(line.strip()) >= 3:
            body = "\n".join(lines[i + 1 :]).strip()
            if body:
                return body
    return text.strip()


def load_prompts(prompts_dir: Path = PROMPTS_DIR) -> Prompts:
    missing = [name for name in PROMPT_FILES.values() if not (prompts_dir / name).exists()]
    if missing:
        raise MissingPrompts(
            "Missing prompt files in prompts/: " + ", ".join(missing)
            + ". Download them from Google Drive (see prompts/README.md)."
        )
    read = lambda key: (prompts_dir / PROMPT_FILES[key]).read_text(encoding="utf-8")
    return Prompts(
        instructions=_instructions_body(read("instructions")),
        playbook=read("playbook").strip(),
        offer=read("offer").strip(),
    )


def hotkey_for_platform(cfg: dict) -> str:
    if sys.platform == "darwin":
        return get(cfg, "hotkey.mac", "<cmd>+<shift>+<space>")
    return get(cfg, "hotkey.windows", "<ctrl>+<shift>+<space>")


def keys_status() -> dict[str, bool]:
    """Which keys are present. Values are never returned or logged."""
    return {
        "deepgram": bool(os.environ.get("DEEPGRAM_API_KEY")),
        "anthropic": bool(os.environ.get("ANTHROPIC_API_KEY")),
    }
