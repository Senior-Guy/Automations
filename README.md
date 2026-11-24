# Automations

A collection of practical automations for everyday tasks and productivity, built with Python, GitHub Actions and [n8n](https://n8n.io).

| Project | What it does | Stack | Runs on |
| --- | --- | --- | --- |
| [AI News Bot](newsletter/) | Finds new AI stories every hour, summarizes them, posts to Telegram | Python, Groq, Telegram | GitHub Actions |
| [Telegram Lyrics Bot](n8n/) | Replies to `/lyrics <song>` with formatted lyrics | n8n, Groq, Telegram | Your own n8n instance |
| [Daily Tech Newsletter](n8n/) | Daily 08:00 digest of tech news to Telegram (original n8n version) | n8n, Groq, Telegram | Your own n8n instance |

**Live output:** the AI News Bot posts to [t.me/Ai_news_latest](https://t.me/Ai_news_latest).

## Repository layout

```text
.
├── .github/workflows/   GitHub Actions workflow that runs the AI News Bot hourly
├── n8n/                 Importable n8n workflows (lyrics bot, daily newsletter)
└── newsletter/          Python AI News Bot and its state
    └── state/           History of already-posted stories (auto-updated)
```

Each folder has its own README with setup details.

## Quick start

**AI News Bot (no server needed)**

1. Fork this repository.
2. Add the secrets listed in [`newsletter/README.md`](newsletter/README.md#configuration) under *Settings → Secrets and variables → Actions*.
3. Open the *Actions* tab and run **Hourly AI News** manually with *dry run* enabled to preview the output.

**n8n workflows**

1. In n8n choose *Workflows → Import from File*.
2. Pick a file from [`n8n/`](n8n/) and follow the setup notes in [`n8n/README.md`](n8n/README.md).

## Security

- No real API keys, bot tokens or chat IDs are stored in this repository. Placeholders such as `PASTE_BOT_TOKEN` and `YOUR_TELEGRAM_CHAT_ID` must be replaced in your own copy.
- Never commit real credentials. If you accidentally do, revoke and regenerate them immediately.
- The Python bot reads all secrets from GitHub Actions secrets and masks them in logs.

## Contributing

Issues and suggestions are welcome. For a change, open a pull request with a short description of what it does and how you tested it (the workflow's *dry run* mode is handy for the news bot).

## License

No license has been added yet, so all rights are reserved by default. If you want others to reuse this work, add a `LICENSE` file (for example MIT).
