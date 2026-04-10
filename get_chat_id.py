#!/usr/bin/env python3
"""
Quick helper to get your Telegram Chat ID.
Run once after creating your bot and sending it a message.

Usage:
  export TELEGRAM_BOT_TOKEN=your_token_here
  python3 get_chat_id.py
"""

import os
import requests

token = os.environ.get("TELEGRAM_BOT_TOKEN")
if not token:
    print("Set TELEGRAM_BOT_TOKEN environment variable first.")
    exit(1)

resp = requests.get(f"https://api.telegram.org/bot{token}/getUpdates")
data = resp.json()

if data.get("result"):
    chat_id = data["result"][0]["message"]["chat"]["id"]
    print(f"\n✅ Your Chat ID: {chat_id}\n")
    print(f"Add this to your .env or GitHub secrets as TELEGRAM_CHAT_ID")
else:
    print("\n❌ No messages found. Send any message to your bot first, then run this again.\n")
