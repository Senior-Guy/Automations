# Tech Newsletter Automation (n8n)

Daily workflow that collects recent tech content from multiple sources, filters by keyword, scores it, summarizes with AI, and posts the best items to Telegram.

## Sources
- arXiv
- Hacker News
- GitHub (new repos)
- Google News RSS
- NewsAPI

## Requirements
- n8n (self-hosted or cloud)
- Free/paid API keys:
  - NewsAPI.org
  - Groq (for the AI summarizer)
- Telegram Bot + target chat/channel

## Setup

1. Import the workflow
   - In n8n: Workflows → Import from File → select `Newsletter.json`

2. Create credentials
   - **NewsAPI**: Header Auth credential with header name `X-Api-Key` and your key
   - **Groq**: Groq credential with your API key
   - **Telegram**: Telegram API credential (bot token)

3. Configure the nodes
   - Open “Fetch NewsAPI” → select the Header Auth credential
   - Open “Groq Chat Model” → select your Groq credential
   - Open “Send a text message” → select Telegram credential and set the correct Chat ID
   - (Optional) Replace the “Send No-Results Notice” HTTP node with a proper Telegram node using the same credential

4. Set the keyword
   - Default is “Artificial Intelligence”
   - Change it in the “Set Config Variables” node or pass it via webhook body later

5. Activate the workflow
   - It runs every day at 08:00 (Schedule Trigger)

## Notes
- No API keys are stored in this repository.
- The workflow uses `continueOnFail: true` on the fetch nodes so one source failing does not kill the whole run.
- AI summarization uses Groq (`llama-3.3-70b-versatile`).

## License
MIT (or whatever you prefer)
