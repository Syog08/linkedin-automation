#!/usr/bin/env python3
"""
LinkedIn Post Intelligence Engine — v2.0
==========================================
For Sergey Tadevosyan — iGaming Affiliate CPO

Upgrades over v1:
  • Editorial triage: AI ranks scraped stories by engagement potential (not just keywords)
  • Data extraction: pulls specific numbers, metrics, entities from top articles
  • Adaptive pillar selection: picks the pillar that fits the news cycle, not mechanical rotation
  • Pre-publish scoring: rates each draft on 5 criteria, auto-regenerates weak posts
  • Feedback loop: logs everything to Supabase, uses past performance to improve
  • Weekly data briefing: aggregates industry intelligence for data-rich posts
  • 3x/week cadence: Tuesday, Thursday, Saturday

Environment variables:
  ANTHROPIC_API_KEY   — Anthropic API key
  TELEGRAM_BOT_TOKEN  — Telegram bot token
  TELEGRAM_CHAT_ID    — Your Telegram chat ID
  SUPABASE_URL        — Supabase project URL
  SUPABASE_KEY        — Supabase service role key (or anon key)
  REGENERATE          — "true" to skip scraping and regenerate from cache
"""

import os
import re
import json
import time
import feedparser
import requests
from bs4 import BeautifulSoup
from datetime import datetime, timedelta
import anthropic

# ── CONFIG ─────────────────────────────────────────────────────────────────────

ANTHROPIC_API_KEY  = os.environ.get("ANTHROPIC_API_KEY")
TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID   = os.environ.get("TELEGRAM_CHAT_ID")
SUPABASE_URL       = os.environ.get("SUPABASE_URL", "")
SUPABASE_KEY       = os.environ.get("SUPABASE_KEY", "")

CACHE_FILE = "/tmp/linkedin_post_cache.json"
MIN_SCORE_THRESHOLD = 6.5  # Minimum quality score to send to Telegram
MAX_REGENERATION_ATTEMPTS = 3

YOUTUBE_CHANNEL_HANDLE = "TrackingtheTruthPodcast"

# ── CONTENT PILLARS ────────────────────────────────────────────────────────────

CONTENT_PILLARS = [
    {
        "id": "tracking_tech",
        "name": "Affiliate Tracking & Technology",
        "description": "Postbacks, S2S tracking, attribution, fraud detection, data quality — the infrastructure layer that makes everything else work.",
        "weight": 10,  # Lower priority — Sergey's strength is data/product, not deep tech
        "data_angles": [
            "attribution accuracy rates",
            "fraud detection false positive rates",
            "tracking discrepancy percentages between platforms",
            "cookie vs server-side conversion rate differences",
        ],
    },
    {
        "id": "data_product",
        "name": "Data, Metrics & Analytics in iGaming Affiliate",
        "description": "Sergey's PRIMARY differentiator. Metrics that actually matter vs vanity metrics. What good affiliate reporting looks like. Turning raw data into decisions operators and affiliates can act on. BI and analytics as a product discipline. Commission economics and how to measure affiliate value. The gap between what's measured and what actually drives performance. Data quality as a product problem.",
        "weight": 35,  # HIGHEST — this is Sergey's core territory
        "data_angles": [
            "FTD rate benchmarks across traffic types (SEO vs paid vs Telegram)",
            "LTV by affiliate tier and how to actually calculate it",
            "click-to-deposit conversion funnels — where the drop-offs are",
            "reporting usage rates: what operators actually look at vs what they ignore",
            "data quality error rates in affiliate platforms",
            "the real cost of a depositing player across different affiliate channels",
            "RevShare percentages: what's standard, what's generous, what's exploitative",
            "average CPA rates across markets and how they correlate with player quality",
            "how to tell if an affiliate is profitable — not just active",
            "the metrics that predict affiliate churn before it happens",
        ],
    },
    {
        "id": "industry_dynamics",
        "name": "Industry Dynamics & Where Things Are Heading",
        "description": "Regulation impact, commission model trends, new affiliate channels (Telegram/WhatsApp/streamers), market consolidation, US vs EU dynamics.",
        "weight": 15,
        "data_angles": [
            "regulatory market opening timelines",
            "commission model split (RevShare vs CPA vs Hybrid) across markets",
            "affiliate channel growth rates",
            "M&A deal volumes in affiliate media",
        ],
    },
    {
        "id": "operator_affiliate",
        "name": "Operator-Affiliate Economics & Relationships",
        "description": "The economics of the operator-affiliate relationship. What affiliates actually want vs what operators think they want. Data transparency as a competitive advantage. Player quality vs traffic volume. Commission negotiation dynamics. Why programmes succeed or fail.",
        "weight": 25,  # High — this is where Sergey's dual-sided experience shines
        "data_angles": [
            "affiliate churn rates by programme type",
            "average time to first referral after signup",
            "correlation between data transparency and affiliate retention",
            "player quality metrics across affiliate tiers",
            "what percentage of affiliates generate 80% of revenue",
            "average number of active affiliates vs registered affiliates",
            "how commission structure affects traffic quality",
            "the real ROI of an affiliate manager's time by affiliate tier",
        ],
    },
    {
        "id": "product_decisions",
        "name": "Product & Decision-Making in iGaming",
        "description": "How to make better decisions with data. Prioritisation when everyone wants something different. The product management lens applied to affiliate operations — not software features, but how operators and affiliates make smarter commercial decisions using data and analytics.",
        "weight": 15,
        "data_angles": [
            "feature adoption rates post-launch",
            "migration timelines and performance impact",
            "how often operators actually use the dashboards they asked for",
            "the gap between what operators request and what moves their KPIs",
            "decision velocity: how fast operators act on data vs how fast data goes stale",
        ],
    },
]

# ── NEWS SOURCES ───────────────────────────────────────────────────────────────

RSS_FEEDS = [
    ("iGB",              "https://igamingbusiness.com/feed/"),
    ("Gambling Insider", "https://gamblinginsider.com/feed/"),
    ("CalvinAyre",       "https://calvinayre.com/feed/"),
    ("AffiliateINSIDER", "https://affiliateinsider.com/feed/"),
    ("EGR Global",       "https://egrglobal.com/feed/"),
    ("SiGMA",            "https://sigma.world/news/feed/"),
]

# Expanded keyword tiers — weighted by engagement potential
KEYWORD_TIERS = {
    # Tier 1: high engagement (3 points) — specific, actionable, data-rich topics
    3: [
        "commission", "revshare", "revenue share", "cpa deal", "hybrid deal",
        "ltv", "lifetime value", "ftd", "first time deposit", "player value",
        "fraud", "bonus abuse", "fake traffic", "quality score",
        "postback", "s2s tracking", "attribution",
        "affiliate programme audit", "affiliate retention",
    ],
    # Tier 2: strong relevance (2 points) — industry dynamics
    2: [
        "affiliate marketing", "affiliate programme", "affiliate platform",
        "affiliate software", "affiliate tracking",
        "partnermatrix", "myaffiliates", "netrefer", "income access",
        "affilka", "cellxpert", "referon",
        "operator", "player acquisition", "regulation",
        "catena media", "better collective", "raketech", "gambling.com",
        "telegram affiliates", "streamer", "influencer marketing",
    ],
    # Tier 3: contextually relevant (1 point) — broad iGaming
    1: [
        "igaming", "online casino", "online gambling", "sportsbook",
        "ukgc", "mga", "compliance", "responsible gambling",
        "data", "analytics", "reporting", "dashboard",
        "game lounge", "retention", "deposit",
    ],
}


# ── SUPABASE HELPERS ───────────────────────────────────────────────────────────

def supabase_insert(table: str, data: dict) -> bool:
    """Insert a row into Supabase. Returns True on success."""
    if not SUPABASE_URL or not SUPABASE_KEY:
        print(f"  ⚠️  Supabase not configured — skipping {table} insert")
        return False
    try:
        resp = requests.post(
            f"{SUPABASE_URL}/rest/v1/{table}",
            headers={
                "apikey": SUPABASE_KEY,
                "Authorization": f"Bearer {SUPABASE_KEY}",
                "Content-Type": "application/json",
                "Prefer": "return=minimal",
            },
            json=data,
            timeout=10,
        )
        if resp.status_code in (200, 201):
            return True
        print(f"  ⚠️  Supabase insert to {table} failed: {resp.status_code} {resp.text[:200]}")
    except Exception as e:
        print(f"  ⚠️  Supabase error: {e}")
    return False


def supabase_query(table: str, select: str = "*", params: str = "") -> list:
    """Query Supabase. Returns list of rows."""
    if not SUPABASE_URL or not SUPABASE_KEY:
        return []
    try:
        url = f"{SUPABASE_URL}/rest/v1/{table}?select={select}"
        if params:
            url += f"&{params}"
        resp = requests.get(
            url,
            headers={
                "apikey": SUPABASE_KEY,
                "Authorization": f"Bearer {SUPABASE_KEY}",
            },
            timeout=10,
        )
        if resp.status_code == 200:
            return resp.json()
    except Exception as e:
        print(f"  ⚠️  Supabase query error: {e}")
    return []


# ── YOUTUBE SCRAPING ───────────────────────────────────────────────────────────

def get_youtube_channel_id(handle: str) -> str | None:
    """Resolve a YouTube @handle to a UC... channel ID."""
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
        for pattern in [
            r'"channelId":"(UC[a-zA-Z0-9_-]{22})"',
            r'"externalId":"(UC[a-zA-Z0-9_-]{22})"',
            r'channel/(UC[a-zA-Z0-9_-]{22})',
        ]:
            match = re.search(pattern, resp.text)
            if match:
                return match.group(1)
    except Exception as e:
        print(f"  ⚠️  Could not resolve YouTube channel ID: {e}")
    return None


def fetch_youtube_episodes(handle: str, max_episodes: int = 5) -> list[dict]:
    """Fetch latest episodes from YouTube RSS."""
    channel_id = get_youtube_channel_id(handle)
    if not channel_id:
        print(f"  ⚠️  Could not get channel ID for @{handle}")
        return []

    rss_url = f"https://www.youtube.com/feeds/videos.xml?channel_id={channel_id}"
    episodes = []
    try:
        feed = feedparser.parse(rss_url)
        for entry in feed.entries[:max_episodes]:
            title = entry.get("title", "")
            description = ""
            if hasattr(entry, "media_group"):
                description = str(entry.media_group)[:500]
            elif entry.get("summary"):
                description = BeautifulSoup(
                    entry.get("summary", ""), "html.parser"
                ).get_text()[:500]

            episodes.append({
                "source": "Tracking the Truth Podcast",
                "title": title,
                "summary": description.strip(),
                "link": entry.get("link", ""),
                "published": entry.get("published", ""),
                "type": "podcast_episode",
            })
    except Exception as e:
        print(f"  ⚠️  Failed to fetch YouTube RSS: {e}")
    return episodes


# ── NEWS SCRAPING ──────────────────────────────────────────────────────────────

def score_relevance(text: str) -> int:
    """Score relevance using tiered keywords. Higher = more engaging potential."""
    text_lower = text.lower()
    score = 0
    for points, keywords in KEYWORD_TIERS.items():
        for kw in keywords:
            if kw in text_lower:
                score += points
    return score


def fetch_rss_stories(max_per_feed: int = 8) -> list[dict]:
    """Fetch and score stories from all RSS feeds."""
    stories = []
    for source_name, url in RSS_FEEDS:
        try:
            feed = feedparser.parse(url)
            for entry in feed.entries[:max_per_feed]:
                title = entry.get("title", "")
                summary = entry.get("summary", "") or entry.get("description", "")
                link = entry.get("link", "")
                published = entry.get("published", "")

                if summary:
                    summary = BeautifulSoup(summary, "html.parser").get_text()[:500]

                combined = title + " " + summary
                relevance = score_relevance(combined)

                if relevance > 0:
                    stories.append({
                        "source": source_name,
                        "title": title,
                        "summary": summary.strip(),
                        "link": link,
                        "published": published,
                        "type": "news",
                        "relevance_score": relevance,
                    })
        except Exception as e:
            print(f"  ⚠️  Failed to fetch {source_name}: {e}")

    stories.sort(key=lambda x: x["relevance_score"], reverse=True)
    return stories[:15]  # Keep top 15 for AI triage


def fetch_article_text(url: str, max_chars: int = 3000) -> str:
    """Fetch full article text for deeper analysis."""
    try:
        headers = {"User-Agent": "Mozilla/5.0"}
        resp = requests.get(url, headers=headers, timeout=8)
        soup = BeautifulSoup(resp.text, "html.parser")
        for tag in soup(["script", "style", "nav", "footer", "header", "aside"]):
            tag.decompose()
        return soup.get_text(separator=" ", strip=True)[:max_chars]
    except Exception:
        return ""


# ── AI EDITORIAL TRIAGE ───────────────────────────────────────────────────────

def editorial_triage(client: anthropic.Anthropic, stories: list[dict]) -> list[dict]:
    """
    AI-powered editorial judgment: rank stories by LinkedIn engagement potential.
    Returns the top 5 stories with AI scores and reasoning.
    """
    if not stories:
        return []

    stories_text = ""
    for i, s in enumerate(stories, 1):
        stories_text += f"{i}. [{s['source']}] {s['title']}\n"
        if s.get("summary"):
            stories_text += f"   {s['summary'][:200]}\n"
        stories_text += "\n"

    prompt = f"""You are an editorial strategist for an iGaming affiliate industry LinkedIn account.

Rate each story below from 1-10 on LinkedIn engagement potential for this specific audience:
- Primary: Heads of Affiliates, affiliate managers, operators, iGaming B2B vendors
- Secondary: product managers, data professionals, curious generalists

Consider:
- Does it have a clear "so what" for practitioners?
- Does it contain or imply specific data points / metrics?
- Is it debatable or just factual reporting?
- Would a Head of Affiliates share an opinion on this?
- Does it connect to a broader trend (not just a one-off event)?

STORIES:
{stories_text}

Respond in JSON only. No preamble. Format:
[
  {{"index": 1, "score": 8, "reason": "...", "data_points": ["any numbers/metrics mentioned or implied"], "best_angle": "the provocative angle for a post"}},
  ...
]"""

    try:
        message = client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=2000,
            messages=[{"role": "user", "content": prompt}],
        )
        raw = message.content[0].text.strip()
        # Clean potential markdown fencing
        raw = re.sub(r"^```json\s*", "", raw)
        raw = re.sub(r"\s*```$", "", raw)
        ratings = json.loads(raw)

        # Merge AI ratings back into stories
        for rating in ratings:
            idx = rating.get("index", 0) - 1
            if 0 <= idx < len(stories):
                stories[idx]["ai_score"] = rating.get("score", 0)
                stories[idx]["ai_reason"] = rating.get("reason", "")
                stories[idx]["ai_data_points"] = rating.get("data_points", [])
                stories[idx]["ai_best_angle"] = rating.get("best_angle", "")

        # Sort by AI score
        stories.sort(key=lambda x: x.get("ai_score", 0), reverse=True)
        return stories[:5]

    except Exception as e:
        print(f"  ⚠️  Editorial triage failed: {e}")
        # Fallback to keyword scoring
        return stories[:5]


# ── DATA EXTRACTION ────────────────────────────────────────────────────────────

def extract_article_intelligence(client: anthropic.Anthropic, article_text: str, title: str) -> dict:
    """
    Extract structured intelligence from a full article:
    - Specific numbers, metrics, percentages
    - Key claims or positions
    - Named entities (companies, people, markets)
    - The "so what" — why this matters for affiliates/operators
    """
    if not article_text or len(article_text) < 100:
        return {}

    prompt = f"""Extract structured intelligence from this iGaming industry article.

TITLE: {title}

ARTICLE TEXT:
{article_text[:2500]}

Respond in JSON only. No preamble. Format:
{{
  "data_points": ["specific numbers, percentages, dollar amounts, metrics mentioned"],
  "key_claims": ["main arguments or positions taken in the article"],
  "entities": ["companies, people, regulators, markets mentioned"],
  "so_what": "one sentence: why this matters for affiliate programme operators or affiliates",
  "post_hook": "a provocative one-liner that could open a LinkedIn post inspired by this"
}}"""

    try:
        message = client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=800,
            messages=[{"role": "user", "content": prompt}],
        )
        raw = message.content[0].text.strip()
        raw = re.sub(r"^```json\s*", "", raw)
        raw = re.sub(r"\s*```$", "", raw)
        return json.loads(raw)
    except Exception as e:
        print(f"  ⚠️  Data extraction failed: {e}")
        return {}


# ── ADAPTIVE PILLAR SELECTION ──────────────────────────────────────────────────

def select_pillar(
    client: anthropic.Anthropic,
    top_stories: list[dict],
    recent_pillars: list[str],
) -> dict:
    """
    AI selects the best pillar for today based on:
    1. What's happening in the news this week
    2. Which pillars haven't been used recently (avoid repetition)
    3. Which pillar + story combination has the highest engagement potential
    """
    pillar_descriptions = "\n".join(
        f"- {p['id']} (weight: {p.get('weight', 15)}%): {p['name']} — {p['description']}"
        for p in CONTENT_PILLARS
    )

    stories_summary = "\n".join(
        f"- [{s['source']}] {s['title']} (AI score: {s.get('ai_score', '?')}, angle: {s.get('ai_best_angle', 'n/a')})"
        for s in top_stories[:5]
    )

    recent_text = ", ".join(recent_pillars[-4:]) if recent_pillars else "none"

    prompt = f"""You are selecting today's content pillar for Sergey Tadevosyan's iGaming affiliate LinkedIn account.

CRITICAL CONTEXT ABOUT SERGEY:
- His STRONGEST differentiator is data, metrics, analytics, and product thinking applied to iGaming affiliate.
- He has worked INSIDE both an affiliate publisher (data products) AND affiliate management software (CPO). This dual perspective is extremely rare.
- His best-performing post was about affiliate economics: FTD rates, LTV, player value, commission models.
- He is NOT a deep technical tracking expert. He is a data product and analytics thinker who understands the business economics.
- Posts about metrics, benchmarks, commission economics, "what the data actually shows", and data-driven decisions consistently outperform pure tech or pure industry news posts.

AVAILABLE PILLARS (with target frequency weights — higher = pick more often):
{pillar_descriptions}

THIS WEEK'S TOP STORIES (ranked by engagement potential):
{stories_summary}

RECENTLY USED PILLARS (avoid repeating): {recent_text}

SELECTION RULES:
1. STRONGLY prefer pillars with higher weights — data_product (35%) and operator_affiliate (25%) should be selected ~60% of the time combined
2. Even when news is about tracking tech or regulation, ask: "Can I frame this through a data/metrics/economics lens instead?" If yes, pick data_product or operator_affiliate.
3. Only pick tracking_tech if the story is SPECIFICALLY about a technical tracking problem that cannot be framed as a data/analytics question.
4. Always find the angle that lets Sergey talk about metrics, benchmarks, what the numbers show, and what decisions should change as a result.

Respond in JSON only. No preamble:
{{
  "pillar_id": "...",
  "reasoning": "why this pillar fits the news cycle and audience right now",
  "suggested_story_index": 0,
  "suggested_angle": "the specific angle to take — preferably involving a metric, benchmark, or data insight"
}}"""

    try:
        message = client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=500,
            messages=[{"role": "user", "content": prompt}],
        )
        raw = message.content[0].text.strip()
        raw = re.sub(r"^```json\s*", "", raw)
        raw = re.sub(r"\s*```$", "", raw)
        result = json.loads(raw)

        # Find the full pillar object
        pillar_obj = next(
            (p for p in CONTENT_PILLARS if p["id"] == result.get("pillar_id")),
            None,
        )
        if pillar_obj:
            result["pillar"] = pillar_obj
            return result
    except Exception as e:
        print(f"  ⚠️  Adaptive pillar selection failed: {e}")

    # Fallback: mechanical rotation (same as v1)
    week = datetime.now().isocalendar()[1]
    dow = datetime.now().weekday()
    day_offset = {1: 0, 3: 1, 5: 2}.get(dow, 0)  # Tue=0, Thu=1, Sat=2
    index = (week * 3 + day_offset) % len(CONTENT_PILLARS)
    return {
        "pillar": CONTENT_PILLARS[index],
        "pillar_id": CONTENT_PILLARS[index]["id"],
        "reasoning": "Mechanical rotation fallback",
        "suggested_angle": "",
    }


# ── FEEDBACK LOOP: GET PAST PERFORMANCE ────────────────────────────────────────

def get_top_performers() -> str:
    """Fetch top 3 past posts by engagement rate to include in the prompt."""
    rows = supabase_query(
        "post_performance",
        select="hook_line,pillar,engagement_rate,comments,format_type,has_data_point",
        params="posted=eq.true&engagement_rate=not.is.null&order=engagement_rate.desc&limit=3",
    )
    if not rows:
        return ""

    block = "YOUR TOP-PERFORMING POSTS (learn from these patterns):\n\n"
    for i, r in enumerate(rows, 1):
        block += f"{i}. Hook: \"{r.get('hook_line', 'n/a')}\"\n"
        block += f"   Pillar: {r.get('pillar', '?')} | Format: {r.get('format_type', '?')} | "
        block += f"Had data: {'Yes' if r.get('has_data_point') else 'No'} | "
        block += f"Engagement: {r.get('engagement_rate', '?')}% | Comments: {r.get('comments', '?')}\n\n"
    return block


def get_recent_pillars() -> list[str]:
    """Get the last 4 pillar IDs used."""
    rows = supabase_query(
        "post_performance",
        select="pillar",
        params="order=post_date.desc&limit=4",
    )
    return [r.get("pillar", "") for r in rows]


# ── POST GENERATION ────────────────────────────────────────────────────────────

SYSTEM_PROMPT = """You are a ghostwriter for Sergey Tadevosyan — a product leader in the iGaming affiliate industry, based in Malta.

ABOUT SERGEY:
- Has worked on both sides of the affiliate relationship: inside a large affiliate publisher (data products) and in affiliate management software (CPO).
- His rare combination: deep iGaming affiliate industry knowledge + data product management expertise. Most people in this industry have one or the other. He has both.
- Data product thinking is THE CORE of his identity — he thinks in metrics, data flows, benchmarks, economics, and what makes a number actionable vs decorative.
- He is a product management leader who applies analytical thinking to the iGaming affiliate industry. He is NOT primarily a tracking technology expert.
- His strongest topics: affiliate programme economics (commission models, FTD rates, LTV, player value), data-driven decision making, what metrics actually matter, why most reporting is useless, and the gap between what operators measure and what drives performance.
- Personal brand only — NEVER mention any company name, product name, or employer.

LENGTH — CRITICAL:
- Maximum 150-180 words (excluding hashtags). Count carefully. No exceptions.
- Fewer, punchier lines beat comprehensive ones.

VOICE & STYLE:
- Open with a short observation, question, or surprising statement — NEVER a bold claim
- Build gradually: context → insight → question. Max 4-5 paragraphs.
- Short paragraphs. Often a single sentence. Never more than 2-3 sentences in one block.
- Tone: curious, confident, accessible. Briefly explains iGaming terms inline.
- Ends with one genuine open question — never a CTA to follow/like.
- Emojis: max 1 per post, only if it adds meaning. Often zero is better.
- Hashtags: exactly 3 on the last line. Always #iGaming and #iGamingAffiliateMarketing, vary the third (#DataProducts #ProductManagement #AffiliateMarketing #BusinessIntelligence #iGamingAffiliate).
- NEVER mention any company, platform, software product, or employer by name.

DATA-DRIVEN POST RULE — CRITICAL:
- Every post MUST include at least ONE specific data point, metric, percentage, benchmark, or numerical comparison.
- If the source material contains data → use it naturally.
- If no data is available → use a credible illustrative number from Sergey's experience (e.g., "In my experience, about 60% of operators..." or "The average RevShare deal sits between 25-40%").
- Posts with specific numbers consistently outperform posts without them.

SERGEY'S FAVOURITE ANGLES (use these often):
- "Here's a number most people in the industry don't know" → explain what it means → what decisions should change
- "Everyone measures X, but the metric that actually predicts Y is Z"
- "The economics behind [thing] are simpler than people think" → break it down with numbers
- "I've seen this pattern across dozens of affiliate programmes" → the data-backed observation
- "Most operators track [vanity metric]. The ones that outperform track [real metric]."

WHAT TO AVOID:
- Pure technical tracking posts about postbacks, cookies, server-side implementation details
- Generic industry news recaps with no data or analytical angle
- Posts that read like a software vendor wrote them
- Posts that could have been written by anyone in any industry — MUST have iGaming affiliate specifics
- Opening with "In today's rapidly evolving..." or any generic LinkedIn opener

POST FORMAT VARIETY:
Rotate between these formats (the prompt will specify which to use):
- Observation: notice a data pattern → explain why it matters → question
- Data insight: one specific number → what it means → what most people miss → question
- Contrarian: common belief → the data says otherwise → what's actually true → question
- Story: specific situation with a client/programme → what the data revealed → the lesson → question
- Industry commentary: news event → the economics/data behind it → second-order implication → question

BEST POST EXAMPLE (match this feel — notice the economics focus, not tech):
"Many people work in iGaming affiliates.

But surprisingly few understand how the economics actually work.

Operators are not buying traffic.
They are buying future player revenue.

That's why an affiliate sending 100 high-quality players can be worth more than one sending 1,000 low-quality users.

Affiliate platforms shouldn't just track traffic.

They should answer one question: which affiliates actually bring valuable players?

What metric do you trust most when evaluating affiliate quality?

#iGaming #iGamingAffiliateMarketing #ProductManagement"

THE TEST: Would a Head of Affiliates at a mid-tier operator AND a data-minded PM from outside iGaming both find this worth reading?"""


POST_FORMATS = [
    "observation",
    "data_insight",
    "contrarian",
    "story",
    "industry_commentary",
]


def select_format() -> str:
    """Select post format, biasing toward data_insight and observation."""
    weights = {
        "observation": 25,
        "data_insight": 35,
        "contrarian": 15,
        "story": 15,
        "industry_commentary": 10,
    }
    import random
    population = []
    for fmt, weight in weights.items():
        population.extend([fmt] * weight)
    return random.choice(population)


def generate_post(
    client: anthropic.Anthropic,
    top_stories: list[dict],
    pillar_selection: dict,
    article_intel: dict,
    performance_context: str,
    post_format: str,
) -> dict:
    """Generate a LinkedIn post with full intelligence context."""

    pillar = pillar_selection["pillar"]
    suggested_angle = pillar_selection.get("suggested_angle", "")

    # Build rich context block
    context_block = ""

    if top_stories:
        context_block += "TOP STORIES THIS WEEK (ranked by engagement potential):\n\n"
        for i, s in enumerate(top_stories[:4], 1):
            context_block += f"{i}. [{s['source']}] {s['title']}\n"
            if s.get("ai_best_angle"):
                context_block += f"   Best angle: {s['ai_best_angle']}\n"
            if s.get("ai_data_points"):
                context_block += f"   Data points: {', '.join(s['ai_data_points'])}\n"
            if s.get("summary"):
                context_block += f"   Summary: {s['summary'][:150]}\n"
            context_block += "\n"

    if article_intel:
        context_block += "DEEP INTEL FROM TOP ARTICLE:\n"
        if article_intel.get("data_points"):
            context_block += f"  Data points: {', '.join(article_intel['data_points'])}\n"
        if article_intel.get("key_claims"):
            context_block += f"  Key claims: {', '.join(article_intel['key_claims'][:3])}\n"
        if article_intel.get("so_what"):
            context_block += f"  So what: {article_intel['so_what']}\n"
        if article_intel.get("post_hook"):
            context_block += f"  Suggested hook: {article_intel['post_hook']}\n"
        context_block += "\n"

    if performance_context:
        context_block += f"\n{performance_context}\n"

    user_prompt = f"""Write one LinkedIn post for Sergey.

CONTENT PILLAR: {pillar['name']} — {pillar['description']}

POST FORMAT: {post_format}
- observation: notice a pattern → explain why it matters → question
- data_insight: open with one specific number → what it means → what most people miss → question
- contrarian: common belief → why it's wrong → what's actually true → question
- story: specific situation → what happened → the lesson → question
- industry_commentary: news event → second-order implication → question

{f"SUGGESTED ANGLE: {suggested_angle}" if suggested_angle else ""}

DATA ANGLES FOR THIS PILLAR (use at least one):
{chr(10).join(f'- {a}' for a in pillar.get('data_angles', []))}

{context_block if context_block else "No external content found — write from Sergey's experience and expertise."}

CRITICAL INSTRUCTIONS:
- Use the content above as INSPIRATION — not as a news summary or recap.
- The post MUST include at least one specific data point or metric.
- Share Sergey's perspective — triggered by what's happening, told through his lens.
- Do NOT write a news recap. Write something that makes people think.
- Match the voice and structure guidelines exactly.
- Keep it under 180 words (excluding hashtags). Count carefully.
- Output ONLY the post text. No preamble, no explanation."""

    message = client.messages.create(
        model="claude-sonnet-4-20250514",
        max_tokens=1000,
        system=SYSTEM_PROMPT,
        messages=[{"role": "user", "content": user_prompt}],
    )

    post_text = message.content[0].text.strip()

    return {
        "post": post_text,
        "pillar_id": pillar["id"],
        "pillar_name": pillar["name"],
        "format": post_format,
        "suggested_angle": suggested_angle,
        "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M"),
    }


# ── POST SCORING ───────────────────────────────────────────────────────────────

def score_post(client: anthropic.Anthropic, post_text: str, pillar_name: str) -> dict:
    """
    AI quality gate: score the post on 5 dimensions before delivery.
    Returns scores + overall + improvement suggestions.
    """
    prompt = f"""Score this LinkedIn post for an iGaming affiliate industry audience.

POST:
---
{post_text}
---

PILLAR: {pillar_name}

Rate each dimension from 1-10:

1. HOOK STRENGTH: Would a Head of Affiliates stop scrolling for the opening line?
2. DATA DENSITY: Does it include at least one specific number, metric, or benchmark?
3. DUAL AUDIENCE: Would a PM outside iGaming still find this interesting?
4. SPECIFICITY: Could only someone with deep affiliate industry experience have written this?
5. QUESTION QUALITY: Does the closing question have teeth — would someone with real experience feel compelled to answer?

Respond in JSON only. No preamble:
{{
  "hook_strength": 7,
  "data_density": 8,
  "dual_audience": 6,
  "specificity": 9,
  "question_quality": 7,
  "overall": 7.4,
  "strengths": "what works well (1 sentence)",
  "weaknesses": "what could be stronger (1 sentence)",
  "suggestion": "one specific edit that would improve engagement"
}}"""

    try:
        message = client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=500,
            messages=[{"role": "user", "content": prompt}],
        )
        raw = message.content[0].text.strip()
        raw = re.sub(r"^```json\s*", "", raw)
        raw = re.sub(r"\s*```$", "", raw)
        return json.loads(raw)
    except Exception as e:
        print(f"  ⚠️  Scoring failed: {e}")
        return {"overall": 7.0, "hook_strength": 7, "data_density": 7,
                "dual_audience": 7, "specificity": 7, "question_quality": 7}


# ── TELEGRAM DELIVERY ──────────────────────────────────────────────────────────

def send_to_telegram(result: dict, scores: dict, top_stories: list[dict]):
    """Send the generated post to Telegram with quality metadata."""
    post = result["post"]
    pillar_name = result["pillar_name"]
    generated_at = result["generated_at"]
    post_format = result["format"]

    day_name = datetime.now().strftime("%A")
    overall_score = scores.get("overall", "?")
    score_emoji = "🟢" if overall_score >= 7.5 else "🟡" if overall_score >= 6.5 else "🔴"

    header = (
        f"✍️ *LinkedIn Post Ready — {day_name}*\n"
        f"_{generated_at}_\n"
        f"Pillar: _{pillar_name}_\n"
        f"Format: _{post_format}_\n"
        f"{score_emoji} Quality: *{overall_score}/10*\n"
    )

    # Score breakdown
    header += (
        f"📊 Hook:{scores.get('hook_strength','?')} "
        f"Data:{scores.get('data_density','?')} "
        f"Dual:{scores.get('dual_audience','?')} "
        f"Spec:{scores.get('specificity','?')} "
        f"Q:{scores.get('question_quality','?')}\n"
    )

    if scores.get("suggestion"):
        header += f"💡 _{scores['suggestion']}_\n"

    # Source attribution
    if top_stories:
        top = top_stories[0]
        header += f"Inspired by: [{top['source']}]({top.get('link','')})\n"

    separator = "\n─────────────────────\n\n"
    footer = "\n\n─────────────────────\n✅ Copy and post on LinkedIn\n⏰ Best time: 8–10am CET"

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
        print("✅ Post sent to Telegram.")
    else:
        print(f"❌ Telegram error {resp.status_code}: {resp.text}")
        print("\n" + "=" * 60)
        print("POST (copy from here if Telegram failed):")
        print("=" * 60)
        print(post)


# ── LOG TO SUPABASE ────────────────────────────────────────────────────────────

def log_post(result: dict, scores: dict, top_stories: list[dict]):
    """Log the generated post and scores to Supabase for the feedback loop."""
    post_text = result["post"]
    hook_line = post_text.split("\n")[0][:200] if post_text else ""

    # Detect if post has a data point
    has_data = bool(re.search(r'\d+[\.\,]?\d*\s*(%|percent|x\b|times|million|billion|€|\$|£)', post_text, re.IGNORECASE))

    data = {
        "post_date": datetime.now().strftime("%Y-%m-%d"),
        "day_of_week": datetime.now().strftime("%A"),
        "pillar": result.get("pillar_id", ""),
        "format_type": result.get("format", "observation"),
        "hook_line": hook_line,
        "post_text": post_text,
        "has_data_point": has_data,
        "source_articles": json.dumps([
            {"source": s["source"], "title": s["title"], "link": s.get("link", "")}
            for s in top_stories[:3]
        ]) if top_stories else None,
        "score_hook": scores.get("hook_strength"),
        "score_data_density": scores.get("data_density"),
        "score_dual_audience": scores.get("dual_audience"),
        "score_specificity": scores.get("specificity"),
        "score_question_quality": scores.get("question_quality"),
        "score_overall": scores.get("overall"),
    }

    if supabase_insert("post_performance", data):
        print("  📊 Post logged to Supabase")


def log_scrape(stories: list[dict]):
    """Log scraped stories to Supabase for analysis over time."""
    today = datetime.now().strftime("%Y-%m-%d")
    for s in stories[:10]:
        data = {
            "scrape_date": today,
            "source": s.get("source", ""),
            "title": s.get("title", ""),
            "summary": s.get("summary", "")[:500],
            "link": s.get("link", ""),
            "relevance_score": s.get("relevance_score", 0),
            "ai_triage_score": s.get("ai_score"),
            "ai_triage_reason": s.get("ai_reason", ""),
            "extracted_data_points": s.get("ai_data_points", []),
            "used_in_post": False,
        }
        supabase_insert("scrape_log", data)


# ── CACHE ──────────────────────────────────────────────────────────────────────

def save_cache(all_content: list, pillar_selection: dict):
    today = datetime.now().strftime("%Y-%m-%d")
    cache = {
        "date": today,
        "pillar_selection": {
            "pillar_id": pillar_selection.get("pillar_id", ""),
            "reasoning": pillar_selection.get("reasoning", ""),
            "suggested_angle": pillar_selection.get("suggested_angle", ""),
        },
        "content": all_content,
    }
    try:
        with open(CACHE_FILE, "w") as f:
            json.dump(cache, f)
        print(f"  💾 Cached for today ({today})")
    except Exception as e:
        print(f"  ⚠️  Cache save failed: {e}")


def load_cache() -> tuple:
    today = datetime.now().strftime("%Y-%m-%d")
    try:
        with open(CACHE_FILE) as f:
            cache = json.load(f)
        if cache.get("date") == today:
            print(f"  ✅ Found today's cache — skipping scrape")
            return cache["content"], cache.get("pillar_selection")
    except Exception:
        pass
    return None, None


# ── MAIN ───────────────────────────────────────────────────────────────────────

def main():
    now = datetime.now()
    regenerate_mode = os.environ.get("REGENERATE", "").lower() == "true"

    mode_label = "♻️  REGENERATE" if regenerate_mode else "🚀 FULL RUN"
    print(f"\n{mode_label} — {now.strftime('%A %Y-%m-%d %H:%M')}")
    print("=" * 60)

    # Validate config
    missing = [k for k, v in {
        "ANTHROPIC_API_KEY": ANTHROPIC_API_KEY,
        "TELEGRAM_BOT_TOKEN": TELEGRAM_BOT_TOKEN,
        "TELEGRAM_CHAT_ID": TELEGRAM_CHAT_ID,
    }.items() if not v]
    if missing:
        print(f"❌ Missing: {', '.join(missing)}")
        return

    client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)

    all_content = None
    pillar_selection = None

    # Try cache in regenerate mode
    if regenerate_mode:
        print("\n🔄 Regenerate mode — loading cache...")
        all_content, pillar_selection = load_cache()
        if all_content is None:
            print("  ⚠️  No cache — running full scrape")

    # ── PHASE 1: SCRAPE ───────────────────────────────────────────────
    if all_content is None:
        print(f"\n📺 Fetching podcast episodes...")
        podcast_episodes = fetch_youtube_episodes(YOUTUBE_CHANNEL_HANDLE, max_episodes=3)
        print(f"  Found {len(podcast_episodes)} episode(s)")

        print(f"\n🔍 Fetching industry news...")
        news_stories = fetch_rss_stories()
        print(f"  Found {len(news_stories)} relevant stories")

        all_content = podcast_episodes + news_stories

        # ── PHASE 2: AI EDITORIAL TRIAGE ──────────────────────────────
        print(f"\n🧠 Running AI editorial triage on {len(news_stories)} stories...")
        top_stories = editorial_triage(client, news_stories)
        print(f"  Top story: {top_stories[0]['title'][:60]}..." if top_stories else "  No stories rated")
        for s in top_stories[:3]:
            print(f"  📰 [{s.get('ai_score','?')}/10] {s['title'][:55]}...")

        # ── PHASE 3: DATA EXTRACTION ──────────────────────────────────
        article_intel = {}
        if top_stories:
            print(f"\n🔬 Extracting intelligence from top article...")
            full_text = fetch_article_text(top_stories[0].get("link", ""))
            if full_text:
                article_intel = extract_article_intelligence(
                    client, full_text, top_stories[0]["title"]
                )
                if article_intel.get("data_points"):
                    print(f"  Found data: {', '.join(article_intel['data_points'][:3])}")
            else:
                print("  ⚠️  Could not fetch full article text")

        # ── PHASE 4: ADAPTIVE PILLAR SELECTION ────────────────────────
        print(f"\n📌 Selecting best pillar for today...")
        recent_pillars = get_recent_pillars()
        pillar_selection = select_pillar(client, top_stories, recent_pillars)
        pillar_selection["article_intel"] = article_intel
        pillar_selection["top_stories"] = top_stories

        print(f"  Selected: {pillar_selection['pillar']['name']}")
        print(f"  Reason: {pillar_selection.get('reasoning', 'n/a')[:80]}")

        # Log scrape data
        log_scrape(all_content)
        save_cache(all_content, pillar_selection)
    else:
        # Rebuild from cache
        if pillar_selection and not isinstance(pillar_selection.get("pillar"), dict):
            # Reconstruct pillar object from cached pillar_id
            pid = pillar_selection.get("pillar_id", "")
            pillar_obj = next((p for p in CONTENT_PILLARS if p["id"] == pid), CONTENT_PILLARS[0])
            pillar_selection["pillar"] = pillar_obj
        if not pillar_selection:
            pillar_selection = select_pillar(client, [], [])

    top_stories = pillar_selection.get("top_stories", [])
    article_intel = pillar_selection.get("article_intel", {})

    # ── PHASE 5: FEEDBACK LOOP ────────────────────────────────────────
    print(f"\n📈 Loading performance history...")
    performance_context = get_top_performers()
    if performance_context:
        print("  Found past performance data — feeding into prompt")
    else:
        print("  No past data yet — will improve over time")

    # ── PHASE 6: GENERATE + SCORE + REGENERATE LOOP ───────────────────
    post_format = select_format()
    print(f"\n✍️  Generating {post_format} post...")

    best_result = None
    best_scores = None
    best_overall = 0

    for attempt in range(1, MAX_REGENERATION_ATTEMPTS + 1):
        result = generate_post(
            client, top_stories, pillar_selection,
            article_intel, performance_context, post_format,
        )

        print(f"\n📊 Scoring attempt {attempt}...")
        scores = score_post(client, result["post"], pillar_selection["pillar"]["name"])
        overall = scores.get("overall", 0)
        print(f"  Score: {overall}/10 — Hook:{scores.get('hook_strength','?')} "
              f"Data:{scores.get('data_density','?')} Dual:{scores.get('dual_audience','?')} "
              f"Spec:{scores.get('specificity','?')} Q:{scores.get('question_quality','?')}")

        if overall > best_overall:
            best_result = result
            best_scores = scores
            best_overall = overall

        if overall >= MIN_SCORE_THRESHOLD:
            print(f"  ✅ Passed quality gate ({overall} >= {MIN_SCORE_THRESHOLD})")
            break
        elif attempt < MAX_REGENERATION_ATTEMPTS:
            print(f"  🔄 Below threshold ({overall} < {MIN_SCORE_THRESHOLD}) — regenerating...")
            # Switch format on retry
            post_format = select_format()
        else:
            print(f"  ⚠️  Max attempts reached — using best ({best_overall}/10)")

    # ── PHASE 7: DELIVER + LOG ────────────────────────────────────────
    print(f"\n📨 Sending to Telegram...")
    send_to_telegram(best_result, best_scores, top_stories)

    print(f"\n💾 Logging to Supabase...")
    log_post(best_result, best_scores, top_stories)

    print(f"\n✅ Done — {best_result['pillar_name']} / {best_result['format']} / score {best_overall}\n")


if __name__ == "__main__":
    main()
