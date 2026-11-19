"""Sequential check-in orchestration.

Accounts and targets are processed in order, with no concurrent mutations to
Telegram chats, and a dead account cannot abort its neighbours.
"""

from __future__ import annotations

import asyncio
from collections.abc import Callable, Sequence
from pathlib import Path

from .config import Credentials, Runtime, Target
from .results import Result, Totals
from .telegram import TelegramConnection, proxy_options


class CheckinRunner:
    def __init__(
        self,
        credentials: Credentials,
        targets: Sequence[Target],
        runtime: Runtime,
        *,
        connection_factory: Callable = TelegramConnection,
        session_directory: Path | None = None,
        log: Callable[[str], None] = print,
    ):
        self.credentials = credentials
        self.targets = tuple(targets)
        self.runtime = runtime
        self.connection_factory = connection_factory
        self.session_directory = session_directory
        self.log = log

    async def run(self) -> list[Result]:
        results: list[Result] = []
        accounts = self.credentials.sessions
        for index, session in enumerate(accounts, 1):
            prefix = f"[{index}/{len(accounts)}]"
            self.log(f"\n{prefix} Connecting to Telegram...")
            proxy = proxy_options(self.runtime.proxy) if self.runtime.proxy_enabled else None
            try:
                async with self.connection_factory(
                    session,
                    self.credentials.api_id,
                    self.credentials.api_hash,
                    proxy=proxy,
                    session_directory=self.session_directory,
                ) as connection:
                    if not await connection.is_user_authorized():
                        self.log(f"{prefix} 🚫 Session expired or revoked")
                        results.append(Result("unknown", "all", "session_invalid"))
                        continue
                    account = await connection.get_identity()
                    self.log(f"{prefix} ✅ Connected as {account}")
                    for target in self.targets:
                        results.append(await self._target(connection, account, target))
            except Exception as exc:  # noqa: BLE001 - each account is isolated by design
                name = type(exc).__name__
                status = (
                    "banned"
                    if name in {"UserDeactivatedBanError", "AuthKeyUnregisteredError", "SessionRevokedError"}
                    else "connection_error"
                )
                self.log(f"{prefix} ❌ {name}")
                results.append(Result("unknown", "all", status, str(exc)[:180]))
            if index < len(accounts):
                await asyncio.sleep(self.runtime.account_delay_seconds)
        return results

    async def _target(self, connection, account: str, target: Target) -> Result:
        self.log(f"  → Sending '{target.command}' to @{target.username} ...")
        try:
            await connection.send_and_read(target.username, target.command)
            await asyncio.sleep(self.runtime.wait_seconds)
            reply = await connection.latest_message(target.username)
            self.log(f"     ✅ Reply: {reply[:250]}{'…' if len(reply) > 250 else ''}")
            return Result(account, target.username, "success", reply)
        except asyncio.CancelledError:
            raise  # an operator's cancellation must not be swallowed as a bot error
        except Exception as exc:  # noqa: BLE001 - isolated target failure
            name = type(exc).__name__
            wait = int(getattr(exc, "seconds", 0) or 0)
            if name == "FloodWaitError":
                self.log(f"     ⏳ FloodWait {wait}s — skipping this target")
                return Result(account, target.username, f"flood_wait_{wait}s")
            if name in {"UserDeactivatedBanError", "AuthKeyUnregisteredError", "SessionRevokedError"}:
                return Result(account, target.username, "banned", str(exc)[:180])
            self.log(f"     ❌ {name}")
            return Result(account, target.username, "error", str(exc)[:160])


def totals(results: Sequence[Result], accounts: int) -> Totals:
    return Totals(
        accounts=accounts,
        sent=sum(result.ok for result in results),
        failed=sum(result.status in {"connection_error", "error", "banned"} for result in results),
        unauthorized=sum(result.status == "session_invalid" for result in results),
    )
