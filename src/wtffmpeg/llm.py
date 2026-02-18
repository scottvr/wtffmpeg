from __future__ import annotations
from openai import OpenAI
from typing import Tuple
from pathlib import Path
from dataclasses import dataclass
from typing import Literal, Optional
import os
import sys

from .config import AppConfig
@dataclass(frozen=True)
class LLMTarget:
    client: OpenAI
    model: str
    base_url: Optional[str]
    provider: str  # "openai" or "compat"

def verify_connection(client: OpenAI, base_url: str | None) -> None:
    """
    Raises a RuntimeError with a helpful message on failure.
    """
    try:
        # Cheap request; no tokens.
        client.models.list()
    except Exception as e:
        target = base_url or "https://api.openai.com/v1"
        raise RuntimeError(
            f"Unable to reach LLM endpoint: {target}\n"
            f"Underlying error: {type(e).__name__}: {e}"
        ) from e

def generate_ffmpeg_command(messages: list[dict], client: OpenAI, model: str) -> Tuple[str, str]:
    """Generate a single ffmpeg command from the LLM, and try to strip markdown/commentary."""
    try:
        resp = client.chat.completions.create(
            model=model,
            messages=messages,
            temperature=0.0,
        )
        raw = (resp.choices[0].message.content or "").strip()
        text = raw


        # strip fenced blocks if present
        if "```" in text:
            parts = text.split("```")
            if len(parts) >= 2:
                text = parts[1].strip()
                if text.lower().startswith(("bash", "sh")):
                    text = text.split("\n", 1)[1].strip()

        if text.lower().startswith("assistant:"):
            text = text[len("assistant:"):].strip()

        if text.startswith("`") and text.endswith("`"):
            text = text.strip("`")

        return raw, text
    except Exception as e:
        print(f"Error during model inference: {e}", file=sys.stderr)
        return "", ""


def build_client(cfg: AppConfig) -> OpenAI:
    if cfg.provider == "openai":
        return OpenAI(api_key=cfg.openai_api_key)
    
    api_key = cfg.bearer_token or "ollama"
    return OpenAI(base_url=cfg.base_url, api_key=api_key)
