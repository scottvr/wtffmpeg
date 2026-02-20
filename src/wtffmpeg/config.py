from __future__ import annotations

from dataclasses import dataclass, replace
from pathlib import Path
from typing import Optional, Literal, Any
import os

from .profiles import load_profile, Profile, DEFAULT_PROFILE_DIR

Provider = Literal["openai", "compat"]

# Defaults / keys
DEFAULT_MODEL_COMPAT = "gpt-oss:20b"
DEFAULT_MODEL_OPENAI = "gpt-4o"
DEFAULT_PROFILE_NAME = "minimal"

DEFAULT_CONFIG_PATH = Path.home() / ".wtffmpeg" / "config.env"

# Keys that are safe to accept from a config file / REPL.
CONFIG_KEYS: set[str] = {
    "model",
    "provider",
    "base_url",
    "openai_api_key",
    "bearer_token",
    "context_turns",
    "profile",
    "no_nag",
    "copy",
}

# Keys we persist by default (avoid secrets).
PERSIST_KEYS: set[str] = {
    "model",
    "provider",
    "base_url",
    "context_turns",
    "profile",
    "no_nag",
    "copy",
}

@dataclass(frozen=True)
class AppConfig:
    # core behavior
    model: str
    provider: Provider

    # endpoint/auth (resolved)
    base_url: Optional[str]          # normalized, includes /v1 for compat
    openai_api_key: Optional[str]
    bearer_token: Optional[str]

    # prompts
    profile_name: str  # name only; resolved to Profile via resolve_profile()
    profile_dir: Path

    # repl/flow
    context_turns: int
    preload_prompt: Optional[str]
    prompt_once: Optional[str]
    no_nag: bool

    # actions
    copy: bool
    # exec_: bool


def _env_nonempty(name: str) -> Optional[str]:
    v = os.environ.get(name)
    if v is None:
        return None
    v = v.strip()
    return v if v else None


def normalize_base_url(url: str) -> str:
    url = url.strip()
    if not url.startswith(("http://", "https://")):
        url = "http://" + url
    url = url.rstrip("/")
    if not url.endswith("/v1"):
        url += "/v1"
    return url


def _coerce_value(key: str, raw: str) -> Any:
    v = raw.strip()
    if v.lower() in ("none", "null"):
        return None
    if key in ("context_turns",):
        return int(v)
    if key in ("copy", "no_nag"):
        if v.lower() in ("1", "true", "yes", "on"):
            return True
        if v.lower() in ("0", "false", "no", "off"):
            return False
        raise ValueError(f"Bad boolean for {key}: {raw}")
    return v


def load_config(path: Path | None = None) -> dict[str, Any]:
    """Load a simple key=value config file.

    - Ignores blank lines and lines starting with '#'
    - Coerces known types (bool/int/None)
    - Returns a dict of keys -> coerced values
    """
    path = path or DEFAULT_CONFIG_PATH
    if not path.exists():
        return {}

    out: dict[str, Any] = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        if "=" not in line:
            # skip junk lines silently; REPL will warn if desired
            continue
        k, v = line.split("=", 1)
        k = k.strip()
        v = v.strip()
        if k not in CONFIG_KEYS:
            continue
        out[k] = _coerce_value(k, v)
    return out

def save_config(cfg: AppConfig, path: Path | None = None, keys: set[str] | None = None) -> Path:
    """Persist selected non-secret config keys to a file."""
    path = path or DEFAULT_CONFIG_PATH
    keys = keys or PERSIST_KEYS
    path.parent.mkdir(parents=True, exist_ok=True)

    lines: list[str] = []
    for k in sorted(keys):
        if k == "profile":
            v = cfg.profile_name
        else:
            v = getattr(cfg, k)
        if v is None:
            continue
        lines.append(f"{k}={v}")
    path.write_text("\n".join(lines) + ("\n" if lines else ""), encoding="utf-8")
    return path


def apply_overrides(cfg: AppConfig, overrides: dict[str, Any]) -> AppConfig:
    """Apply a dict of overrides onto an AppConfig, handling special fields."""
    updates: dict[str, Any] = dict(overrides)

    # profile is stored as a name (string)
    # normalize base_url if present and non-empty
    if "base_url" in updates and updates["base_url"]:
        updates["base_url"] = normalize_base_url(str(updates["base_url"]))

    # provider should be a valid Literal
    if "provider" in updates and updates["provider"] is not None:
        updates["provider"] = str(updates["provider"]).lower()

    return replace(cfg, **updates)


# args/env/file/defaults
def resolve_config(args, *, config_path: Path | None = None) -> AppConfig:
    """Resolve config using the precedence:
        CLI args > env vars > config file > defaults
    """
    file_cfg = load_config(config_path)

    profile_dir = args.profile_dir or DEFAULT_PROFILE_DIR
    profile_spec = (
        getattr(args, "profile", None)
        or _env_nonempty("WTFFMPEG_PROFILE")
        or file_cfg.get("profile")
        or DEFAULT_PROFILE_NAME
    )
    profile_name = str(profile_spec)

    openai_api_key = getattr(args, "api_key", None) or _env_nonempty("WTFFMPEG_OPENAI_API_KEY") or file_cfg.get("openai_api_key")
    bearer_token = getattr(args, "bearer_token", None) or _env_nonempty("WTFFMPEG_BEARER_TOKEN") or file_cfg.get("bearer_token")
    url_raw = getattr(args, "url", None) or _env_nonempty("WTFFMPEG_LLM_API_URL") or file_cfg.get("base_url") or "http://localhost:11434"

    # provider can be forced by args/provider, otherwise inferred
    provider_arg = getattr(args, "provider", None) if hasattr(args, "provider") else None
    provider_env = _env_nonempty("WTFFMPEG_PROVIDER")
    provider_file = file_cfg.get("provider")
    provider: Provider

    if provider_arg:
        provider = str(provider_arg).lower()  # type: ignore[assignment]
    elif provider_env:
        provider = str(provider_env).lower()  # type: ignore[assignment]
    elif provider_file:
        provider = str(provider_file).lower()  # type: ignore[assignment]
    else:
        # use openai if API key set and no explicit compat URL
        if openai_api_key and not getattr(args, "url", None):
            provider = "openai"
        else:
            provider = "compat"

    base_url: Optional[str]
    if provider == "openai":
        base_url = None
    else:
        base_url = normalize_base_url(str(url_raw))

    # args > env > file > provider-default
    model = (
        getattr(args, "model", None)
        or _env_nonempty("WTFFMPEG_MODEL")
        or file_cfg.get("model")
        or (DEFAULT_MODEL_OPENAI if provider == "openai" else DEFAULT_MODEL_COMPAT)
    )

    context_turns = (
        getattr(args, "context_turns", None)
        if getattr(args, "context_turns", None) is not None
        else file_cfg.get("context_turns", 12)
    )
    no_nag = bool(getattr(args, "no_nag", False) or file_cfg.get("no_nag", False))
    copy = bool(getattr(args, "copy", False) or file_cfg.get("copy", False))

    return AppConfig(
        model=str(model),
        provider=provider,
        base_url=base_url,
        openai_api_key=openai_api_key,
        bearer_token=bearer_token,
        context_turns=int(context_turns),
        preload_prompt=getattr(args, "prompt", None),
        prompt_once=getattr(args, "prompt_once", None),
        no_nag=no_nag,
        copy=copy,
        profile_name=profile_name,
        profile_dir=profile_dir,
    )
