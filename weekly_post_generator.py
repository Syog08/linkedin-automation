#!/usr/bin/env python3
"""
LinkedIn Intelligence Engine — v3.1
=====================================
For Sergey Tadevosyan — CPO & Product Leader in iGaming

v3.1 changes:
- PM Experience Bank: 12 real career stories anchoring posts in genuine PM insight
- Pillar weights rebalanced: product_leadership ↑, modern_pm_in_igaming ↑,
  affiliate_economics ↓, igaming_product_ecosystem ↓
- pm_first_mode: ~35% of runs lead with career story, news becomes supporting context
- Added Product Talk + Intercom to RSS feeds
- Stronger PM keywords in tier 1 scoring

Environment variables:
  ANTHROPIC_API_KEY, TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID,
  SUPABASE_URL, SUPABASE_KEY, REGENERATE (optional)
"""

import os
import re
import json
import random
import feedparser
import requests
from bs4 import BeautifulSoup
from datetime import datetime
import anthropic

# ── CONFIG ─────────────────────────────────────────────────────────────────────

ANTHROPIC_API_KEY  = os.environ.get("ANTHROPIC_API_KEY")
TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID   = os.environ.get("TELEGRAM_CHAT_ID")
SUPABASE_URL       = os.environ.get("SUPABASE_URL", "")
SUPABASE_KEY       = os.environ.get("SUPABASE_KEY", "")

CACHE_FILE = "/tmp/linkedin_post_cache.json"
MIN_SCORE_THRESHOLD = 6.5
MAX_REGENERATION_ATTEMPTS = 3

YOUTUBE_CHANNEL_HANDLE = "TrackingtheTruthPodcast"

# ── CONTENT PILLARS ────────────────────────────────────────────────────────────

CONTENT_PILLARS = [
    {
        "id": "data_driven_product",
        "name": "Data-Driven Product Decisions in iGaming",
        "weight": 25,
        "description": (
            "How Sergey uses data to make product decisions in the iGaming affiliate space. "
            "The gap between having dashboards and actually changing decisions. Metrics that "
            "predict affiliate programme outcomes vs metrics that describe the past. Building "
            "data products inside the affiliate ecosystem. Why most operator reporting is useless."
        ),
        "example_angles": [
            "We built a reporting dashboard for operators with 30 metrics. They used 3. Here's what I learned about data products.",
            "Most affiliate programmes track FTD count. The metric that actually predicts programme health is FTD-to-second-deposit rate.",
            "The difference between data that's available and data that changes a decision — illustrated by how operators evaluate affiliate quality.",
            "I stopped asking 'what do operators want to see?' and started asking 'what decision are they trying to make?' Everything changed.",
        ],
    },
    {
        "id": "product_leadership",
        "name": "Product Leadership in a Complex B2B Industry",
        "weight": 30,
        "description": (
            "How Sergey leads product teams to deliver value in iGaming — one of the most "
            "complex regulated B2B industries. Prioritisation when every operator wants something "
            "different. Saying no to features. Using modern PM craft (AI tools, outcome hypotheses, "
            "experimentation) in an industry that's traditionally been feature-factory-driven."
        ),
        "example_angles": [
            "When 50 operators each want a different commission model, here's how I decide what to build first.",
            "The hardest 'no' I ever gave a client — and why the data backed me up.",
            "Most iGaming B2B teams ship features. The best ones ship measurable outcomes. Here's the difference.",
            "How I use AI tools in my daily product work — and where they completely fail in regulated industries.",
        ],
    },
    {
        "id": "igaming_product_ecosystem",
        "name": "iGaming Platforms & Product Ecosystem",
        "weight": 15,
        "description": (
            "The product challenges of building for the iGaming affiliate ecosystem — "
            "operators, affiliate platforms, data intelligence, payments. What makes great "
            "B2B iGaming products vs mediocre ones. Multi-market, multi-regulatory complexity "
            "as a product design problem. How AI is reshaping what's possible."
        ),
        "example_angles": [
            "Why iGaming affiliate platforms are some of the hardest B2B products to build — and what PM lessons they teach.",
            "Building for 50 regulatory markets isn't a compliance problem. It's a product architecture problem.",
            "The affiliate platform your top affiliates actually want looks nothing like what most operators asked for.",
            "AI in iGaming: the real use cases I'm seeing vs the conference buzzwords.",
        ],
    },
    {
        "id": "affiliate_economics",
        "name": "Affiliate Programme Economics & Strategy",
        "weight": 10,
        "description": (
            "The economics and strategy behind affiliate programmes — commission models, "
            "player value, programme performance metrics. Seen through the lens of someone "
            "who has been inside both an affiliate publisher and the software that powers programmes. "
            "Always connected to a product or data insight."
        ),
        "example_angles": [
            "Most CPA deals are priced using competitor rates, not player LTV data. That's a product opportunity.",
            "The 90/10 rule: about 10% of affiliates drive 90% of value. How should that shape the product you build for them?",
            "Commission models aren't commercial decisions. They're product design decisions. Here's why.",
            "What I learned about affiliate economics by sitting on both sides of the table — and how it changed what I build.",
        ],
    },
    {
        "id": "modern_pm_in_igaming",
        "name": "Modern Product Thinking Meets iGaming",
        "weight": 20,
        "description": (
            "Where modern product management thinking (AI tools, outcome-driven development, "
            "continuous discovery, experimentation) meets the reality of building for iGaming. "
            "What works from the PM playbook, what doesn't, and what needs adapting."
        ),
        "example_angles": [
            "I tried applying continuous discovery in iGaming B2B. Here's what worked and what crashed into regulatory reality.",
            "The PM frameworks that break in regulated industries — and the ones that become more powerful.",
            "Everyone's using AI to write user stories. I'm more interested in AI that predicts which affiliate will churn.",
            "Outcome-driven roadmaps sound great until your biggest client needs a compliance feature by Tuesday.",
        ],
    },
]

# ── PM EXPERIENCE BANK ─────────────────────────────────────────────────────────
# Real career stories and product management lessons from Sergey's experience.
# These anchor posts in genuine personal insight rather than invented examples.
# Claude uses these as primary springboards, especially when pm_first_mode=True.

PM_EXPERIENCE_BANK = [
    {
        "id": "dashboard_unused_metrics",
        "hook": "We built a reporting module with 30 metrics. Operators used 3.",
        "story": (
            "When I launched a new analytics section for affiliate programme operators, "
            "I added every metric I could think of — FTD count, FTD rate, NDC, revenue by geo, "
            "by device, by affiliate tier, margins, click-to-FTD conversion... everything. "
            "Then I tracked which ones they actually opened. Three. Revenue, FTD count, and a "
            "custom trend metric I almost didn't build. The rest was noise."
        ),
        "insight": (
            "Data products fail when you optimise for completeness instead of decision support. "
            "The question is never 'what data can we show?' — it's 'what decision are we helping make?'"
        ),
        "pillar": "data_driven_product",
        "format_hint": "data_insight",
    },
    {
        "id": "ftd_second_deposit",
        "hook": "Most affiliate programmes track first deposits. The number that actually predicts programme health is the second-deposit rate.",
        "story": (
            "I started correlating FTD counts against second-deposit rates across affiliate cohorts. "
            "The affiliates sending the most first-time depositors often had the worst second-deposit rates. "
            "Meanwhile the programme was paying CPA on every FTD — "
            "essentially paying for players who churned in their first session."
        ),
        "insight": (
            "The metric you pay on becomes the metric affiliates optimise for. "
            "If you pay on FTDs, you attract affiliates who are good at driving first deposits — "
            "regardless of what happens after. That's a product design problem, not a commercial one."
        ),
        "pillar": "data_driven_product",
        "format_hint": "data_insight",
    },
    {
        "id": "ltv_vs_competitor_cpa",
        "hook": "Most CPA deals I've seen are priced using competitor rates, not player LTV data.",
        "story": (
            "When I worked on the data product side of an affiliate publisher, I checked how often "
            "operator CPA rates correlated with actual player lifetime value from that source. "
            "Almost never. Rates were set by looking at what the market offered — "
            "not what a depositing player was actually worth. "
            "The operators with the highest CPAs weren't the most generous. They had better LTV models."
        ),
        "insight": (
            "If you don't have a reliable player LTV model, you're guessing at your commission rates. "
            "That's not a commercial problem — it's a data product gap."
        ),
        "pillar": "affiliate_economics",
        "format_hint": "contrarian",
    },
    {
        "id": "commission_as_product_design",
        "hook": "Commission models are not commercial decisions. They're product design decisions.",
        "story": (
            "I spent months watching commercial teams debate RevShare vs CPA as if it was a pricing problem. "
            "It's not. Every model creates a different incentive: CPA rewards volume, RevShare rewards quality, "
            "Hybrid tries to balance both. The debate should start with: what affiliate behaviour "
            "do you want to encourage? The commercial team was asking 'how much?' "
            "The product question is 'optimise for what?'"
        ),
        "insight": (
            "The commission structure IS the product mechanism. When you design it, you're designing "
            "what affiliates optimise for — and therefore what players arrive."
        ),
        "pillar": "affiliate_economics",
        "format_hint": "contrarian",
    },
    {
        "id": "b2b_prioritisation_outcomes",
        "hook": "When 50 operators each want a different feature, the list doesn't need prioritisation. It needs collapsing.",
        "story": (
            "Early in B2B iGaming product work I treated every operator request as a distinct feature. "
            "The backlog grew to hundreds of items. "
            "Then I stopped asking 'what do operators want?' and started asking 'what outcome are they trying to achieve?' "
            "The list collapsed by about 70%. "
            "Most requests were different expressions of the same 6 underlying needs."
        ),
        "insight": (
            "In multi-tenant B2B products, surface-level requests compress into a handful of underlying outcomes. "
            "Discover the outcomes and prioritisation becomes dramatically simpler. "
            "Staying at the feature level keeps the backlog infinite."
        ),
        "pillar": "product_leadership",
        "format_hint": "product_lesson",
    },
    {
        "id": "no_to_feature",
        "hook": "The hardest 'no' I gave a client changed how I think about product leadership.",
        "story": (
            "A large operator requested a specific commission calculation feature tied to their "
            "unusual internal accounting setup. Dev cost was significant; it served one client. "
            "The request came with revenue pressure. I said no — and offered instead to solve "
            "the underlying reconciliation problem differently. The alternative took one week. "
            "Twelve other operators later asked for the same solution."
        ),
        "insight": (
            "Saying no to a feature is easy. Saying no while genuinely solving the underlying problem "
            "is product leadership. That's the difference between order-taking and building."
        ),
        "pillar": "product_leadership",
        "format_hint": "product_lesson",
    },
    {
        "id": "b2b_onboarding_product_problem",
        "hook": "Operator onboarding is the most underrated growth lever in iGaming B2B platforms.",
        "story": (
            "When I audited operator activation on our platform, operators who completed a specific "
            "setup sequence within 7 days had roughly 3x the 90-day retention of those who didn't. "
            "But most operators never completed that sequence. "
            "The product made it easy to sign up and made setup optional. "
            "Those were two separate decisions — one deliberate, one by accident."
        ),
        "insight": (
            "In B2B iGaming platforms, onboarding isn't a customer success problem. "
            "It's a product design problem. The path to value needs to be the default path — not the optional one."
        ),
        "pillar": "product_leadership",
        "format_hint": "observation",
    },
    {
        "id": "90_10_affiliate_product",
        "hook": "About 10% of affiliates drive roughly 90% of programme value. Most platforms are built for the 90%.",
        "story": (
            "When I segmented affiliate programme data by actual revenue contribution, "
            "the distribution was more extreme than any Pareto I'd seen. "
            "The top decile drove nearly everything. But the feature roadmap was dominated "
            "by requests from the long tail — they were louder and more numerous. "
            "What our top affiliates actually needed was completely different: "
            "better data exports, faster reporting, flexible deal structures."
        ),
        "insight": (
            "In affiliate platforms you're building two products: a mass-market tool for the long tail, "
            "and a high-performance tool for the top tier. "
            "Most teams build one and wonder why their most valuable affiliates quietly migrate."
        ),
        "pillar": "igaming_product_ecosystem",
        "format_hint": "data_insight",
    },
    {
        "id": "outcome_roadmap_regulated",
        "hook": "Outcome-driven roadmaps sound great until your biggest client needs a compliance feature by Tuesday.",
        "story": (
            "I've run product teams using outcome-based roadmapping in iGaming B2B. "
            "The framework is powerful — until regulatory deadlines land. "
            "In a multi-market regulated industry, compliance requirements aren't user needs "
            "you can deprioritise. They're hard constraints with dates. "
            "The first time a major compliance deadline hit mid-sprint, the whole framework nearly collapsed. "
            "We had to adapt it significantly."
        ),
        "insight": (
            "Modern PM frameworks need adapting for regulated industries. The skill is knowing "
            "which parts apply, which need modifying, and which to set aside entirely. "
            "Applying them wholesale often creates more friction than value."
        ),
        "pillar": "modern_pm_in_igaming",
        "format_hint": "contrarian",
    },
    {
        "id": "ai_fraud_vs_content",
        "hook": "Everyone's talking about AI for content generation. The real iGaming affiliate use case is fraud detection.",
        "story": (
            "Affiliate fraud patterns are surprisingly consistent: traffic spikes without conversion lag, "
            "geo mismatches between clicks and signups, device fingerprint clustering. "
            "These are nearly invisible in standard dashboards but trivial for a well-trained classification model. "
            "I've seen fraud rates drop significantly when detection moved from rules-based to model-based. "
            "Meanwhile most 'AI in iGaming' discussions are still about chatbots."
        ),
        "insight": (
            "In regulated industries, AI earns trust fastest when it solves problems manual processes "
            "genuinely can't keep up with. Fraud detection is that problem. Content generation is not."
        ),
        "pillar": "modern_pm_in_igaming",
        "format_hint": "contrarian",
    },
    {
        "id": "multi_market_architecture",
        "hook": "Building for 50 regulatory markets isn't a compliance problem. It's a product architecture problem.",
        "story": (
            "Early in platform product work, regulatory requirements were treated as compliance layers "
            "bolted on after the fact. The result was a fragile codebase with market-specific hacks everywhere — "
            "brittle, expensive, slow to update. "
            "When I reframed it as a product design challenge — how do we build a configurable system "
            "that adapts to market rules by design? — the architecture became cleaner "
            "and the compliance team stopped being a bottleneck."
        ),
        "insight": (
            "Regulatory flexibility is a product capability, not a compliance tax. "
            "Teams that treat it as a product feature build more durable platforms. "
            "Teams that treat it as an afterthought rebuild every time a market changes."
        ),
        "pillar": "igaming_product_ecosystem",
        "format_hint": "contrarian",
    },
    {
        "id": "banking_to_igaming_lesson",
        "hook": "The product lesson I carried from digital banking into iGaming: people don't use features, they use answers.",
        "story": (
            "In digital banking, users never asked for 'a transaction history view.' "
            "They asked to understand whether they could afford something. "
            "The feature is a means to an answer. "
            "When I moved into iGaming affiliate products, I found the same pattern — "
            "operators don't want dashboards, they want confidence in one question: is my programme healthy?"
        ),
        "insight": (
            "The right product question isn't 'what feature should I build?' "
            "It's 'what question is the user trying to answer?' "
            "That question travels across industries. The iGaming context is different. The human problem is not."
        ),
        "pillar": "modern_pm_in_igaming",
        "format_hint": "observation",
    },
]

# ── NEWS SOURCES ───────────────────────────────────────────────────────────────

RSS_FEEDS = [
    # iGaming & affiliate sources
    ("iGB",              "https://igamingbusiness.com/feed/"),
    ("AffiliateINSIDER", "https://affiliateinsider.com/feed/"),
    ("EGR Global",       "https://egrglobal.com/feed/"),
    ("CalvinAyre",       "https://calvinayre.com/feed/"),
    ("SiGMA",            "https://sigma.world/news/feed/"),
    ("Gambling Insider", "https://gamblinginsider.com/feed/"),
    ("GPWA",             "https://www.gpwa.org/feed/"),
    ("Affiliate Guard Dog", "https://www.affiliateguarddog.com/feed/"),
    ("AffRoom",          "https://www.affroom.com/feed/"),
    ("AffiliateFix",     "https://affiliatefix.com/forums/igaming.54/index.rss"),
    # Product management sources
    ("Lenny's Newsletter",     "https://www.lennysnewsletter.com/feed"),
    ("SVPG",                   "https://www.svpg.com/feed/"),
    ("Mind the Product",       "https://www.mindtheproduct.com/feed/"),
    ("ProductBoard Blog",      "https://www.productboard.com/blog/feed/"),
    ("Shreyas Doshi",          "https://www.shreyasdoshi.com/feed"),
    ("The Pragmatic Engineer", "https://newsletter.pragmaticengineer.com/feed"),
    ("One Knight in Product",  "https://www.oneknightinproduct.com/feed"),
    ("Product Talk",           "https://www.producttalk.org/feed/"),
    ("Intercom Blog",          "https://www.intercom.com/blog/feed"),
]

# Keyword tiers
KEYWORD_TIERS = {
    3: [
        "commission", "revshare", "revenue share", "cpa", "hybrid",
        "ltv", "lifetime value", "ftd", "player value",
        "affiliate programme", "affiliate software", "affiliate platform",
        "data product", "data-driven", "metrics", "kpi", "benchmark",
        "product management", "product strategy", "product leader", "cpo",
        "prioritisation", "roadmap", "migration", "feature adoption",
        "ai in product", "ai product management", "llm", "generative ai",
        "product discovery", "continuous discovery", "jobs to be done", "jtbd",
        "outcome-driven", "north star metric", "activation rate", "churn rate",
        "product-market fit", "b2b product", "platform product", "product ops",
        "user research", "hypothesis testing", "experiment",
    ],
    2: [
        "affiliate", "operator", "igaming", "online casino", "sportsbook",
        "b2b", "saas", "platform", "product development",
        "analytics", "bi ", "business intelligence", "roi", "conversion rate",
        "regulation", "ukgc", "mga", "compliance", "licensing",
        "acquisition", "merger", "partnership", "funding",
        "catena media", "better collective", "raketech",
        "partnermatrix", "myaffiliates", "netrefer", "affilka", "cellxpert",
        "product-led", "outcome", "validation",
        "ai agent", "copilot", "automation", "workflow",
    ],
    1: [
        "gambling", "betting", "casino", "pam", "payment",
        "telegram", "streamer", "influencer",
        "team", "leadership", "hire", "culture", "cross-functional",
        "ai ", "artificial intelligence", "machine learning",
        "responsible gambling", "fraud",
    ],
}


# ── SUPABASE HELPERS ───────────────────────────────────────────────────────────

def supabase_insert(table: str, data: dict) -> bool:
    if not SUPABASE_URL or not SUPABASE_KEY:
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
        return resp.status_code in (200, 201)
    except Exception as e:
        print(f"  ⚠️  Supabase error: {e}")
    return False


def supabase_query(table: str, select: str = "*", params: str = "") -> list:
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
    except Exception:
        pass
    return []


# ── YOUTUBE SCRAPING ───────────────────────────────────────────────────────────

def get_youtube_channel_id(handle: str) -> str | None:
    url = f"https://www.youtube.com/@{handle}"
    try:
        headers = {"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"}
        resp = requests.get(url, headers=headers, timeout=10)
        for pattern in [r'"channelId":"(UC[a-zA-Z0-9_-]{22})"', r'"externalId":"(UC[a-zA-Z0-9_-]{22})"']:
            match = re.search(pattern, resp.text)
            if match:
                return match.group(1)
    except Exception as e:
        print(f"  ⚠️  YouTube channel resolve failed: {e}")
    return None


def fetch_youtube_episodes(handle: str, max_episodes: int = 3) -> list[dict]:
    channel_id = get_youtube_channel_id(handle)
    if not channel_id:
        return []
    rss_url = f"https://www.youtube.com/feeds/videos.xml?channel_id={channel_id}"
    episodes = []
    try:
        feed = feedparser.parse(rss_url)
        for entry in feed.entries[:max_episodes]:
            description = ""
            if hasattr(entry, "media_group"):
                description = str(entry.media_group)[:500]
            elif entry.get("summary"):
                description = BeautifulSoup(entry.get("summary", ""), "html.parser").get_text()[:500]
            episodes.append({
                "source": "Tracking the Truth Podcast",
                "title": entry.get("title", ""),
                "summary": description.strip(),
                "link": entry.get("link", ""),
                "published": entry.get("published", ""),
                "type": "podcast_episode",
            })
    except Exception as e:
        print(f"  ⚠️  YouTube RSS failed: {e}")
    return episodes


# ── NEWS SCRAPING ──────────────────────────────────────────────────────────────

def score_relevance(text: str) -> int:
    text_lower = text.lower()
    score = 0
    for points, keywords in KEYWORD_TIERS.items():
        for kw in keywords:
            if kw in text_lower:
                score += points
    return score


def get_pm_experience_springboard(pillar_id: str = "") -> dict | None:
    """Return a PM experience entry for the given pillar, or any entry if no match."""
    candidates = [e for e in PM_EXPERIENCE_BANK if e.get("pillar") == pillar_id] if pillar_id else []
    if not candidates:
        candidates = PM_EXPERIENCE_BANK
    return random.choice(candidates) if candidates else None


def fetch_rss_stories(max_per_feed: int = 6) -> list[dict]:
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
    return stories[:15]


def fetch_article_text(url: str, max_chars: int = 3000) -> str:
    try:
        resp = requests.get(url, headers={"User-Agent": "Mozilla/5.0"}, timeout=8)
        soup = BeautifulSoup(resp.text, "html.parser")
        for tag in soup(["script", "style", "nav", "footer", "header", "aside"]):
            tag.decompose()
        return soup.get_text(separator=" ", strip=True)[:max_chars]
    except Exception:
        return ""


# ── AI EDITORIAL TRIAGE ───────────────────────────────────────────────────────

def editorial_triage(client: anthropic.Anthropic, stories: list[dict]) -> list[dict]:
    if not stories:
        return []

    stories_text = ""
    for i, s in enumerate(stories, 1):
        stories_text += f"{i}. [{s['source']}] {s['title']}\n"
        if s.get("summary"):
            stories_text += f"   {s['summary'][:200]}\n\n"

    prompt = f"""You are an editorial strategist for a CPO and product leader who works in the iGaming industry.

His audience: product managers, iGaming professionals, data people, B2B SaaS leaders, and curious generalists.

Rate each story 1-10 on how well it can serve as a SPRINGBOARD for a post about:
- Product management and leadership
- Data-driven decision making
- B2B platform building and product strategy
- iGaming industry economics and how products create value

A story about "affiliate tracking" scores LOW unless it connects to a product or data decision.
A story about "company acquisition" scores HIGH if it reveals something about product strategy or market dynamics.
A story about "regulation change" scores HIGH if it has implications for how products need to be rebuilt.

STORIES:
{stories_text}

Respond in JSON only. No preamble:
[
  {{"index": 1, "score": 8, "reason": "...", "data_points": ["any numbers mentioned"], "product_angle": "how a CPO/product leader would react to this — the product/data insight, not the news itself"}}
]"""

    try:
        message = client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=2000,
            messages=[{"role": "user", "content": prompt}],
        )
        raw = message.content[0].text.strip()
        raw = re.sub(r"^```json\s*", "", raw)
        raw = re.sub(r"\s*```$", "", raw)
        ratings = json.loads(raw)
        for rating in ratings:
            idx = rating.get("index", 0) - 1
            if 0 <= idx < len(stories):
                stories[idx]["ai_score"] = rating.get("score", 0)
                stories[idx]["ai_reason"] = rating.get("reason", "")
                stories[idx]["ai_data_points"] = rating.get("data_points", [])
                stories[idx]["ai_product_angle"] = rating.get("product_angle", "")
        stories.sort(key=lambda x: x.get("ai_score", 0), reverse=True)
        return stories[:5]
    except Exception as e:
        print(f"  ⚠️  Triage failed: {e}")
        return stories[:5]


# ── DATA EXTRACTION ────────────────────────────────────────────────────────────

def extract_article_intelligence(client: anthropic.Anthropic, article_text: str, title: str) -> dict:
    if not article_text or len(article_text) < 100:
        return {}
    prompt = f"""Extract intelligence from this iGaming article for a CPO and product leader.

TITLE: {title}
TEXT: {article_text[:2500]}

Respond in JSON only:
{{
  "data_points": ["specific numbers, percentages, deal sizes, metrics mentioned — ONLY real ones from the text, do not invent any"],
  "product_implications": ["what this means for product strategy, platform building, or data decisions"],
  "entities": ["companies, people, regulators, markets mentioned"],
  "springboard": "one sentence: the product/data insight a CPO would extract from this"
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
        print(f"  ⚠️  Extraction failed: {e}")
        return {}


# ── ADAPTIVE PILLAR SELECTION ──────────────────────────────────────────────────

def select_pillar(client: anthropic.Anthropic, top_stories: list[dict], recent_pillars: list[str]) -> dict:
    pillar_descriptions = "\n".join(
        f"- {p['id']} (weight: {p['weight']}%): {p['name']} — {p['description']}"
        for p in CONTENT_PILLARS
    )
    stories_summary = "\n".join(
        f"- [{s['source']}] {s['title']} (score: {s.get('ai_score', '?')}, product angle: {s.get('ai_product_angle', 'n/a')})"
        for s in top_stories[:5]
    ) if top_stories else "No stories available"
    recent_text = ", ".join(recent_pillars[-4:]) if recent_pillars else "none"

    prompt = f"""Select today's content pillar for Sergey Tadevosyan's LinkedIn.

SERGEY IS: A CPO and product leader in the iGaming industry. He builds B2B products, leads teams, uses data to make decisions. iGaming affiliates are ONE part of his world, not all of it.

PILLARS (higher weight = pick more often):
{pillar_descriptions}

TOP STORIES:
{stories_summary}

RECENT PILLARS (avoid repeating): {recent_text}

RULES:
1. Respect the weights — product_leadership (30%) and data_driven_product (25%) should dominate
2. modern_pm_in_igaming (20%) should appear regularly — don't neglect it
3. affiliate_economics (10%) should be rare — only when truly compelling
4. The post should feel like a CPO wrote it, not an affiliate manager
5. Even affiliate-related news should be framed through a product/data lens
6. Pick the pillar where Sergey can share the deepest, most original insight

JSON only:
{{
  "pillar_id": "...",
  "reasoning": "...",
  "suggested_angle": "the specific product/data insight to build the post around"
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
        pillar_obj = next((p for p in CONTENT_PILLARS if p["id"] == result.get("pillar_id")), None)
        if pillar_obj:
            result["pillar"] = pillar_obj
            return result
    except Exception as e:
        print(f"  ⚠️  Pillar selection failed: {e}")

    week = datetime.now().isocalendar()[1]
    dow = datetime.now().weekday()
    day_offset = {1: 0, 3: 1, 5: 2}.get(dow, 0)
    index = (week * 3 + day_offset) % len(CONTENT_PILLARS)
    return {"pillar": CONTENT_PILLARS[index], "pillar_id": CONTENT_PILLARS[index]["id"],
            "reasoning": "fallback", "suggested_angle": ""}


# ── FEEDBACK LOOP ──────────────────────────────────────────────────────────────

def get_top_performers() -> str:
    rows = supabase_query(
        "post_performance",
        select="hook_line,pillar,engagement_rate,comments,format_type,has_data_point",
        params="posted=eq.true&engagement_rate=not.is.null&order=engagement_rate.desc&limit=3",
    )
    if not rows:
        return ""
    block = "YOUR TOP-PERFORMING POSTS (learn from these):\n\n"
    for i, r in enumerate(rows, 1):
        block += f"{i}. Hook: \"{r.get('hook_line', 'n/a')}\"\n"
        block += f"   Pillar: {r.get('pillar', '?')} | Format: {r.get('format_type', '?')} | "
        block += f"Data: {'Yes' if r.get('has_data_point') else 'No'} | "
        block += f"Engagement: {r.get('engagement_rate', '?')}% | Comments: {r.get('comments', '?')}\n\n"
    return block


def get_recent_pillars() -> list[str]:
    rows = supabase_query("post_performance", select="pillar", params="order=post_date.desc&limit=4")
    return [r.get("pillar", "") for r in rows]


# ── THE SYSTEM PROMPT ──────────────────────────────────────────────────────────

SYSTEM_PROMPT = """You are a ghostwriter for Sergey Tadevosyan — a CPO and product leader based in Malta, working in the iGaming affiliate industry.

WHO SERGEY IS:
- Chief Product Officer who builds B2B products in the iGaming affiliate space.
- He is an AUTHORITY on iGaming affiliate business — one of the few people who has worked inside both a major affiliate publisher (building data products) AND in affiliate management software (as CPO).
- His superpower: he sees the affiliate industry through a product management and data lens. He doesn't just know how affiliate programmes work — he knows how to build PRODUCTS and SYSTEMS that make them work better.
- He uses data to make decisions, leads product teams, and cares about modern product craft (AI in PM, outcome-driven development, experimentation).
- Personal brand only — NEVER mention any company, product, or employer by name.

THE GOLDEN RULE — READ THIS CAREFULLY:
- iGaming affiliate is the WORLD Sergey operates in. All examples, data, stories come from this world.
- Product management, data, leadership is the LENS through which he sees that world.
- The post should feel like: "a product leader who deeply understands iGaming affiliate business shares how he thinks about [topic]"
- NOT like: "an affiliate manager who read some PM articles" or "a PM who knows nothing about iGaming"
- 70% of posts should be understandable by a product manager who doesn't know iGaming deeply — but the examples and data are ALWAYS from iGaming affiliate.
- NEVER use examples from fintech, e-commerce, or generic SaaS. ALWAYS iGaming affiliate examples.

WHAT SERGEY WRITES ABOUT:
1. Product management craft — applied to iGaming affiliate: prioritisation, saying no, building for behaviour change, shipping outcomes.
2. Data-driven decisions — in the affiliate context: what metrics predict programme success, why most affiliate reporting fails, how data changes product roadmaps.
3. AI & modern PM — applied to iGaming: how AI changes affiliate fraud detection, how LLMs could transform operator reporting, what AI means for product teams in regulated industries.
4. iGaming affiliate economics — through product eyes: commission models as product design problems, player value as a data product challenge, programme performance as a system design question.
5. Team leadership — with iGaming context: building product culture in B2B iGaming, hiring PMs for regulated industries, cross-functional work with compliance teams.

LENGTH: 150-180 words max (excluding hashtags). No exceptions. Count carefully.

VOICE:
- Curious, confident, grounded in real experience
- Short paragraphs. Often single sentences.
- Opens with an observation or question — NEVER a bold claim
- Builds gradually. Names the insight clearly. Ends with a genuine question.
- Emojis: use 2-3 per post as STRUCTURAL signposts (👉 for key insight, 📊 before data, 💡 before lesson, 🎯 for core point). Never decorative. Never at the start of every line.
- Hashtags: exactly 3 on last line. Rotate from: #ProductManagement #iGaming #DataProducts #B2BSaaS #ProductLeadership #iGamingAffiliateMarketing #AffiliateMarketing

DATA & NUMBERS RULE:
- Include at least one specific number or benchmark per post.
- If from a source article: reference vaguely ("Recent industry data shows...", "A report this week noted...")
- If from Sergey's experience: frame it ("In my experience...", "Across programmes I've worked with...", "In most cases I've seen...")
- NEVER invent precise statistics. "About 60-70%" is honest. "63.4%" without a source is not.

WHAT TO AVOID:
- Generic SaaS, fintech, or e-commerce examples
- Pure affiliate-manager-speak with no product thinking visible
- Posts about tracking technology implementation details
- Summarising news without a product/data/leadership insight
- Generic LinkedIn platitudes

THE TEST: Would a product leader at any B2B company find the THINKING interesting? Would an iGaming insider find the EXAMPLES credible? Both must be true."""


# ── POST FORMATS ───────────────────────────────────────────────────────────────

def select_format() -> str:
    weights = {
        "observation": 25,
        "data_insight": 30,
        "product_lesson": 20,
        "contrarian": 15,
        "industry_lens": 10,
    }
    population = []
    for fmt, weight in weights.items():
        population.extend([fmt] * weight)
    return random.choice(population)


# ── POST GENERATION ────────────────────────────────────────────────────────────

def generate_post(
    client,
    top_stories,
    pillar_selection,
    article_intel,
    performance_context,
    post_format,
    pm_experience: dict = None,
    pm_first_mode: bool = False,
):
    pillar = pillar_selection["pillar"]
    suggested_angle = pillar_selection.get("suggested_angle", "")

    context_block = ""

    # PM experience — always include when available; position depends on mode
    if pm_experience and pm_first_mode:
        context_block += (
            "YOUR CAREER STORY — PRIMARY SPRINGBOARD\n"
            "(Lead with this. Expand it in Sergey's voice. Use news only as a brief supporting reference.)\n\n"
        )
        context_block += f"Hook: {pm_experience['hook']}\n"
        context_block += f"Story: {pm_experience['story']}\n"
        context_block += f"Insight: {pm_experience['insight']}\n\n"

    if top_stories:
        context_block += "INDUSTRY NEWS THIS WEEK (use as springboard or supporting context):\n\n"
        for i, s in enumerate(top_stories[:3], 1):
            context_block += f"{i}. [{s['source']}] {s['title']}\n"
            if s.get("ai_product_angle"):
                context_block += f"   Product angle: {s['ai_product_angle']}\n"
            if s.get("ai_data_points"):
                context_block += f"   Real data from article: {', '.join(s['ai_data_points'])}\n"
            if s.get("summary"):
                context_block += f"   Summary: {s['summary'][:150]}\n"
            context_block += "\n"

    if article_intel:
        context_block += "EXTRACTED INTELLIGENCE FROM TOP ARTICLE:\n"
        if article_intel.get("data_points"):
            context_block += f"  Real data points: {', '.join(article_intel['data_points'])}\n"
        if article_intel.get("product_implications"):
            context_block += f"  Product implications: {', '.join(article_intel['product_implications'][:2])}\n"
        if article_intel.get("springboard"):
            context_block += f"  CPO insight: {article_intel['springboard']}\n"
        context_block += "\n"

    if pm_experience and not pm_first_mode:
        context_block += (
            "YOUR CAREER STORY — AVAILABLE SPRINGBOARD\n"
            "(Use this if it's stronger than the news angle, or blend it in.)\n\n"
        )
        context_block += f"Hook: {pm_experience['hook']}\n"
        context_block += f"Story: {pm_experience['story']}\n"
        context_block += f"Insight: {pm_experience['insight']}\n\n"

    if performance_context:
        context_block += f"\n{performance_context}\n"

    pm_first_instruction = ""
    if pm_first_mode:
        pm_first_instruction = (
            "\n\nPM-FIRST MODE — CRITICAL: This post MUST be built around the career story above. "
            "Start from Sergey's real experience. Expand it, sharpen the insight, give it the iGaming affiliate context. "
            "Any news reference should be one line max and subordinate to the personal story. "
            "The post should feel like a product leader sharing a hard-won lesson — not a reaction to industry news."
        )

    user_prompt = f"""Write one LinkedIn post for Sergey.

PILLAR: {pillar['name']} — {pillar['description']}

FORMAT: {post_format}
- observation: notice a pattern in iGaming/affiliate → explain with product/data thinking → question
- data_insight: a real number from iGaming affiliate → what it means for product decisions → question
- product_lesson: something learned building iGaming products → what happened → the PM insight → question
- contrarian: common iGaming belief → why the data/product thinking disagrees → question
- industry_lens: iGaming news (brief) → product/data implication → question

SUGGESTED ANGLE: {suggested_angle if suggested_angle else "Choose the strongest angle from the pillar examples or the career story."}

PILLAR EXAMPLE ANGLES:
{chr(10).join(f'- {a}' for a in pillar.get('example_angles', []))}

{context_block if context_block else "No news found — write from product leadership experience in iGaming affiliate."}

THE IDENTITY RULE:
- Sergey is an iGaming affiliate authority who THINKS like a product leader.
- ALL examples must come from iGaming affiliate: operators, affiliates, commission models, player data, affiliate platforms.
- The INSIGHT should be a product management or data lesson that any PM would find valuable.
- Pattern: "Here's something from iGaming affiliate [specific example] → here's the product/data lesson [universal insight] → question"

DATA SOURCING:
- From article → "Recent industry data shows...", "A report this week noted..."
- From experience → "In my experience...", "Across programmes I've worked with..."
- NEVER state precise numbers without framing.
{pm_first_instruction}

Output ONLY the post text. No preamble."""

    try:
        message = client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=1000,
            system=SYSTEM_PROMPT,
            messages=[{"role": "user", "content": user_prompt}],
        )
        return {
            "post": message.content[0].text.strip(),
            "pillar_id": pillar["id"],
            "pillar_name": pillar["name"],
            "format": post_format,
            "suggested_angle": suggested_angle,
            "pm_first_mode": pm_first_mode,
            "pm_experience_id": pm_experience.get("id", "") if pm_experience else "",
            "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M"),
        }
    except Exception as e:
        print(f"  ⚠️  Post generation API call failed: {e}")
        return None


# ── POST SCORING ───────────────────────────────────────────────────────────────

def score_post(client, post_text, pillar_name):
    prompt = f"""Score this LinkedIn post. The author is a CPO and product leader in iGaming.

POST:
---
{post_text}
---

PILLAR: {pillar_name}

Rate 1-10:
1. HOOK: Would a product leader stop scrolling?
2. DATA INTEGRITY: Does it include a real number AND frame where it comes from? Orphan stats = low score.
3. PRODUCT DEPTH: Does it land on a genuine product management, data, or platform insight — not just industry commentary?
4. UNIVERSAL APPEAL: Would a PM at Stripe or Shopify find this interesting, while an iGaming insider finds it credible?
5. QUESTION: Does the closing question invite debate about product/data decisions?

CRITICAL: If the post reads like iGaming industry news with numbers sprinkled in — but lacks a real product/data insight — overall MUST be below 6.0.

JSON only:
{{
  "hook_strength": 7,
  "data_integrity": 8,
  "product_depth": 6,
  "universal_appeal": 7,
  "question_quality": 7,
  "overall": 7.0,
  "strengths": "...",
  "weaknesses": "...",
  "suggestion": "one specific edit"
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
        return {"overall": 7.0, "hook_strength": 7, "data_integrity": 7,
                "product_depth": 7, "universal_appeal": 7, "question_quality": 7}


# ── TELEGRAM DELIVERY ──────────────────────────────────────────────────────────

def _escape_md(text: str) -> str:
    """Escape Markdown V1 special characters in dynamic/AI-generated text."""
    for ch in ('_', '*', '`', '['):
        text = text.replace(ch, '\\' + ch)
    return text


def send_to_telegram(result, scores, top_stories):
    post = result["post"]
    day_name = datetime.now().strftime("%A")
    overall = scores.get("overall", 0)
    try:
        overall_num = float(overall)
    except (TypeError, ValueError):
        overall_num = 0.0
    score_emoji = "🟢" if overall_num >= 7.5 else "🟡" if overall_num >= 6.5 else "🔴"
    mode_label = "🎯 PM-first" if result.get("pm_first_mode") else "📰 News-led"

    header = (
        f"✍️ *LinkedIn Post Ready — {day_name}*\n"
        f"_{result['generated_at']}_\n"
        f"Pillar: _{_escape_md(result['pillar_name'])}_\n"
        f"Format: _{result['format']}_ | Mode: _{mode_label}_\n"
        f"{score_emoji} Quality: *{overall}/10*\n"
        f"📊 Hook:{scores.get('hook_strength','?')} "
        f"Data:{scores.get('data_integrity','?')} "
        f"Product:{scores.get('product_depth','?')} "
        f"Universal:{scores.get('universal_appeal','?')} "
        f"Q:{scores.get('question_quality','?')}\n"
    )
    if scores.get("suggestion"):
        header += f"💡 _{_escape_md(scores['suggestion'])}_\n"
    if top_stories:
        header += f"Inspired by: [{top_stories[0]['source']}]({top_stories[0].get('link','')})\n"

    full_message = (
        header
        + "\n─────────────────────\n\n"
        + _escape_md(post)
        + "\n\n─────────────────────\n✅ Copy and post on LinkedIn\n⏰ Best time: 8–10am CET"
    )

    resp = requests.post(
        f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage",
        json={"chat_id": TELEGRAM_CHAT_ID, "text": full_message,
              "parse_mode": "Markdown", "disable_web_page_preview": True},
        timeout=10,
    )
    if resp.status_code == 200:
        print("✅ Sent to Telegram.")
    else:
        print(f"❌ Telegram error: {resp.status_code}")
        print(post)


# ── LOGGING ────────────────────────────────────────────────────────────────────

def log_post(result, scores, top_stories):
    post_text = result["post"]
    has_data = bool(re.search(r'\d+[\.\,]?\d*\s*(%|percent|x\b|times|million|billion|€|\$|£)', post_text, re.IGNORECASE))
    data = {
        "post_date": datetime.now().strftime("%Y-%m-%d"),
        "day_of_week": datetime.now().strftime("%A"),
        "pillar": result.get("pillar_id", ""),
        "format_type": result.get("format", ""),
        "hook_line": post_text.split("\n")[0][:200] if post_text else "",
        "post_text": post_text,
        "has_data_point": has_data,
        "pm_first_mode": result.get("pm_first_mode", False),
        "pm_experience_id": result.get("pm_experience_id", ""),
        "source_articles": json.dumps([
            {"source": s["source"], "title": s["title"], "link": s.get("link", "")}
            for s in top_stories[:3]
        ]) if top_stories else None,
        "score_hook": scores.get("hook_strength"),
        "score_data_density": scores.get("data_integrity"),
        "score_dual_audience": scores.get("universal_appeal"),
        "score_specificity": scores.get("product_depth"),
        "score_question_quality": scores.get("question_quality"),
        "score_overall": scores.get("overall"),
    }
    if supabase_insert("post_performance", data):
        print("  📊 Logged to Supabase")


def log_scrape(stories):
    today = datetime.now().strftime("%Y-%m-%d")
    for s in stories[:10]:
        supabase_insert("scrape_log", {
            "scrape_date": today,
            "source": s.get("source", ""),
            "title": s.get("title", ""),
            "summary": s.get("summary", "")[:500],
            "link": s.get("link", ""),
            "relevance_score": s.get("relevance_score", 0),
            "ai_triage_score": s.get("ai_score"),
            "ai_triage_reason": s.get("ai_reason", ""),
            "used_in_post": False,
        })


# ── CACHE ──────────────────────────────────────────────────────────────────────

def save_cache(all_content, pillar_selection):
    today = datetime.now().strftime("%Y-%m-%d")
    try:
        with open(CACHE_FILE, "w") as f:
            json.dump({"date": today, "pillar_selection": {
                "pillar_id": pillar_selection.get("pillar_id", ""),
                "reasoning": pillar_selection.get("reasoning", ""),
                "suggested_angle": pillar_selection.get("suggested_angle", ""),
                "top_stories": pillar_selection.get("top_stories", []),
                "article_intel": pillar_selection.get("article_intel", {}),
            }, "content": all_content}, f)
    except Exception:
        pass


def load_cache():
    today = datetime.now().strftime("%Y-%m-%d")
    try:
        with open(CACHE_FILE) as f:
            cache = json.load(f)
        if cache.get("date") == today:
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

    missing = [k for k, v in {"ANTHROPIC_API_KEY": ANTHROPIC_API_KEY,
        "TELEGRAM_BOT_TOKEN": TELEGRAM_BOT_TOKEN, "TELEGRAM_CHAT_ID": TELEGRAM_CHAT_ID}.items() if not v]
    if missing:
        print(f"❌ Missing: {', '.join(missing)}")
        return

    client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)
    all_content, pillar_selection = (None, None)

    if regenerate_mode:
        all_content, pillar_selection = load_cache()

    if all_content is None:
        print(f"\n📺 Fetching podcast...")
        podcast = fetch_youtube_episodes(YOUTUBE_CHANNEL_HANDLE)
        print(f"  {len(podcast)} episode(s)")

        print(f"\n🔍 Fetching news from {len(RSS_FEEDS)} sources...")
        news = fetch_rss_stories()
        print(f"  {len(news)} relevant stories")
        sources_found = set(s["source"] for s in news)
        print(f"  Sources: {', '.join(sources_found)}")

        all_content = podcast + news

        print(f"\n🧠 AI editorial triage...")
        top_stories = editorial_triage(client, news)
        for s in top_stories[:3]:
            print(f"  📰 [{s.get('ai_score','?')}/10] [{s['source']}] {s['title'][:55]}...")

        article_intel = {}
        if top_stories:
            print(f"\n🔬 Extracting intelligence...")
            text = fetch_article_text(top_stories[0].get("link", ""))
            if text:
                article_intel = extract_article_intelligence(client, text, top_stories[0]["title"])

        print(f"\n📌 Selecting pillar...")
        recent = get_recent_pillars()
        pillar_selection = select_pillar(client, top_stories, recent)
        pillar_selection["article_intel"] = article_intel
        pillar_selection["top_stories"] = top_stories
        print(f"  → {pillar_selection['pillar']['name']}")
        print(f"  Reason: {pillar_selection.get('reasoning', '')[:80]}")

        log_scrape(all_content)
        save_cache(all_content, pillar_selection)
    else:
        if pillar_selection and not isinstance(pillar_selection.get("pillar"), dict):
            pid = pillar_selection.get("pillar_id", "")
            pillar_selection["pillar"] = next((p for p in CONTENT_PILLARS if p["id"] == pid), CONTENT_PILLARS[0])
        if not pillar_selection:
            pillar_selection = select_pillar(client, [], [])

    top_stories = pillar_selection.get("top_stories", [])
    article_intel = pillar_selection.get("article_intel", {})
    pillar_id = pillar_selection.get("pillar_id", "")

    # PM experience springboard — always fetch one matching the selected pillar
    print(f"\n💡 Loading PM experience springboard...")
    pm_experience = get_pm_experience_springboard(pillar_id)
    if pm_experience:
        print(f"  → {pm_experience['id']}")

    # pm_first_mode: lead with career story rather than news
    # Triggered when: random 35% chance, OR pillar is PM-heavy and top news score is weak
    top_story_score = top_stories[0].get("ai_score", 0) if top_stories else 0
    pm_heavy_pillars = {"product_leadership", "modern_pm_in_igaming"}
    pm_first_mode = (
        random.random() < 0.35
        or (pillar_id in pm_heavy_pillars and top_story_score < 7)
    )
    print(f"  Mode: {'🎯 PM-first (leading with career story)' if pm_first_mode else '📰 News-led'}")

    print(f"\n📈 Loading performance history...")
    perf = get_top_performers()
    print("  Found past data" if perf else "  No past data yet")

    post_format = select_format()
    print(f"\n✍️  Generating {post_format} post...")
    best_result, best_scores, best_overall = None, None, 0

    for attempt in range(1, MAX_REGENERATION_ATTEMPTS + 1):
        result = generate_post(
            client, top_stories, pillar_selection, article_intel,
            perf, post_format, pm_experience, pm_first_mode,
        )
        if result is None:
            print(f"  ⚠️  Attempt {attempt}: generation failed, skipping...")
            if attempt < MAX_REGENERATION_ATTEMPTS:
                post_format = select_format()
            continue
        scores = score_post(client, result["post"], pillar_selection["pillar"]["name"])
        overall = scores.get("overall", 0)
        print(f"  Attempt {attempt}: {overall}/10 — Hook:{scores.get('hook_strength','?')} "
              f"Data:{scores.get('data_integrity','?')} Product:{scores.get('product_depth','?')} "
              f"Universal:{scores.get('universal_appeal','?')} Q:{scores.get('question_quality','?')}")

        if overall > best_overall:
            best_result, best_scores, best_overall = result, scores, overall
        if overall >= MIN_SCORE_THRESHOLD:
            break
        elif attempt < MAX_REGENERATION_ATTEMPTS:
            post_format = select_format()

    if best_result is None:
        print("❌ All generation attempts failed — cannot send post.")
        return

    print(f"\n📨 Sending to Telegram...")
    send_to_telegram(best_result, best_scores, top_stories)
    log_post(best_result, best_scores, top_stories)
    print(f"\n✅ Done — {best_result['pillar_name']} / {best_result['format']} / score {best_overall}\n")


if __name__ == "__main__":
    main()
