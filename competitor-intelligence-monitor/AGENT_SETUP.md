# Agent Setup Guide

Complete setup instructions for every component of the Competitor Intelligence Monitor.

---

## Table of contents

1. [Prerequisites](#1-prerequisites)
2. [Installation](#2-installation)
3. [Interactive setup wizard](#3-interactive-setup-wizard)
4. [Nimble API](#4-nimble-api)
5. [Anthropic API](#5-anthropic-api)
6. [Slack integration](#6-slack-integration)
7. [GitHub API token](#7-github-api-token)
8. [GitHub Actions — automated daily runs](#8-github-actions--automated-daily-runs)
9. [Slack bot hosting](#9-slack-bot-hosting)
10. [Troubleshooting](#10-troubleshooting)

---

## 1. Prerequisites

- Python 3.11 or higher
- A GitHub account (for automated runs)
- A Nimble account — sign up at [nimbleway.com](https://nimbleway.com)
- An Anthropic account — sign up at [console.anthropic.com](https://console.anthropic.com)

---

## 2. Installation

```bash
git clone <your-repo-url>
cd <repo-name>
pip install -r requirements.txt
```

If you use a virtual environment (recommended):

```bash
python -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

---

## 3. Interactive setup wizard

The fastest way to get started. Run:

```bash
python onboard.py
```

The wizard walks through 5 steps:

1. **Your company** — name, aliases, description, industry
2. **Competitors** — add as many as you want; name, aliases, optional GitHub repo and PyPI package
3. **API keys** — Nimble and Anthropic (required)
4. **Slack** — bot token, channel ID, signing secret (optional)
5. **GitHub** — API token for release and repo tracking (optional)

At the end it writes `config.json` and `.env`. You can re-run it at any time to reconfigure.

If you prefer to configure manually, skip the wizard and create the files yourself using the templates in [README.md](README.md#configuration).

---

## 4. Nimble API

The Nimble API powers all web search — Reddit, news, LinkedIn, reviews, blogs, and everything else.

**Get your key:**

1. Sign up at [nimbleway.com](https://nimbleway.com)
2. Go to your dashboard → API Keys
3. Create a new key
4. Copy the key into `.env` as `NIMBLE_API_KEY`

The agent makes roughly 10–15 search calls per competitor per run. A standard Nimble account handles this comfortably at daily frequency.

---

## 5. Anthropic API

Claude performs the synthesis: reading all raw search results, identifying what's actually new and significant, writing summaries, scoring impact, and building the Slack messages.

The model used is `claude-sonnet-4-6` for the main synthesis pass.

**Get your key:**

1. Go to [console.anthropic.com](https://console.anthropic.com)
2. API Keys → Create Key
3. Copy the key into `.env` as `ANTHROPIC_API_KEY`

**Cost estimate:** A typical daily run with 5 competitors costs approximately $0.05–0.15 in API credits depending on how much raw content is found.

---

## 6. Slack integration

Enables two things:
- **Daily channel digest** — the agent posts a formatted summary to a channel after each run
- **Personalized DMs** — team members run `/competitor-digest` to subscribe to a personal digest filtered by their role and preferences

Both require a Slack app. The daily digest only needs `SLACK_BOT_TOKEN` and `SLACK_CHANNEL_ID`. The slash command also needs `SLACK_SIGNING_SECRET` and a running instance of `slack_bot.py`.

### 6.1 Create a Slack app

1. Go to [api.slack.com/apps](https://api.slack.com/apps)
2. Click **Create New App** → **From scratch**
3. Name it (e.g. "Competitor Monitor") and select your workspace

### 6.2 Set OAuth scopes

In **OAuth & Permissions** → **Bot Token Scopes**, add:

| Scope | Required for |
|---|---|
| `chat:write` | Posting channel digests and DMs |
| `commands` | The `/competitor-digest` slash command |
| `users:read` (optional) | Looking up user names |

### 6.3 Install the app to your workspace

1. In **OAuth & Permissions**, click **Install to Workspace**
2. Authorize the app
3. Copy the **Bot User OAuth Token** (starts with `xoxb-`) into `.env` as `SLACK_BOT_TOKEN`

### 6.4 Get the channel ID

1. Open the channel where you want the daily digest posted
2. Right-click the channel name → **Copy link** or **View channel details**
3. The channel ID appears at the end of the URL: `...slack.com/app_redirect?channel=C0123456789`
4. Copy this ID into `.env` as `SLACK_CHANNEL_ID`

Alternatively: right-click the channel name in the sidebar → **Copy channel ID** (in newer Slack versions).

### 6.5 Invite the bot to the channel

In the channel, type `/invite @YourBotName` to allow it to post there.

### 6.6 Add the signing secret (for slash commands)

1. In your Slack app → **Basic Information** → **App Credentials**
2. Copy the **Signing Secret** into `.env` as `SLACK_SIGNING_SECRET`

The signing secret is only needed if you're running `slack_bot.py` for the `/competitor-digest` slash command. The daily digest does not require it.

### 6.7 Create the slash command (optional)

This enables `/competitor-digest` for personalized DM subscriptions.

1. In your Slack app → **Slash Commands** → **Create New Command**
2. Command: `/competitor-digest`
3. Request URL: your `slack_bot.py` server URL + `/slack/events` (e.g. `https://your-app.railway.app/slack/events`)
4. Short description: `Subscribe to your competitor intelligence digest`
5. Save

See [Section 9](#9-slack-bot-hosting) for hosting `slack_bot.py`.

---

## 7. GitHub API token

Used for two things:
- Searching GitHub repos and issues mentioning competitors
- Fetching release notes from competitors' GitHub repos

Without a token, GitHub search hits the public unauthenticated rate limit quickly (60 requests/hour). A token raises this to 5,000/hour.

**Get a token:**

1. Go to [github.com/settings/tokens](https://github.com/settings/tokens)
2. **Generate new token (classic)**
3. No extra scopes needed — the default read-only permissions are sufficient for public repos
4. Copy the token (starts with `ghp_`) into `.env` as `GH_API_KEY`

---

## 8. GitHub Actions — automated daily runs

The agent is designed to run on a schedule via GitHub Actions. The workflow file is already included at `.github/workflows/daily_monitor.yml`.

### 8.1 Add secrets to your repository

The workflow reads API keys from GitHub Secrets (never hardcode them in the workflow file).

1. Go to your repository on GitHub → **Settings** → **Secrets and variables** → **Actions**
2. Add the following secrets (use the same names as your `.env` keys):

| Secret name | Required |
|---|---|
| `NIMBLE_API_KEY` | Yes |
| `ANTHROPIC_API_KEY` | Yes |
| `SLACK_BOT_TOKEN` | If using Slack |
| `SLACK_CHANNEL_ID` | If using Slack |
| `GH_API_KEY` | If using GitHub tracking |

### 8.2 Commit `config.json`

`config.json` holds your competitor list and is not a secret — it should be committed to the repo so GitHub Actions can read it.

```bash
git add config.json
git commit -m "add competitor config"
git push
```

Do not commit `.env` — it is in `.gitignore`.

### 8.3 Set up a daily trigger

The workflow uses `workflow_dispatch` (manual or API trigger) rather than GitHub's built-in `schedule:` cron. GitHub's scheduled workflows run 4–10 hours late during peak times, which makes daily digests unreliable.

**Recommended: use [cron-job.org](https://cron-job.org) (free)**

1. Sign up at cron-job.org
2. Create a new cron job
3. Set the URL to trigger your workflow:
   ```
   https://api.github.com/repos/{owner}/{repo}/actions/workflows/daily_monitor.yml/dispatches
   ```
4. Set the HTTP method to `POST`
5. Add a header: `Authorization: Bearer {your_github_personal_access_token}`
6. Add a header: `Accept: application/vnd.github.v3+json`
7. Set the body to: `{"ref": "main"}`
8. Schedule it for your preferred time (e.g. `0 12 * * 1-5` for 12:00 UTC on weekdays)

The GitHub token used here only needs `workflow` scope. Create one at [github.com/settings/tokens](https://github.com/settings/tokens).

### 8.4 How state is persisted

After each run, the workflow commits two files back to the repo:

- `seen_urls.json` — 30-day URL history used to deduplicate results across runs
- `seen_context.json` — 7-day topic history used to prevent re-reporting the same story

The workflow has `permissions: contents: write` for this reason. The commit message includes `[skip ci]` to prevent triggering another run.

---

## 9. Slack bot hosting

`slack_bot.py` is a Flask server that handles the `/competitor-digest` slash command. It needs to be publicly accessible so Slack can send requests to it.

The Procfile is already configured for platforms that support it:
```
web: python3 slack_bot.py
```

### Required environment variables

```env
SLACK_BOT_TOKEN=xoxb-...
SLACK_SIGNING_SECRET=your_secret
```

### Deploy to Railway (recommended, free tier available)

1. Push your repo to GitHub
2. Go to [railway.app](https://railway.app) → New Project → Deploy from GitHub repo
3. Select your repo
4. In Variables, add the two env vars above
5. Railway detects the Procfile and starts `slack_bot.py` automatically
6. Copy the generated public URL (e.g. `https://your-app.up.railway.app`)
7. Update your Slack slash command's Request URL to `{your-url}/slack/events`

### Deploy to Render (free tier available)

1. Go to [render.com](https://render.com) → New → Web Service → Connect your repo
2. Runtime: Python 3, Build command: `pip install -r requirements.txt`
3. Start command: `python slack_bot.py`
4. Add env vars in the Environment section
5. Use the Render URL for the Slack slash command

### Testing locally with ngrok

For local development and testing before deploying:

```bash
# In one terminal
python slack_bot.py

# In another terminal
ngrok http 8080
```

Use the ngrok HTTPS URL as the slash command Request URL in your Slack app.

---

## 10. Troubleshooting

### Agent runs but posts nothing to Slack

- Confirm `SLACK_BOT_TOKEN` starts with `xoxb-`
- Confirm `SLACK_CHANNEL_ID` is the channel ID (e.g. `C0123456789`), not the channel name
- Make sure the bot has been invited to the channel: `/invite @YourBotName`
- Check the agent logs — `[Slack] API error:` lines will name the specific Slack error

### "No findings" on first run

The agent filters results to the past 24 hours by default. On a first run there may simply be no fresh results for some competitors. Try widening by editing `SEARCH_START` in `agent.py` temporarily, or wait a day.

### GitHub Actions workflow not running

- Confirm `config.json` is committed to the repo (not gitignored)
- Confirm all required secrets are added to the repository
- Check the Actions tab in GitHub for error logs
- If using cron-job.org, verify the Authorization header uses a valid personal access token with `workflow` scope

### Duplicate findings across days

`seen_urls.json` is the deduplication state. If it gets out of sync (e.g. a failed commit in GitHub Actions), the agent may re-report previously seen items. You can clear it by resetting the file to `{"entries": {}}` — the agent will treat the next run as a fresh start.

### Claude synthesis returns malformed JSON

The agent handles this gracefully — it logs the parse error and skips the failed synthesis. This occasionally happens if Claude's output is very long and gets cut off. If it happens consistently, check that `max_tokens=8192` is not being hit (look for `stop_reason=max_tokens` in the logs).

### The Slack bot returns "dispatch_failed" on slash commands

This means Slack sent a request to your bot's URL but got no response within 3 seconds. Common causes:
- The bot server isn't running or is starting up (cold start on free hosting tiers)
- The Request URL in the Slack app is wrong or missing `/slack/events`
- A firewall or proxy is blocking the request

Use the `/health` endpoint to verify the bot is reachable: `curl https://your-bot-url/health` should return `{"status": "ok"}`.
