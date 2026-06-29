# Competitor Intelligence Monitor

A daily AI agent that tracks what competitors are doing across the web — news, social, GitHub, developer communities, reviews, and job boards — and delivers synthesized intelligence to Slack, Google Sheets, and a Streamlit dashboard.

Configured for any company and any set of competitors via `config.json`. Run once a day, either locally or on GitHub Actions.

---

## How it works

```
config.json          .env
(who to track)    (API keys)
       │               │
       └──────┬────────┘
              ▼
         agent.py  ──── runs daily ────────────────────────────────┐
              │                                                     │
     ┌────────▼─────────┐                                          │
     │  Nimble Web API   │  Searches Reddit, Twitter/X, LinkedIn,  │
     │  (per competitor) │  HN, GitHub, blogs, news, reviews…      │
     └────────┬─────────┘                                          │
              │  raw results                                        │
     ┌────────▼──────────┐                                         │
     │  Claude (Anthropic)│  Deduplicates, synthesizes, scores     │
     │  Synthesis pass   │  impact, flags positioning alerts        │
     └────────┬──────────┘                                         │
              │                                                     │
     ┌────────▼────────────────────────────────┐                   │
     │  Outputs                                │◄──────────────────┘
     │  • Slack channel digest                 │
     │  • Personalized Slack DMs               │
     │  • Google Sheets database               │
     │  • Obsidian vault notes                 │
     └────────┬────────────────────────────────┘
              │
     ┌────────▼────────┐
     │   app.py        │  Streamlit dashboard reading from Sheets
     │   (dashboard)   │
     └─────────────────┘
```

---

## Quick start

```bash
# 1. Clone and install dependencies
git clone <this-repo>
cd <this-repo>
pip install -r requirements.txt

# 2. Run the interactive setup wizard
python onboard.py

# 3. Run the agent
python agent.py

# 4. (Optional) Launch the dashboard
streamlit run app.py
```

`onboard.py` walks you through configuring your company, competitors, and all API keys in about 2 minutes. It writes `config.json` and `.env` for you.

For automated daily runs and detailed integration setup, see [AGENT_SETUP.md](AGENT_SETUP.md).

---

## What gets monitored

The agent runs the following searches for each competitor every day:

| Source | What it looks for |
|---|---|
| Reddit | Any mention in any subreddit |
| Twitter / X | Any public mention |
| LinkedIn | Company and brand mentions |
| Hacker News | Stories and comments via Algolia API |
| GitHub | Repos, issues, and release notes |
| News | General press coverage |
| Blogs | Official blog posts and announcements |
| Medium / Dev.to / Substack | Developer writing |
| G2 / Capterra | Customer reviews (Mondays) |
| Product Hunt | Product launches (Mondays) |
| YouTube | Videos mentioning the competitor (Mon/Wed/Fri) |
| Positioning | Direct comparisons to your company across the web |

On Mondays, it also collects GitHub stars/forks, PyPI download counts, open job postings, and web traffic estimates per competitor.

---

## What gets delivered

### Slack channel digest
Posted daily to a channel of your choice. Includes:
- Executive overview (2 sentences)
- Signal of the Day (most important competitive move)
- Positioning alerts (competitors directly comparing to you)
- Top 3 findings per competitor, sorted by impact
- Your company's own market mentions
- Link to the full Google Sheets database

### Personalized Slack DMs
Team members can run `/competitor-digest` to subscribe to a personal digest filtered to their role (Sales, Marketing, Product, Engineering, Executive, Growth). Delivered on their chosen days, in brief or detailed format.

### Google Sheets database
All findings written to a structured spreadsheet with tabs:
- **All Findings** — every signal, with competitor, category, sentiment, impact, source type
- **Positioning Alerts** — any direct comparisons to your company
- **Weekly Digest** — one-row summary per day with signal counts per competitor
- **Per-competitor tabs** — auto-filtered views using QUERY formulas
- **Metrics** — GitHub stars, PyPI downloads, job counts (Mondays)

### Streamlit dashboard
9-page analytics dashboard reading from Google Sheets:
1. Executive Summary — ranked competitor activity scorecard
2. Momentum — activity scores vs prior week
3. Organic Share of Voice — third-party coverage breakdown
4. Where Are You Absent? — conversations competitors are in that you're missing
5. Category Heatmap — activity by competitor × signal type
6. Sales Battlecards — negative competitor signals to use in deals
7. Sentiment Trends — competitor coverage tone over time
8. Sales Talking Points — how to position against each competitor's latest move
9. Signal Velocity — volume spikes and what caused them

### Obsidian vault
Individual Markdown notes for each finding, daily index notes, and weekly trend reports — compatible with the Dataview plugin for querying across all intelligence.

---

## Configuration

### `config.json` — who to track

```json
{
  "your_company": {
    "name": "Acme Corp",
    "aliases": ["Acme", "acme.com", "Acme API"],
    "description": "a cloud infrastructure company",
    "industry": "cloud infrastructure"
  },
  "competitors": [
    {
      "name": "CompetitorX",
      "aliases": ["CompetitorX", "competitorx.com"],
      "github_repo": "competitorx/sdk",
      "pypi_package": "competitorx",
      "color": "#3498db"
    }
  ]
}
```

- **`your_company.name`** — used in all AI prompts, Slack messages, and the dashboard
- **`your_company.aliases`** — all the ways your company appears in search results
- **`your_company.description`** — one sentence used to frame the AI analysis
- **`competitors[].aliases`** — all the spellings and domains the agent searches for
- **`competitors[].github_repo`** — `owner/repo` for release tracking, or `null`
- **`competitors[].pypi_package`** — package name for download stats, or `null`
- **`competitors[].color`** — hex color for the dashboard charts

### `.env` — API keys

```env
NIMBLE_API_KEY=your_key
ANTHROPIC_API_KEY=your_key

# Optional — Slack
SLACK_BOT_TOKEN=xoxb-...
SLACK_CHANNEL_ID=C0123456789
SLACK_SIGNING_SECRET=your_secret

# Optional — Google Sheets
GOOGLE_SHEET_ID=your_sheet_id
GOOGLE_SHEETS_CREDENTIALS=base64_encoded_service_account_json

# Optional — GitHub
GH_API_KEY=ghp_...
```

All optional keys can be omitted. The agent skips integrations whose keys are missing.

---

## Project structure

```
├── agent.py          Main agent — data collection, synthesis, all outputs
├── app.py            Streamlit dashboard
├── slack_bot.py      Slack /competitor-digest slash command handler
├── user_prefs.py     Read/write user digest preferences from Google Sheets
├── email_renderer.py Email digest rendering (used with RESEND_API_KEY)
├── onboard.py        Interactive setup wizard
├── config.json       Company and competitor configuration
├── requirements.txt  Python dependencies
├── seen_urls.json    Rolling 30-day URL deduplication state
├── seen_context.json Rolling 7-day topic deduplication state
├── vault/            Obsidian vault (daily notes, findings, weekly trends)
└── .github/
    └── workflows/
        └── daily_monitor.yml   GitHub Actions daily run
```

---

## Running on a schedule

The agent is designed to run once daily. The recommended approach is GitHub Actions triggered by [cron-job.org](https://cron-job.org) (GitHub's built-in `schedule` trigger runs 4–10 hours late in practice).

See [AGENT_SETUP.md → GitHub Actions](AGENT_SETUP.md#github-actions) for the full setup.

---

## Requirements

- Python 3.11+
- Nimble API key (required — used for all web search)
- Anthropic API key (required — used for synthesis and impact scoring)
- All other integrations are optional
