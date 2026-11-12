<h1 align="center">Manhwa Bot</h1>

<p align="center">
  A Telegram manga/manhwa downloader built on Pyrogram (Kurigram).
</p>

<p align="center">
  <a href="https://github.com/Dra-Sama/Manhwa-Bot/stargazers"><img src="https://img.shields.io/github/stars/Dra-Sama/Manhwa-Bot?style=flat&logo=github&labelColor=292c3b&color=yellow" alt="Stars"></a>
  <a href="https://github.com/Dra-Sama/Manhwa-Bot/fork"><img src="https://img.shields.io/github/forks/Dra-Sama/Manhwa-Bot?style=flat&logo=github&labelColor=292c3b" alt="Forks"></a>
  <a href="https://github.com/Dra-Sama/Manhwa-Bot/issues"><img src="https://img.shields.io/github/issues/Dra-Sama/Manhwa-Bot?labelColor=292c3b" alt="Issues"></a>
  <a href="https://github.com/Dra-Sama/Manhwa-Bot/blob/v3/LICENSE"><img src="https://img.shields.io/github/license/Dra-Sama/Manhwa-Bot?labelColor=292c3b" alt="License"></a>
  <a href="https://t.me/Wizard_Bots"><img src="https://img.shields.io/badge/Telegram-Channel-9cf?logo=telegram&labelColor=292c3b" alt="Channel"></a>
  <a href="https://t.me/WizardBotHelper"><img src="https://img.shields.io/badge/Telegram-Support-9cf?logo=telegram&labelColor=292c3b" alt="Support"></a>
</p>

> If you like this project, give it a ⭐ and follow on GitHub.

## Features

- Custom thumbnails
- First and last page banners inside PDFs
- Output format matched to your channel style
- Custom captions (HTML supported)
- Merge multiple chapters into one file (2, 5, 10+)
- Password-protected PDFs
- Cache/dump channel for direct uploads

## Requirements

- Python 3.11+
- A MongoDB database ([mongodb.com](https://www.mongodb.com))
- Telegram API credentials from [my.telegram.org](https://my.telegram.org)
- A bot token from [@BotFather](https://t.me/BotFather)

## Configuration

Copy `.env.example` to `.env` and fill it in. **Never commit `.env`.**

| Variable | Required | Description |
|---|---|---|
| `API_ID` | ✅ | From my.telegram.org |
| `API_HASH` | ✅ | From my.telegram.org |
| `BOT_TOKEN` | ✅ | From @BotFather |
| `DB_URL` | ✅ | MongoDB connection string |
| `DB_NAME` | | Database name (default `test`) |
| `ADMINS` | | Admin user IDs, space or comma separated |
| `OWNER` | | Owner's Telegram username |
| `LOG_CHANNEL` | | Channel ID for bot logs |
| `UPDATE_CHANNEL` | | Channel ID for new chapter updates |
| `CONSTANT_DUMP_CHANNEL` | | Channel ID for the cache/dump channel |
| `IS_PRIVATE` | | `true` to restrict the bot to admins |
| `WEBS_HOST` | | `true` on Koyeb/Render, leave empty on a VPS |
| `FORCE_SUB_CHANNEL` | | `Button Name:channel_username`, comma separated |
| `DURATION` | | Shortener validity in hours (default `20`) |

## Running

### Locally

```bash
git clone https://github.com/Dra-Sama/Manhwa-Bot.git
cd Manhwa-Bot
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env   # then edit it
python main.py
```

### Docker

```bash
git clone https://github.com/Dra-Sama/Manhwa-Bot.git
cd Manhwa-Bot
cp .env.example .env   # then edit it
sudo apt install docker.io
sudo docker build -t manhwabot .
sudo docker run -d --name manhwabot --env-file .env manhwabot
```

Stop it with `sudo docker stop manhwabot`.

### Koyeb

[![Deploy to Koyeb](https://www.koyeb.com/static/images/deploy/button.svg)](https://app.koyeb.com/deploy?type=git&repository=github.com/Dra-Sama/Manhwa-Bot&name=manhwabot)

Set the environment variables in the Koyeb dashboard, and set `WEBS_HOST=true`.

## Commands

Paste this into @BotFather → `/setcommands`:

```
start - Check the bot
help - Show help
search - Search manhwa
subs - Manage subscriptions
unsubs - Unsubscribe from a manga
queue - Check your queue
clean_tasks - Delete pending tasks
user_setting - User settings
stats - Bot stats
```

**Admin only:** `clean`, `import`, `export`, `shell`, `restart`, `broadcast`, `pbroadcast`, `add`, `del`, `premium_users`, `del_expired`

## Authors

<table>
  <tr>
    <td align="center">
      <a href="https://github.com/Dra-Sama">
        <img width="100" src="https://avatars.githubusercontent.com/u/106417401" alt="Dra Sama"><br>
        <b>Dra Sama</b>
      </a>
    </td>
    <td align="center">
      <a href="https://t.me/Shanks_Pro"><b>Shanks Kun</b></a>
    </td>
    <td align="center">
      <a href="https://t.me/V_Sbotmaker"><b>V_Sbotmaker</b></a>
    </td>
  </tr>
</table>

Thanks to all [contributors](https://github.com/Dra-Sama/Manhwa-Bot/graphs/contributors).

## Disclaimer

This project is provided for educational purposes. You are responsible for how you use it and for complying with the terms of service and copyright laws that apply to the content you download or distribute.
