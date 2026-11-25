# Telegram Auto-Checkin

Configuration-driven daily check-in via Telegram MTProto (Telethon), with an interactive menu, a headless CI mode, and per-account notifications.

**Target bot:** `dump`

## Features

- Multi-account and multi-target support; one failed account does not abort its neighbours.
- Same secrets as before: `API_ID`, `API_HASH`, `SESSIONS`, optional `BOTS`, and report credentials.
- Interactive **Rich** menu for manual runs, plus **one-command** non-interactive mode for Actions/systemd.
- TOML defaults, strict input validation, explicit manual proxy (never automatic IP detection).
- HTML-escaped reports, isolated target failures, session persistence outside the checkout, tests and lint/dependency-audit jobs.

## Quick start

Requires Python 3.11+.

```bash
git clone https://github.com/emowbaik/telegram-auto-checkin.git
cd telegram-auto-checkin
python3.11 -m venv .venv
source .venv/bin/activate
pip install -r requirements-dev.txt
cp .env.example .env
# Fill .env locally (never commit it)
```

Interactive mode (TTY):

```bash
python main.py
```

One-off headless run:

```bash
python main.py --non-interactive
```

For a temporary override without changing `config.toml` or `BOTS`:

```bash
python main.py --non-interactive --bot 'dump:/checkin'
```

Configuration check (does not connect):

```bash
python main.py --check-config --config config.toml
```

Default exit policy: success means **every** account×target pair sent a verified reply; a missing reply or any failed target exits `1`. Add `--strict` for the same behaviour explicitly.

## Secrets and sessions

Create an application at [my.telegram.org/apps](https://my.telegram.org/apps), then generate each session **interactively and only once** per Telegram account:

```bash
python generate_session.py
```

Store credentials in **Settings → Secrets and variables → Actions**, or a locally ignored `.env` file.

| Secret / environment variable | Required | Purpose |
|---|---|---|
| `API_ID` | yes | Telegram application ID |
| `API_HASH` | yes | Telegram application hash |
| `SESSIONS` | yes | One Telethon session string per line |
| `BOTS` | no | `username:command` per line; overrides every target in `config.toml` |
| `TG_BOT_TOKEN` | no | Bot token used only for the summary report |
| `TG_CHAT_ID` | no | Chat ID used only for the summary report |

`BOTS` format (repeat for additional targets):

```text
dump:/checkin
```

Sessions, passwords, API hashes, target usernames and report credentials remain outside source control. `.env`, `.env.*`, session files and generated data are gitignored. After a Telethon DC refresh the adapter stores the updated session under `~/.local/share/auto-checkin/` (directory `0700`, files `0600`), never in the repository. Keep a backup because invalid/revoked sessions cannot be renewed by a check-in script. A status counts as success only when a **new incoming message from that bot** is verified; old or outgoing messages never count.

## Configuration

[`config.toml`](config.toml) contains public, non-secret defaults.

```toml
[runtime]
wait_seconds = 5
account_delay_seconds = 3
notify_timeout_seconds = 10
timezone_offset_hours = 7

[network]
enabled = false
url = ""

[[targets]]
username = "dump"
command = "/checkin"
```

| Setting | Effect |
|---|---|
| `wait_seconds` | Delay after sending a command before fetching the bot's last reply. |
| `account_delay_seconds` | Delay between accounts to reduce flood-risk. |
| `notify_timeout_seconds` | Bot API report HTTP timeout. |
| `timezone_offset_hours` | Report timezone; `7` means WIB. |
| `[[targets]]` | Repeat this table for every desired target. |
| `network.enabled` | Opt-in proxy switch; `false` uses the host connection directly. |
| `network.url` | `http`, `https`, `socks5` or `socks5h` URL, with optional authentication. |

Environment overrides: `WAIT_FOR_RESPONSE_SEC`, `DELAY_BETWEEN_ACCOUNTS_SEC`, `NOTIFY_TIMEOUT_SEC`, `PROXY_ENABLED`, `TELEGRAM_PROXY`. No proxy endpoint is discovered automatically.

## GitHub Actions

Two scheduled runs are configured in [checkin.yml](.github/workflows/checkin.yml):

- **Primary:** `0 0 * * *` = **07:00 WIB** daily.
- **Backup:** `10 1 * * *` = **08:10 WIB** daily (GitHub can drop primary scheduled ticks).

A concurrency group prevents collisions between the primary and the backup. Run history is retained for audit; Dependabot and the weekly lock-refresh PR keep repository activity high enough to avoid GitHub's 60-day scheduled-workflow timeout. The check-in job carries only `contents: read` and never holds a repository write token.

Secrets are checked before dependencies are installed; a missing required secret fails immediately. Results are reported to `TG_CHAT_ID` if notification credentials are configured; the full report is **not** printed to the public job log.

Enable the repo in the **Actions** tab, then use **Run workflow** before waiting for the next scheduled slot.

## Project layout

```text
main.py                    # CLI entry point
checkin.py                 # Backward-compatible headless wrapper
auto_checkin/
  cli.py                   # interactive/non-interactive application
  config.py                # environment, TOML, target validation
  runner.py                # sequential accounts + targets
  telegram.py              # Telethon boundary and session handling
  notifier.py              # one-shot Bot API report
  results.py               # outcome models + HTML-safe report
config.toml                # public defaults
generate_session.py        # one-time interactive session generator
data/                      # ignored runtime output (kept by .gitkeep)
tests/                     # mocked unit tests, no network/credentials
.github/workflows/ci.yml   # tests + dependency audit
.github/workflows/checkin.yml
```

See [docs/architecture.md](docs/architecture.md) for data flow and error handling.

## Development

```bash
pip install -r requirements-dev.txt
python -m unittest discover -s tests -v
ruff check auto_checkin tests main.py checkin.py
```

`requirements.txt` contains direct runtime requirements; `requirements-dev.txt` adds lint tooling. `requirements.lock` hashes the full resolution for the CI platform (Linux x86_64 / CPython 3.11). CI checks that locked versions satisfy every declared constraint, and a weekly workflow opens a PR to refresh the lock when upstream releases appear; see [docs/dependencies.md](docs/dependencies.md). `pyproject.toml` also exposes `auto-checkin` via `pip install -e .`.

## Responsible use

This project acts as a Telegram **user client** through MTProto. Automating a user account can trigger rate-limits or account restrictions. Use low-frequency commands, never share API credentials or session strings, and review Telegram's applicable terms before operating unattended.

See [SECURITY.md](SECURITY.md) for secret handling and reporting a security issue.
