"""Interactive Rich menu and non-interactive / GitHub Actions entry point."""

from __future__ import annotations

import argparse
import asyncio
import os
from datetime import datetime, timedelta, timezone
from pathlib import Path

from . import __version__
from .config import ConfigError, read_settings
from .notifier import Notifier
from .results import build_report
from .runner import CheckinRunner, totals


def parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="auto-checkin",
        description="Send daily commands to Telegram bots using Telethon sessions.",
    )
    p.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    p.add_argument("--config", type=Path, default=Path("config.toml"), help="TOML settings (default: config.toml)")
    p.add_argument(
        "--bot", action="append", metavar="USERNAME:COMMAND", help="target override; repeat for multiple targets"
    )
    p.add_argument("--non-interactive", action="store_true", help="one run, no menu; required by GitHub Actions")
    p.add_argument("--check-config", action="store_true", help="validate credentials/configuration without connecting")
    p.add_argument("--strict", action="store_true", help="exit 1 if any target fails (default: fail only if all fail)")
    return p


def run_once(args) -> int:
    credentials, targets, runtime = read_settings(args.config, config_override=bool(args.config.is_absolute()))
    results = asyncio.run(CheckinRunner(credentials, targets, runtime).run())
    counts = totals(results, len(credentials.sessions))
    timestamp = datetime.now(timezone(timedelta(hours=runtime.timezone_offset_hours))).strftime("%Y-%m-%d %H:%M UTC%z")
    summary = f"📊 Accounts: {counts.accounts} · sent: {counts.sent} · other: {len(results) - counts.sent}"
    print(summary)
    notifier = Notifier(credentials.notify_token, credentials.notify_chat_id, runtime.notify_timeout_seconds)
    notifier.send(build_report(results, timestamp))
    failed = list(filter(lambda result: not result.ok, results))
    if args.strict and failed:
        return 1
    return 0 if counts.sent else 1


def _interactive(args) -> int:
    try:
        from rich.console import Console
        from rich.table import Table
    except ImportError as exc:
        raise ConfigError("interactive mode needs `pip install -r requirements.txt`") from exc

    console = Console()
    while True:
        console.rule(f"auto-checkin [bold]{__version__}[/bold]")
        console.print("1. [bold]Run check-in[/bold]")
        console.print("2. Show configuration (credentials hidden)")
        console.print("3. Exit")
        choice = console.input("\nSelect [1/2/3]: ").strip()
        if choice == "1":
            try:
                result = run_once(args)
                console.print(f"exit code: {result}")
            except (ConfigError, RuntimeError) as exc:
                console.print(f"[red]{exc}[/red]")
        elif choice == "2":
            config_path = args.config
            console.print(f"config: [cyan]{config_path}[/cyan]")
            console.print(f"config file present: {config_path.is_file()}")
            try:
                credentials, targets, runtime = read_settings(config_path)
                table = Table(show_header=False)
                table.add_row("Telegram API", "configured")
                table.add_row("Accounts", str(len(credentials.sessions)))
                table.add_row("Targets", ", ".join(f"@{t.username}" for t in targets))
                table.add_row(
                    "Notify", "enabled" if credentials.notify_token and credentials.notify_chat_id else "disabled"
                )
                table.add_row("Proxy", "enabled" if runtime.proxy_enabled else "disabled (direct)")
                console.print(table)
            except ConfigError as exc:
                console.print(f"[red]{exc}[/red]")
        elif choice == "3":
            return 0


def main(argv: list[str] | None = None) -> int:
    parser_instance = parser()
    args = parser_instance.parse_args(argv)
    if args.bot:
        os.environ["BOTS"] = "\n".join(args.bot)
    try:
        if args.check_config:
            credentials, targets, _runtime = read_settings(args.config, config_override=True)
            print(f"valid: {len(credentials.sessions)} accounts, {len(targets)} target(s)")
            return 0
        if args.non_interactive or not os.isatty(0) or os.environ.get("GITHUB_ACTIONS") == "true":
            return run_once(args)
        return _interactive(args)
    except ConfigError as exc:
        print(f"error: {exc}")
        return 2
    except KeyboardInterrupt:
        print("cancelled")
        return 130


if __name__ == "__main__":
    raise SystemExit(main())
