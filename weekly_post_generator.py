#!/usr/bin/env python3
"""
LinkedIn Post Automation for Sergey Tadevosyan
-----------------------------------------------
Runs weekly. Scrapes iGaming industry news, picks the most relevant
signal, drafts a LinkedIn post in Sergey's voice, sends it to Telegram.

Setup:
  pip install requests python-telegram-bot anthropic beautifulsoup4 feedparser

Environment variables required (put in .env or export before running):
  ANTHROPIC_API_KEY   — your Anthropic API key
  TELEGRAM_BOT_TOKEN  — from @BotFather on Telegram
  TELEGRAM_CHAT_ID    — your personal chat ID (run get_chat_id.py once to find it)
"""

import os
import json
import random
import feedparser
import requests
from bs4 import BeautifulSoup
from datetime import datetime
import anthropic

# ── CONFIG ─────────────────────────────────────────────────────────────────────

ANTHROPIC_API_KEY   = os.environ.get("ANTHROPIC_API_KEY")
TELEGRAM_BOT_TOKEN  = os.environ.get("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID    = os.environ.get("TELEGRAM_CHAT_ID")

# Rotate pillars week-by-week so content stays varied
CONTENT_PILLARS = [
    "affiliate tracking & technology (postbacks, attribution, fraud, data quality)",
    "industry dynamics & where things are heading (regulation, commission models, new channels, market consolidation)",
    "operator-affiliate relationship dynamics (what affiliates want, what operators get wrong, data transparency)",
]

# RSS feeds — reliable, no login required
RSS_FEEDS = [
    # iGaming news
    ("iGB", "https://igamingbusiness.com/feed/"),
    ("Gambling Insider", "https://gamblinginsider.com/feed/"),
    ("CalvinAyre", "https://calvinayre.com/feed/"),
    ("AffiliateINSIDER", "https://affiliateinsider.com/feed/"),
    ("EGR", "https://egrglobal.com/feed/"),
]

# Keywords that make a story relevant to Sergey's niche
RELEVANCE_KEYWORDS = [
    "affiliate", "affiliates", "affiliate marketing", "affiliate programme",
    "affiliate software", "affiliate platform", "affiliate tracking",
    "partnermatrix", "myaffiliates", "netrefer", "income access", "affilka",
    "commission", "revshare", "revenue share", "cpa", "hybrid deal",
    "igaming", "online casino", "online gambling", "sportsbook",
    "regulation", "ukgc", "mga", "compliance", "responsible gambling",
    "operator", "player acquisition", "retention", "ltv", "fraud",
    "catena media", "better collective", "game lounge", "raketech",
    "telegram affiliates", "streamer", "influencer marketing",
]

# ── NEWS SCRAPING ───────────────────────────────────────────────────────────────

def fetch_rss_stories(max_per_feed: int = 5) -> list[dict]:
    """Fetch recent stories from RSS feeds, return relevant ones."""
    stories = []

    for source_name, url in RSS_FEEDS:
        try:
            feed = feedparser.parse(url)
            for entry in feed.entries[:max_per_feed]:
                title = entry.get("title", "")
                summary = entry.get("summary", "") or entry.get("description", "")
                link = entry.get("link", "")
                published = entry.get("published", "")

                # Clean HTML from summary
                if summary:
                    summary = BeautifulSoup(summary, "html.parser").get_text()[:500]

                combined = (title + " " + summary).lower()
                relevance_score = sum(
                    1 for kw in RELEVANCE_KEYWORDS if kw in combined
                )

                if relevance_score > 0:
                    stories.append({
                        "source": source_name,
                        "title": title,
                        "summary": summary.strip(),
                        "link": link,
                        "published": published,
                        "relevance_score": relevance_score,
                    })
        except Exception as e:
            print(f"  ⚠️  Failed to fetch {source_name}: {e}")

    # Sort by relevance, take top 8
    stories.sort(key=lambda x: x["relevance_score"], reverse=True)
    return stories[:8]


def fetch_article_text(url: str, max_chars: int = 2000) -> str:
    """Try to fetch the full article text for the top story."""
    try:
        headers = {"User-Agent": "Mozilla/5.0"}
        resp = requests.get(url, headers=headers, timeout=8)
        soup = BeautifulSoup(resp.text, "html.parser")
        # Remove nav/footer/script noise
        for tag in soup(["script", "style", "nav", "footer", "header", "aside"]):
            tag.decompose()
        text = soup.get_text(separator=" ", strip=True)
        return text[:max_chars]
    except Exception:
        return ""


# ── POST GENERATION ─────────────────────────────────────────────────────────────

SYSTEM_PROMPT = """You are a ghostwriter for Sergey Tadevosyan — a product leader and CPO in the iGaming affiliate software space, based in Malta.

ABOUT SERGEY:
- Career: banking (Armenia) → fintech → Digitain (B2B sportsbook, account management) → Game Lounge (major affiliate publisher, data products) → CPO at PartnerMatrix (affiliate management software)
- Key differentiator: he has sat INSIDE a major affiliate publisher (Game Lounge) AND now leads product at affiliate software (PartnerMatrix). He sees both sides. Reference this naturally when relevant.
- This is personal brand — never mention PartnerMatrix promotionally.

VOICE & STYLE (strictly follow):
- Open with a relatable observation, question, or surprising statement — NEVER a bold claim
- Build the point gradually: context → layers → insight → question
- Short paragraphs. Often single sentences. Stacked for rhythm when emphasising.
- Tone: curious, confident, accessible. Explains iGaming terms briefly inline.
- Medium heat: takes a position but grounds it in observation, not provocation.
- Ends with a genuine open question — never a CTA to follow or like.
- Emojis: 1–2 max, functional not decorative (👉 💰 📈 🎯)
- Hashtags: exactly 3. Always include #iGaming and #iGamingAffiliateMarketing, vary the third.
- NEVER mention PartnerMatrix. NEVER write promotional content.

BEST POST EXAMPLE (match this structure and feel):
"Many people work in iGaming affiliates.

But surprisingly few understand how the economics actually work behind the scenes.

At the core, the entire system revolves around one thing:

🎯 Player value

Operators are not really buying traffic.
They are buying future player revenue.

That's why affiliate deals usually take one of these forms:

💰 CPA (Cost Per Acquisition) — A fixed payment for every depositing player.
📈 Revenue Share — A percentage of the player's losses over time.
🖥️ Hybrid — A combination of CPA and RevShare.

But the real economics go deeper.

Operators evaluate affiliate traffic based on signals like:
• First Time Deposit rate (FTD)
• Average deposit size
• Player lifetime value (LTV)
• Retention and activity
• Fraud and bonus abuse risk

An affiliate sending 100 high-quality players can be far more valuable than one sending 1,000 low-quality users.

This is where product management becomes interesting.

Affiliate platforms shouldn't just track traffic.

They should help answer the real question:

👉 Which affiliates actually bring the most valuable players?

Curious to hear from operators and affiliates in the network:

What metric do you trust most when evaluating affiliate traffic?

#iGaming #iGamingAffiliateMarketing #ProductManagement"

THE TEST: Would a Head of Affiliates at a mid-tier European operator AND a product manager outside iGaming both find this worth reading? If yes — it's good. If it's too insider or too generic — rewrite it.
"""


def generate_post(stories: list[dict], pillar: str) -> dict:
    """Call Claude to generate the LinkedIn post based on news + pillar."""
    client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)

    # Build the news context
    news_context = ""
    if stories:
        news_context = "CURRENT INDUSTRY NEWS THIS WEEK:\n\n"
        for i, s in enumerate(stories[:5], 1):
            news_context += f"{i}. [{s['source']}] {s['title']}\n"
            if s['summary']:
                news_context += f"   {s['summary'][:200]}\n"
            news_context += f"   Link: {s['link']}\n\n"

        # Try to get full text of the top story
        top_article = fetch_article_text(stories[0]["link"])
        if top_article:
            news_context += f"\nFULL ARTICLE (top story):\n{top_article}\n"

    user_prompt = f"""Write one LinkedIn post for Sergey.

THIS WEEK'S CONTENT PILLAR: {pillar}

{news_context}

INSTRUCTIONS:
- Use the news above as inspiration and context, NOT as the subject of a news summary. 
- The post should share Sergey's perspective, observation, or insight — triggered by what's happening in the industry, but told through his lens.
- If the news is directly relevant to the pillar, weave them together naturally.
- If the news is not strongly relevant, use the pillar alone and write from Sergey's experience.
- Do NOT write a news recap. Write a post that makes people think.
- Follow the voice and structure guidelines exactly.
- Output ONLY the post text. Nothing else. No preamble, no "here is the post", no explanation."""

    message = client.messages.create(
        model="claude-sonnet-4-20250514",
        max_tokens=1000,
        system=SYSTEM_PROMPT,
        messages=[{"role": "user", "content": user_prompt}]
    )

    post_text = message.content[0].text.strip()

    return {
        "post": post_text,
        "pillar": pillar,
        "top_story": stories[0] if stories else None,
        "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M"),
    }


# ── TELEGRAM DELIVERY ───────────────────────────────────────────────────────────

def send_to_telegram(result: dict):
    """Send the generated post to Telegram."""
    post = result["post"]
    pillar = result["pillar"]
    generated_at = result["generated_at"]
    top_story = result.get("top_story")

    # Build the Telegram message
    header = (
        f"📝 *LinkedIn Post Ready*\n"
        f"_{generated_at}_\n"
        f"Pillar: _{pillar.split('(')[0].strip()}_\n"
    )

    if top_story:
        header += f"Inspired by: [{top_story['source']}]({top_story['link']})\n"

    separator = "\n─────────────────────\n\n"
    footer = "\n\n─────────────────────\n✅ Copy and post on LinkedIn\n⏰ Best time: Tue–Thu 8–10am CET"

    full_message = header + separator + post + footer

    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    payload = {
        "chat_id": TELEGRAM_CHAT_ID,
        "text": full_message,
        "parse_mode": "Markdown",
        "disable_web_page_preview": True,
    }

    resp = requests.post(url, json=payload, timeout=10)

    if resp.status_code == 200:
        print("✅ Post sent to Telegram successfully.")
    else:
        print(f"❌ Telegram send failed: {resp.status_code} — {resp.text}")
        # Fallback: print to console
        print("\n" + "="*60)
        print("POST (Telegram failed — copy from here):")
        print("="*60)
        print(post)


# ── PILLAR ROTATION ─────────────────────────────────────────────────────────────

def get_this_weeks_pillar() -> str:
    """Rotate pillars by week number so content stays varied."""
    week_number = datetime.now().isocalendar()[1]
    return CONTENT_PILLARS[week_number % len(CONTENT_PILLARS)]


# ── MAIN ────────────────────────────────────────────────────────────────────────

def main():
    print(f"\n🚀 LinkedIn Post Generator — {datetime.now().strftime('%Y-%m-%d')}")
    print("=" * 50)

    # 1. Validate config
    missing = [k for k, v in {
        "ANTHROPIC_API_KEY": ANTHROPIC_API_KEY,
        "TELEGRAM_BOT_TOKEN": TELEGRAM_BOT_TOKEN,
        "TELEGRAM_CHAT_ID": TELEGRAM_CHAT_ID,
    }.items() if not v]
    if missing:
        print(f"❌ Missing environment variables: {', '.join(missing)}")
        print("   See setup instructions in README.md")
        return

    # 2. Pick this week's pillar
    pillar = get_this_weeks_pillar()
    print(f"📌 This week's pillar: {pillar.split('(')[0].strip()}")

    # 3. Fetch news
    print("\n🔍 Fetching industry news...")
    stories = fetch_rss_stories()
    print(f"   Found {len(stories)} relevant stories")
    if stories:
        print(f"   Top story: {stories[0]['title'][:70]}...")

    # 4. Generate post
    print("\n✍️  Generating post with Claude...")
    result = generate_post(stories, pillar)
    print("   Done.")

    # 5. Send to Telegram
    print("\n📨 Sending to Telegram...")
    send_to_telegram(result)

    print("\n✅ All done.\n")


if __name__ == "__main__":
    main()
