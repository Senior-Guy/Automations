# n8n workflows

Importable [n8n](https://n8n.io) workflows. They run on your own n8n instance (self-hosted or cloud), not on GitHub.

| File | Workflow | Trigger |
| --- | --- | --- |
| `Telegram _lyrics_bot.json` | Telegram `/lyrics` bot | Telegram message |
| `Newsletter.json` | Daily tech newsletter | Schedule, every day at 08:00 |

> The hourly AI news posts on the Telegram channel come from the Python bot in [`../newsletter/`](../newsletter/), not from `Newsletter.json`.

## How to import

1. In n8n open *Workflows → Import from File*.
2. Select the JSON file.
3. Create the credentials listed below and attach them to the nodes.
4. Activate the workflow.

---

## Telegram lyrics bot (`Telegram _lyrics_bot.json`)

Replies to a command in Telegram with the song's lyrics, formatted in short pairs of lines.

**Usage**

```text
/lyrics Title - Artist
/lyrics part of the lyrics
```

Replies are sent in the same Telegram topic the command came from.

**Flow**

1. **Telegram Trigger** receives `/lyrics …` from a chat or channel.
2. **Parse Query** extracts the title/artist and builds the search URLs.
3. Three sources are searched: **Genius**, **African Gospel Lyrics** and **LRCLIB**.
4. Links are merged, de-duplicated, and each lyrics page is fetched and parsed.
5. **Pick Best Lyrics** chooses the closest match.
6. A Groq **AI Agent** only reformats the text (title, blank line, lyrics in pairs). **Prepare Message** checks that the AI did not change the lyrics and falls back to formatting in code if it did, or if Groq fails.
7. The result is sent back to Telegram in message-sized chunks. If nothing is found, a no-results notice is sent.

**Setup**

| Where | What to do |
| --- | --- |
| **Parse Query** node | Replace `PASTE_BOT_TOKEN` with your token from [@BotFather](https://t.me/BotFather) |
| **Parse Query** node | Optional: replace `PASTE_GENIUS_TOKEN` (free at [genius.com/api-clients](https://genius.com/api-clients)) to search by part of the lyrics |
| **Groq Chat Model** node | Select your Groq credential |
| **Telegram Trigger** | The n8n instance must be reachable over HTTPS for Telegram webhooks |

The Telegram Trigger contains pinned test data. Change `chat.id` to your own chat ID when testing locally.

**Limits**

- AZLyrics and Ceenaija are intentionally not used because they block plain HTTP requests.
- Lyrics are fetched from third-party sites and remain the property of their owners. Respect each source's terms of use.

---

## Daily tech newsletter (`Newsletter.json`)

Every day at 08:00 it collects tech content, filters by keyword, scores it, summarizes it with AI and posts the best items to Telegram.

**Flow**

1. **Schedule Trigger (8AM Daily)** starts the run.
2. **Set Config Variables** holds the keyword (default `Artificial Intelligence`).
3. Fetches from arXiv, Hacker News, GitHub (new repositories), Google News RSS and NewsAPI. Each fetch uses *continue on fail*, so one broken source does not stop the run.
4. **Normalize & Deduplicate All Sources** merges everything into one list.
5. **Score & Sort by Relevance** ranks by source quality, recency and keyword match (top 20 kept).
6. A Groq **AI Agent** (`llama-3.3-70b-versatile`) writes short summaries.
7. **Send a text message** posts to Telegram. If nothing relevant was found, **Send No-Results Notice** is used.

**Setup**

| Credential | Used by | Notes |
| --- | --- | --- |
| NewsAPI key | `Fetch NewsAPI` | Header Auth, header name `X-Api-Key` ([newsapi.org](https://newsapi.org)) |
| Groq API | `Groq Chat Model` | [console.groq.com](https://console.groq.com) |
| Telegram API | `Send a text message` | Bot token, and set `YOUR_TELEGRAM_CHAT_ID` to your chat ID |

Recommended: replace the `Send No-Results Notice` HTTP node with a regular Telegram node that uses the same credential.

---

## Security

The exported files contain placeholders only. After importing, keep real tokens in n8n credentials where possible, and never commit a workflow export that contains a real token.
