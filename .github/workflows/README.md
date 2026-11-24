# Workflows

## `newsletter.yml` — Hourly AI News

Runs the [AI News Bot](../../newsletter/) and saves its history.

| Setting | Value |
| --- | --- |
| Schedule | Every hour at minute 7 (`7 * * * *`, UTC). Minute 7 avoids GitHub's busiest minute at :00 |
| Manual run | *Actions → Hourly AI News → Run workflow*, with an optional **dry run** input |
| Runtime | Ubuntu, Python 3.12, pip cache enabled |
| Timeout | 55 minutes |
| Concurrency | One run at a time; a new run waits instead of cancelling the one in progress |

### Steps

1. Check out the repository and set up Python.
2. Install `newsletter/requirements.txt`.
3. Run `python newsletter/newsletter.py` with secrets and variables passed as environment variables.
4. Commit `newsletter/state/` back to the repository (skipped on dry runs).
5. Re-enable the workflow through the GitHub API so GitHub does not disable the schedule after 60 days of repository inactivity.

### Permissions

| Permission | Why |
| --- | --- |
| `contents: write` | To push the updated posted history |
| `actions: write` | To keep the scheduled workflow from being auto-disabled |

### Secrets and variables

See the [configuration table](../../newsletter/README.md#configuration) for everything this workflow reads.

### Good to know

- Commits made by the workflow include `[skip ci]` so they do not trigger more runs.
- Scheduled runs can start a few minutes late during busy periods on GitHub.
