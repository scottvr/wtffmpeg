from dataclasses import dataclass
from typing import Optional, Any, Tuple
from .profiles import load_profile
from .llm import build_client

@dataclass
class RuntimeState:
    client: Optional[Any] = None
    profile: Optional[Any] = None

    # fingerprints for deterministic rebuilds
    _client_fp: Optional[Tuple] = None
    _profile_fp: Optional[Tuple] = None

    # tools_registry: Optional[Tools] = None
    # _tools_fp: Optional[Tuple] = None


def client_fingerprint(cfg) -> tuple:
    return (
        cfg.provider,
        cfg.base_url,
        cfg.model,
        bool(cfg.openai_api_key),  
        # cfg.api_key_source
        # include anything else that affects client construction:
        getattr(cfg, "timeout_s", None),
        getattr(cfg, "max_retries", None),
    )

def profile_fingerprint(cfg) -> tuple:
    # add anything else that changes load semantics
    return (cfg.profile_name, cfg.profile_dir)

def reconcile_runtime(cfg, rt: RuntimeState, *, force: bool = False) -> RuntimeState:
    # client
    cfp = client_fingerprint(cfg)
    if force or rt.client is None or rt._client_fp != cfp:
        rt.client = build_client(cfg)
        rt._client_fp = cfp

    # profile
    pfp = profile_fingerprint(cfg)
    if force or rt.profile is None or rt._profile_fp != pfp:
        rt.profile = load_profile(cfg.profile_name, cfg.profile_dir)  
        rt._profile_fp = pfp

    return rt
