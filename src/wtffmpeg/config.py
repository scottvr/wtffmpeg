from dataclasses import dataclass
from pathlib import Path
from typing import Optional, Literal
import os

from .profiles import load_profile, Profile

Provider = Literal["openai", "compat"]

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
    profile: Profile

    # repl/flow
    context_turns: int
    preload_prompt: Optional[str]
    prompt_once: Optional[str]

    # actions
    copy: bool
    exec_: bool


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


DEFAULT_MODEL_COMPAT = "gpt-oss:20b"
DEFAULT_MODEL_OPENAI = "gpt-4o"
DEFAULT_PROFILE_DIR = Path.home() / ".wtffmpeg" / "profiles"
DEFAULT_PROFILE_NAME = "minimal"

def resolve_config(args) -> AppConfig:
    # profile
    profile_spec = (
        args.profile
        or _env_nonempty("WTFFMPEG_PROFILE")
        or DEFAULT_PROFILE_NAME
    )
    profile = load_profile(profile_spec, args.profile_dir)

    # auth/url
    openai_api_key = args.api_key or _env_nonempty("WTFFMPEG_OPENAI_API_KEY")
    bearer_token = args.bearer_token or _env_nonempty("WTFFMPEG_BEARER_TOKEN")
    url_raw = args.url or _env_nonempty("WTFFMPEG_LLM_API_URL") or "http://localhost:11434"

    # provider selection
    if openai_api_key:
        provider: Provider = "openai"
        base_url = None
        model = args.model or _env_nonempty("WTFFMPEG_MODEL") or DEFAULT_MODEL_OPENAI
    else:
        provider = "compat"
        base_url = normalize_base_url(url_raw)
        model = args.model or _env_nonempty("WTFFMPEG_MODEL") or DEFAULT_MODEL_COMPAT

    return AppConfig(
        model=model,
        provider=provider,
        base_url=base_url,
        openai_api_key=openai_api_key,
        bearer_token=bearer_token,
        profile=profile,
        context_turns=args.context_turns,
        preload_prompt=args.prompt,
        prompt_once=args.prompt_once,
        copy=args.copy,
        exec_=args.exec_,
    )