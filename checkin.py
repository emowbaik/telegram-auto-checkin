#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
auto-checkin-tele — Send check-in commands to Telegram bots using user accounts.

Environment variables (all set as GitHub Secrets):
    API_ID        — Telegram application ID (from https://my.telegram.org/apps)
    API_HASH      — Telegram application hash
    SESSIONS      — Newline-separated Telethon session strings (one per account)
    BOTS          — Newline-separated bot configs in "username:command" format
                    If omitted, defaults to freexzteam_bot and sheeridverifier_bot
    TG_BOT_TOKEN  — (optional) Telegram bot token for result notifications
    TG_CHAT_ID    — (optional) Telegram chat ID to receive notifications
"""

import asyncio
import os
import sys
import requests
from datetime import datetime, timezone, timedelta

try:
    from telethon import TelegramClient
    from telethon.sessions import StringSession
    from telethon.errors import (
        FloodWaitError,
        UserDeactivatedBanError,
        AuthKeyUnregisteredError,
        SessionRevokedError,
    )
except ImportError:
    print("❌ Telethon not installed. Run: pip install telethon")
    sys.exit(1)


# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------

API_ID   = int(os.environ.get("API_ID", "0") or "0")
API_HASH = os.environ.get("API_HASH", "")

TG_BOT_TOKEN = os.environ.get("TG_BOT_TOKEN", "")
TG_CHAT_ID   = os.environ.get("TG_CHAT_ID", "")

WIB = timezone(timedelta(hours=7))

# Seconds to wait after sending a command before reading the bot's reply
WAIT_FOR_RESPONSE_SEC = 5

# Delay between processing different accounts (to avoid rate limits)
DELAY_BETWEEN_ACCOUNTS_SEC = 3

# Default bots if BOTS env var is not set
DEFAULT_BOTS = [
    {"username": "freexzteam_bot",      "command": "/checkin"},
    {"username": "sheeridverifier_bot", "command": "/start"},
]


# ---------------------------------------------------------------------------
# Loaders
# ---------------------------------------------------------------------------

def load_sessions() -> list[str]:
    """
    Return list of Telethon session strings from the SESSIONS env var.
    Each non-empty line is treated as one session string.
    """
    raw = os.environ.get("SESSIONS", "").strip()
    if not raw:
        return []
    return [line.strip() for line in raw.splitlines() if line.strip()]


def load_bots() -> list[dict]:
    """
    Return list of {username, command} from the BOTS env var.
    Format: one entry per line → "botusername:command"

    Example BOTS value:
        freexzteam_bot:/checkin
        sheeridverifier_bot:/start
    """
    raw = os.environ.get("BOTS", "").strip()
    if not raw:
        print("ℹ️  BOTS not set — using default bot list.")
        return DEFAULT_BOTS

    bots: list[dict] = []
    for line_no, line in enumerate(raw.splitlines(), 1):
        line = line.strip()
        if not line:
            continue
        if ":" not in line:
            print(f"⚠️  BOTS line {line_no} malformed (expected username:command) — skipped")
            continue
        username, command = line.split(":", 1)
        username = username.strip().lstrip("@")
        command  = command.strip()
        if username and command:
            bots.append({"username": username, "command": command})
        else:
            print(f"⚠️  BOTS line {line_no} has empty username or command — skipped")
    return bots


# ---------------------------------------------------------------------------
# Notification
# ---------------------------------------------------------------------------

def send_telegram_notification(message: str) -> None:
    """Send a summary message via Telegram bot (HTML parse mode)."""
    print("\n" + "=" * 45)
    print(message)
    print("=" * 45)

    if not TG_BOT_TOKEN or not TG_CHAT_ID:
        print("ℹ️  TG_BOT_TOKEN / TG_CHAT_ID not configured — skipping notification.")
        return

    try:
        resp = requests.post(
            f"https://api.telegram.org/bot{TG_BOT_TOKEN}/sendMessage",
            json={
                "chat_id":    TG_CHAT_ID,
                "text":       message,
                "parse_mode": "HTML",
            },
            timeout=10,
        )
        if resp.status_code == 200:
            print("📨 Telegram notification sent.")
        else:
            print(f"⚠️  Notification failed: {resp.status_code} — {resp.text}")
    except Exception as exc:
        print(f"⚠️  Notification exception: {exc}")


# ---------------------------------------------------------------------------
# Core checkin
# ---------------------------------------------------------------------------

async def checkin_for_session(
    session_str: str,
    bots: list[dict],
    index: int,
    total: int,
) -> list[dict]:
    """
    Connect to Telegram as the user represented by *session_str*, then send
    the configured command to each bot in *bots*.

    Returns a list of result dicts, one per bot interaction.
    """
    results: list[dict] = []
    prefix = f"[{index}/{total}]"
    print(f"\n{'─' * 45}")
    print(f"{prefix} Connecting to Telegram...")

    client = TelegramClient(StringSession(session_str), API_ID, API_HASH)

    try:
        await client.connect()

        if not await client.is_user_authorized():
            print(f"{prefix} ❌ Session not authorized (expired or revoked)")
            return [{"account": "unknown", "bot": "all", "status": "session_invalid", "reply": ""}]

        me = await client.get_me()
        account_name = (
            f"@{me.username}" if me.username else f"{me.first_name} (ID: {me.id})"
        )
        print(f"{prefix} ✅ Connected as {account_name}")

        for bot in bots:
            bot_username = bot["username"]
            command      = bot["command"]
            print(f"  → Sending '{command}' to @{bot_username} ...")

            try:
                await client.send_message(bot_username, command)
                await asyncio.sleep(WAIT_FOR_RESPONSE_SEC)

                # Read last message in the chat (should be bot's reply)
                messages = await client.get_messages(bot_username, limit=1)
                reply = (messages[0].text or "(no text)") if messages else "(no response)"
                if len(reply) > 250:
                    reply = reply[:250] + "…"

                print(f"     ✅ Reply: {reply}")
                results.append({
                    "account": account_name,
                    "bot":     bot_username,
                    "status":  "success",
                    "reply":   reply,
                })

            except FloodWaitError as exc:
                wait_sec = exc.seconds
                print(f"     ⏳ FloodWait — need to wait {wait_sec}s. Skipping this bot.")
                results.append({
                    "account": account_name,
                    "bot":     bot_username,
                    "status":  f"flood_wait_{wait_sec}s",
                    "reply":   "",
                })

            except Exception as exc:
                print(f"     ❌ Error: {exc}")
                results.append({
                    "account": account_name,
                    "bot":     bot_username,
                    "status":  "error",
                    "reply":   str(exc)[:200],
                })

    except (UserDeactivatedBanError, AuthKeyUnregisteredError, SessionRevokedError) as exc:
        print(f"{prefix} 🚫 Account banned or session revoked: {exc}")
        results.append({
            "account": "banned/revoked",
            "bot":     "all",
            "status":  "banned",
            "reply":   str(exc)[:200],
        })

    except Exception as exc:
        print(f"{prefix} ❌ Connection error: {exc}")
        results.append({
            "account": "unknown",
            "bot":     "all",
            "status":  "connection_error",
            "reply":   str(exc)[:200],
        })

    finally:
        try:
            await client.disconnect()
        except Exception:
            pass

    return results


# ---------------------------------------------------------------------------
# Build notification message
# ---------------------------------------------------------------------------

def build_notification(all_results: list[list[dict]], now: str) -> str:
    """Format a human-readable HTML summary for Telegram."""
    lines = [
        "🤖 <b>Auto Checkin Report</b>",
        f"⏱️ {now}",
        "",
    ]

    for session_results in all_results:
        if not session_results:
            continue

        account = session_results[0].get("account", "unknown")
        lines.append(f"👤 <b>{account}</b>")

        for r in session_results:
            bot    = r.get("bot", "?")
            status = r.get("status", "?")
            reply  = r.get("reply", "")

            if status == "success":
                icon = "✅"
                detail = reply or "OK"
            elif "flood" in status:
                icon   = "⏳"
                detail = status
            elif status in ("banned", "session_invalid", "session_revoked"):
                icon   = "🚫"
                detail = status
            else:
                icon   = "❌"
                detail = reply or status

            lines.append(f"  {icon} @{bot}: {detail}")

        lines.append("")

    return "\n".join(lines).strip()


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

async def main() -> None:
    if not API_ID or not API_HASH:
        print(
            "❌ API_ID and API_HASH are required.\n"
            "   Set them as GitHub Secrets and pass via workflow env."
        )
        sys.exit(1)

    sessions = load_sessions()
    if not sessions:
        print(
            "❌ No sessions found.\n"
            "   Set the SESSIONS GitHub Secret (one session string per line).\n"
            "   Generate session strings using: python generate_session.py"
        )
        sys.exit(1)

    bots = load_bots()
    if not bots:
        print("❌ No bots configured. Check the BOTS secret format.")
        sys.exit(1)

    now   = datetime.now(WIB).strftime("%Y-%m-%d %H:%M WIB")
    total = len(sessions)

    print("🚀 auto-checkin-tele starting")
    print(f"   Sessions : {total}")
    print(f"   Bots     : {', '.join('@' + b['username'] for b in bots)}")
    print(f"   Time     : {now}")

    all_results: list[list[dict]] = []

    for i, session_str in enumerate(sessions, 1):
        result = await checkin_for_session(session_str, bots, i, total)
        all_results.append(result)
        if i < total:
            await asyncio.sleep(DELAY_BETWEEN_ACCOUNTS_SEC)

    # Summary log
    print(f"\n{'=' * 45}")
    print(f"📊 Done — {total} account(s) processed")

    # Send notification
    message = build_notification(all_results, now)
    send_telegram_notification(message)


if __name__ == "__main__":
    asyncio.run(main())
