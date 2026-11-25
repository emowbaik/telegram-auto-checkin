"""Telethon adapter.

The rest of the application depends on this small surface, not on Telethon
itself, so unit tests do not need a network or a Telethon import.
"""

from __future__ import annotations

import asyncio
import os
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


def _write_private(path: Path, text: str) -> None:
    """Write a credential with 0600 even when the file already exists."""
    descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
        handle.write(text + "\n")
    os.chmod(path, 0o600)


def make_session_storage(session_string: str, directory: Path):
    """Persist the session with owner-only permissions, beside (never inside) the repo."""
    directory.mkdir(parents=True, exist_ok=True, mode=0o700)
    os.chmod(directory, 0o700)
    current = directory / "telegram-session.txt"
    previous = directory / "telegram-session.previous.txt"
    old = current.read_text(encoding="utf-8").rstrip("\r\n") if current.is_file() else ""
    if old and old != session_string:
        _write_private(previous, old)
    _write_private(current, session_string)
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

    async def send_and_wait_reply(self, username: str, command: str, delay: float = 0) -> tuple[int | None, str | None]:
        """Return (sent message id, reply) and accept only a newer message from that bot."""
        assert self._client is not None  # set by __aenter__ before any call
        sent = await self._client.send_message(username, command)
        sent_id = getattr(sent, "id", None)
        if delay > 0:
            await asyncio.sleep(delay)
        entity = await self._client.get_entity(username)
        bot_id = getattr(entity, "id", None)
        async for message in self._client.iter_messages(entity, min_id=sent_id or 0, limit=10):
            if sent_id is not None and getattr(message, "id", 0) <= sent_id:
                continue  # older message, never a reply to this command
            if getattr(message, "out", False):
                continue
            sender = getattr(message, "sender_id", None)
            if sender is None:
                sender_object = getattr(message, "from_id", None)
                sender = getattr(sender_object, "user_id", sender_object)
            if bot_id is not None and sender != bot_id:
                continue
            return sent_id, getattr(message, "text", None) or "(no text)"
        return sent_id, None
