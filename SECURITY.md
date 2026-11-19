# Security

https://github.com/emowbaik/telegram-auto-checkin/security/advisories

Please do not open a public issue containing a leaked credential. If you find a vulnerability, use a private GitHub security advisory for this repository instead.

## Never commit secrets

- Telethon session strings (`SESSIONS`)
- Telegram API hashes (`API_HASH`)
- Bot credentials (`TG_BOT_TOKEN`, target usernames)
- `.env` files, `.session` files, session journals, and local data output

Only `API_ID` is potentially less sensitive by itself; keep the full credential set private anyway. `.gitignore` already covers local credentials and runtime data. The neutral placeholder `dump` in examples is intentional, not a live username.

## Response to exposure

1. Delete active Telethon sessions from **Telegram → Settings → Devices → Active Sessions**.
2. Revoke/rotate the application API hash and the notification bot token.
3. Generate a new session (`.session` or session-string) and rotate it in GitHub Secrets.
4. Revoke the compromised repository secret if a GitHub token was exposed.
5. Check the repository and pushed history before assuming deletion is enough; secrets in a public fork may already be copied.

This tool provides no recovery for a revoked session and no automated IP-assignment functionality.
