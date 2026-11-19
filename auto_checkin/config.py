"""Configuration and input parsing.

Credentials live in environment variables (or an explicitly ignored .env
file). Public defaults belong in config.toml; never put a session string in
the repository configuration.
"""

from __future__ import annotations

import os
import tomllib
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urlparse

WIB_HOURS = 7


class ConfigError(ValueError):
    """A configuration error safe to show without exposing a credential."""


@dataclass(frozen=True)
class Target:
    username: str
    command: str


@dataclass(frozen=True)
class Runtime:
    wait_seconds: float
    account_delay_seconds: float
    timezone_offset_hours: int = WIB_HOURS
    notify_timeout_seconds: float = 10.0
    proxy_enabled: bool = False
    proxy: str = ""


@dataclass(frozen=True)
class Credentials:
    api_id: int
    api_hash: str
    sessions: tuple[str, ...]
    notify_token: str = ""
    notify_chat_id: str = ""


def read_dotenv(path: Path, env: dict[str, str]) -> None:
    """Load KEY=VALUE pairs without modifying the live system environment."""
    if not path.is_file():
        return
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("export "):
            line = line.removeprefix("export ")
        if "=" not in line:
            continue
        key, value = line.split("=", 1)
        key, value = key.strip(), value.strip()
        if len(value) >= 2 and value[0] == value[-1] and value[0] in "\"'":
            value = value[1:-1]
        env[key] = value


def parse_target(line: str) -> Target:
    """Strictly parse exactly one 'username:command' entry."""
    if ":" not in line:
        raise ConfigError("expected one bot entry in the form 'username:command'")
    username, command = (item.strip() for item in line.split(":", 1))
    username = username.removeprefix("@")
    if not username or " " in username:
        raise ConfigError("bot username is empty or contains whitespace")
    if username.startswith("http") or "/" in username:
        raise ConfigError("provide a bot username, not a URL")
    if not command or len(command) > 4096:
        raise ConfigError("bot command must contain 1-4096 characters")
    return Target(username, command)


def parse_targets(raw: str, origin: str) -> tuple[Target, ...]:
    """Reject malformed lines; silently skipping one would skip a check-in."""
    targets: list[Target] = []
    for number, line in enumerate(raw.splitlines(), 1):
        if line.strip():
            try:
                targets.append(parse_target(line.strip()))
            except ConfigError as exc:
                raise ConfigError(f"{origin}, line {number}: {exc}") from exc
    if not targets:
        raise ConfigError(f"no target bots configured ({origin} is empty)")
    return tuple(targets)


def _positive(raw: str, name: str, default: float) -> float:
    if not raw:
        return default
    try:
        value = float(raw)
    except ValueError as exc:
        raise ConfigError(f"{name} must be a number") from exc
    if not 0 <= value <= 3600:
        raise ConfigError(f"{name} must be between 0 and 3600 seconds")
    return value


def _bool(raw: str | bool | None, name: str) -> bool:
    if raw is None:
        return False
    if isinstance(raw, bool):
        return raw
    if raw.lower() in {"1", "true", "yes", "on"}:
        return True
    if raw.lower() in {"0", "false", "no", "off"}:
        return False
    raise ConfigError(f"{name} must be true or false")


def validate_proxy(url: str) -> str:
    if not url:
        return ""
    parts = urlparse(url)
    if parts.scheme not in {"socks5", "socks5h", "http", "https"}:
        raise ConfigError("proxy scheme must be socks5, socks5h, http, or https")
    if not parts.hostname or not parts.port:
        raise ConfigError("proxy must include hostname and port")
    return url


def read_settings(path: Path, *, config_override: bool = False):
    env = dict(os.environ)
    read_dotenv(Path(env.get("ENV_FILE", ".env")), env)
    cfg: dict = {}
    if path.is_file():
        with path.open("rb") as handle:
            cfg = tomllib.load(handle)
    elif config_override:
        raise ConfigError(f"configuration file not found: {path}")

    table = cfg.get("runtime", {})
    offset = table.get("timezone_offset_hours", WIB_HOURS)
    if isinstance(offset, bool) or not isinstance(offset, (int, float)) or not -12 <= offset <= 14:
        raise ConfigError("runtime.timezone_offset_hours must be between -12 and 14")
    for key in ("wait_seconds", "account_delay_seconds", "notify_timeout_seconds"):
        if key in table and (not isinstance(table[key], (int, float)) or table[key] < 0):
            raise ConfigError(f"runtime.{key} must be a non-negative number")
    seconds = _positive(env.get("WAIT_FOR_RESPONSE_SEC", ""), "WAIT_FOR_RESPONSE_SEC", table.get("wait_seconds", 5))
    delay = _positive(
        env.get("DELAY_BETWEEN_ACCOUNTS_SEC", ""), "DELAY_BETWEEN_ACCOUNTS_SEC", table.get("account_delay_seconds", 3)
    )
    timeout = _positive(
        env.get("NOTIFY_TIMEOUT_SEC", ""), "NOTIFY_TIMEOUT_SEC", table.get("notify_timeout_seconds", 10)
    )
    network = cfg.get("network", {})
    proxy_enabled = _bool(env.get("PROXY_ENABLED", network.get("enabled", False)), "PROXY_ENABLED")
    proxy = validate_proxy(env.get("TELEGRAM_PROXY", "") or network.get("url", ""))
    if proxy_enabled and not proxy:
        raise ConfigError("network.enabled/PROXY_ENABLED is true but no proxy URL is set")
    target_lines = env.get("BOTS", "").strip()
    if target_lines:
        origin = "BOTS"
    else:
        if not cfg.get("targets"):
            raise ConfigError("no targets configured; put [[targets]] in config.toml or set BOTS")
        target_lines = "\n".join(
            f"{entry.get('username', '')}:{entry.get('command', '')}"
            for entry in cfg["targets"]
            if isinstance(entry, dict)
        )
        origin = str(path)
    targets = parse_targets(target_lines, origin)

    try:
        api_id = int(env.get("API_ID", "0"))
    except ValueError as exc:
        raise ConfigError("API_ID must be an integer") from exc
    if api_id <= 0:
        raise ConfigError("API_ID is required and must be positive")
    api_hash = env.get("API_HASH", "")
    if not api_hash:
        raise ConfigError("API_HASH is required")
    sessions = tuple(line.strip() for line in env.get("SESSIONS", "").splitlines() if line.strip())
    if not sessions:
        raise ConfigError("SESSIONS is required; one Telethon session string per line")

    creds = Credentials(
        api_id=api_id,
        api_hash=api_hash,
        sessions=sessions,
        notify_token=env.get("TG_BOT_TOKEN", ""),
        notify_chat_id=env.get("TG_CHAT_ID", ""),
    )
    runtime = Runtime(
        wait_seconds=seconds,
        account_delay_seconds=delay,
        notify_timeout_seconds=timeout,
        timezone_offset_hours=int(offset),
        proxy_enabled=proxy_enabled,
        proxy=proxy,
    )
    return creds, targets, runtime
