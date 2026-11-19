"""Outcome types and the Telegram-safe summary renderer."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass


@dataclass(frozen=True)
class Result:
    account: str
    bot: str
    status: str
    reply: str = ""

    @property
    def ok(self) -> bool:
        return self.status == "success"


@dataclass(frozen=True)
class Totals:
    accounts: int
    sent: int
    failed: int
    unauthorized: int


def html_escape(text: str) -> str:
    """Escape dynamic text before embedding it in Telegram HTML."""
    return text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def compact_reply(text: str, limit: int = 700) -> str:
    clean = " ".join(text.split())
    return clean if len(clean) <= limit else clean[: limit - 1] + "…"


def build_report(results: Sequence[Result], timestamp: str) -> str:
    lines = ["🤖 <b>Auto Checkin Report</b>", f"⏱️ {html_escape(timestamp)}", ""]
    current = None
    for result in results:
        if result.account != current:
            current = result.account
            lines.append(f"👤 <b>{html_escape(current)}</b>")
        icon = {
            "success": "✅",
            "banned": "🚫",
            "session_invalid": "🚫",
            "session_revoked": "🚫",
        }.get(result.status, "⏳" if result.status.startswith("flood_wait") else "❌")
        detail = result.reply if result.status == "success" else result.reply or result.status
        lines.append(f"  {icon} @{html_escape(result.bot)}: {html_escape(compact_reply(detail))}")
    return "\n".join(lines)
