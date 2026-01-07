# Ticker Inbox

GitHub Pages is static, so SMS/email/Viber can’t write to the site directly.

Instead, send messages into GitHub, which updates `data/ticker.json`. The site reads that JSON at runtime.

## Option A (manual): run workflow

- Go to GitHub → repo → **Actions** → **Ticker Inbox** → **Run workflow**
- Enter `text` (and optional `source`)

## Option B (automated): webhook → GitHub repository_dispatch

1) Create a GitHub token
- Create a fine-grained PAT with **Contents: Read/Write** on this repo.
- Store it somewhere safe (for automation, store it in your relay service).

2) Trigger the inbox workflow

Send an HTTP POST to GitHub:

- URL: `https://api.github.com/repos/<owner>/<repo>/dispatches`
- Headers:
  - `Authorization: Bearer <TOKEN>`
  - `Accept: application/vnd.github+json`
  - `X-GitHub-Api-Version: 2022-11-28`
- JSON body:

```json
{
  "event_type": "ticker_inbox",
  "client_payload": {
    "text": "Gold up on London open",
    "source": "sms"
  }
}
```

3) Put a relay in front of GitHub

Most sources (SMS/email/Viber) can call a webhook. Use any simple relay to:
- validate a shared secret,
- extract message text,
- call the GitHub API above.

Common choices:
- Cloudflare Worker (cheap, fast)
- AWS Lambda
- Zapier / Make.com / IFTTT webhook action

## Notes
- Messages are prepended and the list is capped (default 50).
- Long messages are trimmed to ~160 chars.
