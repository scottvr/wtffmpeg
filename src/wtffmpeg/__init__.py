
def main():
    parser = argparse.ArgumentParser(
        description="Translate natural language to an ffmpeg command.",
        formatter_class=argparse.RawTextHelpFormatter
    )
    parser.add_argument(
        "prompt",
        nargs='?', # Make the prompt optional for interactive mode
        default=None,
        type=str,
        help="The natural language instruction for the ffmpeg command.\n" \
             "Required unless running in interactive mode."
    )
    parser.add_argument(
        "--model",
        type=str,
        default=os.environ.get("WTFFMPEG_MODEL", "gpt-oss:20b"),
        help="The model to use. For Ollama, this should be a model you have downloaded. Defaults to the WTFFMPEG_MODEL env var, then 'gpt-oss:20b'."
    )
    parser.add_argument(
        "--api-key",
        type=str,
        default=os.environ.get("WTFFMPEG_OPENAI_API_KEY"),
        help="OpenAI API key. Defaults to WTFFMPEG_OPENAI_API_KEY environment variable."
    )
    parser.add_argument(
        "--bearer-token",
        type=str,
        default=os.environ.get("WTFFMPEG_BEARER_TOKEN"),
        help="Bearer token for authentication. Defaults to WTFFMPEG_BEARER_TOKEN environment variable."
    )
    parser.add_argument(
        "--url",
        type=str,
        default=os.environ.get("WTFFMPEG_LLM_API_URL", "http://localhost:11434"),
        help="Base URL for a local LLM API (e.g., http://localhost:11434). Defaults to WTFFMPEG_LLM_API_URL env var, then http://localhost:11434. The '/v1' suffix for OpenAI compatibility will be added automatically."
    )
    parser.add_argument(
        "-x", "--execute",
        action="store_true",
        help="Execute the generated command without confirmation."
    )
    parser.add_argument(
        "-c", "--copy",
        action="store_true",
        help="Copy the generated command to the clipboard."
    )
    parser.add_argument(
        "-i", "--interactive",
        action="store_true",
        help="Enter interactive mode to run multiple commands."
    )
    args = parser.parse_args()

    if not args.interactive and not args.prompt:
        parser.error("The 'prompt' argument is required for non-interactive mode.")

    # If an API key is provided, use OpenAI. Otherwise, assume Ollama or another bearer-token based service.
    if args.api_key:
        client = OpenAI(api_key=args.api_key)
        # If using OpenAI, but the model is the default, change it to a sensible OpenAI default.
        if args.model == "gpt-oss:20b":
            args.model = "gpt-4o"
    else:
        base_url = args.url
        # Ensure the URL for Ollama ends with /v1 for OpenAI client compatibility
        if not base_url.endswith("/v1"):
            base_url = base_url.rstrip('/') + "/v1"

        # Print a message if we are using the hardcoded default Ollama URL
        if args.url == "http://localhost:11434" and not os.environ.get("WTFFMPEG_LLM_API_URL"):
             print(f"INFO: No API key or WTFFMPEG_LLM_API_URL env var provided. Defaulting to local Ollama at {args.url}")
        
        # Use the bearer token if provided, otherwise use a dummy key for Ollama.
        api_key = args.bearer_token if args.bearer_token else "ollama"
        client = OpenAI(base_url=base_url, api_key=api_key)

    if args.interactive:
        interactive_mode(client, args.model)
        sys.exit(0)

    ffmpeg_command = generate_ffmpeg_command(args.prompt, client, args.model)

    if not ffmpeg_command:
        print("Failed to generate a command.", file=sys.stderr)
        sys.exit(1)

    if args.copy:
        pyperclip.copy(ffmpeg_command)
        print("Command copied to clipboard.")
        sys.exit(0)

    print("\n--- Generated ffmpeg Command ---")
    print(ffmpeg_command)
    print("------------------------------")

    if args.execute:
        execute_command(ffmpeg_command)
    else:
        try:
            confirm = input("Execute this command? [y/N] ")
            if confirm.lower() == 'y':
                execute_command(ffmpeg_command)
            else:
                print("Execution cancelled by user.")
        except (EOFError, KeyboardInterrupt):
            print("\nExecution cancelled by user.")
            sys.exit(0)

