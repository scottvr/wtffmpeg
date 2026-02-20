import sys
import subprocess
import pyperclip
import shlex
from pathlib import Path
from dataclasses import replace
from prompt_toolkit import PromptSession
from prompt_toolkit.history import FileHistory
from prompt_toolkit.auto_suggest import AutoSuggestFromHistory
from pypager.pager import Pager
from pypager.source import StringSource
from pygments.lexers.python import PythonLexer
from prompt_toolkit.styles import Style
from prompt_toolkit.lexers import PygmentsLexer
from prompt_toolkit.enums import EditingMode
from prompt_toolkit import print_formatted_text as print
from prompt_toolkit.formatted_text import HTML
from prompt_toolkit.application import get_app

from .llm import generate_ffmpeg_command, verify_connection
from .config import AppConfig
from .llm import build_client
from .profiles import Profile
from .profiles import load_profile, list_profiles

matrix_style = Style.from_dict({
    # The prompt itself
    'prompt': 'ansigreen bold',
    
    # Syntax highlighting (pygments tokens)
    'pygments.keyword': '#00ff00 bold',
    'pygments.string': '#aaffaa',
    'pygments.comment': '#008800',
    'pygments.name.function': '#00ff00',
    'pygments.operator': '#00ff00',
    
    # Background and default text
    '': 'bg:#000000 #00ff00',
})


CMD_HISTFILE = Path.home() / ".wtff_history"

CONFIG_KEYS = {
    "model",
    "provider",
    "base_url",
    "openai_api_key",
    "bearer_token",
    "context_turns",
    "profile",
    "no_nag",
    "copy",
}

PERSIST_KEYS = {
    "model",
    "provider",
    "base_url",
    "context_turns",
    "profile",
    "copy",
}

def _parse_kv(tokens: list[str]) -> dict[str, str]:
    out = {}
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
    if key in ("copy",):
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
        "profile": cfg.profile.name,
        "copy": cfg.copy,  
        "no_nag": cfg.no_nag,
    }


def handle_config_command(cmdline: str, session: PromptSession, cfg: AppConfig, client) -> tuple[AppConfig, object]:
    handled = True
    # cmdline is the full line starting with "/config ..."
    parts = shlex.split(cmdline)
    # parts[0] == "/config"
    sub = parts[1] if len(parts) > 1 else "show"

    # do something better with this dispatch, maybe a dict of subcommand -> handler fn

    if sub == "help":
        outstr =""" 
  /config — inspect and modify runtime configuration

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
      Clear one or more configuration values (sets to None).

  /config reset
      Reset configuration back to startup defaults.

  /config save [path]
      Save current persistent configuration to file.
      Default path: ~/.wtffmpeg/config.env

  /config load [path]
      Load configuration from file and apply it.
      Default path: ~/.wtffmpeg/config.env


COMMON SHORTCUTS

  /model <name>
      Equivalent to: /config set model=<name>

  /provider <name>
      Equivalent to: /config set provider=<name>

  /url <base_url>
      Equivalent to: /config set base_url=<base_url>

  /profile <name>
      Equivalent to: /config set profile=<name>


CONFIGURABLE KEYS

  model
      Model name used for requests.

  provider
      LLM provider (e.g. openai, compat).

  base_url
      OpenAI-compatible endpoint base URL.

  openai_api_key
      API key for OpenAI provider.
      WARNING: Not displayed in plaintext.

  bearer_token
      Bearer token for compat provider.
      WARNING: Not displayed in plaintext.

  context_turns
      Number of previous turns retained in context window.

  profile
      Active profile name.

  copy
      If true, copy generated ffmpeg command to clipboard automatically.


VALUE RULES

  key=value format is required.
  Strings may be quoted.
  Booleans accept: true/false, 1/0, yes/no.
  None values: none or null.


PERSISTENCE

  Only non-secret keys are saved by default:
      model
      provider
      base_url
      context_turns
      profile
      copy

  API keys and bearer tokens are NOT written unless explicitly supported
  by future options.

  Saved format is a simple key=value file.


NOTES

  Changing provider, base_url, or authentication will rebuild the client.
  Changes take effect immediately for subsequent requests.
  Configuration changes apply only to the current session unless saved.
"""
        pager = Pager()
        pager.add_source(StringSource(outstr))
        pager.run()

    if sub in ("show",):
        print(_sanitize_cfg(cfg))
        return cfg, client

    if sub == "keys":
        for k in sorted(CONFIG_KEYS):
            print(k)
        return cfg, client

    if sub == "set":
        kv = _parse_kv(parts[2:])
        updates = {}
        for k, raw in kv.items():
            if k not in CONFIG_KEYS:
                print(f"Unknown config key: {k}", file=sys.stderr)
                handled = False
                continue
            updates[k] = _coerce_value(k, raw)

        # special: profile needs loading
        if "profile" in updates:
            prof = load_profile(str(updates["profile"]), cfg.profile_dir)
            updates["profile"] = prof.name

        if "copy" in updates:
            print(f"Setting copy to {updates['copy']}. This will {'enable' if updates['copy'] else 'disable'} automatic copying of generated commands to the clipboard.")
            updates["copy"] = updates.pop("copy")
            print(f"copy is now set to {updates['copy']}")

        new_cfg = replace(cfg, **updates)

        # rebuild client if transport/auth/provider changed
        if any(k in updates for k in ("provider", "base_url", "openai_api_key", "bearer_token")):
            client = build_client(new_cfg)

        if handled:
            print("OK")
        return new_cfg, client
    
    if sub == "save":
        path = Path(parts[2]) if len(parts) > 2 else Path.home() / ".wtffmpeg" / "config.env"
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("w", encoding="utf-8") as f:
            for k in PERSIST_KEYS:
                v = getattr(cfg, k)
                if v is not None:
                    if isinstance(v, Profile):
                        v = v.name
                    f.write(f"{k}={v}\n")
        print(f"Configuration saved to {path}")
        return cfg, client

    if sub == "load":
        path = Path(parts[2]) if len(parts) > 2 else Path.home() / ".wtffmpeg" / "config.env"
        if not path.exists():
            print(f"No config file found at {path}", file=sys.stderr)
            return cfg, client
        new_cfg = cfg
        with path.open("r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith("#"):
                    continue
                if "=" not in line:
                    print(f"Skipping invalid config line: {line}", file=sys.stderr)
                    continue
                k, v = line.split("=", 1)
                k = k.strip()
                v = v.strip()
                if k not in CONFIG_KEYS:
                    print(f"Skipping unknown config key: {k}", file=sys.stderr)
                    continue
                coerced = _coerce_value(k, v)
                if k == "profile":
                    coerced = load_profile(str(coerced), cfg.profile_dir)
                new_cfg = replace(new_cfg, **{k: coerced})
        
        # rebuild client if transport/auth/provider changed
        if any(k in _parse_kv(parts[2:]) for k in ("provider", "base_url", "openai_api_key", "bearer_token")):
            client = build_client(new_cfg)

        print(f"Configuration loaded from {path}")
        return new_cfg, client

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


def nag(cmd: str):
    print("Press enter to execute the command at your prompt immediately",
          " or edit it as needed. You can also copy/paste it elsewhere.",
          " To run shell commands directly, prefix with ! (e.g. !ls -la).",
          " remove this reminder with --no-nag or /config set no_nag=true.",)

def single_shot(prompt: str, client: OpenAI, model: str,  copy: bool,  profile: Profile) -> int:
    messages = [
        {"role": "system", "content": profile.text},
        {"role": "user", "content": prompt},
    ]

    raw, cmd = generate_ffmpeg_command(messages, client, model)
    if not cmd:
        print("Failed to generate a command.", file=sys.stderr)
        return 1

    print(cmd)

    if cmd and copy:
        pyperclip.copy(cmd)
        print("Command copied to clipboard.")

    return 0



def repl(client: OpenAI, cfg : AppConfig | None  = None):
    def _client_base_url(client) -> str | None:
        for attr in ("base_url", "_base_url"):
            print("debug: looking for client attr", attr)
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

        # Detect the current mode from the session state
        bind_txt = "Vi" if session.editing_mode == EditingMode.VI else "Emacs"
        copy_mode = "ON" if cfg.copy else "OFF"
        copy_txt = f"Copy: {copy_mode}"
        padding = width - len(bind_txt) - len(copy_txt) - 12  
        if padding < 1:
            padding = 1
        return HTML(f'<b>[Mode: {bind_txt}]</b> {" " * padding} <b>{copy_txt}</b>')
    
    messages = [{"role": "system", "content": cfg.profile.text}]

    if cfg.preload_prompt:
        messages.append({"role": "user", "content": cfg.preload_prompt})    # preload is "safe landing": run once, then drop into repl

        messages = trim_messages(messages, keep_last_turns=cfg.context_turns)
        raw, cmd = generate_ffmpeg_command(
            messages, client, model=model
        )
        if cmd:
            messages.append({"role": "assistant", "content": raw})
            messages = trim_messages(messages, keep_last_turns=cfg.context_turns)
            pyperclip.copy(cmd)

    print("Entering interactive mode. Type 'exit'/'quit'/'logout' to leave. Use !<cmd> to run shell commands.")
    if not cfg.no_nag:
        nag("")

    prefilled = True if cfg.preload_prompt else False
    while True:
        if prefilled:
            prefill = "!" + " ".join(cmd.splitlines()).strip() if cmd else ""
            prefilled = False
        try:
            line = session.prompt("wtff> ", 
                default=str(prefill) if 'prefill' in locals() else "", 
                lexer=PygmentsLexer(PythonLexer),
                bottom_toolbar=get_toolbar,
                rprompt=lambda: f"{cfg.profile.name} | {cfg.model} |",
                style=matrix_style
            )
        except (EOFError, KeyboardInterrupt):
            print("\nExiting interactive mode.")
            return
        

        if not line:
            continue
        
        prefill = ""
        cmd = line[1:].strip().lower()
       
        if cmd in ("exit", "quit", "logout", ":q", ":q!"):
            return

        if line.startswith("/"):
            if cmd  in ("help", "h", "?"):
                print("Available /commands:")
                print("  /help, /h, /? - Show this help message")
                print("  /ping - Check LLM connectivity")
                print("  /reset - Clear conversation history (keep system prompt)")
                print("  /profile - Show current profile info")
                print("  /profiles - List available profiles")
                print("  /config - View and modify configuration (type /config help for details)") 
                print("  /bindings - List special keybindings (e.g. for Vi/Emacs modes)")
                print("  /q|quit|/exit|/logout - Exit the REPL")
                print("- Use !<command> to execute shell commands")
                print("- Just type in natural language to generate ffmpeg commands.")
                print("- See the README in github.com/scottvr/wtffmpeg.") 
                continue

            elif cmd in ("ping"):
                try:
                    verify_connection(client, base_url=_client_base_url(client))
                    print("LLM connectivity: OK")
                except RuntimeError as e:
                    print(str(e), file=sys.stderr)
            elif cmd == "reset":
                messages = messages[:1]  # keep system prompt
                print("Conversation history cleared.")
            elif cmd == "profile":
                print(f"Current profile: {cfg.profile.name}")
                print(profile.text)
            elif cmd == "profiles":
                avail = list_profiles()
                print("User profiles:")
                for n in avail["user"]:
                    print(f"  {n}")
                print("Built-in profiles:")
                for n in avail["builtin"]:
                    print(f"  {n}")
            elif cmd.startswith(f"config"):
                cfg, handled = handle_config_command(line, session=session, cfg=cfg, client=client)
                if handled:
                    print("Configuration updated.")

            elif cmd.startswith("bindings"):
                mode = line[len("/bindings"):].strip().lower()
                if mode == "vi":
                    session.editing_mode = EditingMode.VI
                    print("Switched to Vi mode.")
                elif mode == "emacs":
                    session.editing_mode = EditingMode.EMACS
                    print("Switched to Emacs mode.")
            else:
                print(f"Unknown command: {line}", file=sys.stderr)
            continue
        
        messages.append({"role": "user", "content": line})
        messages = trim_messages(messages, keep_last_turns=cfg.context_turns)

        if line.startswith("!"):
            shell_cmd = line[1:].strip()
            if shell_cmd:
                rc = execute_command(shell_cmd)
                if rc != 0:
                    print(f"Shell command exited {rc}", file=sys.stderr)
                    #preload = None
        else:
            raw, cmd = generate_ffmpeg_command(messages, client, cfg.model)
            if not cmd:
                print("Failed to generate a command.", file=sys.stderr)
                print(raw)
                messages.pop()
                continue

            messages.append({"role": "assistant", "content": raw})
            messages = trim_messages(messages, keep_last_turns=cfg.context_turns)

            if copy and cmd:
                pyperclip.copy(cmd)
            if cmd:
                prefill = "!" + " ".join(cmd.splitlines()).strip()

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