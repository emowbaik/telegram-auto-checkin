"""Telethon adapter.

The rest of the application depends on this small surface, not on Telethon
itself, so unit tests do not need a network or a Telethon import.
"""

from __future__ import annotations

from pathlib import Path


def proxy_options(url: str) -> dict | None:
    """Translate proxy URLs to Telethon's dict format without guessing an IP.

    This must only be called when the user explicitly enables a proxy. Telethon
    does not support the socks5h spelling, so that alias means SOCKS5 with
    remote DNS enabled (rdns=True).
    """
    from urllib.parse import unquote, urlparse

    if not url:
        return None
    parsed = urlparse(url)
    proxy_type = {
        "socks5": "socks5",
        "socks5h": "socks5",
        "http": "http",
        "https": "https",
    }.get(parsed.scheme)
    if proxy_type is None:
        raise ValueError("unsupported proxy scheme")
    return {
        "proxy_type": proxy_type,
        "addr": parsed.hostname,
        "port": parsed.port,
        "rdns": parsed.scheme != "http",
        "username": unquote(parsed.username) if parsed.username else None,
        "password": unquote(parsed.password) if parsed.password else None,
    }


def make_session_storage(session_string: str, directory: Path):
    """Persist the session beside (never inside) the repository checkout."""
    directory.mkdir(parents=True, exist_ok=True)
    current = directory / "telegram-session.txt"
    previous = directory / "telegram-session.previous.txt"
    if current.is_file() and current.read_text(encoding="utf-8") != session_string:
        previous.write_text(current.read_text(encoding="utf-8"), encoding="utf-8")
    current.write_text(session_string + "\n", encoding="utf-8")
    return current


class TelegramConnection:
    def __init__(
        self,
        session_string: str,
        api_id: int,
        api_hash: str,
        *,
        proxy: dict | None = None,
        session_directory: Path | None = None,
    ):
        self.session_string = session_string
        self.api_id = api_id
        self.api_hash = api_hash
        self.proxy = proxy
        self.session_directory = session_directory
        self._client = None

    async def __aenter__(self):
        try:
            from telethon import TelegramClient
        except ImportError as exc:
            raise RuntimeError("telethon is not installed; run `pip install -r requirements.txt`") from exc

        from telethon.sessions import StringSession

        self._client = TelegramClient(
            StringSession(self.session_string),
            self.api_id,
            self.api_hash,
            proxy=self.proxy,
        )
        await self._client.connect()
        return self

    async def __aexit__(self, exc_type, exc, tb):
        if self._client is not None:
            try:
                await self._client.disconnect()
            except Exception:  # noqa: BLE001,S110 - cleanup cannot replace the original error
                pass  # never replace the actual connection or authorization error
        # Telethon can rotate the session upon refresh. Preserve the latest
        # validated string outside the repository so it can be reused.
        if exc_type is None and self._client is not None:
            try:
                session = self._client.session.save()
                if isinstance(session, str) and session:
                    make_session_storage(
                        session,
                        self.session_directory or (Path.home() / ".local" / "share" / "auto-checkin"),
                    )
            except (OSError, ValueError):
                pass  # session persistence is best-effort

    async def is_user_authorized(self) -> bool:
        return bool(await self._client.is_user_authorized())

    async def get_identity(self) -> str:
        me = await self._client.get_me()
        if not me:
            raise RuntimeError("session is no longer authorized")
        return f"@{me.username}" if me.username else f"{me.first_name} (ID: {me.id})"

    async def send_and_read(self, username: str, command: str) -> str:
        messages = await self._client.send_message(username, command)
        return getattr(messages, "text", None) or "(no text)"

    async def latest_message(self, username: str) -> str:
        messages = await self._client.get_messages(username, limit=1)
        return (messages[0].text or "(no text)") if messages else "(no response)"


def telethon_error_classes() -> tuple[type[Exception], ...]:
    """Resolve library-specific errors only after optional imports are present."""
    from telethon import errors

    return tuple(
        errors_cls
        for name in (
            "FloodWaitError",
            "UserDeactivatedBanError",
            "AuthKeyUnregisteredError",
            "SessionRevokedError",
        )
        if (errors_cls := getattr(errors, name, None)) is not None
    )
