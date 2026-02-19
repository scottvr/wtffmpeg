import argparse
import os
from pathlib import Path

from .llm import build_client
from .repl import repl, single_shot 
from .config import AppConfig, resolve_config
from .profiles import list_profiles, load_profile

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
        default=None,
        help="Model to use. Defaults WTFFMPEG_MODEL then 'gpt-oss:20b'.",
    )
    p.add_argument(
        "--api-key",
        type=str,
        default=None,
        help="OpenAI API key. Defaults WTFFMPEG_OPENAI_API_KEY (or none).",
    )
    p.add_argument(
        "--bearer-token",
        type=str,
        default=None,
        help="Bearer token. Defaults WTFFMPEG_BEARER_TOKEN.",
    )
    p.add_argument(
        "--url",
        type=str,
        default=None,
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

    p.add_argument(
        "-A", "--Always-copy",
        action="store_true",
        help="Always copy generated command to clipboard without confirmation.",
    )

#    p.add_argument(
#        "-l", "--log-prompts",
#        action="store_true",
#        help="Log prompts to history file for better autosuggest. Uses ~/.wtff_history.",
#    )
    # Keep -i as NOP to avoid breaking old aliases
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

def _env_nonempty(name: str) -> str | None:
    v = os.environ.get(name)
    if v and v.strip():
        return v.strip()
    return None


def main():
    parser = build_parser()
    args = parser.parse_args()

    cfg = resolve_config(args)
    
    if args.list_profiles:
        avail = list_profiles(cfg.profile_dir)
        print("User profiles:")
        for n in avail["user"]:
            print(f"  {n}")
        print("Built-in profiles:")
        for n in avail["builtin"]:
            print(f"  {n}")
        raise SystemExit(0)
    
    client  = build_client(cfg)

    if cfg.prompt_once is not None:
        rc = single_shot(cfg.prompt_once, client, cfg.model, profile=cfg.profile,
                         always_copy=args.Always_copy, do_exec=cfg.exec_)
        raise SystemExit(rc)

    repl(cfg.preload_prompt, client, cfg.model, cfg.context_turns, always_copy=args.Always_copy, profile=cfg.profile, cfg=cfg)

if __name__ == "__main__":
    main()
