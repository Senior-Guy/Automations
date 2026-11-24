# AI News Bot

A Python script that runs every hour on GitHub Actions, collects fresh AI news from many sources, writes a short summary of each story with an LLM, and posts it to a Telegram channel. Stories that were already posted are never repeated.

Live channel: [t.me/Ai_news_latest](https://t.me/Ai_news_latest)

## How it works

1. **Collect** — gathers stories from:
   - ~20 RSS feeds (OpenAI, Anthropic, Google DeepMind, Hugging Face, Mistral, TechCrunch, The Verge, Ars Technica, MIT Technology Review and more)
   - arXiv, Hacker News, new GitHub repositories, and NewsAPI
2. **Filter** — keeps only stories published within the last **1.5 hours** and drops any URL already in `state/posted.json`.
3. **Rank** — scores each story by source quality, recency, keyword matches and engagement (stars/points).
4. **Enrich** — downloads the article text and a cover image (Open Graph image, resized with Pillow).
5. **Summarize** — asks Groq for a short title and a ~100–130 word neutral summary. If the model is rate limited or fails, it falls back to the feed's own excerpt.
6. **Post** — sends a photo (or text) message to Telegram, then records the story in `state/posted.json`.

Posted history is kept for 21 days and then pruned.

## Files

| File | Purpose |
| --- | --- |
| `newsletter.py` | The bot itself |
| `requirements.txt` | Python dependencies (`requests`, `Pillow`) |
| `state/` | Memory of posted/skipped stories, committed back by the workflow |

The scheduling workflow lives in [`../.github/workflows/`](../.github/workflows/).

## Configuration

### Required secrets

Add these under *Settings → Secrets and variables → Actions → Secrets*.

| Secret | Where to get it |
| --- | --- |
| `TELEGRAM_BOT_TOKEN` | Create a bot with [@BotFather](https://t.me/BotFather) |
| `TELEGRAM_CHAT_ID` | ID of your channel or chat (the bot must be an admin of the channel) |
| `GROQ_API_KEY` | [console.groq.com](https://console.groq.com) |

### Optional secret

| Secret | Purpose |
| --- | --- |
| `NEWSAPI_KEY` | Enables the NewsAPI source ([newsapi.org](https://newsapi.org)). Skipped if missing. |

`GITHUB_TOKEN` is provided automatically by GitHub Actions and is used for the GitHub search source.

### Optional variables

Set under *Settings → Secrets and variables → Actions → Variables*.

| Variable | Default | Meaning |
| --- | --- | --- |
| `KEYWORDS` | AI, LLM, OpenAI, Anthropic, Gemini, … | Comma-separated topics used for search and ranking |
| `MAX_POSTS` | `100` | Maximum stories posted per run |
| `GROQ_MODEL` | `openai/gpt-oss-120b` | Preferred model; falls back to `llama-3.3-70b-versatile`, then `llama-3.1-8b-instant` |

Other environment variables read by the script: `MAX_EVAL` (stories evaluated per run, default `200`), `DRY_RUN` and `STATE_PATH`.

## Running it

**On GitHub:** *Actions → Hourly AI News → Run workflow*. Tick **dry run** to preview posts without sending or saving anything.

**Locally:**

```bash
pip install -r newsletter/requirements.txt

export GROQ_API_KEY=...
export DRY_RUN=1              # remove to really post
export TELEGRAM_BOT_TOKEN=... # only needed when not a dry run
export TELEGRAM_CHAT_ID=...

python newsletter/newsletter.py
```

Logs are written to stderr and any configured secret is masked.

## Troubleshooting

| Symptom | Likely cause |
| --- | --- |
| `Missing TELEGRAM_BOT_TOKEN or TELEGRAM_CHAT_ID` | Secrets not set, or set as *Variables* instead of *Secrets* |
| Nothing is posted | No story newer than 1.5 hours that is not already in `state/posted.json` |
| Posts without AI summaries | Groq rate limit or key problem; the bot falls back to the feed excerpt |
| `TG Error 400/403` | Wrong chat ID, or the bot is not an admin of the channel |
