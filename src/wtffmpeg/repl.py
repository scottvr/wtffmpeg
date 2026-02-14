import sys
import subprocess
import pyperclip
from wtffmpeg.llm import OpenAI, SYSTEM_PROMPT, generate_ffmpeg_command

from pathlib import Path
HISTFILE = Path("~/.wtff_history").expanduser()
from prompt_toolkit import PromptSession
from prompt_toolkit.history import FileHistory

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
