#!/usr/bin/env python3
"""
Run this ONCE to find your Telegram Chat ID.

Steps:
1. Create a bot via @BotFather on Telegram → copy the token
2. Send any message to your new bot on Telegram
3. Run: TELEGRAM_BOT_TOKEN=your_token python3 get_chat_id.py
4. Copy the chat_id printed — add it to your .env
"""

import os
import requests

token = os.environ.get("TELEGRAM_BOT_TOKEN")
if not token:
    print("❌ Set TELEGRAM_BOT_TOKEN first:\n   export TELEGRAM_BOT_TOKEN=your_token")
    exit(1)

resp = requests.get(f"https://api.telegram.org/bot{token}/getUpdates")
data = resp.json()

if not data.get("result"):
    print("❌ No messages found. Send a message to your bot on Telegram first, then run this again.")
else:
    for update in data["result"]:
        chat = update.get("message", {}).get("chat", {})
        print(f"✅ Your Chat ID: {chat.get('id')}")
        print(f"   Name: {chat.get('first_name', '')} {chat.get('last_name', '')}")
        break
