# LinkedIn Intelligence Engine — v2.0

An AI-powered editorial system that generates high-engagement LinkedIn posts for the iGaming affiliate industry. Goes beyond basic automation — this system thinks, scores, learns, and improves.

---

## What's New in v2

| Feature | v1 | v2 |
|---|---|---|
| Source filtering | Keyword matching | AI editorial triage (rates stories 1-10) |
| Pillar selection | Mechanical rotation | AI picks the best pillar for the news cycle |
| Data extraction | None | Extracts numbers, metrics, entities from articles |
| Quality control | None | AI scores every post on 5 dimensions, auto-regenerates weak ones |
| Feedback loop | None | Tracks performance in Supabase, feeds winners back into prompts |
| Post formats | One style | 5 rotating formats (observation, data insight, contrarian, story, commentary) |
| Cadence | 2x/week | 3x/week (Tue, Thu, Sat) |
| Data requirement | Optional | Every post MUST include at least one specific metric |

---

## How It Works

Every run executes 7 phases:

1. **Scrape** — Pull latest from iGB, Gambling Insider, CalvinAyre, AffiliateINSIDER, EGR, SiGMA + Tracking the Truth podcast
2. **Editorial Triage** — AI rates all stories by LinkedIn engagement potential (not just keyword matching)
3. **Data Extraction** — Deep-reads the top article, extracts specific numbers, claims, entities, and "so what"
4. **Adaptive Pillar Selection** — AI picks the best content pillar for today's news cycle (avoids recent repeats)
5. **Feedback Loop** — Loads your top-performing past posts to guide generation
6. **Generate + Score** — Drafts a post, scores it on 5 dimensions (hook, data density, dual audience, specificity, question quality). Auto-regenerates if below 6.5/10
7. **Deliver + Log** — Sends to Telegram with quality metadata; logs everything to Supabase

---

## Setup

### Step 1 — Same as v1
```bash
pip install anthropic requests beautifulsoup4 feedparser
```

### Step 2 — Supabase (new in v2)

The feedback loop needs a Supabase project. If you already have `linkedin-intelligence`:

1. Go to your Supabase dashboard
2. Get your **Project URL** and **anon key** (or service role key) from Settings → API
3. The migration creates 3 tables automatically: `post_performance`, `scrape_log`, `weekly_briefing`

### Step 3 — GitHub Secrets

Add these to your repo → Settings → Secrets and variables → Actions:

| Secret | Description |
|---|---|
| `ANTHROPIC_API_KEY` | Your Anthropic API key |
| `TELEGRAM_BOT_TOKEN` | From @BotFather on Telegram |
| `TELEGRAM_CHAT_ID` | Your chat ID (run `get_chat_id.py`) |
| `SUPABASE_URL` | e.g. `https://lpzuinapbangebuxhiix.supabase.co` |
| `SUPABASE_KEY` | Your Supabase anon or service role key |

### Step 4 — Test
```bash
export ANTHROPIC_API_KEY=sk-ant-...
export TELEGRAM_BOT_TOKEN=...
export TELEGRAM_CHAT_ID=...
export SUPABASE_URL=https://your-project.supabase.co
export SUPABASE_KEY=your-key
python3 weekly_post_generator.py
```

---

## What You Receive on Telegram

```
✍️ LinkedIn Post Ready — Tuesday
2026-04-11 08:00
Pillar: Data Product Thinking in iGaming Affiliate
Format: data_insight
🟢 Quality: 8.2/10
📊 Hook:8 Data:9 Dual:7 Spec:9 Q:8
💡 Consider adding a comparison to make the metric more tangible

Inspired by: [iGB](https://...)

─────────────────────

[The full post, ready to copy-paste]

─────────────────────
✅ Copy and post on LinkedIn
⏰ Best time: 8–10am CET
```

---

## The Feedback Loop (Important)

The system gets smarter over time, but it needs your help:

**After posting**, update the `post_performance` table in Supabase with actual results:
- `impressions` — from LinkedIn analytics
- `reactions` — total likes/celebrates/etc
- `comments` — comment count
- `posted` — set to `true` if you actually posted it
- `engagement_rate` — (reactions + comments) / impressions × 100
- `notes` — your observations ("hook was weak", "great debate in comments", etc.)

Even updating 1-2 posts per week makes a difference. After 10-15 posts with data, the system starts learning what works for your specific audience.

---

## Cost

- **Anthropic API**: ~$0.08–0.15 per run (4-6 Claude Sonnet calls: triage + extraction + pillar selection + generation + scoring + possible regeneration)
- **Supabase**: Free tier (plenty for this use case)
- **Telegram**: Free
- **GitHub Actions**: Free tier

Total: ~$1-2/month for 12 posts.

---

## Architecture

```
RSS Feeds ─────────────┐
YouTube Podcast ───────┤
                       ▼
              ┌─── SCRAPE ───┐
              │  15 stories   │
              └──────┬────────┘
                     ▼
          ┌── AI TRIAGE ──┐
          │ Score 1-10     │
          │ Best angles    │
          │ Data points    │
          └──────┬─────────┘
                 ▼
       ┌── DATA EXTRACT ──┐
       │ Numbers, metrics  │
       │ Claims, entities  │
       │ "So what"         │
       └──────┬────────────┘
              ▼
    ┌── PILLAR SELECT ──┐
    │ News-aware         │
    │ Avoids repeats     │
    │ Best angle         │
    └──────┬─────────────┘
           ▼
    ┌── FEEDBACK ──┐
    │ Top 3 past    │
    │ performers    │
    └──────┬────────┘
           ▼
    ┌── GENERATE ──┐
    │ Rich context  │
    │ Data required │
    │ Format varied │
    └──────┬────────┘
           ▼
    ┌── SCORE ────────┐
    │ Hook: 8/10       │
    │ Data: 9/10       │  ─── Below 6.5? ──→ Regenerate (max 3x)
    │ Dual: 7/10       │
    │ Spec: 9/10       │
    │ Q:    8/10       │
    └──────┬───────────┘
           ▼
    ┌── DELIVER ──┐      ┌── LOG ──┐
    │ Telegram     │      │ Supabase │
    │ + scores     │      │ feedback │
    └──────────────┘      └──────────┘
```
