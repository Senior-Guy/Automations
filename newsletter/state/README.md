# State

`posted.json` is the bot's memory. It maps a normalized story URL (host + path) to what happened with it:

```json
{
  "items": {
    "example.com/some-article": {
      "ts": 1794540151,
      "status": "posted",
      "label": "Short headline",
      "title": "Original article title"
    }
  }
}
```

| Field | Meaning |
| --- | --- |
| `ts` | Unix timestamp of when the story was handled |
| `status` | `posted` (sent to Telegram) or `skipped` |
| `label` | Headline used in the Telegram post |
| `title` | Original title from the source |

## Notes

- **Do not edit by hand** while the workflow is running.
- The GitHub Actions workflow commits this file automatically (`chore: update posted history [skip ci]`), which is why the commit history contains many such entries.
- Entries older than 21 days are removed on each run.
- Deleting the file makes the bot treat every recent story as new, so you may get repeats on the next run.
