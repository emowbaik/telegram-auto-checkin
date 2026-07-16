#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
generate_session.py — One-time helper to generate a Telethon session string.

Run this on your LOCAL machine (not GitHub Actions):

    pip install telethon
    python generate_session.py

You will be prompted for:
  1. API_ID   → from https://my.telegram.org/apps
  2. API_HASH → from https://my.telegram.org/apps
  3. Phone number (with country code, e.g. +628xxx)
  4. OTP / 2FA password (if enabled)

After login, the script prints your SESSION STRING.
Copy it into your GitHub repository secret named SESSIONS.
For multiple accounts, repeat the process and paste each string on a new line.
"""

import asyncio

try:
    from telethon import TelegramClient
    from telethon.sessions import StringSession
except ImportError:
    print("❌ Telethon is not installed.")
    print("   Run:  pip install telethon")
    raise SystemExit(1)


async def main() -> None:
    print()
    print("=" * 55)
    print("   🔑  Telethon Session String Generator")
    print("=" * 55)
    print()
    print("  Get your credentials at: https://my.telegram.org/apps")
    print()

    api_id_raw = input("  API_ID   : ").strip()
    if not api_id_raw.isdigit():
        print("❌ API_ID must be a number.")
        return

    api_id   = int(api_id_raw)
    api_hash = input("  API_HASH : ").strip()

    if not api_hash:
        print("❌ API_HASH cannot be empty.")
        return

    print()
    print("  Logging in… You will receive a Telegram OTP code.")
    print()

    client = TelegramClient(StringSession(), api_id, api_hash)

    # start() handles phone + OTP + 2FA prompts interactively
    await client.start()

    session_string = client.session.save()
    me = await client.get_me()

    display_name = me.first_name or ""
    if me.username:
        display_name += f" (@{me.username})"
    display_name += f"  [ID: {me.id}]"

    print()
    print("=" * 55)
    print(f"  ✅ Logged in as: {display_name.strip()}")
    print()
    print("  📋 Session String — paste this into GitHub Secret SESSIONS:")
    print()
    print(session_string)
    print()
    print("=" * 55)
    print()
    print("  ⚠️  Keep this string private — it grants full account access.")
    print("  ℹ️  For multiple accounts: run this script once per account,")
    print("      then put each session string on a separate line in SESSIONS.")
    print()

    await client.disconnect()


if __name__ == "__main__":
    asyncio.run(main())
