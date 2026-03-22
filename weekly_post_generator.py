#!/usr/bin/env python3
"""
LinkedIn Post Automation for Sergey Tadevosyan
-----------------------------------------------
Runs Tuesday and Thursday mornings. Scrapes iGaming industry news
and the Tracking the Truth podcast (MyAffiliates), drafts a LinkedIn
post in Sergey's voice, sends it to Telegram ready to copy-paste.

Setup:
  pip install requests anthropic beautifulsoup4 feedparser

Environment variables required:
  ANTHROPIC_API_KEY   — your Anthropic API key
  TELEGRAM_BOT_TOKEN  — from @BotFather on Telegram
  TELEGRAM_CHAT_ID    — your personal chat ID (run get_chat_id.py once)
"""

import os
import re
import json
import feedparser
import requests
from bs4 import BeautifulSoup
from datetime import datetime
import anthropic

# Cache file — stores today's scraped content so regenerate skips scraping
CACHE_FILE = "/tmp/linkedin_post_cache.json"

# ── CONFIG ─────────────────────────────────────────────────────────────────────

ANTHROPIC_API_KEY  = os.environ.get("ANTHROPIC_API_KEY")
TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID   = os.environ.get("TELEGRAM_CHAT_ID")

# YouTube channel handle for Tracking the Truth (MyAffiliates podcast)
YOUTUBE_CHANNEL_HANDLE = "TrackingtheTruthPodcast"

# Rotate content pillars — alternates naturally across Tuesday/Thursday runs
CONTENT_PILLARS = [
    "affiliate tracking & technology (postbacks, S2S tracking, attribution, fraud detection, data quality)",
    "industry dynamics & where things are heading (regulation, commission model trends, new channels like Telegram/WhatsApp, market consolidation)",
    "operator-affiliate relationship dynamics (what affiliates actually want, what operators get wrong, data transparency, player quality vs volume)",
    "product decisions in iGaming affiliate software (build vs buy, prioritisation, what operators ask for vs what they need, shipping real features)",
]

# News RSS feeds
RSS_FEEDS = [
    ("iGB",              "https://igamingbusiness.com/feed/"),
    ("Gambling Insider", "https://gamblinginsider.com/feed/"),
    ("CalvinAyre",       "https://calvinayre.com/feed/"),
    ("AffiliateINSIDER", "https://affiliateinsider.com/feed/"),
    ("EGR Global",       "https://egrglobal.com/feed/"),
    ("SiGMA",            "https://sigma.world/news/feed/"),
]

# Keywords that signal relevance to Sergey's niche
RELEVANCE_KEYWORDS = [
    "affiliate", "affiliates", "affiliate marketing", "affiliate programme",
    "affiliate software", "affiliate platform", "affiliate tracking",
    "partnermatrix", "myaffiliates", "netrefer", "income access", "affilka",
    "cellxpert", "referon",
    "commission", "revshare", "revenue share", "cpa", "hybrid",
    "igaming", "online casino", "online gambling", "sportsbook",
    "regulation", "ukgc", "mga", "compliance",
    "operator", "player acquisition", "retention", "ltv", "fraud",
    "catena media", "better collective", "game lounge", "raketech",
    "telegram affiliates", "streamer", "influencer",
    "tracking", "postback", "attribution", "data",
]


# ── YOUTUBE SCRAPING ────────────────────────────────────────────────────────────

def get_youtube_channel_id(handle: str) -> str | None:
    """
    Resolve a YouTube @handle to a UC... channel ID by reading the channel page source.
    YouTube embeds the channel ID in the page metadata — no API key needed.
    """
    url = f"https://www.youtube.com/@{handle}"
    try:
        headers = {
            "User-Agent": (
                "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/120.0.0.0 Safari/537.36"
            )
        }
        resp = requests.get(url, headers=headers, timeout=10)
        # YouTube embeds channel ID in multiple places in the page source
        # Look for: "channelId":"UC..." or "externalId":"UC..."
        patterns = [
            r'"channelId":"(UC[a-zA-Z0-9_-]{22})"',
            r'"externalId":"(UC[a-zA-Z0-9_-]{22})"',
            r'channel/(UC[a-zA-Z0-9_-]{22})',
        ]
        for pattern in patterns:
            match = re.search(pattern, resp.text)
            if match:
                return match.group(1)
    except Exception as e:
        print(f"  ⚠️  Could not resolve YouTube channel ID: {e}")
    return None


def fetch_youtube_episodes(handle: str, max_episodes: int = 5) -> list[dict]:
    """
    Fetch latest episodes from a YouTube channel via RSS.
    YouTube provides a public RSS feed for every channel at:
    https://www.youtube.com/feeds/videos.xml?channel_id=UC...
    """
    episodes = []

    channel_id = get_youtube_channel_id(handle)
    if not channel_id:
        print(f"  ⚠️  Could not get channel ID for @{handle} — skipping YouTube source")
        return []

    rss_url = f"https://www.youtube.com/feeds/videos.xml?channel_id={channel_id}"
    print(f"  📺 YouTube RSS: {rss_url}")

    try:
        feed = feedparser.parse(rss_url)
        for entry in feed.entries[:max_episodes]:
            title       = entry.get("title", "")
            description = ""
            # feedparser puts YouTube description in media_group or summary
            if hasattr(entry, "media_group"):
                description = str(entry.media_group)[:300]
            elif entry.get("summary"):
                description = BeautifulSoup(
                    entry.get("summary", ""), "html.parser"
                ).get_text()[:300]

            link      = entry.get("link", "")
            published = entry.get("published", "")

            episodes.append({
                "source":    "Tracking the Truth Podcast (MyAffiliates)",
                "title":     title,
                "summary":   description.strip(),
                "link":      link,
                "published": published,
                "type":      "podcast_episode",
                # Podcast episodes always relevant — give them high base score
                "relevance_score": 5,
            })
    except Exception as e:
        print(f"  ⚠️  Failed to fetch YouTube RSS: {e}")

    return episodes


# ── NEWS SCRAPING ───────────────────────────────────────────────────────────────

def fetch_rss_stories(max_per_feed: int = 5) -> list[dict]:
    """Fetch recent stories from news RSS feeds."""
    stories = []

    for source_name, url in RSS_FEEDS:
        try:
            feed = feedparser.parse(url)
            for entry in feed.entries[:max_per_feed]:
                title   = entry.get("title", "")
                summary = entry.get("summary", "") or entry.get("description", "")
                link    = entry.get("link", "")
                published = entry.get("published", "")

                if summary:
                    summary = BeautifulSoup(summary, "html.parser").get_text()[:500]

                combined = (title + " " + summary).lower()
                relevance_score = sum(
                    1 for kw in RELEVANCE_KEYWORDS if kw in combined
                )

                if relevance_score > 0:
                    stories.append({
                        "source":          source_name,
                        "title":           title,
                        "summary":         summary.strip(),
                        "link":            link,
                        "published":       published,
                        "type":            "news",
                        "relevance_score": relevance_score,
                    })
        except Exception as e:
            print(f"  ⚠️  Failed to fetch {source_name}: {e}")

    stories.sort(key=lambda x: x["relevance_score"], reverse=True)
    return stories[:8]


def fetch_article_text(url: str, max_chars: int = 2000) -> str:
    """Fetch full article text for extra context."""
    try:
        headers = {"User-Agent": "Mozilla/5.0"}
        resp = requests.get(url, headers=headers, timeout=8)
        soup = BeautifulSoup(resp.text, "html.parser")
        for tag in soup(["script", "style", "nav", "footer", "header", "aside"]):
            tag.decompose()
        return soup.get_text(separator=" ", strip=True)[:max_chars]
    except Exception:
        return ""


# ── POST GENERATION ─────────────────────────────────────────────────────────────

SYSTEM_PROMPT = """You are a ghostwriter for Sergey Tadevosyan — a product leader in the iGaming affiliate industry, based in Malta.

ABOUT SERGEY:
- Has worked on both sides of the affiliate relationship: inside a large affiliate publisher (data products) and in affiliate management software (CPO). He sees the industry from both angles.
- Personal brand only — NEVER mention any company name, product name, or employer. Not even vaguely. No "at my current company", no "the platform I work on". Write as if he's an independent industry expert.

LENGTH — CRITICAL RULE:
- Maximum 150-180 words for the entire post (excluding hashtags)
- Count carefully. If it's over 180 words — cut it. No exceptions.
- Fewer, punchier lines beat more comprehensive ones every time.

VOICE & STYLE (strictly follow):
- Open with a short observation, question, or surprising statement — NEVER a bold claim
- Build gradually: context → insight → question. Maximum 4-5 paragraphs total.
- Short paragraphs. Often a single sentence. Never more than 2-3 sentences in one block.
- Tone: curious, confident, accessible. Briefly explains iGaming terms inline for non-iGaming readers.
- Ends with one genuine open question — never a CTA to follow/like.
- Emojis: 1 max per post, only if it genuinely adds meaning. Often zero is better.
- Hashtags: exactly 3, on the last line. Always #iGaming and #iGamingAffiliateMarketing, vary the third.
- NEVER mention any company, platform, software product, or employer by name.

BEST POST EXAMPLE (match this length and feel exactly — note how short it is):
"Many people work in iGaming affiliates.

But surprisingly few understand how the economics actually work.

Operators are not buying traffic.
They are buying future player revenue.

That's why an affiliate sending 100 high-quality players can be worth more than one sending 1,000 low-quality users.

Affiliate platforms shouldn't just track traffic.

They should answer one question: which affiliates actually bring valuable players?

What metric do you trust most when evaluating affiliate quality?

#iGaming #iGamingAffiliateMarketing #ProductManagement"

THE TEST: Would a Head of Affiliates at a mid-tier operator AND a PM from outside iGaming both find this worth reading? Both must get something from it."""


def generate_post(all_content: list[dict], pillar: str) -> dict:
    """Call Claude to draft the LinkedIn post."""
    client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)

    # Separate podcast episodes from news for clearer context
    podcast_episodes = [c for c in all_content if c.get("type") == "podcast_episode"]
    news_stories     = [c for c in all_content if c.get("type") == "news"]

    context_block = ""

    if podcast_episodes:
        context_block += "LATEST PODCAST EPISODES — Tracking the Truth (MyAffiliates):\n\n"
        for i, ep in enumerate(podcast_episodes[:3], 1):
            context_block += f"{i}. {ep['title']}\n"
            if ep['summary']:
                context_block += f"   {ep['summary'][:200]}\n"
            context_block += f"   Watch: {ep['link']}\n\n"

    if news_stories:
        context_block += "LATEST INDUSTRY NEWS:\n\n"
        for i, s in enumerate(news_stories[:5], 1):
            context_block += f"{i}. [{s['source']}] {s['title']}\n"
            if s['summary']:
                context_block += f"   {s['summary'][:200]}\n"
            context_block += f"   Link: {s['link']}\n\n"

    # Try to get full text of the single most relevant item
    top_item = (podcast_episodes + news_stories)[0] if (podcast_episodes or news_stories) else None
    if top_item:
        full_text = fetch_article_text(top_item["link"])
        if full_text:
            context_block += f"\nFULL TEXT (top item — {top_item['source']}):\n{full_text}\n"

    user_prompt = f"""Write one LinkedIn post for Sergey.

THIS POST'S CONTENT PILLAR: {pillar}

{context_block if context_block else "No external content found this run — write from Sergey's experience and expertise on the pillar above."}

INSTRUCTIONS:
- Use the content above as INSPIRATION and CONTEXT — not as the subject of a news summary or episode recap.
- The post should share Sergey's perspective or insight — triggered by what's happening in the industry, but told through his lens and experience.
- If a podcast episode topic connects naturally to the pillar, use it as a springboard. Do not summarise the episode.
- If the news content is relevant, weave it in naturally. If not, ignore it and write purely from his expertise.
- Do NOT write a news recap or podcast roundup. Write something that makes people think.
- Follow the voice and structure guidelines exactly. Match the feel of the example post.
- Output ONLY the post text. No preamble, no explanation, no "here is the post"."""

    message = client.messages.create(
        model="claude-sonnet-4-20250514",
        max_tokens=1000,
        system=SYSTEM_PROMPT,
        messages=[{"role": "user", "content": user_prompt}]
    )

    post_text = message.content[0].text.strip()

    return {
        "post":         post_text,
        "pillar":       pillar,
        "top_item":     top_item,
        "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M"),
    }


# ── TELEGRAM DELIVERY ───────────────────────────────────────────────────────────

def send_to_telegram(result: dict):
    """Send the generated post to Telegram."""
    post         = result["post"]
    pillar       = result["pillar"]
    generated_at = result["generated_at"]
    top_item     = result.get("top_item")

    day_name = datetime.now().strftime("%A")  # "Tuesday" or "Thursday"

    header = (
        f"✍️ *LinkedIn Post Ready — {day_name}*\n"
        f"_{generated_at}_\n"
        f"Pillar: _{pillar.split('(')[0].strip()}_\n"
    )

    if top_item:
        source_label = top_item["source"]
        link         = top_item["link"]
        title        = top_item["title"][:60]
        header += f"Inspired by: [{source_label}]({link})\n_{title}..._\n"

    separator = "\n─────────────────────\n\n"
    footer    = "\n\n─────────────────────\n✅ Copy and post on LinkedIn\n⏰ Best time: 8–10am CET"

    full_message = header + separator + post + footer

    url     = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    payload = {
        "chat_id":                  TELEGRAM_CHAT_ID,
        "text":                     full_message,
        "parse_mode":               "Markdown",
        "disable_web_page_preview": True,
    }

    resp = requests.post(url, json=payload, timeout=10)

    if resp.status_code == 200:
        print("✅ Post sent to Telegram.")
    else:
        print(f"❌ Telegram error {resp.status_code}: {resp.text}")
        print("\n" + "=" * 60)
        print("POST (copy from here if Telegram failed):")
        print("=" * 60)
        print(post)


# ── PILLAR ROTATION ─────────────────────────────────────────────────────────────

def get_pillar_for_today() -> str:
    """
    Rotate pillar based on the run number (week × 2 + day offset).
    Tuesday = 0 offset, Thursday = 1 offset.
    This ensures Tuesday and Thursday never repeat the same pillar.
    """
    week   = datetime.now().isocalendar()[1]
    is_thu = datetime.now().weekday() == 3  # 0=Mon, 3=Thu
    index  = (week * 2 + int(is_thu)) % len(CONTENT_PILLARS)
    return CONTENT_PILLARS[index]


# ── CACHE ───────────────────────────────────────────────────────────────────────

def save_cache(all_content: list, pillar: str):
    """Save today's scraped content so regenerate can skip scraping."""
    today = datetime.now().strftime("%Y-%m-%d")
    cache = {"date": today, "pillar": pillar, "content": all_content}
    try:
        with open(CACHE_FILE, "w") as f:
            json.dump(cache, f)
        print(f"   💾 Content cached for today ({today})")
    except Exception as e:
        print(f"   ⚠️  Could not save cache: {e}")


def load_cache() -> tuple[list, str] | tuple[None, None]:
    """Load today's cached content if it exists."""
    today = datetime.now().strftime("%Y-%m-%d")
    try:
        with open(CACHE_FILE) as f:
            cache = json.load(f)
        if cache.get("date") == today:
            print(f"   ✅ Found today's cached content — skipping scraping")
            return cache["content"], cache["pillar"]
    except Exception:
        pass
    return None, None


# ── MAIN ────────────────────────────────────────────────────────────────────────

def main():
    now = datetime.now()

    # Check if running in regenerate mode (set REGENERATE=true env var)
    regenerate_mode = os.environ.get("REGENERATE", "").lower() == "true"

    mode_label = "♻️  REGENERATE MODE" if regenerate_mode else "🚀 FULL RUN"
    print(f"\n{mode_label} — {now.strftime('%A %Y-%m-%d %H:%M')}")
    print("=" * 55)

    # Validate config
    missing = [k for k, v in {
        "ANTHROPIC_API_KEY":   ANTHROPIC_API_KEY,
        "TELEGRAM_BOT_TOKEN":  TELEGRAM_BOT_TOKEN,
        "TELEGRAM_CHAT_ID":    TELEGRAM_CHAT_ID,
    }.items() if not v]
    if missing:
        print(f"❌ Missing environment variables: {', '.join(missing)}")
        print("   See README.md for setup instructions.")
        return

    all_content = None
    pillar = None

    # In regenerate mode — try to load from cache first
    if regenerate_mode:
        print("\n🔄 Regenerate mode — loading cached content...")
        all_content, pillar = load_cache()
        if all_content is None:
            print("   ⚠️  No cache found for today — running full scrape instead")

    # Full scrape (either normal mode, or regenerate with no cache)
    if all_content is None:
        pillar = get_pillar_for_today()
        print(f"📌 Today's pillar: {pillar.split('(')[0].strip()}")

        print(f"\n📺 Fetching Tracking the Truth podcast episodes...")
        podcast_episodes = fetch_youtube_episodes(YOUTUBE_CHANNEL_HANDLE, max_episodes=3)
        print(f"   Found {len(podcast_episodes)} episode(s)")
        if podcast_episodes:
            print(f"   Latest: {podcast_episodes[0]['title'][:70]}")

        print(f"\n🔍 Fetching industry news...")
        news_stories = fetch_rss_stories()
        print(f"   Found {len(news_stories)} relevant stories")
        if news_stories:
            print(f"   Top story: {news_stories[0]['title'][:70]}")

        all_content = podcast_episodes + news_stories
        save_cache(all_content, pillar)
    else:
        print(f"📌 Pillar: {pillar.split('(')[0].strip()}")
        print(f"   Using {len(all_content)} cached items — no scraping needed")

    # Generate a fresh post (always calls Claude — different result each time)
    print(f"\n✍️  Generating post with Claude...")
    result = generate_post(all_content, pillar)
    print("   Done.")

    # Send to Telegram
    print(f"\n📨 Sending to Telegram...")
    send_to_telegram(result)

    print(f"\n✅ Done.\n")


if __name__ == "__main__":
    main()
