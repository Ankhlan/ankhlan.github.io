# Notebook + LCD Wall

This repo is a static GitHub Pages site (a Tufte-inspired notebook) plus a full-screen “LCD wall” page.

## Pages

- Home: `/`
- Posts: `/posts/<slug>/`
- LCD Wall: `/lcd.html`

The LCD wall is designed to run fullscreen on TVs / signage players / kiosk browsers. It renders a pixel/scanline-style board and scrolls the shared ticker feed.

## Ticker

The ticker appears site-wide (home, posts, topics/projects/about, and the LCD wall).

### Data sources

- Primary messages: `data/ticker.json` (array of strings)
- Optional prices: `data/prices.json`

The ticker supports tokens:

- `{TIME}` → inserts UB + UTC time
- `{PRICE:KEY}` → replaced with `data/prices.json.values.KEY` when available

Example ticker line:

- `BTC {PRICE:BTCUSD} • XAU {PRICE:XAUUSD} • {TIME}`

## Feeding messages (inbox)

Because GitHub Pages is static, external sources (SMS/email/messenger) can’t write to the site directly.

Instead:

1) Send a message into GitHub (workflow/webhook)
2) GitHub updates `data/ticker.json`
3) All pages pick up the new feed automatically

See `INBOX.md` for the full “Ticker Inbox” workflow and webhook details.

## Custom domain

GitHub Pages can serve this site from a custom domain (e.g. `wall.mn`).

High-level steps:

- GitHub repo → Settings → Pages → set **Custom domain**
- Configure DNS at your registrar (A/AAAA/CNAME as GitHub instructs)
- Enable HTTPS once DNS is live

## Deployment to screens

Use any device/player that can load a URL in kiosk mode:

- Android TV box / signage player app
- Windows mini-PC in kiosk mode
- Pro signage (Samsung/LG) “web page” content

Point all screens to the same URL:

- `https://<your-domain>/lcd.html`

Control content by updating `data/ticker.json` (and optionally `data/prices.json`).
