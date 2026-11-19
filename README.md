# Telegram Auto-Checkin

Automatically sends check-in commands to Telegram bots using your own user accounts, running daily via GitHub Actions.

**Target bot:** `dump`

---

## ✨ Features

- ✅ Multi-account support (unlimited accounts via GitHub Secrets)
- ✅ Multi-bot support (configurable via `BOTS` secret)
- ✅ Telegram notification report after each run
- ✅ Runs daily at **07:00 WIB** automatically
- ✅ Keeps GitHub Actions tab clean (only 1 run history kept)

---

## 🚀 Setup Guide

### Step 1 — Get Telegram API Credentials

1. Go to **https://my.telegram.org/apps**
2. Log in with your Telegram phone number
3. Create a new application (any name/platform)
4. Copy your **API ID** and **API Hash**

> ⚠️ Never share these. They grant access to your Telegram account.

---

### Step 2 — Generate Session String(s)

Run this **once per account on your local machine**:

```bash
# Install telethon locally
pip install telethon

# Run the session generator
python generate_session.py
```

The script will ask for your API ID, API Hash, and phone number (including country code, e.g. `+628xxx`). After entering the OTP, it prints your **session string**.

**Copy the session string** — you'll need it in Step 3.

For multiple accounts, repeat this for each account.

---

### Step 3 — Fork & Configure GitHub Secrets

1. **Fork** this repository to your GitHub account
2. Go to your fork → **Settings → Secrets and variables → Actions**
3. Add the following secrets:

| Secret Name   | Value | Required |
|---------------|-------|----------|
| `API_ID`      | Your Telegram API ID (number) | ✅ |
| `API_HASH`    | Your Telegram API Hash | ✅ |
| `SESSIONS`    | Session string(s) — one per line for multiple accounts | ✅ |
| `BOTS`        | Bot configs (see format below) — leave empty for defaults | ⬜ optional |
| `TG_BOT_TOKEN`| Bot token for result notifications | ⬜ optional |
| `TG_CHAT_ID`  | Chat ID to receive notifications | ⬜ optional |

#### `SESSIONS` format (multi-account):
```
1BVtsOHHBu3XXXXXXXXXXXXXXXXXXX...
1BVtsOHHBu4XXXXXXXXXXXXXXXXXXX...
```
Each line = one account's session string.

#### `BOTS` format (optional, overrides defaults):
```
freexzteam_bot:/checkin
sheeridverifier_bot:/start
```
Format: `botusername:command` — one per line. If left empty, the two default bots above are used.

---

### Step 4 — Enable GitHub Actions

1. Go to your fork → **Actions** tab
2. Click **"I understand my workflows, go ahead and enable them"** if prompted
3. To test immediately: click **"Telegram Daily Checkin"** → **"Run workflow"**

The workflow runs automatically every day at **07:00 WIB (00:00 UTC)**.

---

## 📁 File Structure

```
auto-checkin-tele/
├── checkin.py              # Main script — connects & sends commands
├── generate_session.py     # One-time local helper to generate session strings
├── requirements.txt        # Python dependencies
└── .github/
    └── workflows/
        └── checkin.yml     # GitHub Actions workflow definition
```

---

## 📊 Notification Example

After each run, you'll receive a Telegram message like:

```
🤖 Auto Checkin Report
⏱️ 2026-07-16 07:00 WIB

👤 @youraccount1
  ✅ @freexzteam_bot: Checkin berhasil! Reward: 50 poin
  ✅ @sheeridverifier_bot: Verified successfully!

👤 @youraccount2
  ✅ @freexzteam_bot: Anda sudah checkin hari ini
  ✅ @sheeridverifier_bot: Already verified today
```

---

## ⚙️ Customization

To add more bots or change commands, update the `BOTS` secret:

```
freexzteam_bot:/checkin
sheeridverifier_bot:/start
someotherbot:/daily
```

To change the schedule, edit `.github/workflows/checkin.yml`:
```yaml
- cron: '0 0 * * *'   # 07:00 WIB — change as needed
```
Use https://crontab.guru to generate cron expressions.

---

## ⚠️ Disclaimer

This project uses the **Telegram MTProto API** (not the Bot API) to act as a user client. Use responsibly and at your own risk. Automating user actions may violate Telegram's Terms of Service. The author is not responsible for any account restrictions.
