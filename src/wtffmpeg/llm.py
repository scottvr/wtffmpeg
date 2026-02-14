from openai import OpenAI
from typing import Tuple


from wtffmpeg.prompt import SYSTEM_PROMPT


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
