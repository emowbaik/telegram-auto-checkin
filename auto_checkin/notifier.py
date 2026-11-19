"""One-shot Bot API reporting.

No automatic fallback to a third-party endpoint: the MTProto sessions and the
notification channel are independent credentials.
"""

from __future__ import annotations

import json
import urllib.error
import urllib.request


class Notifier:
    def __init__(self, token: str = "", chat_id: str = "", timeout: float = 10):
        self.token = token
        self.chat_id = chat_id
        self.timeout = timeout

    @property
    def configured(self) -> bool:
        return bool(self.token and self.chat_id)

    def send(self, message: str) -> bool:
        print("\n" + "=" * 45)
        print(message)
        print("=" * 45)
        if not self.configured:
            print("Telegram notification: disabled (missing TG_BOT_TOKEN / TG_CHAT_ID)")
            return False
        body = json.dumps(
            {
                "chat_id": self.chat_id,
                "text": message,
                "parse_mode": "HTML",
                "disable_web_page_preview": True,
            }
        ).encode()
        request = urllib.request.Request(
            f"https://api.telegram.org/bot{self.token}/sendMessage",
            data=body,
            headers={"Accept": "application/json", "Content-Type": "application/json"},
            method="POST",
        )
        try:
            with urllib.request.urlopen(request, timeout=self.timeout) as response:
                if response.status == 200:
                    print("Telegram notification: sent")
                    return True
                print(f"Telegram notification: HTTP {response.status}")
        except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError) as exc:
            print(f"Telegram notification: failed ({type(exc).__name__})")
        return False
