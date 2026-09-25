# Tech Newsletter Automation (n8n)

Daily automation that pulls recent tech content from multiple sources, filters by keyword, scores relevance, summarizes with AI, and posts the best items to Telegram.

## What it does

Every day at 08:00 it:

1. Fetches fresh content from:
   - arXiv
   - Hacker News
   - GitHub (new repositories)
   - Google News
   - NewsAPI
2. Normalizes and deduplicates the results
3. Filters by keyword (default: "Artificial Intelligence")
4. Scores items by source quality, recency, and keyword relevance
5. Uses Groq (Llama 3.3) to generate short summaries
6. Sends the top results to a Telegram chat/channel

If nothing relevant is found, it can send a "no results" notice.

## Requirements

- n8n (self-hosted or cloud)
- NewsAPI key → [newsapi.org](https://newsapi.org)
- Groq API key → [console.groq.com](https://console.groq.com)
- Telegram Bot + Chat/Channel ID

## Setup

1. **Import the workflow**
   - In n8n go to Workflows → Import from File
   - Select `Newsletter.json`

2. **Create credentials in n8n**
   - NewsAPI → Header Auth (Header name: `X-Api-Key`)
   - Groq → Groq API credential
   - Telegram → Telegram API credential (bot token)

3. **Configure the nodes**
   - `Fetch NewsAPI` → attach the Header Auth credential (or paste your key if you prefer)
   - `Groq Chat Model` → select your Groq credential
   - `Send a text message` → select Telegram credential and set your Chat ID
   - (Recommended) Replace the `Send No-Results Notice` HTTP node with a normal Telegram node that uses the same credential

4. **Optional: change the keyword**
   - Open `Set Config Variables`
   - Change the default from `"Artificial Intelligence"` or pass it via webhook body later

5. **Activate** the workflow

## Notes

- No real API keys or chat IDs are stored in this repository.
- Fetch nodes use `continueOnFail: true` so one source failing does not stop the whole run.
- The AI step uses `llama-3.3-70b-versatile` via Groq.
- The workflow currently keeps the top 20 scored items before sending.

## File

- `Newsletter.json` — the full n8n workflow export
