# LinkedIn Post Automation — Setup Guide

Generates one LinkedIn post per week, in your voice, grounded in current iGaming affiliate news. Delivers it to your Telegram, ready to copy-paste.

---

## What It Does

Every time it runs (you set the schedule):
1. Scrapes iGB, Gambling Insider, CalvinAyre, AffiliateINSIDER, EGR for relevant news
2. Picks the most iGaming-affiliate-relevant stories
3. Rotates through your 3 content pillars (so posts stay varied week to week)
4. Calls Claude to draft a post in your voice — grounded in current news, not a news recap
5. Sends it to you on Telegram, formatted and ready to post

---

## One-Time Setup (15 minutes)

### Step 1 — Install dependencies

```bash
pip install anthropic requests beautifulsoup4 feedparser python-telegram-bot
```

### Step 2 — Get your Anthropic API key

1. Go to https://console.anthropic.com
2. Create an API key
3. Copy it

### Step 3 — Create a Telegram bot

1. Open Telegram, search for **@BotFather**
2. Send `/newbot` and follow the prompts
3. Copy the **bot token** it gives you (looks like `123456:ABC-DEF...`)
4. Open your new bot in Telegram and send it any message (e.g. "hello")

### Step 4 — Get your Telegram Chat ID

```bash
export TELEGRAM_BOT_TOKEN=your_token_here
python3 get_chat_id.py
```

Copy the Chat ID it prints.

### Step 5 — Set your environment variables

Create a `.env` file in this folder:

```
ANTHROPIC_API_KEY=sk-ant-...
TELEGRAM_BOT_TOKEN=123456:ABC-DEF...
TELEGRAM_CHAT_ID=987654321
```

Or export them directly:

```bash
export ANTHROPIC_API_KEY=sk-ant-...
export TELEGRAM_BOT_TOKEN=123456:ABC-DEF...
export TELEGRAM_CHAT_ID=987654321
```

### Step 6 — Test it manually

```bash
python3 weekly_post_generator.py
```

You should receive a Telegram message within ~30 seconds.

---

## Scheduling (Run Automatically Every Week)

### Option A — Mac/Linux (cron job)

Run every Monday at 8am Malta time (CET = UTC+1):

```bash
crontab -e
```

Add this line:

```
0 8 * * 1 cd /path/to/linkedin-automation && ANTHROPIC_API_KEY=xxx TELEGRAM_BOT_TOKEN=xxx TELEGRAM_CHAT_ID=xxx python3 weekly_post_generator.py >> cron.log 2>&1
```

### Option B — Free cloud scheduler (no computer needed)

Use **GitHub Actions** (free):

1. Push this folder to a private GitHub repo
2. Create `.github/workflows/weekly_post.yml`:

```yaml
name: Weekly LinkedIn Post

on:
  schedule:
    - cron: '0 7 * * 1'  # Every Monday 7am UTC (8am Malta)
  workflow_dispatch:       # Also allows manual trigger

jobs:
  generate:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      - uses: actions/setup-python@v4
        with:
          python-version: '3.11'
      - run: pip install anthropic requests beautifulsoup4 feedparser
      - run: python3 weekly_post_generator.py
        env:
          ANTHROPIC_API_KEY: ${{ secrets.ANTHROPIC_API_KEY }}
          TELEGRAM_BOT_TOKEN: ${{ secrets.TELEGRAM_BOT_TOKEN }}
          TELEGRAM_CHAT_ID: ${{ secrets.TELEGRAM_CHAT_ID }}
```

3. Add your secrets in GitHub → Repo Settings → Secrets and variables → Actions

That's it. Free, runs in the cloud, no computer needs to be on.

---

## What You Receive on Telegram

```
📝 LinkedIn Post Ready
2026-03-24 08:00
Pillar: affiliate tracking & technology
Inspired by: [iGB] How postback fraud is evolving in 2026

─────────────────────

[The full post, ready to copy-paste]

─────────────────────
✅ Copy and post on LinkedIn
⏰ Best time: Tue–Thu 8–10am CET
```

---

## Customisation

**Change posting day/time**: Edit the cron schedule.

**Add more news sources**: Add RSS feed URLs to the `RSS_FEEDS` list in the script.

**Change content pillars**: Edit the `CONTENT_PILLARS` list. Add or remove pillars as your focus evolves.

**Run more frequently**: Change the cron to `0 8 * * 1,4` for Monday + Thursday (2x/week).

---

## Cost

- **Anthropic API**: ~$0.01–0.03 per post (Claude Sonnet). 1 post/week = pennies per month.
- **Telegram**: Free.
- **GitHub Actions**: Free (2,000 minutes/month, this uses ~1 minute per run).

Total: effectively free.

---

## Troubleshooting

**No Telegram message received**: Run `get_chat_id.py` again and make sure you've messaged your bot first.

**"Missing environment variables" error**: Check your `.env` file or exports.

**Empty news / no stories found**: RSS feeds occasionally go down. The script will still generate a post using your content pillars — it just won't be news-inspired that week.

**Post doesn't sound right**: The script uses your voice guidelines baked into the system prompt. If a post is off, you can run it again — Claude will generate a different angle. Over time, reply to the Telegram message with feedback and we can refine the prompt.
