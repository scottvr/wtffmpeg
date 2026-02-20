from __future__ import annotations

import sys
import subprocess
import shlex
from dataclasses import replace
from pathlib import Path

import pyperclip
from prompt_toolkit import PromptSession
from prompt_toolkit.history import FileHistory
from prompt_toolkit.auto_suggest import AutoSuggestFromHistory
from prompt_toolkit.enums import EditingMode
from prompt_toolkit.lexers import PygmentsLexer
from prompt_toolkit.styles import Style
from prompt_toolkit.application import get_app
from prompt_toolkit import print_formatted_text as print
from prompt_toolkit.formatted_text import HTML

from pygments.lexers.python import PythonLexer
from pypager.pager import Pager
from pypager.source import StringSource

from .llm import generate_ffmpeg_command, verify_connection, build_client
from .config import (
    AppConfig,
    CONFIG_KEYS,
    PERSIST_KEYS,
    DEFAULT_CONFIG_PATH,
    apply_overrides,
    load_config,
    save_config,
    normalize_base_url,
)
from .profiles import load_profile, list_profiles, resolve_profile


matrix_style = Style.from_dict(
    {
        "prompt": "ansigreen bold",
        "pygments.keyword": "#00ff00 bold",
        "pygments.string": "#aaffaa",
        "pygments.comment": "#008800",
        "pygments.name.function": "#00ff00",
        "pygments.operator": "#00ff00",
        "": "bg:#000000 #00ff00",
    }
)

CMD_HISTFILE = Path.home() / ".wtff_history"


def _parse_kv(tokens: list[str]) -> dict[str, str]:
    out: dict[str, str] = {}
    for t in tokens:
        if "=" not in t:
            raise ValueError(f"Expected key=value, got: {t}")
        k, v = t.split("=", 1)
        out[k.strip()] = v.strip()
    return out


def _coerce_value(key: str, raw: str):
    v = raw.strip()
    if v.lower() in ("none", "null"):
        return None
    if key in ("context_turns",):
        return int(v)
    if key in ("copy", "no_nag"):
        if v.lower() in ("1", "true", "yes", "on"):
            return True
        if v.lower() in ("0", "false", "no", "off"):
            return False
        raise ValueError(f"Bad boolean for {key}: {raw}")
    return v


def _sanitize_cfg(cfg: AppConfig) -> dict:
    return {
        "model": cfg.model,
        "provider": cfg.provider,
        "base_url": cfg.base_url,
        "openai_api_key": ("(set)" if cfg.openai_api_key else "(unset)"),
        "bearer_token": ("(set)" if cfg.bearer_token else "(unset)"),
        "context_turns": cfg.context_turns,
        "profile": resolve_profile(cfg).name,
        "copy": cfg.copy,
        "no_nag": cfg.no_nag,
    }


def _transport_changed(a: AppConfig, b: AppConfig) -> bool:
    keys = ("provider", "base_url", "openai_api_key", "bearer_token")
    return any(getattr(a, k) != getattr(b, k) for k in keys)


def handle_config_command(cmdline: str, *, session: PromptSession, cfg: AppConfig, client):
    """Handle '/config ...' commands. Returns (new_cfg, new_client)."""
    parts = shlex.split(cmdline)
    sub = parts[1] if len(parts) > 1 else "show"

    if sub == "help":
        outstr = """/config — inspect and modify runtime configuration

USAGE

  /config
  /config show
      Show current effective configuration (secrets are masked).

  /config keys
      List configurable keys.

  /config get <key> [<key> ...]
      Show the current value of one or more keys.

  /config set key=value [key=value ...]
      Set one or more configuration values for the current session.

  /config unset <key> [<key> ...]
      Clear one or more configuration values (sets to None where allowed).

  /config reset
      Reset configuration back to startup defaults (from CLI/env/file).

  /config save [path]
      Save current persistent configuration to file.
      Default: ~/.wtffmpeg/config.env

  /config load [path]
      Load configuration from file and apply it.
      Default: ~/.wtffmpeg/config.env
"""
        pager = Pager()
        pager.add_source(StringSource(outstr))
        pager.run()
        return cfg, client

    if sub in ("show",):
        print(_sanitize_cfg(cfg))
        return cfg, client

    if sub == "keys":
        for k in sorted(CONFIG_KEYS):
            print(k)
        return cfg, client

    if sub == "get":
        keys = parts[2:] or []
        if not keys:
            print(_sanitize_cfg(cfg))
            return cfg, client
        for k in keys:
            if k not in CONFIG_KEYS:
                print(f"Unknown config key: {k}", file=sys.stderr)
                continue
            v = getattr(cfg, k)
            if k in ("openai_api_key", "bearer_token"):
                v = "(set)" if v else "(unset)"
            if k == "profile":
                v = resolve_profile(cfg).name
            print(f"{k}={v}")
        return cfg, client

    if sub == "set":
        kv = _parse_kv(parts[2:])
        updates = {}
        for k, raw in kv.items():
            if k not in CONFIG_KEYS:
                print(f"Unknown config key: {k}", file=sys.stderr)
                continue
            updates[k] = _coerce_value(k, raw)

        if "base_url" in updates and updates["base_url"]:
            updates["base_url"] = normalize_base_url(str(updates["base_url"]))

        if "profile" in updates:
            updates["profile"] = load_profile(str(updates["profile"]), cfg.profile_dir)

        new_cfg = apply_overrides(cfg, updates)
        new_client = client
        if _transport_changed(cfg, new_cfg):
            new_client = build_client(new_cfg)

        print("OK")
        return new_cfg, new_client

    if sub == "unset":
        keys = parts[2:]
        updates = {}
        for k in keys:
            if k not in CONFIG_KEYS:
                print(f"Unknown config key: {k}", file=sys.stderr)
                continue
            if k == "profile":
                # keep profile always valid; interpret unset as default
                updates["profile"] = load_profile("minimal", cfg.profile_dir)
            elif k in ("model", "provider", "context_turns", "copy", "no_nag"):
                print(f"Cannot unset required key: {k}", file=sys.stderr)
            else:
                updates[k] = None

        new_cfg = apply_overrides(cfg, updates)
        new_client = client
        if _transport_changed(cfg, new_cfg):
            new_client = build_client(new_cfg)
        print("OK")
        return new_cfg, new_client

    if sub == "save":
        path = Path(parts[2]) if len(parts) > 2 else DEFAULT_CONFIG_PATH
        save_config(cfg, path=path, keys=PERSIST_KEYS)
        print(f"Configuration saved to {path}")
        return cfg, client

    if sub == "load":
        path = Path(parts[2]) if len(parts) > 2 else DEFAULT_CONFIG_PATH
        data = load_config(path)
        if not data and not path.exists():
            print(f"No config file found at {path}", file=sys.stderr)
            return cfg, client

        # 'profile' in file is a name -> load Profile object
        if "profile" in data:
            data["profile"] = load_profile(str(data["profile"]), cfg.profile_dir)

        new_cfg = apply_overrides(cfg, data)
        new_client = client
        if _transport_changed(cfg, new_cfg):
            new_client = build_client(new_cfg)

        print(f"Configuration loaded from {path}")
        return new_cfg, new_client

    print(f"Unknown /config subcommand: {sub}", file=sys.stderr)
    return cfg, client


def execute_command(command: str) -> int:
    """Execute a shell command, streaming output. Returns exit code."""
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


def nag():
    print(
        "Press enter to execute the command at your prompt immediately"
        " or edit it as needed. You can also copy/paste it elsewhere."
        " To run shell commands directly, prefix with ! (e.g. !ls -la)."
        " Remove this reminder with --no-nag or /config set no_nag=true."
    )


def single_shot(*, client, cfg: AppConfig) -> int:
    """Run exactly one prompt (cfg.prompt_once) and exit."""
    if not cfg.prompt_once:
        print("single_shot called without cfg.prompt_once", file=sys.stderr)
        return 2

    messages = [
        {"role": "system", "content": resolve_profile(cfg).text},
        {"role": "user", "content": cfg.prompt_once},
    ]

    raw, cmd = generate_ffmpeg_command(messages, client, cfg.model)
    if not cmd:
        print("Failed to generate a command.", file=sys.stderr)
        print(raw)
        return 1

    print(cmd)

    if cfg.copy:
        pyperclip.copy(cmd)
        print("Command copied to clipboard.")

    return 0


def repl(*, client, cfg: AppConfig):
    def _client_base_url(client) -> str | None:
        for attr in ("base_url", "_base_url"):
            v = getattr(client, attr, None)
            if v:
                return str(v)
        return None

    session = PromptSession(
        history=FileHistory(str(CMD_HISTFILE)),
        auto_suggest=AutoSuggestFromHistory(),
    )

    def get_toolbar():
        try:
            width = get_app().output.get_size().columns
        except Exception:
            width = 80

        bind_txt = "Vi" if session.editing_mode == EditingMode.VI else "Emacs"
        copy_txt = f"Copy: {'ON' if cfg.copy else 'OFF'}"
        padding = width - len(bind_txt) - len(copy_txt) - 12
        if padding < 1:
            padding = 1
        return HTML(f"<b>[Mode: {bind_txt}]</b> {' ' * padding} <b>{copy_txt}</b>")

    messages = [{"role": "system", "content": resolve_profile(cfg).text}]

    # preload: run once, then drop into repl with prefilled !cmd
    prefill = ""
    if cfg.preload_prompt:
        messages.append({"role": "user", "content": cfg.preload_prompt})
        messages = trim_messages(messages, keep_last_turns=cfg.context_turns)
        raw, cmd = generate_ffmpeg_command(messages, client, model=cfg.model)
        if cmd:
            messages.append({"role": "assistant", "content": raw})
            messages = trim_messages(messages, keep_last_turns=cfg.context_turns)
            if cfg.copy:
                pyperclip.copy(cmd)
            prefill = "!" + " ".join(cmd.splitlines()).strip()

    print("Entering interactive mode. Type 'exit'/'quit' to leave. Use !<cmd> to run shell commands.")
    if not cfg.no_nag:
        nag()

    while True:
        try:
            line = session.prompt(
                "wtff> ",
                default=prefill,
                lexer=PygmentsLexer(PythonLexer),
                bottom_toolbar=get_toolbar,
                rprompt=lambda: f"{resolve_profile(cfg).name} | {cfg.model} |",
                style=matrix_style,
            )
        except (EOFError, KeyboardInterrupt):
            print("\nExiting interactive mode.")
            return

        prefill = ""
        if not line:
            continue

        # explicit exits
        if line.strip().lower() in ("exit", "quit", "logout", ":q", ":q!"):
            print("\nExiting interactive mode.")
            return

        # /slash commands
        if line.startswith("/"):
            cmd = line[1:].strip().lower()

            if cmd in ("exit", "quit", "logout", ":q", ":q!"):
                print("\nExiting interactive mode.")
                return

            if cmd in ("help", "h", "?"):
                print("Available /commands:")
                print("  /help, /h, /? - Show this help message")
                print("  /ping - Check LLM connectivity")
                print("  /reset - Clear conversation history (keep system prompt)")
                print("  /profile - Show current profile")
                print("  /profiles - List available profiles")
                print("  /config - View and modify configuration (/config help)")
                print("  /bindings [vi|emacs] - Switch keybindings")
                print("  /q|/quit|/exit|/logout - Exit the REPL")
                print("- Use !<command> to execute shell commands")
                continue

            if cmd == "ping":
                try:
                    verify_connection(client, base_url=_client_base_url(client))
                    print("LLM connectivity: OK")
                except RuntimeError as e:
                    print(str(e), file=sys.stderr)
                continue

            if cmd == "reset":
                messages = messages[:1]
                print("Conversation history cleared.")
                continue

            if cmd == "profile":
                print(f"Current profile: {resolve_profile(cfg).name}")
                print(resolve_profile(cfg).text)
                continue

            if cmd == "profiles":
                avail = list_profiles(cfg.profile_dir)
                print("User profiles:")
                for n in avail["user"]:
                    print(f"  {n}")
                print("Built-in profiles:")
                for n in avail["builtin"]:
                    print(f"  {n}")
                continue

            if cmd.startswith("config"):
                cfg, client = handle_config_command(line, session=session, cfg=cfg, client=client)
                continue

            if cmd.startswith("bindings"):
                mode = cmd[len("bindings") :].strip()
                if mode == "vi":
                    session.editing_mode = EditingMode.VI
                    print("Switched to Vi mode.")
                elif mode == "emacs":
                    session.editing_mode = EditingMode.EMACS
                    print("Switched to Emacs mode.")
                else:
                    print("Usage: /bindings vi|emacs")
                continue

            print(f"Unknown command: {line}", file=sys.stderr)
            continue

        # !shell commands
        if line.startswith("!"):
            shell_cmd = line[1:].strip()
            if shell_cmd:
                rc = execute_command(shell_cmd)
                if rc != 0:
                    print(f"Shell command exited {rc}", file=sys.stderr)
            continue

        # LLM request
        messages.append({"role": "user", "content": line})
        messages = trim_messages(messages, keep_last_turns=cfg.context_turns)

        raw, cmd = generate_ffmpeg_command(messages, client, cfg.model)
        if not cmd:
            print("Failed to generate a command.", file=sys.stderr)
            print(raw)
            messages.pop()
            continue

        messages.append({"role": "assistant", "content": raw})
        messages = trim_messages(messages, keep_last_turns=cfg.context_turns)

        if cfg.copy:
            pyperclip.copy(cmd)
        prefill = "!" + " ".join(cmd.splitlines()).strip()


def trim_messages(messages: list[dict], keep_last_turns: int = 12) -> list[dict]:
    if keep_last_turns <= 0:
        return messages[:1]  # keep only system

    system = messages[0:1]
    rest = messages[1:]
    max_msgs = keep_last_turns * 2
    if len(rest) <= max_msgs:
        return messages
    return system + rest[-max_msgs:]
