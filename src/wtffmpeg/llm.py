from __future__ import annotations
from openai import OpenAI
from typing import Tuple
from pathlib import Path
from dataclasses import dataclass
from typing import Literal, Optional
import os

try:
    from importlib import resources as importlib_resources
except Exception:  # pragma: no cover
    import importlib_resources  # type: ignore

class Profile(frozen=True):
    name: str
    source: Literal["user", "builtin", "path"]
    path: Optional[Path]
    text: str

DEFAULT_PROFILE_DIR = Path.home() / ".wtffmpeg" / "profiles"
BUILTIN_PROFILES_PKG = "wtffmpeg.profiles"  # package data dir: src/wtffmpeg/profiles/


def _looks_like_path(spec: str) -> bool:
    if spec.startswith(("~", ".", os.sep)):
        return True
    return ("/" in spec) or ("\\" in spec)

def _read_text_file(p: Path, max_bytes: int = 256 * 1024) -> str:
    if not p.exists():
        raise FileNotFoundError(str(p))
    if not p.is_file():
        raise ValueError(f"Profile path is not a regular file: {p}")
    size = p.stat().st_size
    if size > max_bytes:
        raise ValueError(f"Profile file too large ({size} bytes): {p}")
    return p.read_text(encoding="utf-8", errors="replace")


def _candidate_paths_in_dir(profile_dir: Path, name: str) -> list[Path]:
    # Try exact then with .txt
    return [profile_dir / name, profile_dir / f"{name}.txt"]

def list_profiles(profile_dir: Path | None = None) -> dict[str, list[str]]:
    """
    Return available profiles grouped by source.
    Values are *names* (without .txt normalization guarantees).
    """
    pd = profile_dir or DEFAULT_PROFILE_DIR

    user_names: set[str] = set()
    if pd.exists() and pd.is_dir():
        for p in pd.iterdir():
            if p.is_file():
                user_names.add(p.name)

    builtin_names: set[str] = set()
    try:
        files = importlib_resources.files(BUILTIN_PROFILES_PKG)
        for entry in files.iterdir():
            if entry.is_file():
                builtin_names.add(entry.name)
    except Exception:
        # If package data isn't present, keep empty; callers can still use path/user.
        pass

    return {
        "user": sorted(user_names),
        "builtin": sorted(builtin_names),
    }


def load_profile(profile_spec: str, profile_dir: Path | None = None) -> Profile:
    """
    Load a prompt profile.

    Resolution:
      - If profile_spec looks like a path, treat it as a path (expand ~, resolve).
      - Else treat as a name:
          1) user dir (~/.wtffmpeg/profiles or overridden profile_dir), try name and name.txt
          2) built-in package profiles, try name and name.txt

    Returns a Profile with source in {"user","builtin","path"}.
    """
    if not profile_spec or not profile_spec.strip():
        raise ValueError("Empty profile spec")

    spec = profile_spec.strip()
    pd = profile_dir or DEFAULT_PROFILE_DIR

    if _looks_like_path(spec):
        p = Path(spec).expanduser()
        # Don't resolve() aggressively (can fail on non-existent segments), but normalize.
        p = p if p.is_absolute() else (Path.cwd() / p)
        text = _read_text_file(p)
        return Profile(name=p.name, source="path", path=p, text=text)

    for cand in _candidate_paths_in_dir(pd, spec):
        if cand.exists():
            text = _read_text_file(cand)
            return Profile(name=spec, source="user", path=cand, text=text)

    builtin_candidates = [spec, f"{spec}.txt"]
    try:
        files = importlib_resources.files(BUILTIN_PROFILES_PKG)
        for fname in builtin_candidates:
            entry = files / fname
            if entry.is_file():
                # Read as text; resources provides binary, decode.
                data = entry.read_bytes()
                if len(data) > 256 * 1024:
                    raise ValueError(f"Built-in profile too large: {fname}")
                text = data.decode("utf-8", errors="replace")
                return Profile(name=spec, source="builtin", path=None, text=text)
    except ModuleNotFoundError:
        pass
    except FileNotFoundError:
        pass

    avail = list_profiles(pd)
    raise ValueError(
        f"Profile '{spec}' not found. "
        f"User profiles in {pd}: {', '.join(avail['user']) or '(none)'}; "
        f"Built-ins: {', '.join(avail['builtin']) or '(none)'}."
    )

def build_client_and_model(args) -> tuple[OpenAI, str]:
    """
    Build an OpenAI-compatible client.
    - If --api-key is provided, use OpenAI official API (and default model -> gpt-4o).
    - Else assume Ollama or other OpenAI-compatible endpoint via --url + optional bearer token.
    """
    model = args.model

    if args.api_key:
        client = OpenAI(api_key=args.api_key)
        if model == "gpt-oss:20b":
            model = "gpt-4o"
        return client, model

    base_url = args.url.rstrip("/")
    if not base_url.endswith("/v1"):
        base_url = base_url + "/v1"

    if args.url == "http://localhost:11434" and not os.environ.get("WTFFMPEG_LLM_API_URL"):
        print("INFO: No API key or WTFFMPEG_LLM_API_URL provided. Defaulting to local Ollama at http://localhost:11434")

    api_key = args.bearer_token if args.bearer_token else "ollama"
    client = OpenAI(base_url=base_url, api_key=api_key)
    return client, model


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
