import argparse
import os
import sys
import subprocess
from pathlib import Path

import pyperclip
from openai import OpenAI
from typing import Tuple

from prompt_toolkit import PromptSession
from prompt_toolkit.history import FileHistory

from wtffmpeg.prompt import SYSTEM_PROMPT

HISTFILE = Path("~/.wtff_history").expanduser()


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

def trim_messages(messages: list[dict], keep_last_turns: int = 12) -> list[dict]:
    if keep_last_turns <= 0:
        # keep only system
        return messages[:1]

    system = messages[0:1]
    rest = messages[1:]
    max_msgs = keep_last_turns * 2
    if len(rest) <= max_msgs:
        return messages
    return system + rest[-max_msgs:]


def execute_command(command: str) -> int:
    """Execute a shell command, streaming output. Returns exit code."""
    print(f"\nExecuting: {command}\n")
    try:
        with subprocess.Popen(
            command,
            shell=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1,
            universal_newlines=True,
        ) as proc:
            if proc.stdout:
                for line in proc.stdout:
                    print(line, end="")
            return proc.wait()
    except Exception as e:
        print(f"Error executing command: {e}", file=sys.stderr)
        return 1


def print_command(cmd: str):
    print("\n--- Generated ffmpeg Command ---")
    print(cmd)
    print("------------------------------")


def single_shot(prompt: str, client: OpenAI, model: str, *, do_copy: bool, do_exec: bool) -> int:
    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": prompt},
    ]

    raw, cmd = generate_ffmpeg_command(messages, client, model)
    if not cmd:
        print("Failed to generate a command.", file=sys.stderr)
        return 1

    print_command(cmd)

    if do_copy:
        pyperclip.copy(cmd)
        print("Command copied to clipboard.")

    if do_exec:
        return execute_command(cmd)

    try:
        confirm = input("Execute this command? [y/N] ")
        if confirm.lower() == "y":
            return execute_command(cmd)
        print("Execution cancelled by user.")
        return 0
    except (EOFError, KeyboardInterrupt):
        print("\nExecution cancelled by user.")
        return 0


def repl(preload: str | None, client: OpenAI, model: str, keep_last_turns: int):
    session = PromptSession(history=FileHistory(str(HISTFILE)))

    messages = [{"role": "system", "content": SYSTEM_PROMPT}]

    if preload:
        messages.append({"role": "user", "content": preload})    # preload is "safe landing": run once, then drop into repl

        messages = trim_messages(messages, keep_last_turns=keep_last_turns)
        raw, cmd = generate_ffmpeg_command(messages, client, model)
        if cmd:
            messages.append({"role": "assistant", "content": cmd})
            messages = trim_messages(messages, keep_last_turns=keep_last_turns)
            print_command(cmd)

    print("Entering interactive mode. Type 'exit'/'quit'/'logout' to leave. Use !<cmd> to run shell commands.")

    while True:
        try:
            line = session.prompt("wtff> ")
        except (EOFError, KeyboardInterrupt):
            print("\nExiting interactive mode.")
            return

        if not line:
            continue

        low = line.strip().lower()
        if low in ("exit", "quit", "logout"):
            return

        if line.startswith("!"):
            shell_cmd = line[1:].strip()
            if shell_cmd:
                rc = execute_command(shell_cmd)
                if rc != 0:
                    print(f"Shell command exited {rc}", file=sys.stderr)
            continue
        messages.append({"role": "user", "content": line})
        messages = trim_messages(messages, keep_last_turns=keep_last_turns)

        raw, cmd = generate_ffmpeg_command(messages, client, model)
        if not cmd:
            print("Failed to generate a command.", file=sys.stderr)
            # roll back last user turn so a failed call doesnt poison context
            messages.pop()
            continue

        messages.append({"role": "assistant", "content": raw})
        messages = trim_messages(messages, keep_last_turns=keep_last_turns)

        print_command(cmd)

        try:
            confirm = session.prompt("Execute? [y/N], or (c)opy to clipboard: ").strip().lower()
        except (EOFError, KeyboardInterrupt):
            print("\nExiting interactive mode.")
            return

        if confirm == "y":
            pyperclip.copy(cmd)
            rc = execute_command(cmd)
            if rc != 0:
                print(f"Command exited {rc}", file=sys.stderr)
        elif confirm == "c":
            pyperclip.copy(cmd)
            print("Command copied to clipboard.")
        else:
            print("Execution cancelled.")


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
