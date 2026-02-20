from pathlib import Path
from dataclasses import dataclass
from typing import Optional, Literal
from functools import lru_cache
import os

import importlib.resources  # type: ignore
from .config import AppConfig, DEFAULT_PROFILE_DIR


@dataclass(frozen=True)
class Profile():
    name: str
    source: Literal["user", "builtin", "path"]
    path: Optional[Path]
    text: str

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
        files = importlib.resources.files('wtffmpeg').joinpath('profiles')
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
        files = importlib.resources.files('wtffmpeg').joinpath('profiles')
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

def resolve_profile(cfg: AppConfig) -> Profile:
    """Return the Profile for cfg.profile_name (cached)."""
    return _cached_profile(str(cfg.profile_dir), cfg.profile_name)

# Profile resolution (name -> Profile)
@lru_cache(maxsize=64)
def _cached_profile(profile_dir_str: str, profile_name: str) -> Profile:
    return load_profile(profile_name, Path(profile_dir_str))