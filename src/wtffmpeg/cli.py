
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

    return p


def main():
    parser = build_parser()
    args = parser.parse_args()

    client, model = build_client_and_model(args)

    # Single-shot mode wins if explicitly requested.
    if args.prompt_once is not None:
        rc = single_shot(args.prompt_once, client, model, do_copy=args.copy, do_exec=args.exec_)
        raise SystemExit(rc)

    # Default: REPL, optionally with preload prompt (positional)
    repl(args.prompt, client, model, args.context_turns)
    raise SystemExit(0)


if __name__ == "__main__":
    main()
