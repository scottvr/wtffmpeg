import argparse
from pathlib import Path

from .llm import build_client
from .repl import repl, single_shot
from .config import resolve_config, DEFAULT_CONFIG_PATH
from .profiles import list_profiles


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        description="Translate natural language to an ffmpeg command.",
        formatter_class=argparse.RawTextHelpFormatter,
    )

    p.add_argument(
        "prompt",
        nargs="?",
        default=None,
        help="Optional preload prompt. Runs once, then drops you into the REPL.",
    )

    p.add_argument(
        "-p",
        "--prompt-once",
        dest="prompt_once",
        metavar="PROMPT",
        default=None,
        help="Single-shot mode: generate for PROMPT once, then exit (use -c to copy).",
    )

    p.add_argument(
        "--model",
        type=str,
        default=None,
        help="Model to use. Defaults WTFFMPEG_MODEL then provider default.",
    )
    p.add_argument(
        "--api-key",
        type=str,
        default=None,
        help="OpenAI API key. Defaults WTFFMPEG_OPENAI_API_KEY.",
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
        "-c",
        "--copy",
        action="store_true",
        help="Copy generated command to clipboard automatically.",
    )

    # Keep -i as NOP to avoid breaking old aliases
    p.add_argument(
        "-i",
        "--interactive",
        action="store_true",
        help="Deprecated no-op. REPL is now the default.",
    )

    p.add_argument(
        "--context-turns",
        type=int,
        default=None,
        help="How many prior user/assistant turns to include in REPL requests (0 = stateless).",
    )

    p.add_argument("--profile", type=str, default=None, help="Profile name or path")
    p.add_argument("--list-profiles", action="store_true", help="List available profiles and exit")
    p.add_argument("--profile-dir", type=Path, default=None, help="Override ~/.wtffmpeg/profiles")
    p.add_argument("--no-nag", action="store_true", help="Disable nag reminder above every prompt")
    p.add_argument(
        "--config",
        type=Path,
        default=None,
        help=f"Path to config.env (default: {DEFAULT_CONFIG_PATH})",
    )
    return p


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()

    cfg = resolve_config(args, config_path=args.config)

    if args.list_profiles:
        avail = list_profiles(cfg.profile_dir)
        print("User profiles:")
        for n in avail["user"]:
            print(f"  {n}")
        print("Built-in profiles:")
        for n in avail["builtin"]:
            print(f"  {n}")
        raise SystemExit(0)

    client = build_client(cfg)

    if cfg.prompt_once is not None:
        rc = single_shot(client=client, cfg=cfg)
        raise SystemExit(rc)

    repl(client=client, cfg=cfg)


if __name__ == "__main__":
    main()
