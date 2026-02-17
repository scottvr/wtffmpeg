import argparse
import os

from .llm import build_client_and_model, generate_ffmpeg_command, list_profiles
from .repl import repl, single_shot
from .config import AppConfig

DEFAULT_PROFILE_NAME = "minimal"  # choose this and ship it as a built-in

def _resolve_profile_spec(args) -> str:
    # Precedence: CLI -> env -> default
    if getattr(args, "profile", None):
        return args.profile
    env = os.environ.get("WTFFMPEG_PROFILE")
    if env:
        return env
    return DEFAULT_PROFILE_NAME

def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        description="Translate natural language to an ffmpeg command.",
        formatter_class=argparse.RawTextHelpFormatter,
    )

    # Positional prompt: preload then drop into REPL
    p.add_argument(
        "prompt",
        nargs="?",
        default=None,
        help="Optional preload prompt. Runs once, then drops you into the REPL.",
    )

    # Single-shot prompt: exactly one turn then exit
    p.add_argument(
        "-p", "--prompt-once",
        dest="prompt_once",
        metavar="PROMPT",
        default=None,
        help="Single-shot mode: generate for PROMPT once, then exit (use -c/-x to copy/exec).",
    )

    p.add_argument(
        "--model",
        type=str,
        default=os.environ.get("WTFFMPEG_MODEL", "gpt-oss:20b"),
        help="Model to use. Defaults WTFFMPEG_MODEL then 'gpt-oss:20b'.",
    )
    p.add_argument(
        "--api-key",
        type=str,
        default=os.environ.get("WTFFMPEG_OPENAI_API_KEY"),
        help="OpenAI API key. Defaults WTFFMPEG_OPENAI_API_KEY.",
    )
    p.add_argument(
        "--bearer-token",
        type=str,
        default=os.environ.get("WTFFMPEG_BEARER_TOKEN"),
        help="Bearer token. Defaults WTFFMPEG_BEARER_TOKEN.",
    )
    p.add_argument(
        "--url",
        type=str,
        default=os.environ.get("WTFFMPEG_LLM_API_URL", "http://localhost:11434"),
        help="Base URL for OpenAI-compatible API. Defaults WTFFMPEG_LLM_API_URL then http://localhost:11434",
    )

    p.add_argument(
        "-x", "-e", "--exec",
        dest="exec_",
        action="store_true",
        help="Execute generated command without confirmation (single-shot only).",
    )
    p.add_argument(
        "-c", "--copy",
        action="store_true",
        help="Copy generated command to clipboard (single-shot only).",
    )

    # Keep -i as no-op to avoid breaking old aliases
    p.add_argument(
        "-i", "--interactive",
        action="store_true",
        help="Deprecated no-op. REPL is now the default.",
    )

    p.add_argument(
       "--context-turns",
        type=int,
        default=12,
        help="How many prior user/assistant turns to include in REPL requests (0 = stateless).",
    )

    p.add_argument("--profile", type=str, default=None, help="Profile name or path")
    p.add_argument("--list-profiles", action="store_true", help="List available profiles and exit")
    p.add_argument("--profile-dir", type=Path, default=None, help="Override ~/.wtffmpeg/profiles")

    return p


def main():
    parser = build_parser()
    args = parser.parse_args()

    if args.list_profiles:
        avail = list_profiles(getattr(args, "profile_dir", None))
        print("User profiles:")
        for n in avail["user"]:
            print(f"  {n}")
        print("Built-in profiles:")
        for n in avail["builtin"]:
            print(f"  {n}")
        raise SystemExit(0)

    profile_spec = _resolve_profile_spec(args)
    profile = load_profile(profile_spec, args.profile_dir) 
    if profile.source == "path":
        print(f"Profile: {profile.name} (path)")
    elif profile.source == "user":
        print(f"Profile: {profile.name} (user)")
    else:
        print(f"Profile: {profile.name} (built-in)")


    
    cfg = AppConfig(
        profile=profile,
        context_turns=args.context_turns,
        copy=args.copy,
        exec_=args.exec_,
        prompt_once=args.prompt_once,
        preload_prompt=args.prompt,  # positional prompt
    )

    client, model = build_client_and_model(args)

    if cfg.prompt_once is not None:
        rc = single_shot(
            cfg.prompt_once, client, model,
            profile=cfg.profile,
            do_copy=cfg.copy,
            do_exec=cfg.exec_,
        )
        raise SystemExit(rc)

    repl(cfg.preload_prompt, client, model, cfg.context_turns, profile=cfg.profile)
    raise SystemExit(0)

if __name__ == "__main__":
    main()
